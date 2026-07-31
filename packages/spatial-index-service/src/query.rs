use std::sync::Arc;

use axum::extract::{Query, State};
use axum::http::{Method, StatusCode};
use axum::response::IntoResponse;
use axum::routing::get;
use axum::Router;
use serde::Deserialize;
use axum::http::HeaderValue;
use tower_http::compression::CompressionLayer;
use tower_http::cors::{AllowOrigin, Any, CorsLayer};

use crate::index::{build_rtree, inflate_rect, query_rtree};
use crate::response::{serialize_response, SIS_MAGIC_EXACT, SIS_MAGIC_INFLATED};
use crate::store::ArchivedSisStore;
use rkyv::Archived;
use static_aabb2d_index::StaticAABB2DIndex;

/// Parsed query parameters from GET request.
#[derive(Debug)]
pub struct SpatialQueryParams {
    pub pc_south: f64,
    pub pc_west: f64,
    pub pc_north: f64,
    pub pc_east: f64,
    pub pc_lat: f64,
    pub pc_lon: f64,
    pub map_south: f64,
    pub map_west: f64,
    pub map_north: f64,
    pub map_east: f64,
}

/// Haversine distance in kilometres between two lat/lon points.
pub fn haversine(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f32 {
    const EARTH_R: f64 = 6371.0; // Earth radius in km
    let dlat = (lat2 - lat1).to_radians();
    let dlon = (lon2 - lon1).to_radians();
    let a = (dlat / 2.0).sin().powi(2)
        + lat1.to_radians().cos() * lat2.to_radians().cos() * (dlon / 2.0).sin().powi(2);
    let c = 2.0 * a.sqrt().asin();
    (EARTH_R * c) as f32
}

/// Compute distance from postcode centroid to a provider.
///
/// Point providers: haversine to the point.
/// Bbox providers: max haversine to the 4 bbox corners.
fn provider_distance(
    pc_lat: f64,
    pc_lon: f64,
    store: &ArchivedSisStore,
    provider_idx: usize,
) -> f32 {
    let lat = store.provider_centre_lat[provider_idx].to_native() as f64;
    let lon = store.provider_centre_lon[provider_idx].to_native() as f64;
    let first_row = store.provider_first_row[provider_idx].to_native() as usize;
    let blat = store.bbox_lat[first_row].to_native();
    let blon = store.bbox_lon[first_row].to_native();

    if blat.is_nan() {
        // Point provider — distance to point
        haversine(pc_lat, pc_lon, lat, lon)
    } else {
        // Bbox provider — max distance to 4 corners
        let plat = store.lat[first_row].to_native() as f64; // NW corner lat (north)
        let plon = store.lon[first_row].to_native() as f64; // NW corner lon (west)
        let slat = blat as f64; // SE corner lat (south)
        let elon = blon as f64; // SE corner lon (east)

        let d1 = haversine(pc_lat, pc_lon, plat, plon); // NW
        let d2 = haversine(pc_lat, pc_lon, plat, elon); // NE
        let d3 = haversine(pc_lat, pc_lon, slat, plon); // SW
        let d4 = haversine(pc_lat, pc_lon, slat, elon); // SE

        d1.max(d2).max(d3).max(d4)
    }
}

/// Check whether completeness circle *R*'s boundary crosses viewport *V*'s boundary.
///
/// Returns `true` when *R* and *V* partially overlap (neither fully contains
/// the other). This is the condition that triggers a re-query against *V*
/// without inflation. See README § Terminology.
pub fn circle_rect_boundary_intersects(
    c_lat: f64,
    c_lon: f64,
    radius: f32,
    south: f64,
    west: f64,
    north: f64,
    east: f64,
) -> bool {
    // Corner distances
    let d_sw = haversine(c_lat, c_lon, south, west);
    let d_se = haversine(c_lat, c_lon, south, east);
    let d_nw = haversine(c_lat, c_lon, north, west);
    let d_ne = haversine(c_lat, c_lon, north, east);
    let max_corner = d_sw.max(d_se).max(d_nw).max(d_ne);

    // All corners inside circle → V ⊂ R → no boundary crossing
    if max_corner <= radius {
        return false;
    }

    // At least one corner is outside R. Check containment the other way.
    let center_in_v =
        c_lat >= south && c_lat <= north && c_lon >= west && c_lon <= east;

    if center_in_v {
        // Distances from center to each edge (perpendicular)
        let d_s = haversine(c_lat, c_lon, south, c_lon);
        let d_n = haversine(c_lat, c_lon, north, c_lon);
        let d_w = haversine(c_lat, c_lon, c_lat, west);
        let d_e = haversine(c_lat, c_lon, c_lat, east);
        let min_edge = d_s.min(d_n).min(d_w).min(d_e);

        // radius > min_edge → circle extends past V → boundary crossing
        // radius <= min_edge → R ⊂ V → no crossing
        return radius > min_edge;
    }

    // Center outside V, at least one corner outside R.
    // Circle overlaps V iff the nearest point on V is within radius.
    let nearest_lat = c_lat.clamp(south, north);
    let nearest_lon = c_lon.clamp(west, east);
    let d_nearest = haversine(c_lat, c_lon, nearest_lat, nearest_lon);
    d_nearest < radius
}

/// Check whether all 4 corners of viewport *V* are within the completeness
/// circle *R* (centre `c_lat`/`c_lon`, radius in km). Returns `true` when
/// V ⊆ R — i.e. the cached results fully cover the visible area.
pub fn viewport_within_circle(
    c_lat: f64,
    c_lon: f64,
    radius: f32,
    south: f64,
    west: f64,
    north: f64,
    east: f64,
) -> bool {
    haversine(c_lat, c_lon, south, west) <= radius
        && haversine(c_lat, c_lon, south, east) <= radius
        && haversine(c_lat, c_lon, north, west) <= radius
        && haversine(c_lat, c_lon, north, east) <= radius
}

/// Check if a provider has any care-type row matching the bitfield mask.
fn provider_matches_care_type(
    store: &ArchivedSisStore,
    provider_idx: usize,
    care_type_mask: u8,
) -> bool {
    if care_type_mask == 0 {
        return true; // 0 = no filter, all types
    }
    let first = store.provider_first_row[provider_idx].to_native() as usize;
    let count = store.provider_row_count[provider_idx].to_native() as usize;
    for r in first..first + count {
        let ct = store.care_type[r] as u8;
        if ct < 8 && (care_type_mask & (1 << ct)) != 0 {
            return true;
        }
    }
    false
}

/// Check whether a provider is a bbox provider (has bbox coordinates).
fn is_bbox_provider(store: &ArchivedSisStore, provider_idx: usize) -> bool {
    let first_row = store.provider_first_row[provider_idx].to_native() as usize;
    !store.bbox_lat[first_row].to_native().is_nan()
}

/// Spatial search returning point and bbox populations separately.
///
/// Both lists are sorted by distance from *P* and independently truncated to
/// `result_limit`. Returns `(point_providers, point_hit_limit, bbox_providers,
/// bbox_hit_limit)`.
fn find_providers(
    store: &ArchivedSisStore,
    rtree: &StaticAABB2DIndex<f32>,
    aabb_provider_idx: &[Archived<u32>],
    pc_lat: f64,
    pc_lon: f64,
    south: f32,
    west: f32,
    north: f32,
    east: f32,
    result_limit: usize,
    care_type_mask: u8,
) -> (Vec<(u32, f32)>, bool, Vec<(u32, f32)>, bool) {
    let aabb_hits = query_rtree(rtree, south, west, north, east);

    let mut point_distances: Vec<(u32, f32)> = Vec::new();
    let mut bbox_distances: Vec<(u32, f32)> = Vec::new();

    for &aabb_idx in &aabb_hits {
        let pidx = aabb_provider_idx[aabb_idx].to_native();
        if !provider_matches_care_type(store, pidx as usize, care_type_mask) {
            continue;
        }
        let dist = provider_distance(pc_lat, pc_lon, store, pidx as usize);
        if is_bbox_provider(store, pidx as usize) {
            bbox_distances.push((pidx, dist));
        } else {
            point_distances.push((pidx, dist));
        }
    }

    point_distances
        .sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
    bbox_distances
        .sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));

    let point_hit_limit = point_distances.len() > result_limit;
    point_distances.truncate(result_limit);

    let bbox_hit_limit = bbox_distances.len() > result_limit;
    bbox_distances.truncate(result_limit);

    (point_distances, point_hit_limit, bbox_distances, bbox_hit_limit)
}

/// Merge point and bbox provider lists into a single globally-sorted list.
fn merge_providers(
    point_providers: Vec<(u32, f32)>,
    bbox_providers: Vec<(u32, f32)>,
) -> Vec<(u32, f32)> {
    let mut combined = point_providers;
    combined.extend(bbox_providers);
    combined.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
    combined
}

/// Expand a provider list into row indices + per-row distances.
fn expand_to_rows(
    store: &ArchivedSisStore,
    provider_distances: &[(u32, f32)],
) -> (Vec<usize>, Vec<f32>) {
    let mut row_indices: Vec<usize> = Vec::new();
    let mut distances: Vec<f32> = Vec::new();

    for &(pidx, dist) in provider_distances {
        let first = store.provider_first_row[pidx as usize].to_native() as usize;
        let count = usize::from(store.provider_row_count[pidx as usize].to_native());
        for r in first..first + count {
            row_indices.push(r);
            distances.push(dist);
        }
    }

    (row_indices, distances)
}

/// Run the full spatial query pipeline with split point/bbox populations.
///
/// *P* is the postcode centroid (`pc_lat`/`pc_lon`); *N* is `result_limit`.
/// Queries the unified R-tree, splits hits into point and bbox populations,
/// each independently sorted and truncated to *N*. The R-circle completeness
/// check uses only the point population — bbox max-corner distances are not
/// meaningful for the R-circle geometry. After the completeness decision,
/// both populations are merged into a single globally-sorted list.
pub fn execute_query(
    store: &ArchivedSisStore,
    rtree: &StaticAABB2DIndex<f32>,
    params: &SpatialQueryParams,
    bbox_inflation: f64,
    result_limit: usize,
    care_type_mask: u8,
) -> Vec<u8> {
    // 1. Inflate the map viewport → I
    let (inf_south, inf_west, inf_north, inf_east) = inflate_rect(
        params.map_south,
        params.map_west,
        params.map_north,
        params.map_east,
        bbox_inflation,
    );

    // 2. Query I — split into point and bbox populations
    let (point_providers, point_hit_limit, bbox_providers, _bbox_hit_limit) =
        find_providers(
            store,
            rtree,
            &store.aabb_provider_idx,
            params.pc_lat,
            params.pc_lon,
            inf_south,
            inf_west,
            inf_north,
            inf_east,
            result_limit,
            care_type_mask,
        );

    // 3. R-circle completeness check — point providers only
    if point_hit_limit && !point_providers.is_empty() {
        let r_radius = point_providers.last().unwrap().1;

        if !viewport_within_circle(
            params.pc_lat,
            params.pc_lon,
            r_radius,
            params.map_south,
            params.map_west,
            params.map_north,
            params.map_east,
        ) {
            // Re-query both populations against exact viewport V
            let (v_point, _, v_bbox, _) = find_providers(
                store,
                rtree,
                &store.aabb_provider_idx,
                params.pc_lat,
                params.pc_lon,
                params.map_south as f32,
                params.map_west as f32,
                params.map_north as f32,
                params.map_east as f32,
                result_limit,
                care_type_mask,
            );
            let merged = merge_providers(v_point, v_bbox);
            let (row_indices, distances) = expand_to_rows(store, &merged);
            return serialize_response(store, &row_indices, &distances, SIS_MAGIC_EXACT);
        }
    }

    // 4. Normal inflated response — globally sorted by distance
    let merged = merge_providers(point_providers, bbox_providers);
    let (row_indices, distances) = expand_to_rows(store, &merged);
    serialize_response(store, &row_indices, &distances, SIS_MAGIC_INFLATED)
}

/// Shared server state holding the archived store bytes and rebuilt R-tree.
pub struct SisState {
    // Keep the bytes alive so the archived reference remains valid
    _bytes: memmap2::Mmap,
    pub rtree: StaticAABB2DIndex<f32>,
    pub bbox_inflation: f64,
    pub result_limit: usize,
}

impl SisState {
    /// Load the SIS file and rebuild the R-tree.
    pub fn load(
        filepath: &str,
        bbox_inflation: f64,
        result_limit: usize,
    ) -> Self {
        let file = std::fs::File::open(filepath)
            .unwrap_or_else(|e| panic!("Failed to open SIS file {filepath}: {e}"));

        let mmap = unsafe { memmap2::Mmap::map(&file) }.expect("Failed to mmap SIS file");

        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&mmap)
            .expect("Failed to access archived SIS store — rkyv validation failed");

        let rtree = build_rtree(archived);
        let num_providers = archived.provider_first_row.len();
        let num_rows = archived.len.to_native();
        let num_aabbs = archived.aabb_min_x.len();
        tracing::info!(
            providers = num_providers,
            rows = num_rows,
            aabbs = num_aabbs,
            "SIS store loaded, R-tree rebuilt"
        );

        Self {
            _bytes: mmap,
            rtree,
            bbox_inflation,
            result_limit,
        }
    }

    /// Get a reference to the archived store.
    pub fn store(&self) -> &ArchivedSisStore {
        rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&self._bytes)
            .expect("rkyv access failed")
    }
}

// --- Axum handlers & router ---

#[derive(Deserialize)]
struct QueryParams {
    pc_south: f64,
    pc_west: f64,
    pc_north: f64,
    pc_east: f64,
    pc_lat: f64,
    pc_lon: f64,
    map_south: f64,
    map_west: f64,
    map_north: f64,
    map_east: f64,
    #[serde(default)]
    ct: u8,
}

async fn spatial_query_handler(
    State(state): State<Arc<SisState>>,
    Query(params): Query<QueryParams>,
) -> impl IntoResponse {
    let sq_params = SpatialQueryParams {
        pc_south: params.pc_south,
        pc_west: params.pc_west,
        pc_north: params.pc_north,
        pc_east: params.pc_east,
        pc_lat: params.pc_lat,
        pc_lon: params.pc_lon,
        map_south: params.map_south,
        map_west: params.map_west,
        map_north: params.map_north,
        map_east: params.map_east,
    };

    let body = execute_query(
        state.store(),
        &state.rtree,
        &sq_params,
        state.bbox_inflation,
        state.result_limit,
        params.ct,
    );

    (
        StatusCode::OK,
        [("content-type", "application/octet-stream")],
        body,
    )
}

async fn health_handler() -> &'static str {
    "OK"
}

/// Parse a CORS origin string into an `AllowOrigin`.
///
/// - `"*"` → any origin
/// - `"https://a.com,https://b.com"` → comma-separated list
/// - `"https://example.com"` → exact single origin
///
/// Panics on invalid header values (same pattern as other `SIS_*` env vars).
fn parse_cors_origin(value: &str) -> AllowOrigin {
    if value == "*" {
        AllowOrigin::any()
    } else if value.contains(',') {
        let origins: Vec<HeaderValue> = value
            .split(',')
            .map(|s| {
                s.trim()
                    .parse::<HeaderValue>()
                    .unwrap_or_else(|e| panic!("Invalid CORS origin {s:?}: {e}"))
            })
            .collect();
        AllowOrigin::list(origins)
    } else {
        AllowOrigin::exact(
            value
                .parse::<HeaderValue>()
                .unwrap_or_else(|e| panic!("Invalid CORS origin {value:?}: {e}")),
        )
    }
}

/// Build the shared Axum router with CORS middleware.
pub fn build_router(state: Arc<SisState>, cors_origin: &str) -> Router {
    let cors = CorsLayer::new()
        .allow_origin(parse_cors_origin(cors_origin))
        .allow_methods([Method::GET])
        .allow_headers(Any);

    Router::new()
        .route("/api/spatial-query", get(spatial_query_handler))
        .route("/health", get(health_handler))
        // lambda_http >=0.12 prepends the API Gateway stage name to the URI path
        // for REST API v1 events (e.g. /dev/api/spatial-query). Register the same
        // handlers under a single-segment wildcard so both forms work.
        .route("/{stage}/api/spatial-query", get(spatial_query_handler))
        .route("/{stage}/health", get(health_handler))
        .layer(cors)
        .layer(CompressionLayer::new())
        .with_state(state)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn haversine_london_to_paris() {
        // London (51.5074, -0.1278) to Paris (48.8566, 2.3522) ≈ 343 km
        let d = haversine(51.5074, -0.1278, 48.8566, 2.3522);
        assert!(
            (d - 343.0).abs() < 5.0,
            "London-Paris should be ~343km, got {d}"
        );
    }

    #[test]
    fn haversine_same_point() {
        let d = haversine(51.5, -0.1, 51.5, -0.1);
        assert!(d < 0.001, "Same point should be ~0km");
    }

    #[test]
    fn circle_fully_contains_rect() {
        // Large circle, small rect → V ⊂ R → false
        assert!(!circle_rect_boundary_intersects(
            51.5, -0.1, 500.0, // 500 km radius
            51.4, -0.2, 51.6, 0.0,
        ));
    }

    #[test]
    fn rect_fully_contains_circle() {
        // Small circle, large rect → R ⊂ V → false
        assert!(!circle_rect_boundary_intersects(
            51.5, -0.1, 1.0, // 1 km radius
            50.0, -2.0, 53.0, 2.0,
        ));
    }

    #[test]
    fn circle_rect_partial_overlap() {
        // Circle centered at 51.5, -0.1 with ~20 km radius.
        // Rect that extends well beyond 20 km in some directions but
        // the circle clips one edge.
        assert!(circle_rect_boundary_intersects(
            51.5, -0.1, 20.0,
            51.3, -0.3, 51.7, 0.1, // ~22 km tall, ~28 km wide
        ));
    }

    #[test]
    fn circle_rect_no_overlap() {
        // Circle far from rect → false
        assert!(!circle_rect_boundary_intersects(
            51.5, -0.1, 10.0,
            55.0, 5.0, 56.0, 6.0,
        ));
    }

    #[test]
    fn full_pipeline_with_fixture() {
        let store = crate::parquet::load_parquet_to_store(
            &PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("testdata")
                .join("test_spatial_index.parquet"),
        );

        let bytes = rkyv::to_bytes::<rkyv::rancor::Error>(&store).unwrap();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();
        let rtree = build_rtree(archived);

        let params = SpatialQueryParams {
            pc_south: 51.0,
            pc_west: -1.0,
            pc_north: 52.0,
            pc_east: 1.0,
            pc_lat: 51.5,
            pc_lon: -0.05,
            map_south: 50.0,
            map_west: -2.0,
            map_north: 53.0,
            map_east: 2.0,
        };

        let resp = execute_query(archived, &rtree, &params, 1.0, 500, 0);

        // Should have at least a header
        assert!(resp.len() >= 8, "Response should have header");

        let magic = u32::from_le_bytes(resp[0..4].try_into().unwrap());
        assert_eq!(magic, SIS_MAGIC_INFLATED);

        let row_count = u32::from_le_bytes(resp[4..8].try_into().unwrap());
        assert!(row_count > 0, "Should find some providers in wide query");
    }

    /// Helper: load fixture, build archived store + R-tree.
    fn fixture_store_and_rtree() -> (
        rkyv::util::AlignedVec,
        StaticAABB2DIndex<f32>,
    ) {
        let store = crate::parquet::load_parquet_to_store(
            &PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("testdata")
                .join("test_spatial_index.parquet"),
        );
        let bytes = rkyv::to_bytes::<rkyv::rancor::Error>(&store).unwrap();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();
        let rtree = build_rtree(archived);
        (bytes, rtree)
    }

    #[test]
    fn limit_hit_r_intersects_v_returns_exact() {
        let (bytes, rtree) = fixture_store_and_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        let params = SpatialQueryParams {
            pc_south: 51.4,
            pc_west: -0.2,
            pc_north: 51.6,
            pc_east: 0.1,
            pc_lat: 51.5,
            pc_lon: -0.05,
            map_south: 51.4,
            map_west: -0.2,
            map_north: 51.6,
            map_east: 0.1,
        };

        let resp = execute_query(archived, &rtree, &params, 1.0, 1, 0);

        assert!(resp.len() >= 8);
        let magic = u32::from_le_bytes(resp[0..4].try_into().unwrap());
        assert_eq!(
            magic, SIS_MAGIC_EXACT,
            "R boundary crosses V → should re-query with exact viewport"
        );
    }

    #[test]
    fn limit_hit_r_inside_v_returns_exact() {
        let (bytes, rtree) = fixture_store_and_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        let params = SpatialQueryParams {
            pc_south: 51.0,
            pc_west: -1.0,
            pc_north: 52.0,
            pc_east: 1.0,
            pc_lat: 51.5,
            pc_lon: -0.05,
            map_south: 51.0,
            map_west: -1.0,
            map_north: 52.0,
            map_east: 1.0,
        };

        let resp = execute_query(archived, &rtree, &params, 1.0, 1, 0);

        assert!(resp.len() >= 8);
        let magic = u32::from_le_bytes(resp[0..4].try_into().unwrap());
        assert_eq!(
            magic, SIS_MAGIC_EXACT,
            "R fully inside V → V not within R → should re-query with exact viewport"
        );
    }

    #[test]
    fn limit_hit_v_inside_r_returns_inflated() {
        let (bytes, rtree) = fixture_store_and_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        let params = SpatialQueryParams {
            pc_south: 51.47,
            pc_west: -0.08,
            pc_north: 51.53,
            pc_east: -0.02,
            pc_lat: 51.5,
            pc_lon: -0.05,
            map_south: 51.47,
            map_west: -0.08,
            map_north: 51.53,
            map_east: -0.02,
        };

        let resp = execute_query(archived, &rtree, &params, 5.0, 1, 0);

        assert!(resp.len() >= 8);
        let magic = u32::from_le_bytes(resp[0..4].try_into().unwrap());
        assert_eq!(
            magic, SIS_MAGIC_INFLATED,
            "V fully inside R → should keep inflated results"
        );
    }

    #[test]
    fn limit_hit_v_disjoint_from_r_returns_exact() {
        let (bytes, rtree) = fixture_store_and_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        let params = SpatialQueryParams {
            pc_south: 51.4,
            pc_west: -0.2,
            pc_north: 51.6,
            pc_east: 0.1,
            pc_lat: 51.5,
            pc_lon: -0.05,
            map_south: 52.0,
            map_west: -0.2,
            map_north: 52.5,
            map_east: 0.1,
        };

        let resp = execute_query(archived, &rtree, &params, 3.0, 1, 0);

        assert!(resp.len() >= 8);
        let magic = u32::from_le_bytes(resp[0..4].try_into().unwrap());
        assert_eq!(
            magic, SIS_MAGIC_EXACT,
            "V completely disjoint from R → should re-query with exact viewport"
        );
    }

    #[test]
    fn viewport_within_circle_v_inside_r() {
        // Large circle, small rect → V ⊂ R → true
        assert!(viewport_within_circle(
            51.5, -0.1, 500.0,
            51.4, -0.2, 51.6, 0.0,
        ));
    }

    #[test]
    fn viewport_within_circle_r_inside_v() {
        // Small circle, large rect → R ⊂ V → false
        assert!(!viewport_within_circle(
            51.5, -0.1, 1.0,
            50.0, -2.0, 53.0, 2.0,
        ));
    }

    #[test]
    fn viewport_within_circle_partial_overlap() {
        // Partial overlap → false
        assert!(!viewport_within_circle(
            51.5, -0.1, 20.0,
            51.3, -0.3, 51.7, 0.1,
        ));
    }

    #[test]
    fn viewport_within_circle_no_overlap() {
        // No overlap → false
        assert!(!viewport_within_circle(
            51.5, -0.1, 10.0,
            55.0, 5.0, 56.0, 6.0,
        ));
    }

    #[test]
    fn distances_ascending() {
        let store = crate::parquet::load_parquet_to_store(
            &PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("testdata")
                .join("test_spatial_index.parquet"),
        );

        let bytes = rkyv::to_bytes::<rkyv::rancor::Error>(&store).unwrap();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();
        let rtree = build_rtree(archived);

        let params = SpatialQueryParams {
            pc_south: 51.0,
            pc_west: -1.0,
            pc_north: 52.0,
            pc_east: 1.0,
            pc_lat: 51.5,
            pc_lon: -0.05,
            map_south: 50.0,
            map_west: -2.0,
            map_north: 53.0,
            map_east: 2.0,
        };

        let resp = execute_query(archived, &rtree, &params, 1.0, 500, 0);
        let n = u32::from_le_bytes(resp[4..8].try_into().unwrap()) as usize;
        assert!(n > 1, "Need multiple rows for ordering test");

        let dist_offset = 8 + 8 * n + n; // after provider_id + care_type

        // Distances should be globally ascending (grouped by provider)
        let mut prev_dist = f32::NEG_INFINITY;
        let mut prev_pid = i64::MIN;

        for i in 0..n {
            let pid = i64::from_le_bytes(
                resp[8 + 8 * i..8 + 8 * i + 8].try_into().unwrap(),
            );
            let d = f32::from_le_bytes(
                resp[dist_offset + 4 * i..dist_offset + 4 * i + 4]
                    .try_into()
                    .unwrap(),
            );

            if pid != prev_pid {
                assert!(
                    d >= prev_dist,
                    "Providers should be in ascending distance order: row {i} dist={d} < prev={prev_dist}"
                );
                prev_dist = d;
                prev_pid = pid;
            }
        }
    }

    #[test]
    fn response_contains_both_point_and_bbox_rows() {
        let (bytes, rtree) = fixture_store_and_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        // Wide query returning all providers
        let params = SpatialQueryParams {
            pc_south: 51.0,
            pc_west: -1.0,
            pc_north: 52.0,
            pc_east: 1.0,
            pc_lat: 51.5,
            pc_lon: -0.05,
            map_south: 50.0,
            map_west: -2.0,
            map_north: 53.0,
            map_east: 2.0,
        };

        let resp = execute_query(archived, &rtree, &params, 1.0, 500, 0);
        let n = u32::from_le_bytes(resp[4..8].try_into().unwrap()) as usize;
        assert!(n > 1);

        let bbox_south_offset = 8 + 62 * n;
        let mut point_count = 0usize;
        let mut bbox_count = 0usize;

        let bbox_west_offset = 8 + 66 * n;
        let bbox_north_offset = 8 + 70 * n;
        let bbox_east_offset = 8 + 74 * n;

        for i in 0..n {
            let bs = f32::from_le_bytes(
                resp[bbox_south_offset + 4 * i..bbox_south_offset + 4 * i + 4]
                    .try_into()
                    .unwrap(),
            );
            let bw = f32::from_le_bytes(
                resp[bbox_west_offset + 4 * i..bbox_west_offset + 4 * i + 4]
                    .try_into()
                    .unwrap(),
            );
            let bn = f32::from_le_bytes(
                resp[bbox_north_offset + 4 * i..bbox_north_offset + 4 * i + 4]
                    .try_into()
                    .unwrap(),
            );
            let be = f32::from_le_bytes(
                resp[bbox_east_offset + 4 * i..bbox_east_offset + 4 * i + 4]
                    .try_into()
                    .unwrap(),
            );

            if bs.is_nan() {
                point_count += 1;
                // Point rows: bbox_north/bbox_west carry lat/lon
                assert!(!bn.is_nan(), "point row bbox_north should carry lat");
                assert!(!bw.is_nan(), "point row bbox_west should carry lon");
                assert!(be.is_nan(), "point row bbox_east should be NaN");
            } else {
                bbox_count += 1;
                assert!(!bw.is_nan(), "bbox_west should not be NaN for bbox row");
                assert!(!bn.is_nan(), "bbox_north should not be NaN for bbox row");
                assert!(!be.is_nan(), "bbox_east should not be NaN for bbox row");
                assert!(bs <= bn, "bbox_south ({bs}) should be <= bbox_north ({bn})");
                assert!(bw <= be, "bbox_west ({bw}) should be <= bbox_east ({be})");
            }
        }

        assert!(point_count > 0, "Should have point provider rows");
        assert!(bbox_count > 0, "Should have bbox provider rows");
    }

    #[test]
    fn care_type_filter_zero_returns_all() {
        let (bytes, rtree) = fixture_store_and_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        let params = SpatialQueryParams {
            pc_south: 51.0,
            pc_west: -1.0,
            pc_north: 52.0,
            pc_east: 1.0,
            pc_lat: 51.5,
            pc_lon: -0.05,
            map_south: 50.0,
            map_west: -2.0,
            map_north: 53.0,
            map_east: 2.0,
        };

        let resp_all = execute_query(archived, &rtree, &params, 1.0, 500, 0);
        let n_all = u32::from_le_bytes(resp_all[4..8].try_into().unwrap());

        // mask=0 should return the same as no filter
        assert!(n_all > 0, "Should find providers with mask=0");
    }

    #[test]
    fn care_type_filter_reduces_results() {
        let (bytes, rtree) = fixture_store_and_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        let params = SpatialQueryParams {
            pc_south: 51.0,
            pc_west: -1.0,
            pc_north: 52.0,
            pc_east: 1.0,
            pc_lat: 51.5,
            pc_lon: -0.05,
            map_south: 50.0,
            map_west: -2.0,
            map_north: 53.0,
            map_east: 2.0,
        };

        let resp_all = execute_query(archived, &rtree, &params, 1.0, 500, 0);
        let n_all = u32::from_le_bytes(resp_all[4..8].try_into().unwrap());

        // mask=4 = childminder only (bit 2)
        let resp_cm = execute_query(archived, &rtree, &params, 1.0, 500, 4);
        let n_cm = u32::from_le_bytes(resp_cm[4..8].try_into().unwrap());

        assert!(
            n_cm < n_all,
            "Childminder-only filter should return fewer rows ({n_cm}) than all ({n_all})"
        );

        // Verify all returned rows have care_type matching the mask
        let dist_offset = 8 + 8 * n_cm as usize; // after provider_id
        for i in 0..n_cm as usize {
            let ct = resp_cm[dist_offset + i]; // care_type column
            assert_eq!(ct, 2, "All rows should be childminder (care_type=2), got {ct}");
        }
    }

    #[test]
    fn bbox_providers_in_separate_list() {
        let (bytes, rtree) = fixture_store_and_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        // Wide query that catches all providers
        let (point, _, bbox, _) = find_providers(
            archived,
            &rtree,
            &archived.aabb_provider_idx,
            51.5,
            -0.05,
            50.0,
            -3.5,
            56.0,
            2.0,
            500,
            0,
        );

        assert!(!point.is_empty(), "Should have point providers");
        assert!(!bbox.is_empty(), "Should have bbox providers");

        // No provider ID should appear in both lists
        let point_ids: std::collections::HashSet<u32> = point.iter().map(|&(id, _)| id).collect();
        let bbox_ids: std::collections::HashSet<u32> = bbox.iter().map(|&(id, _)| id).collect();
        let overlap: Vec<_> = point_ids.intersection(&bbox_ids).collect();
        assert!(
            overlap.is_empty(),
            "No provider should appear in both point and bbox lists: {:?}",
            overlap
        );
    }

    #[test]
    fn bbox_limit_independent_of_point_limit() {
        let (bytes, rtree) = fixture_store_and_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        // With result_limit=1, each population truncated independently
        let (point, point_hit, bbox, bbox_hit) = find_providers(
            archived,
            &rtree,
            &archived.aabb_provider_idx,
            51.5,
            -0.05,
            50.0,
            -3.5,
            56.0,
            2.0,
            1,
            0,
        );

        assert!(point.len() <= 1, "Point list should be truncated to 1");
        assert!(bbox.len() <= 1, "Bbox list should be truncated to 1");
        assert!(point_hit, "Point limit should be hit (fixture has >1 point provider)");
        assert!(bbox_hit, "Bbox limit should be hit (fixture has >1 bbox provider)");
    }

    #[test]
    fn point_hit_limit_does_not_affect_bbox_count() {
        let (bytes, rtree) = fixture_store_and_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        // First, get full counts
        let (all_point, _, all_bbox, _) = find_providers(
            archived,
            &rtree,
            &archived.aabb_provider_idx,
            51.5,
            -0.05,
            50.0,
            -3.5,
            56.0,
            2.0,
            500,
            0,
        );

        // Now with limit=1: point is truncated but bbox count depends only on
        // its own population size, not the point limit
        let (point, point_hit, bbox, _) = find_providers(
            archived,
            &rtree,
            &archived.aabb_provider_idx,
            51.5,
            -0.05,
            50.0,
            -3.5,
            56.0,
            2.0,
            1,
            0,
        );

        assert!(point_hit, "Point limit should be hit");
        assert_eq!(point.len(), 1, "Point list should be truncated to 1");
        assert!(
            all_point.len() > 1,
            "Fixture should have >1 point provider"
        );
        // Bbox list is limited to 1 too (same result_limit), but the important
        // thing is that the point truncation didn't eat into the bbox population
        assert_eq!(bbox.len(), 1, "Bbox list should be truncated to 1");
        assert!(
            all_bbox.len() > 1,
            "Fixture should have >1 bbox provider"
        );
    }

    #[test]
    fn r_circle_check_uses_point_radius_not_bbox() {
        let (bytes, rtree) = fixture_store_and_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        // Postcode centroid at 51.5, -0.05 (central London area).
        // Viewport: a small box around London that is near the postcode.
        // With result_limit=2, the point limit will be hit (5 point providers
        // exist). The 2 nearest point providers are ~6-15 km away. The bbox
        // providers have max-corner distances of ~20-90 km. If the R-circle
        // used bbox distances, R would be huge and V would be inside R (→
        // INFLATED). With point-only R, R is smaller — we choose V to be
        // inside the point-only R, so the response should be INFLATED.
        //
        // This test verifies the code uses point R, not bbox R.
        let params = SpatialQueryParams {
            pc_south: 51.47,
            pc_west: -0.08,
            pc_north: 51.53,
            pc_east: -0.02,
            pc_lat: 51.5,
            pc_lon: -0.05,
            // Small viewport fully within the point-R circle
            map_south: 51.47,
            map_west: -0.08,
            map_north: 51.53,
            map_east: -0.02,
        };

        // result_limit=2: hits point limit (5 point providers) but the 2
        // nearest point providers' max distance defines a small R.
        // With bbox_inflation=5.0, the inflated viewport I catches enough
        // providers. The small V should be inside point-R → INFLATED.
        let resp = execute_query(archived, &rtree, &params, 5.0, 2, 0);

        assert!(resp.len() >= 8);
        let magic = u32::from_le_bytes(resp[0..4].try_into().unwrap());
        assert_eq!(
            magic, SIS_MAGIC_INFLATED,
            "V should be inside point-only R → INFLATED (not re-queried against V)"
        );

        // Verify the response contains bbox rows alongside point rows
        let n = u32::from_le_bytes(resp[4..8].try_into().unwrap()) as usize;
        let bbox_south_offset = 8 + 62 * n;
        let mut has_bbox = false;
        for i in 0..n {
            let bs = f32::from_le_bytes(
                resp[bbox_south_offset + 4 * i..bbox_south_offset + 4 * i + 4]
                    .try_into()
                    .unwrap(),
            );
            if !bs.is_nan() {
                has_bbox = true;
                break;
            }
        }
        assert!(has_bbox, "Response should contain bbox provider rows");
    }
}

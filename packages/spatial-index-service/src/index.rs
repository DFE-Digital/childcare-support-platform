use rkyv::Archived;
use static_aabb2d_index::{StaticAABB2DIndex, StaticAABB2DIndexBuilder};

use crate::store::ArchivedSisStore;

fn build_from_arrays(
    min_x: &[Archived<f32>],
    min_y: &[Archived<f32>],
    max_x: &[Archived<f32>],
    max_y: &[Archived<f32>],
) -> StaticAABB2DIndex<f32> {
    let n = min_x.len();
    let mut builder: StaticAABB2DIndexBuilder<f32> = StaticAABB2DIndexBuilder::new(n);

    for i in 0..n {
        builder.add(
            min_x[i].to_native(),
            min_y[i].to_native(),
            max_x[i].to_native(),
            max_y[i].to_native(),
        );
    }

    builder.build().expect("Failed to build R-tree")
}

/// Build a unified `StaticAABB2DIndex<f32>` from all located provider AABBs.
pub fn build_rtree(store: &ArchivedSisStore) -> StaticAABB2DIndex<f32> {
    build_from_arrays(
        &store.aabb_min_x,
        &store.aabb_min_y,
        &store.aabb_max_x,
        &store.aabb_max_y,
    )
}

/// Inflate a viewport rectangle symmetrically.
pub fn inflate_rect(
    south: f64,
    west: f64,
    north: f64,
    east: f64,
    inflation: f64,
) -> (f32, f32, f32, f32) {
    let height = north - south;
    let width = east - west;
    let half_inf = inflation * 0.5;

    let inf_south = south - half_inf * height;
    let inf_north = north + half_inf * height;
    let inf_west = west - half_inf * width;
    let inf_east = east + half_inf * width;

    (inf_south as f32, inf_west as f32, inf_north as f32, inf_east as f32)
}

/// Query the R-tree with an inflated rectangle. Returns indices into the AABB arrays.
pub fn query_rtree(
    rtree: &StaticAABB2DIndex<f32>,
    south: f32,
    west: f32,
    north: f32,
    east: f32,
) -> Vec<usize> {
    // static_aabb2d_index query: (min_x, min_y, max_x, max_y)
    rtree.query(west, south, east, north)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parquet::load_parquet_to_store;
    use std::path::PathBuf;

    fn fixture_path() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("testdata")
            .join("test_spatial_index.parquet")
    }

    fn build_test_rtree() -> (rkyv::util::AlignedVec, StaticAABB2DIndex<f32>) {
        let store = load_parquet_to_store(&fixture_path());
        let bytes = rkyv::to_bytes::<rkyv::rancor::Error>(&store).unwrap();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();
        let rtree = build_rtree(archived);
        (bytes, rtree)
    }

    #[test]
    fn wide_rect_finds_all_located() {
        let (bytes, rtree) = build_test_rtree();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        // Query with a rect covering the whole world
        let results = query_rtree(&rtree, -90.0, -180.0, 90.0, 180.0);
        assert_eq!(
            results.len(),
            archived.aabb_min_x.len(),
            "Wide query should find all located providers in unified index"
        );
    }

    #[test]
    fn small_rect_finds_subset() {
        let (_bytes, rtree) = build_test_rtree();

        // Very small rect around London (51.5, -0.1) — should find fewer than all
        let all = query_rtree(&rtree, -90.0, -180.0, 90.0, 180.0);
        if all.len() > 1 {
            let small = query_rtree(&rtree, 51.49, -0.11, 51.51, -0.09);
            assert!(
                small.len() < all.len(),
                "Small rect should find fewer than wide rect"
            );
        }
    }

    #[test]
    fn inflation_expands_correctly() {
        let (s, w, n, e) = inflate_rect(51.0, -1.0, 52.0, 0.0, 1.0);
        // inflation=1.0 → 0.5 * dimension per side
        // height=1.0, so 0.5 each side → south=50.5, north=52.5
        // width=1.0, so 0.5 each side → west=-1.5, east=0.5
        assert!((s - 50.5).abs() < 0.01);
        assert!((w - (-1.5)).abs() < 0.01);
        assert!((n - 52.5).abs() < 0.01);
        assert!((e - 0.5).abs() < 0.01);
    }
}

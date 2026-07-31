use std::path::Path;

use arrow::array::{Array, BooleanArray, Float32Array, Int32Array, Int64Array, Int8Array};
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;

use crate::store::SisStore;

struct ParquetRows {
    provider_id: Vec<i64>,
    caretype_index: Vec<i8>,
    care_type: Vec<i8>,
    lat: Vec<f32>,
    lon: Vec<f32>,
    bbox_lat: Vec<f32>,
    bbox_lon: Vec<f32>,
    filter_accepts_funded_hours: Vec<u8>,
    filter_eligible_min_months: Vec<i8>,
    filter_eligible_min_years: Vec<i8>,
    filter_eligible_max_years: Vec<i8>,
    sort_daily_open: Vec<f32>,
    sort_daily_close: Vec<f32>,
    sort_annual_opening: Vec<i8>,
    sort_ofsted: Vec<f32>,
    sort_graduates: Vec<f32>,
    sort_turnover: Vec<f32>,
    sort_cost_all: Vec<f32>,
    sort_cost_under2: Vec<f32>,
    sort_cost_age2: Vec<f32>,
    sort_cost_age3to4: Vec<f32>,
    sort_cost_age2plus: Vec<f32>,
    sort_cost_age5plus: Vec<f32>,
    lad_code: Vec<i32>,
}

fn nullable_f32(arr: &Float32Array, i: usize) -> f32 {
    if arr.is_null(i) {
        f32::NAN
    } else {
        arr.value(i)
    }
}

fn nullable_i8(arr: &Int8Array, i: usize) -> i8 {
    if arr.is_null(i) {
        -1
    } else {
        arr.value(i)
    }
}

fn read_parquet(path: &Path) -> ParquetRows {
    let file = std::fs::File::open(path)
        .unwrap_or_else(|e| panic!("Failed to open parquet file {}: {e}", path.display()));

    let builder = ParquetRecordBatchReaderBuilder::try_new(file)
        .expect("Failed to create parquet reader");
    let reader = builder.build().expect("Failed to build parquet reader");

    let mut rows = ParquetRows {
        provider_id: Vec::new(),
        caretype_index: Vec::new(),
        care_type: Vec::new(),
        lat: Vec::new(),
        lon: Vec::new(),
        bbox_lat: Vec::new(),
        bbox_lon: Vec::new(),
        filter_accepts_funded_hours: Vec::new(),
        filter_eligible_min_months: Vec::new(),
        filter_eligible_min_years: Vec::new(),
        filter_eligible_max_years: Vec::new(),
        sort_daily_open: Vec::new(),
        sort_daily_close: Vec::new(),
        sort_annual_opening: Vec::new(),
        sort_ofsted: Vec::new(),
        sort_graduates: Vec::new(),
        sort_turnover: Vec::new(),
        sort_cost_all: Vec::new(),
        sort_cost_under2: Vec::new(),
        sort_cost_age2: Vec::new(),
        sort_cost_age3to4: Vec::new(),
        sort_cost_age2plus: Vec::new(),
        sort_cost_age5plus: Vec::new(),
        lad_code: Vec::new(),
    };

    for batch in reader {
        let batch = batch.expect("Failed to read record batch");
        let n = batch.num_rows();

        let col_provider_id = batch
            .column_by_name("provider_id")
            .expect("Missing column: provider_id")
            .as_any()
            .downcast_ref::<Int64Array>()
            .expect("provider_id must be Int64");

        let col_caretype_index = batch
            .column_by_name("caretype_index")
            .expect("Missing column: caretype_index")
            .as_any()
            .downcast_ref::<Int8Array>()
            .expect("caretype_index must be Int8");

        let col_care_type = batch
            .column_by_name("care_type")
            .expect("Missing column: care_type")
            .as_any()
            .downcast_ref::<Int8Array>()
            .expect("care_type must be Int8");

        let col_lat = batch
            .column_by_name("lat")
            .expect("Missing column: lat")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("lat must be Float32");

        let col_lon = batch
            .column_by_name("lon")
            .expect("Missing column: lon")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("lon must be Float32");

        let col_bbox_lat = batch
            .column_by_name("bbox_lat")
            .expect("Missing column: bbox_lat")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("bbox_lat must be Float32");

        let col_bbox_lon = batch
            .column_by_name("bbox_lon")
            .expect("Missing column: bbox_lon")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("bbox_lon must be Float32");

        let col_funded = batch
            .column_by_name("filter_accepts_funded_hours")
            .expect("Missing column: filter_accepts_funded_hours")
            .as_any()
            .downcast_ref::<BooleanArray>()
            .expect("filter_accepts_funded_hours must be Boolean");

        let col_min_months = batch
            .column_by_name("filter_eligible_min_months")
            .expect("Missing column: filter_eligible_min_months")
            .as_any()
            .downcast_ref::<Int8Array>()
            .expect("filter_eligible_min_months must be Int8");

        let col_min_years = batch
            .column_by_name("filter_eligible_min_years")
            .expect("Missing column: filter_eligible_min_years")
            .as_any()
            .downcast_ref::<Int8Array>()
            .expect("filter_eligible_min_years must be Int8");

        let col_max_years = batch
            .column_by_name("filter_eligible_max_years")
            .expect("Missing column: filter_eligible_max_years")
            .as_any()
            .downcast_ref::<Int8Array>()
            .expect("filter_eligible_max_years must be Int8");

        let col_daily_open = batch
            .column_by_name("sort_daily_open")
            .expect("Missing column: sort_daily_open")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("sort_daily_open must be Float32");

        let col_daily_close = batch
            .column_by_name("sort_daily_close")
            .expect("Missing column: sort_daily_close")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("sort_daily_close must be Float32");

        let col_annual = batch
            .column_by_name("sort_annual_opening")
            .expect("Missing column: sort_annual_opening")
            .as_any()
            .downcast_ref::<Int8Array>()
            .expect("sort_annual_opening must be Int8");

        let col_ofsted = batch
            .column_by_name("sort_ofsted")
            .expect("Missing column: sort_ofsted")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("sort_ofsted must be Float32");

        let col_graduates = batch
            .column_by_name("sort_graduates")
            .expect("Missing column: sort_graduates")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("sort_graduates must be Float32");

        let col_turnover = batch
            .column_by_name("sort_turnover")
            .expect("Missing column: sort_turnover")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("sort_turnover must be Float32");

        let col_cost_all = batch
            .column_by_name("sort_cost_all")
            .expect("Missing column: sort_cost_all")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("sort_cost_all must be Float32");

        let col_cost_under2 = batch
            .column_by_name("sort_cost_under2")
            .expect("Missing column: sort_cost_under2")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("sort_cost_under2 must be Float32");

        let col_cost_age2 = batch
            .column_by_name("sort_cost_age2")
            .expect("Missing column: sort_cost_age2")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("sort_cost_age2 must be Float32");

        let col_cost_age3to4 = batch
            .column_by_name("sort_cost_age3to4")
            .expect("Missing column: sort_cost_age3to4")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("sort_cost_age3to4 must be Float32");

        let col_cost_age2plus = batch
            .column_by_name("sort_cost_age2plus")
            .expect("Missing column: sort_cost_age2plus")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("sort_cost_age2plus must be Float32");

        let col_cost_age5plus = batch
            .column_by_name("sort_cost_age5plus")
            .expect("Missing column: sort_cost_age5plus")
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("sort_cost_age5plus must be Float32");

        let col_lad_code = batch
            .column_by_name("lad_code")
            .expect("Missing column: lad_code")
            .as_any()
            .downcast_ref::<Int32Array>()
            .expect("lad_code must be Int32");

        for i in 0..n {
            rows.provider_id.push(col_provider_id.value(i));
            rows.caretype_index.push(col_caretype_index.value(i));
            rows.care_type.push(col_care_type.value(i));
            rows.lat.push(nullable_f32(col_lat, i));
            rows.lon.push(nullable_f32(col_lon, i));
            rows.bbox_lat.push(nullable_f32(col_bbox_lat, i));
            rows.bbox_lon.push(nullable_f32(col_bbox_lon, i));
            rows.filter_accepts_funded_hours
                .push(if col_funded.value(i) { 1 } else { 0 });
            rows.filter_eligible_min_months
                .push(nullable_i8(col_min_months, i));
            rows.filter_eligible_min_years
                .push(nullable_i8(col_min_years, i));
            rows.filter_eligible_max_years
                .push(nullable_i8(col_max_years, i));
            rows.sort_daily_open.push(nullable_f32(col_daily_open, i));
            rows.sort_daily_close.push(nullable_f32(col_daily_close, i));
            rows.sort_annual_opening.push(col_annual.value(i));
            rows.sort_ofsted.push(col_ofsted.value(i));
            rows.sort_graduates.push(nullable_f32(col_graduates, i));
            rows.sort_turnover.push(nullable_f32(col_turnover, i));
            rows.sort_cost_all.push(nullable_f32(col_cost_all, i));
            rows.sort_cost_under2.push(nullable_f32(col_cost_under2, i));
            rows.sort_cost_age2.push(nullable_f32(col_cost_age2, i));
            rows.sort_cost_age3to4
                .push(nullable_f32(col_cost_age3to4, i));
            rows.sort_cost_age2plus
                .push(nullable_f32(col_cost_age2plus, i));
            rows.sort_cost_age5plus
                .push(nullable_f32(col_cost_age5plus, i));
            rows.lad_code.push(col_lad_code.value(i));
        }
    }

    rows
}

/// Build provider lookup tables from sorted rows.
///
/// Returns `(first_row, row_count, centre_lat, centre_lon)` per unique provider.
fn build_provider_lookup(
    rows: &ParquetRows,
) -> (Vec<u32>, Vec<u16>, Vec<f32>, Vec<f32>) {
    let mut first_row: Vec<u32> = Vec::new();
    let mut row_count: Vec<u16> = Vec::new();
    let mut centre_lat: Vec<f32> = Vec::new();
    let mut centre_lon: Vec<f32> = Vec::new();

    let n = rows.provider_id.len();
    if n == 0 {
        return (first_row, row_count, centre_lat, centre_lon);
    }

    let mut start = 0usize;
    let mut current_id = rows.provider_id[0];

    for i in 1..=n {
        if i == n || rows.provider_id[i] != current_id {
            first_row.push(start as u32);
            row_count.push((i - start) as u16);

            // Compute centre from first row of this provider
            let lat = rows.lat[start];
            let lon = rows.lon[start];
            let blat = rows.bbox_lat[start];
            let blon = rows.bbox_lon[start];

            if !lat.is_nan() && !blat.is_nan() {
                // Bbox provider: centre is midpoint of NW corner (lat,lon) and SE corner (bbox_lat,bbox_lon)
                centre_lat.push((lat + blat) / 2.0);
                centre_lon.push((lon + blon) / 2.0);
            } else if !lat.is_nan() {
                // Point provider
                centre_lat.push(lat);
                centre_lon.push(lon);
            } else {
                // Unlocated provider
                centre_lat.push(f32::NAN);
                centre_lon.push(f32::NAN);
            }

            if i < n {
                start = i;
                current_id = rows.provider_id[i];
            }
        }
    }

    (first_row, row_count, centre_lat, centre_lon)
}

/// Load a parquet file and build a complete `SisStore`.
pub fn load_parquet_to_store(path: &Path) -> SisStore {
    let rows = read_parquet(path);
    let n = rows.provider_id.len() as u32;

    let (provider_first_row, provider_row_count, provider_centre_lat, provider_centre_lon) =
        build_provider_lookup(&rows);

    // Build unified AABBs — both point (degenerate) and bbox providers
    let num_providers = provider_first_row.len();
    let mut aabb_min_x: Vec<f32> = Vec::new();
    let mut aabb_min_y: Vec<f32> = Vec::new();
    let mut aabb_max_x: Vec<f32> = Vec::new();
    let mut aabb_max_y: Vec<f32> = Vec::new();
    let mut aabb_provider_idx: Vec<u32> = Vec::new();

    for pidx in 0..num_providers {
        let row = provider_first_row[pidx] as usize;
        let lat = rows.lat[row];
        let lon = rows.lon[row];

        if lat.is_nan() {
            continue; // Skip unlocated providers
        }

        let blat = rows.bbox_lat[row];
        let blon = rows.bbox_lon[row];

        if !blat.is_nan() {
            // Bbox provider → full-extent AABB
            let north = lat;
            let west = lon;
            let south = blat;
            let east = blon;
            aabb_min_x.push(west.min(east));
            aabb_min_y.push(south.min(north));
            aabb_max_x.push(west.max(east));
            aabb_max_y.push(south.max(north));
        } else {
            // Point provider → degenerate AABB
            aabb_min_x.push(lon);
            aabb_min_y.push(lat);
            aabb_max_x.push(lon);
            aabb_max_y.push(lat);
        }
        aabb_provider_idx.push(pidx as u32);
    }

    SisStore {
        len: n,
        provider_id: rows.provider_id,
        caretype_index: rows.caretype_index,
        care_type: rows.care_type,
        lat: rows.lat,
        lon: rows.lon,
        bbox_lat: rows.bbox_lat,
        bbox_lon: rows.bbox_lon,
        filter_accepts_funded_hours: rows.filter_accepts_funded_hours,
        filter_eligible_min_months: rows.filter_eligible_min_months,
        filter_eligible_min_years: rows.filter_eligible_min_years,
        filter_eligible_max_years: rows.filter_eligible_max_years,
        sort_daily_open: rows.sort_daily_open,
        sort_daily_close: rows.sort_daily_close,
        sort_annual_opening: rows.sort_annual_opening,
        sort_ofsted: rows.sort_ofsted,
        sort_graduates: rows.sort_graduates,
        sort_turnover: rows.sort_turnover,
        sort_cost_all: rows.sort_cost_all,
        sort_cost_under2: rows.sort_cost_under2,
        sort_cost_age2: rows.sort_cost_age2,
        sort_cost_age3to4: rows.sort_cost_age3to4,
        sort_cost_age2plus: rows.sort_cost_age2plus,
        sort_cost_age5plus: rows.sort_cost_age5plus,
        lad_code: rows.lad_code,
        provider_first_row,
        provider_row_count,
        provider_centre_lat,
        provider_centre_lon,
        aabb_min_x,
        aabb_min_y,
        aabb_max_x,
        aabb_max_y,
        aabb_provider_idx,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn fixture_path() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("testdata")
            .join("test_spatial_index.parquet")
    }

    #[test]
    fn load_fixture() {
        let store = load_parquet_to_store(&fixture_path());
        assert!(store.len > 0, "Fixture should have rows");
        assert_eq!(store.provider_id.len(), store.len as usize);
        assert_eq!(store.care_type.len(), store.len as usize);
        assert_eq!(store.lat.len(), store.len as usize);
        assert!(
            !store.provider_first_row.is_empty(),
            "Should have at least one provider"
        );
    }

    #[test]
    fn provider_lookup_correct() {
        let store = load_parquet_to_store(&fixture_path());

        // Each provider's rows should be contiguous and match row_count
        for (pidx, &first) in store.provider_first_row.iter().enumerate() {
            let count = store.provider_row_count[pidx] as usize;
            let first = first as usize;
            let pid = store.provider_id[first];
            for r in first..first + count {
                assert_eq!(
                    store.provider_id[r], pid,
                    "All rows in provider range should have same provider_id"
                );
            }
        }
    }

    #[test]
    fn unlocated_excluded_from_aabbs() {
        let store = load_parquet_to_store(&fixture_path());

        // All AABB entries should reference located providers
        for &pidx in &store.aabb_provider_idx {
            let row = store.provider_first_row[pidx as usize] as usize;
            assert!(
                !store.lat[row].is_nan(),
                "AABB should not include unlocated providers"
            );
        }
    }

    #[test]
    fn located_providers_in_unified_index() {
        let store = load_parquet_to_store(&fixture_path());

        // Count located providers
        let num_located = (0..store.provider_first_row.len())
            .filter(|&pidx| {
                let row = store.provider_first_row[pidx] as usize;
                !store.lat[row].is_nan()
            })
            .count();

        assert_eq!(
            store.aabb_provider_idx.len(),
            num_located,
            "Unified index should contain all located providers (point + bbox)"
        );

        // Should have both point and bbox providers
        let has_point = store.aabb_provider_idx.iter().any(|&pidx| {
            let row = store.provider_first_row[pidx as usize] as usize;
            store.bbox_lat[row].is_nan()
        });
        let has_bbox = store.aabb_provider_idx.iter().any(|&pidx| {
            let row = store.provider_first_row[pidx as usize] as usize;
            !store.bbox_lat[row].is_nan()
        });
        assert!(has_point, "Should have point providers in unified index");
        assert!(has_bbox, "Should have bbox providers in unified index");
    }
}

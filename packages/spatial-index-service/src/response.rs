use crate::store::ArchivedSisStore;

/// Magic bytes: response from inflated rectangle *I* (backward-compatible default).
pub const SIS_MAGIC_INFLATED: u32 = 0x53495300; // "SIS\0"
/// Magic bytes: re-queried against exact viewport *V* because *R* crossed *V*.
pub const SIS_MAGIC_EXACT: u32 = 0x53495301; // "SIS\x01"

/// Serialize selected rows into the column-major binary response format.
///
/// `row_indices` are indices into the store's column arrays.
/// `distances` is parallel to `row_indices` — one distance per row.
/// `magic` selects the header magic (inflated vs exact).
pub fn serialize_response(
    store: &ArchivedSisStore,
    row_indices: &[usize],
    distances: &[f32],
    magic: u32,
) -> Vec<u8> {
    let n = row_indices.len();

    // 8 bytes header + 82 bytes per row
    let mut buf = Vec::with_capacity(8 + 82 * n);

    // Header
    buf.extend_from_slice(&magic.to_le_bytes());
    buf.extend_from_slice(&(n as u32).to_le_bytes());

    // Columns in schema order
    // provider_id: i64
    for &ri in row_indices {
        buf.extend_from_slice(&store.provider_id[ri].to_native().to_le_bytes());
    }
    // care_type: i8
    for &ri in row_indices {
        buf.push(store.care_type[ri] as u8);
    }
    // sort_distance: f32
    for &d in distances {
        buf.extend_from_slice(&d.to_le_bytes());
    }
    // sort_daily_open: f32
    for &ri in row_indices {
        buf.extend_from_slice(&store.sort_daily_open[ri].to_native().to_le_bytes());
    }
    // sort_daily_close: f32
    for &ri in row_indices {
        buf.extend_from_slice(&store.sort_daily_close[ri].to_native().to_le_bytes());
    }
    // sort_annual_opening: i8
    for &ri in row_indices {
        buf.push(store.sort_annual_opening[ri] as u8);
    }
    // sort_ofsted: f32
    for &ri in row_indices {
        buf.extend_from_slice(&store.sort_ofsted[ri].to_native().to_le_bytes());
    }
    // sort_graduates: f32
    for &ri in row_indices {
        buf.extend_from_slice(&store.sort_graduates[ri].to_native().to_le_bytes());
    }
    // sort_turnover: f32
    for &ri in row_indices {
        buf.extend_from_slice(&store.sort_turnover[ri].to_native().to_le_bytes());
    }
    // sort_cost_all: f32
    for &ri in row_indices {
        buf.extend_from_slice(&store.sort_cost_all[ri].to_native().to_le_bytes());
    }
    // sort_cost_under2: f32
    for &ri in row_indices {
        buf.extend_from_slice(&store.sort_cost_under2[ri].to_native().to_le_bytes());
    }
    // sort_cost_age2: f32
    for &ri in row_indices {
        buf.extend_from_slice(&store.sort_cost_age2[ri].to_native().to_le_bytes());
    }
    // sort_cost_age3to4: f32
    for &ri in row_indices {
        buf.extend_from_slice(&store.sort_cost_age3to4[ri].to_native().to_le_bytes());
    }
    // sort_cost_age2plus: f32
    for &ri in row_indices {
        buf.extend_from_slice(&store.sort_cost_age2plus[ri].to_native().to_le_bytes());
    }
    // sort_cost_age5plus: f32
    for &ri in row_indices {
        buf.extend_from_slice(&store.sort_cost_age5plus[ri].to_native().to_le_bytes());
    }
    // filter_accepts_funded_hours: u8
    for &ri in row_indices {
        buf.push(store.filter_accepts_funded_hours[ri]);
    }
    // filter_eligible_min_months: i8
    for &ri in row_indices {
        buf.push(store.filter_eligible_min_months[ri] as u8);
    }
    // filter_eligible_min_years: i8
    for &ri in row_indices {
        buf.push(store.filter_eligible_min_years[ri] as u8);
    }
    // filter_eligible_max_years: i8
    for &ri in row_indices {
        buf.push(store.filter_eligible_max_years[ri] as u8);
    }
    // Bbox columns carry location data for all located providers:
    //   bbox_south = bbox_lat (SE lat for bbox; NaN for point/unlocated)
    //   bbox_west  = lon      (NW lon for bbox, point lon for point; NaN for unlocated)
    //   bbox_north = lat      (NW lat for bbox, point lat for point; NaN for unlocated)
    //   bbox_east  = bbox_lon (SE lon for bbox; NaN for point/unlocated)
    // Discriminator: isNaN(bbox_south) → not a bbox provider.
    // bbox_north/bbox_west always contain lat/lon for all located providers.
    for &ri in row_indices {
        buf.extend_from_slice(&store.bbox_lat[ri].to_native().to_le_bytes());
    }
    for &ri in row_indices {
        buf.extend_from_slice(&store.lon[ri].to_native().to_le_bytes());
    }
    for &ri in row_indices {
        buf.extend_from_slice(&store.lat[ri].to_native().to_le_bytes());
    }
    for &ri in row_indices {
        buf.extend_from_slice(&store.bbox_lon[ri].to_native().to_le_bytes());
    }
    // lad_code: i32
    for &ri in row_indices {
        buf.extend_from_slice(&store.lad_code[ri].to_native().to_le_bytes());
    }

    buf
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

    #[test]
    fn header_correct() {
        let store = load_parquet_to_store(&fixture_path());
        let bytes = rkyv::to_bytes::<rkyv::rancor::Error>(&store).unwrap();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        let indices: Vec<usize> = (0..store.len.min(3) as usize).collect();
        let distances: Vec<f32> = indices.iter().map(|&i| i as f32 * 1.0).collect();

        let resp = serialize_response(archived, &indices, &distances, SIS_MAGIC_INFLATED);
        let n = indices.len();

        // Check magic
        let magic = u32::from_le_bytes(resp[0..4].try_into().unwrap());
        assert_eq!(magic, SIS_MAGIC_INFLATED);

        // Check row count
        let row_count = u32::from_le_bytes(resp[4..8].try_into().unwrap());
        assert_eq!(row_count, n as u32);

        // Check total size: 8 + 82 * n
        assert_eq!(resp.len(), 8 + 82 * n);
    }

    #[test]
    fn column_offsets_correct() {
        let store = load_parquet_to_store(&fixture_path());
        let bytes = rkyv::to_bytes::<rkyv::rancor::Error>(&store).unwrap();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        let indices = vec![0usize];
        let distances = vec![1.5f32];

        let resp = serialize_response(archived, &indices, &distances, SIS_MAGIC_INFLATED);

        // provider_id at offset 8, 8 bytes
        let pid = i64::from_le_bytes(resp[8..16].try_into().unwrap());
        assert_eq!(pid, store.provider_id[0]);

        // care_type at offset 8 + 8*1 = 16, 1 byte
        assert_eq!(resp[16] as i8, store.care_type[0]);

        // sort_distance at offset 17, 4 bytes
        let dist = f32::from_le_bytes(resp[17..21].try_into().unwrap());
        assert!((dist - 1.5).abs() < f32::EPSILON);
    }

    #[test]
    fn bbox_column_values_correct() {
        let store = load_parquet_to_store(&fixture_path());
        let bytes = rkyv::to_bytes::<rkyv::rancor::Error>(&store).unwrap();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        // Row 0 = Provider 1 (point), fixture row 3 = Provider 3 (bbox)
        let indices = vec![0usize, 3];
        let distances = vec![1.5f32, 3.0];
        let resp = serialize_response(archived, &indices, &distances, SIS_MAGIC_INFLATED);
        let n = 2usize;

        let bbox_south = 8 + 62 * n;
        let bbox_west = 8 + 66 * n;
        let bbox_north = 8 + 70 * n;
        let bbox_east = 8 + 74 * n;

        let read_f32 =
            |offset: usize| f32::from_le_bytes(resp[offset..offset + 4].try_into().unwrap());

        // Row 0 (point): bbox_south/bbox_east = NaN, bbox_north/bbox_west = lat/lon
        assert!(read_f32(bbox_south).is_nan(), "point row bbox_south should be NaN");
        assert_eq!(read_f32(bbox_west), archived.lon[0].to_native(), "point row bbox_west = lon");
        assert_eq!(read_f32(bbox_north), archived.lat[0].to_native(), "point row bbox_north = lat");
        assert!(read_f32(bbox_east).is_nan(), "point row bbox_east should be NaN");

        // Row 1 (bbox, fixture row 3 = Provider 3):
        //   south = bbox_lat[3], west = lon[3], north = lat[3], east = bbox_lon[3]
        assert_eq!(read_f32(bbox_south + 4), archived.bbox_lat[3].to_native());
        assert_eq!(read_f32(bbox_west + 4), archived.lon[3].to_native());
        assert_eq!(read_f32(bbox_north + 4), archived.lat[3].to_native());
        assert_eq!(read_f32(bbox_east + 4), archived.bbox_lon[3].to_native());
    }
}

use rkyv::{Archive, Deserialize, Serialize};

#[derive(Archive, Serialize, Deserialize, Debug)]
#[rkyv(compare(PartialEq), derive(Debug))]
pub struct SisStore {
    pub len: u32,
    // Identity
    pub provider_id: Vec<i64>,
    pub caretype_index: Vec<i8>,
    pub care_type: Vec<i8>,
    // Geometry (used for spatial queries; lat/lon also serialized as bbox_north/bbox_west)
    pub lat: Vec<f32>,
    pub lon: Vec<f32>,
    pub bbox_lat: Vec<f32>,
    pub bbox_lon: Vec<f32>,
    // Filters (sent over wire)
    pub filter_accepts_funded_hours: Vec<u8>, // 0/1
    pub filter_eligible_min_months: Vec<i8>,
    pub filter_eligible_min_years: Vec<i8>,
    pub filter_eligible_max_years: Vec<i8>,
    // Sort scores (sent over wire)
    pub sort_daily_open: Vec<f32>,
    pub sort_daily_close: Vec<f32>,
    pub sort_annual_opening: Vec<i8>,
    pub sort_ofsted: Vec<f32>,
    pub sort_graduates: Vec<f32>,
    pub sort_turnover: Vec<f32>,
    pub sort_cost_all: Vec<f32>,
    pub sort_cost_under2: Vec<f32>,
    pub sort_cost_age2: Vec<f32>,
    pub sort_cost_age3to4: Vec<f32>,
    pub sort_cost_age2plus: Vec<f32>,
    pub sort_cost_age5plus: Vec<f32>,
    // LAD identity
    pub lad_code: Vec<i32>,
    // Provider lookup (for row expansion)
    pub provider_first_row: Vec<u32>,
    pub provider_row_count: Vec<u16>,
    pub provider_centre_lat: Vec<f32>,
    pub provider_centre_lon: Vec<f32>,
    // R-tree AABBs for all located providers (unified index)
    pub aabb_min_x: Vec<f32>,
    pub aabb_min_y: Vec<f32>,
    pub aabb_max_x: Vec<f32>,
    pub aabb_max_y: Vec<f32>,
    pub aabb_provider_idx: Vec<u32>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rkyv_round_trip() {
        let store = SisStore {
            len: 2,
            provider_id: vec![100, 100],
            caretype_index: vec![0, 1],
            care_type: vec![0, 2],
            lat: vec![51.5, 51.5],
            lon: vec![-0.1, -0.1],
            bbox_lat: vec![f32::NAN, f32::NAN],
            bbox_lon: vec![f32::NAN, f32::NAN],
            filter_accepts_funded_hours: vec![1, 0],
            filter_eligible_min_months: vec![0, -1],
            filter_eligible_min_years: vec![0, -1],
            filter_eligible_max_years: vec![5, -1],
            sort_daily_open: vec![7.5, f32::NAN],
            sort_daily_close: vec![17.5, f32::NAN],
            sort_annual_opening: vec![50, -1],
            sort_ofsted: vec![0.8, 0.8],
            sort_graduates: vec![0.5, f32::NAN],
            sort_turnover: vec![0.1, f32::NAN],
            sort_cost_all: vec![5.0, f32::NAN],
            sort_cost_under2: vec![6.0, f32::NAN],
            sort_cost_age2: vec![5.5, f32::NAN],
            sort_cost_age3to4: vec![5.0, f32::NAN],
            sort_cost_age2plus: vec![5.2, f32::NAN],
            sort_cost_age5plus: vec![4.0, f32::NAN],
            lad_code: vec![106000023, 106000023],
            provider_first_row: vec![0],
            provider_row_count: vec![2],
            provider_centre_lat: vec![51.5],
            provider_centre_lon: vec![-0.1],
            aabb_min_x: vec![-0.1],
            aabb_min_y: vec![51.5],
            aabb_max_x: vec![-0.1],
            aabb_max_y: vec![51.5],
            aabb_provider_idx: vec![0],
        };

        let bytes = rkyv::to_bytes::<rkyv::rancor::Error>(&store).unwrap();
        let archived = rkyv::access::<ArchivedSisStore, rkyv::rancor::Error>(&bytes).unwrap();

        assert_eq!(archived.len, 2);
        assert_eq!(archived.provider_id.as_slice(), &[100i64, 100]);
        assert_eq!(archived.care_type.as_slice(), &[0i8, 2]);
        assert_eq!(archived.provider_first_row.as_slice(), &[0u32]);
        assert_eq!(archived.provider_row_count.as_slice(), &[2u16]);
    }
}

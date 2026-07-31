import pyarrow as pa

CARE_TYPE_ENUM = {
    "private_nursery": 0,
    "school_based_nursery": 1,
    "childminder": 2,
    "breakfast_club": 3,
    "free_breakfast_club": 4,
    "after_school_club": 5,
    "holiday_club": 6,
}

SPATIAL_INDEX_SCHEMA = pa.schema(
    [
        pa.field("provider_id", pa.int64(), nullable=False),
        pa.field("caretype_index", pa.int8(), nullable=False),
        pa.field("care_type", pa.int8(), nullable=False),
        pa.field("lat", pa.float32()),
        pa.field("lon", pa.float32()),
        pa.field("bbox_lat", pa.float32()),
        pa.field("bbox_lon", pa.float32()),
        pa.field("filter_accepts_funded_hours", pa.bool_(), nullable=False),
        pa.field("filter_eligible_min_months", pa.int8()),
        pa.field("filter_eligible_min_years", pa.int8()),
        pa.field("filter_eligible_max_years", pa.int8()),
        pa.field("sort_daily_open", pa.float32()),
        pa.field("sort_daily_close", pa.float32()),
        pa.field("sort_annual_opening", pa.int8(), nullable=False),
        pa.field("sort_ofsted", pa.float32(), nullable=False),
        pa.field("sort_graduates", pa.float32()),
        pa.field("sort_turnover", pa.float32()),
        pa.field("sort_cost_all", pa.float32()),
        pa.field("sort_cost_under2", pa.float32()),
        pa.field("sort_cost_age2", pa.float32()),
        pa.field("sort_cost_age3to4", pa.float32()),
        pa.field("sort_cost_age2plus", pa.float32()),
        pa.field("sort_cost_age5plus", pa.float32()),
        pa.field("lad_code", pa.int32(), nullable=False),
    ]
)

"""Generate a test parquet fixture for the Spatial Index Service.

Creates ~20 rows with a mix of:
- Point providers (lat/lon only)
- Bbox providers (lat/lon + bbox_lat/bbox_lon)
- Unlocated providers (all coords NaN)
- Multiple care types per provider
- Various filter/sort values including nulls
"""

import math

import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA = pa.schema(
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

NaN = float("nan")

# Rows sorted by provider_id, then caretype_index
rows = [
    # Provider 1: Point provider in London, 2 care types
    {
        "provider_id": 1,
        "caretype_index": 0,
        "care_type": 0,  # private_nursery
        "lat": 51.5074,
        "lon": -0.1278,
        "bbox_lat": None,
        "bbox_lon": None,
        "filter_accepts_funded_hours": True,
        "filter_eligible_min_months": 3,
        "filter_eligible_min_years": 0,
        "filter_eligible_max_years": 5,
        "sort_daily_open": 7.5,
        "sort_daily_close": 18.0,
        "sort_annual_opening": 50,
        "sort_ofsted": 0.85,
        "sort_graduates": 0.6,
        "sort_turnover": 0.12,
        "sort_cost_all": 5.5,
        "sort_cost_under2": 7.0,
        "sort_cost_age2": 6.0,
        "sort_cost_age3to4": 5.5,
        "sort_cost_age2plus": 5.8,
        "sort_cost_age5plus": 4.0,
        "lad_code": 109000001,  # E09000001
    },
    {
        "provider_id": 1,
        "caretype_index": 1,
        "care_type": 5,  # after_school_club
        "lat": 51.5074,
        "lon": -0.1278,
        "bbox_lat": None,
        "bbox_lon": None,
        "filter_accepts_funded_hours": False,
        "filter_eligible_min_months": None,
        "filter_eligible_min_years": 5,
        "filter_eligible_max_years": 11,
        "sort_daily_open": 15.0,
        "sort_daily_close": 18.0,
        "sort_annual_opening": 38,
        "sort_ofsted": 0.85,
        "sort_graduates": 0.6,
        "sort_turnover": 0.12,
        "sort_cost_all": 4.0,
        "sort_cost_under2": None,
        "sort_cost_age2": None,
        "sort_cost_age3to4": None,
        "sort_cost_age2plus": None,
        "sort_cost_age5plus": 4.0,
        "lad_code": 109000001,  # E09000001
    },
    # Provider 2: Point provider in Manchester, 1 care type
    {
        "provider_id": 2,
        "caretype_index": 0,
        "care_type": 2,  # childminder
        "lat": 53.4808,
        "lon": -2.2426,
        "bbox_lat": None,
        "bbox_lon": None,
        "filter_accepts_funded_hours": True,
        "filter_eligible_min_months": 0,
        "filter_eligible_min_years": 0,
        "filter_eligible_max_years": 8,
        "sort_daily_open": 7.0,
        "sort_daily_close": 18.0,
        "sort_annual_opening": 48,
        "sort_ofsted": 0.72,
        "sort_graduates": None,
        "sort_turnover": None,
        "sort_cost_all": 4.5,
        "sort_cost_under2": 5.5,
        "sort_cost_age2": 5.0,
        "sort_cost_age3to4": 4.5,
        "sort_cost_age2plus": 4.8,
        "sort_cost_age5plus": 3.5,
        "lad_code": 108000003,  # E08000003
    },
    # Provider 3: Bbox provider (local authority area), 3 care types
    {
        "provider_id": 3,
        "caretype_index": 0,
        "care_type": 0,  # private_nursery
        # NW corner (north lat, west lon)
        "lat": 51.6,
        "lon": -0.3,
        # SE corner (south lat, east lon)
        "bbox_lat": 51.4,
        "bbox_lon": 0.1,
        "filter_accepts_funded_hours": True,
        "filter_eligible_min_months": 6,
        "filter_eligible_min_years": 0,
        "filter_eligible_max_years": 5,
        "sort_daily_open": 8.0,
        "sort_daily_close": 17.0,
        "sort_annual_opening": 51,
        "sort_ofsted": 0.90,
        "sort_graduates": 0.8,
        "sort_turnover": 0.08,
        "sort_cost_all": 6.0,
        "sort_cost_under2": 8.0,
        "sort_cost_age2": 7.0,
        "sort_cost_age3to4": 6.0,
        "sort_cost_age2plus": 6.5,
        "sort_cost_age5plus": 5.0,
        "lad_code": 109000001,  # E09000001
    },
    {
        "provider_id": 3,
        "caretype_index": 1,
        "care_type": 1,  # school_based_nursery
        "lat": 51.6,
        "lon": -0.3,
        "bbox_lat": 51.4,
        "bbox_lon": 0.1,
        "filter_accepts_funded_hours": True,
        "filter_eligible_min_months": None,
        "filter_eligible_min_years": 3,
        "filter_eligible_max_years": 5,
        "sort_daily_open": 9.0,
        "sort_daily_close": 15.5,
        "sort_annual_opening": 38,
        "sort_ofsted": 0.90,
        "sort_graduates": 0.8,
        "sort_turnover": 0.08,
        "sort_cost_all": None,
        "sort_cost_under2": None,
        "sort_cost_age2": None,
        "sort_cost_age3to4": None,
        "sort_cost_age2plus": None,
        "sort_cost_age5plus": None,
        "lad_code": 109000001,  # E09000001
    },
    {
        "provider_id": 3,
        "caretype_index": 2,
        "care_type": 6,  # holiday_club
        "lat": 51.6,
        "lon": -0.3,
        "bbox_lat": 51.4,
        "bbox_lon": 0.1,
        "filter_accepts_funded_hours": False,
        "filter_eligible_min_months": None,
        "filter_eligible_min_years": 4,
        "filter_eligible_max_years": 12,
        "sort_daily_open": 9.0,
        "sort_daily_close": 17.0,
        "sort_annual_opening": 12,
        "sort_ofsted": 0.90,
        "sort_graduates": 0.8,
        "sort_turnover": 0.08,
        "sort_cost_all": 5.0,
        "sort_cost_under2": None,
        "sort_cost_age2": None,
        "sort_cost_age3to4": 5.0,
        "sort_cost_age2plus": 5.0,
        "sort_cost_age5plus": 5.0,
        "lad_code": 109000001,  # E09000001
    },
    # Provider 4: Unlocated provider, 1 care type (no care type)
    {
        "provider_id": 4,
        "caretype_index": 0,
        "care_type": -1,
        "lat": None,
        "lon": None,
        "bbox_lat": None,
        "bbox_lon": None,
        "filter_accepts_funded_hours": False,
        "filter_eligible_min_months": None,
        "filter_eligible_min_years": None,
        "filter_eligible_max_years": None,
        "sort_daily_open": None,
        "sort_daily_close": None,
        "sort_annual_opening": -1,
        "sort_ofsted": 0.0,
        "sort_graduates": None,
        "sort_turnover": None,
        "sort_cost_all": None,
        "sort_cost_under2": None,
        "sort_cost_age2": None,
        "sort_cost_age3to4": None,
        "sort_cost_age2plus": None,
        "sort_cost_age5plus": None,
        "lad_code": 106000023,  # E06000023
    },
    # Provider 5: Point provider in Birmingham, 2 care types
    {
        "provider_id": 5,
        "caretype_index": 0,
        "care_type": 0,  # private_nursery
        "lat": 52.4862,
        "lon": -1.8904,
        "bbox_lat": None,
        "bbox_lon": None,
        "filter_accepts_funded_hours": True,
        "filter_eligible_min_months": 0,
        "filter_eligible_min_years": 0,
        "filter_eligible_max_years": 5,
        "sort_daily_open": 7.5,
        "sort_daily_close": 17.5,
        "sort_annual_opening": 51,
        "sort_ofsted": 0.65,
        "sort_graduates": 0.4,
        "sort_turnover": 0.20,
        "sort_cost_all": 5.0,
        "sort_cost_under2": 6.5,
        "sort_cost_age2": 5.5,
        "sort_cost_age3to4": 5.0,
        "sort_cost_age2plus": 5.2,
        "sort_cost_age5plus": 4.0,
        "lad_code": 108000025,  # E08000025
    },
    {
        "provider_id": 5,
        "caretype_index": 1,
        "care_type": 3,  # breakfast_club
        "lat": 52.4862,
        "lon": -1.8904,
        "bbox_lat": None,
        "bbox_lon": None,
        "filter_accepts_funded_hours": False,
        "filter_eligible_min_months": None,
        "filter_eligible_min_years": 4,
        "filter_eligible_max_years": 11,
        "sort_daily_open": 7.5,
        "sort_daily_close": 9.0,
        "sort_annual_opening": 38,
        "sort_ofsted": 0.65,
        "sort_graduates": 0.4,
        "sort_turnover": 0.20,
        "sort_cost_all": 2.0,
        "sort_cost_under2": None,
        "sort_cost_age2": None,
        "sort_cost_age3to4": None,
        "sort_cost_age2plus": None,
        "sort_cost_age5plus": 2.0,
        "lad_code": 108000025,  # E08000025
    },
    # Provider 6: Point provider in Edinburgh (Scotland), 1 care type
    {
        "provider_id": 6,
        "caretype_index": 0,
        "care_type": 0,  # private_nursery
        "lat": 55.9533,
        "lon": -3.1883,
        "bbox_lat": None,
        "bbox_lon": None,
        "filter_accepts_funded_hours": True,
        "filter_eligible_min_months": 0,
        "filter_eligible_min_years": 0,
        "filter_eligible_max_years": 5,
        "sort_daily_open": 7.5,
        "sort_daily_close": 17.5,
        "sort_annual_opening": 50,
        "sort_ofsted": 0.0,  # No Ofsted in Scotland
        "sort_graduates": None,
        "sort_turnover": None,
        "sort_cost_all": 4.0,
        "sort_cost_under2": 5.0,
        "sort_cost_age2": 4.5,
        "sort_cost_age3to4": 4.0,
        "sort_cost_age2plus": 4.2,
        "sort_cost_age5plus": 3.5,
        "lad_code": 212000036,  # S12000036
    },
    # Provider 7: Point provider near London (Croydon), 1 care type
    {
        "provider_id": 7,
        "caretype_index": 0,
        "care_type": 2,  # childminder
        "lat": 51.3762,
        "lon": -0.0982,
        "bbox_lat": None,
        "bbox_lon": None,
        "filter_accepts_funded_hours": False,
        "filter_eligible_min_months": 0,
        "filter_eligible_min_years": 0,
        "filter_eligible_max_years": 8,
        "sort_daily_open": 7.0,
        "sort_daily_close": 17.0,
        "sort_annual_opening": 48,
        "sort_ofsted": 0.50,
        "sort_graduates": None,
        "sort_turnover": None,
        "sort_cost_all": 6.0,
        "sort_cost_under2": 7.5,
        "sort_cost_age2": 6.5,
        "sort_cost_age3to4": 6.0,
        "sort_cost_age2plus": 6.2,
        "sort_cost_age5plus": 5.0,
        "lad_code": 109000021,  # E09000021
    },
    # Provider 8: Bbox provider covering SE England (large, overlaps Provider 3)
    {
        "provider_id": 8,
        "caretype_index": 0,
        "care_type": 0,  # private_nursery
        # NW corner
        "lat": 52.0,
        "lon": -1.0,
        # SE corner
        "bbox_lat": 51.0,
        "bbox_lon": 1.0,
        "filter_accepts_funded_hours": True,
        "filter_eligible_min_months": 0,
        "filter_eligible_min_years": 0,
        "filter_eligible_max_years": 5,
        "sort_daily_open": 7.5,
        "sort_daily_close": 17.5,
        "sort_annual_opening": 50,
        "sort_ofsted": 0.70,
        "sort_graduates": None,
        "sort_turnover": None,
        "sort_cost_all": 5.5,
        "sort_cost_under2": 7.0,
        "sort_cost_age2": 6.0,
        "sort_cost_age3to4": 5.5,
        "sort_cost_age2plus": 5.8,
        "sort_cost_age5plus": 4.5,
        "lad_code": 109000001,  # E09000001
    },
    # Provider 9: Bbox provider covering the Midlands
    {
        "provider_id": 9,
        "caretype_index": 0,
        "care_type": 2,  # childminder
        # NW corner
        "lat": 53.0,
        "lon": -2.5,
        # SE corner
        "bbox_lat": 52.0,
        "bbox_lon": -1.0,
        "filter_accepts_funded_hours": False,
        "filter_eligible_min_months": 0,
        "filter_eligible_min_years": 0,
        "filter_eligible_max_years": 8,
        "sort_daily_open": 7.5,
        "sort_daily_close": 17.0,
        "sort_annual_opening": 48,
        "sort_ofsted": 0.60,
        "sort_graduates": None,
        "sort_turnover": None,
        "sort_cost_all": 4.5,
        "sort_cost_under2": 5.5,
        "sort_cost_age2": 5.0,
        "sort_cost_age3to4": 4.5,
        "sort_cost_age2plus": 4.8,
        "sort_cost_age5plus": 3.5,
        "lad_code": 108000025,  # E08000025
    },
]

# Build columnar arrays
columns = {field.name: [] for field in SCHEMA}
for row in rows:
    for field in SCHEMA:
        v = row[field.name]
        if v is None and pa.types.is_floating(field.type):
            columns[field.name].append(float("nan"))
        else:
            columns[field.name].append(v)

arrays = []
for field in SCHEMA:
    arrays.append(pa.array(columns[field.name], type=field.type))

table = pa.table(arrays, schema=SCHEMA)
out_path = "testdata/test_spatial_index.parquet"
pq.write_table(table, out_path)
print(f"Wrote {len(table)} rows to {out_path}")

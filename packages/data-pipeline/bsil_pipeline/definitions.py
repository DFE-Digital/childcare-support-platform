import os

from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    DefaultSensorStatus,
    Definitions,
    define_asset_job,
    EnvVar,
    in_process_executor,
)

from bsil_pipeline.assets.fixtures import provider_fixtures
from bsil_pipeline.assets.export import export_providers, export_spatial_index
from bsil_pipeline.assets.family_information_services import family_information_services
from bsil_pipeline.assets.ofsted_inspections import ofsted_inspections
from bsil_pipeline.assets.ofsted_school_inspections import ofsted_school_inspections
from bsil_pipeline.assets.ofsted_scraper import ofsted_scrape_results
from bsil_pipeline.assets.la_scraper import la_scrape_results
from bsil_pipeline.assets.la_extract import la_extract_results
from bsil_pipeline.assets.provider_linkage import provider_linkage
from bsil_pipeline.assets.care_offerings import care_offerings
from bsil_pipeline.assets.providers import providers
from bsil_pipeline.assets.provider_details import provider_details
from bsil_pipeline.assets.care_types import care_types
from bsil_pipeline.assets.opening_hours import opening_hours
from bsil_pipeline.assets.fee_rates import fee_rates
from bsil_pipeline.assets.ofsted_places import ofsted_places_geocode
from bsil_pipeline.assets.la_places import la_places_geocode
from bsil_pipeline.assets.bbox_lookup import bbox_lookup
from bsil_pipeline.assets.postcode_autocomplete import postcode_autocomplete
from bsil_pipeline.assets.os_bounding_boxes import os_bounding_boxes
from bsil_pipeline.assets.postcode_lookup import postcode_lookup
from bsil_pipeline.assets.la_boundaries import la_boundaries
from bsil_pipeline.assets.parquet_backup import export_all_parquet, restore_all_parquet
from bsil_pipeline.assets.schema_tables import (
    dfe_gias_schools_table,
    dfe_school_census_table,
    dfe_free_breakfast_club_schools_table,
    la_family_information_services_table,
    la_scrape_results_table,
    la_extract_results_table,
    ofsted_inspections_table,
    ofsted_school_inspections_table,
    ofsted_scrape_results_table,
    ofsted_consented_addresses_table,
    os_bounding_boxes_table,
    os_la_name_lookup_table,
    os_ofsted_places_table,
    os_la_places_table,
    ten_ds_cost_estimates_table,
    mhclg_iod_2025_table,
    tiney_childminders_table,
    posthog_events_table,
)
from bsil_pipeline.assets.posthog_events import posthog_events
from bsil_pipeline.assets.posthog_sessions import posthog_sessions
from bsil_pipeline.assets.tiney_childminders import tiney_childminders
from bsil_pipeline.assets.cost_estimates import cost_estimates
from bsil_pipeline.assets.iod_2025 import iod_2025
from bsil_pipeline.assets.export_costs import export_costs
from bsil_pipeline.assets.publish import publish_providers, clean_schemas
from bsil_pipeline.assets.spatial_index import spatial_index
from bsil_pipeline.assets.vector_tiles import vector_tiles
from bsil_pipeline.assets.validate import validate_published
from bsil_pipeline.assets.validate_exports import validate_exports
from bsil_pipeline.assets.data_version import data_version
from bsil_pipeline.assets.bristol_council_merge import bristol_council_merge
from bsil_pipeline.assets.bristol_wraparound import bristol_wraparound_matches
from bsil_pipeline.assets.school_census import school_census
from bsil_pipeline.assets.gias_schools import gias_schools
from bsil_pipeline.assets.free_breakfast_club_schools import free_breakfast_club_schools
from bsil_pipeline.assets.ofsted_consented_addresses import ofsted_consented_addresses
from bsil_pipeline.resources.postgres import BsilPostgresResource

draft_provider_data = define_asset_job(
    name="draft_provider_data",
    selection=[provider_fixtures],
)

export_app_data = define_asset_job(
    name="export_app_data",
    selection=[
        export_providers,
        export_spatial_index,
        postcode_autocomplete,
        vector_tiles,
        export_costs,
        validate_exports,
        data_version,
    ],
)

scrape_ofsted_reports = define_asset_job(
    name="scrape_ofsted_reports",
    selection=[ofsted_scrape_results],
)

scrape_la_providers = define_asset_job(
    name="scrape_la_providers",
    selection=[la_scrape_results],
    executor_def=in_process_executor,
)

export_parquet_data = define_asset_job(
    name="export_parquet_data",
    selection=[export_all_parquet],
)

restore_parquet_data = define_asset_job(
    name="restore_parquet_data",
    selection=[
        restore_all_parquet,
        dfe_gias_schools_table,
        dfe_school_census_table,
        dfe_free_breakfast_club_schools_table,
        la_family_information_services_table,
        la_scrape_results_table,
        la_extract_results_table,
        ofsted_inspections_table,
        ofsted_school_inspections_table,
        ofsted_scrape_results_table,
        ofsted_consented_addresses_table,
        os_bounding_boxes_table,
        os_la_name_lookup_table,
        os_ofsted_places_table,
        os_la_places_table,
        ten_ds_cost_estimates_table,
        mhclg_iod_2025_table,
    ],
)

extract_la_providers = define_asset_job(
    name="extract_la_providers",
    selection=[la_extract_results],
    executor_def=in_process_executor,
)

geocode_ofsted_places = define_asset_job(
    name="geocode_ofsted_places",
    selection=[ofsted_places_geocode],
    executor_def=in_process_executor,
)

geocode_la_places = define_asset_job(
    name="geocode_la_places",
    selection=[la_places_geocode],
    executor_def=in_process_executor,
)

build_draft = define_asset_job(
    name="build_draft",
    selection=[
        bristol_council_merge,
        bristol_wraparound_matches,
        provider_linkage,
        care_offerings,
        providers,
        provider_details,
        care_types,
        opening_hours,
        fee_rates,
    ],
)

publish_data = define_asset_job(
    name="publish_data",
    selection=[publish_providers, validate_published, spatial_index],
)

clean_data = define_asset_job(
    name="clean_data",
    selection=[clean_schemas],
)

pipeline_automation_sensor = AutomationConditionSensorDefinition(
    name="pipeline_automation",
    target=AssetSelection.all(),
    default_status=DefaultSensorStatus.RUNNING,
    run_tags={"CASCADE": "true", "BETA": "true", "METADATA": "false"},
)

posthog_sync = define_asset_job(
    name="posthog_sync",
    selection=[posthog_events_table, posthog_events, posthog_sessions],
)

load_source_data = define_asset_job(
    name="load_source_data",
    selection=[
        dfe_gias_schools_table,
        dfe_school_census_table,
        dfe_free_breakfast_club_schools_table,
        la_family_information_services_table,
        la_scrape_results_table,
        la_extract_results_table,
        ofsted_inspections_table,
        ofsted_school_inspections_table,
        ofsted_scrape_results_table,
        ofsted_consented_addresses_table,
        os_bounding_boxes_table,
        os_la_name_lookup_table,
        os_ofsted_places_table,
        os_la_places_table,
        ten_ds_cost_estimates_table,
        mhclg_iod_2025_table,
        ofsted_inspections,
        ofsted_school_inspections,
        ofsted_consented_addresses,
        family_information_services,
        school_census,
        gias_schools,
        free_breakfast_club_schools,
        bbox_lookup,
        os_bounding_boxes,
        postcode_lookup,
        la_boundaries,
        cost_estimates,
        iod_2025,
        tiney_childminders_table,
        tiney_childminders,
    ],
    executor_def=in_process_executor,
)

defs = Definitions(
    assets=[
        dfe_gias_schools_table,
        dfe_school_census_table,
        dfe_free_breakfast_club_schools_table,
        la_family_information_services_table,
        la_scrape_results_table,
        la_extract_results_table,
        ofsted_inspections_table,
        ofsted_school_inspections_table,
        ofsted_scrape_results_table,
        ofsted_consented_addresses_table,
        os_bounding_boxes_table,
        os_la_name_lookup_table,
        os_ofsted_places_table,
        os_la_places_table,
        provider_fixtures,
        export_providers,
        export_spatial_index,
        family_information_services,
        ofsted_inspections,
        ofsted_school_inspections,
        ofsted_scrape_results,
        ofsted_consented_addresses,
        la_scrape_results,
        la_extract_results,
        bristol_council_merge,
        bristol_wraparound_matches,
        provider_linkage,
        care_offerings,
        providers,
        provider_details,
        care_types,
        opening_hours,
        fee_rates,
        ofsted_places_geocode,
        la_places_geocode,
        bbox_lookup,
        os_bounding_boxes,
        postcode_lookup,
        la_boundaries,
        export_all_parquet,
        restore_all_parquet,
        school_census,
        gias_schools,
        free_breakfast_club_schools,
        publish_providers,
        spatial_index,
        validate_published,
        validate_exports,
        clean_schemas,
        postcode_autocomplete,
        vector_tiles,
        ten_ds_cost_estimates_table,
        mhclg_iod_2025_table,
        tiney_childminders_table,
        tiney_childminders,
        cost_estimates,
        iod_2025,
        export_costs,
        posthog_events_table,
        posthog_events,
        posthog_sessions,
        data_version,
    ],
    jobs=[
        draft_provider_data,
        export_app_data,
        load_source_data,
        scrape_ofsted_reports,
        scrape_la_providers,
        extract_la_providers,
        geocode_ofsted_places,
        geocode_la_places,
        build_draft,
        export_parquet_data,
        restore_parquet_data,
        publish_data,
        clean_data,
        posthog_sync,
    ],
    sensors=[pipeline_automation_sensor],
    resources={
        "bsil_postgres": BsilPostgresResource(
            host=EnvVar("POSTGRES_HOST"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            user=EnvVar("POSTGRES_USER"),
            password=EnvVar("POSTGRES_PASSWORD"),
            dbname=EnvVar("POSTGRES_DB"),
        ),
    },
)

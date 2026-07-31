use std::path::Path;

use spatial_index_service::config::SisConfig;
use spatial_index_service::parquet::load_parquet_to_store;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        eprintln!("Usage: sis-preprocess <parquet-path>");
        std::process::exit(1);
    }

    let parquet_path = Path::new(&args[1]);
    let config = SisConfig::from_env();

    tracing::info!(
        parquet = %parquet_path.display(),
        output = %config.filepath,
        schema = %config.schema_json_path,
        "Starting SIS preprocessing"
    );

    // 1. Load parquet and build store
    let store = load_parquet_to_store(parquet_path);
    tracing::info!(
        rows = store.len,
        providers = store.provider_first_row.len(),
        aabbs = store.aabb_min_x.len(),
        "Parquet loaded, store built"
    );

    // 2. Serialize with rkyv
    let bytes = rkyv::to_bytes::<rkyv::rancor::Error>(&store)
        .expect("Failed to serialize SIS store with rkyv");
    tracing::info!(bytes = bytes.len(), "rkyv serialization complete");

    // 3. Write .sis file
    let sis_path = Path::new(&config.filepath);
    if let Some(parent) = sis_path.parent() {
        std::fs::create_dir_all(parent).unwrap_or_else(|e| {
            panic!(
                "Failed to create directory {}: {e}",
                parent.display()
            )
        });
    }
    std::fs::write(sis_path, &bytes)
        .unwrap_or_else(|e| panic!("Failed to write SIS file {}: {e}", sis_path.display()));
    tracing::info!(path = %sis_path.display(), bytes = bytes.len(), "SIS file written");

    // 4. Write schema JSON
    let schema_json = serde_json::json!({
        "SisDataSchema": [
            ["provider_id", "int64"],
            ["care_type", "int8"],
            ["sort_distance", "float32"],
            ["sort_daily_open", "float32"],
            ["sort_daily_close", "float32"],
            ["sort_annual_opening", "int8"],
            ["sort_ofsted", "float32"],
            ["sort_graduates", "float32"],
            ["sort_turnover", "float32"],
            ["sort_cost_all", "float32"],
            ["sort_cost_under2", "float32"],
            ["sort_cost_age2", "float32"],
            ["sort_cost_age3to4", "float32"],
            ["sort_cost_age2plus", "float32"],
            ["sort_cost_age5plus", "float32"],
            ["filter_accepts_funded_hours", "uint8"],
            ["filter_eligible_min_months", "int8"],
            ["filter_eligible_min_years", "int8"],
            ["filter_eligible_max_years", "int8"],
            ["bbox_south", "float32"],
            ["bbox_west", "float32"],
            ["bbox_north", "float32"],
            ["bbox_east", "float32"],
            ["lad_code", "int32"]
        ],
        "SisBBoxInflation": config.bbox_inflation,
        "SisResultLimit": config.result_limit,
        "SisCareTypes": {
            "private_nursery": 0,
            "school_based_nursery": 1,
            "childminder": 2,
            "breakfast_club": 3,
            "free_breakfast_club": 4,
            "after_school_club": 5,
            "holiday_club": 6
        },
        "SisCareTypeBits": {
            "private_nursery": 1,
            "school_based_nursery": 2,
            "childminder": 4,
            "breakfast_club": 8,
            "free_breakfast_club": 16,
            "after_school_club": 32,
            "holiday_club": 64
        }
    });

    let schema_path = Path::new(&config.schema_json_path);
    if let Some(parent) = schema_path.parent() {
        std::fs::create_dir_all(parent).unwrap_or_else(|e| {
            panic!(
                "Failed to create directory {}: {e}",
                parent.display()
            )
        });
    }
    std::fs::write(
        schema_path,
        serde_json::to_string_pretty(&schema_json).unwrap(),
    )
    .unwrap_or_else(|e| {
        panic!(
            "Failed to write schema JSON {}: {e}",
            schema_path.display()
        )
    });
    tracing::info!(path = %schema_path.display(), "Schema JSON written");

    tracing::info!("SIS preprocessing complete");
}

use std::path::PathBuf;
use std::process::Command;
use std::sync::Arc;

fn fixture_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("testdata")
        .join("test_spatial_index.parquet")
}

fn sis_preprocess_bin() -> PathBuf {
    PathBuf::from(env!("CARGO_BIN_EXE_sis-preprocess"))
}

fn sis_query_bin() -> PathBuf {
    PathBuf::from(env!("CARGO_BIN_EXE_sis-query"))
}

/// Retry an HTTP GET until it succeeds or we exhaust attempts.
fn get_with_retry(url: &str, max_attempts: u32) -> reqwest::blocking::Response {
    let client = reqwest::blocking::Client::new();
    for attempt in 1..=max_attempts {
        match client.get(url).send() {
            Ok(resp) => return resp,
            Err(_) if attempt < max_attempts => {
                std::thread::sleep(std::time::Duration::from_millis(200));
            }
            Err(e) => panic!("HTTP request failed after {max_attempts} attempts: {e}"),
        }
    }
    unreachable!()
}

#[test]
fn end_to_end_http() {
    let tmp = std::env::temp_dir().join("sis_integration_test");
    std::fs::create_dir_all(&tmp).unwrap();
    let sis_file = tmp.join("test.sis");
    let schema_file = tmp.join("sis_schema.json");

    // 1. Run sis-preprocess
    let status = Command::new(sis_preprocess_bin())
        .arg(fixture_path())
        .env("SIS_FILEPATH", &sis_file)
        .env("SIS_SCHEMA_JSON_PATH", &schema_file)
        .env("SIS_BBOX_INFLATION", "1")
        .env("SIS_RESULT_LIMIT", "500")
        .env("RUST_LOG", "info")
        .status()
        .expect("Failed to run sis-preprocess");

    assert!(status.success(), "sis-preprocess should exit 0");
    assert!(sis_file.exists(), ".sis file should exist");
    assert!(schema_file.exists(), "schema JSON should exist");

    // Verify schema JSON
    let schema_str = std::fs::read_to_string(&schema_file).unwrap();
    let schema: serde_json::Value = serde_json::from_str(&schema_str).unwrap();
    assert!(schema["SisDataSchema"].is_array());
    assert_eq!(schema["SisDataSchema"].as_array().unwrap().len(), 24);
    assert_eq!(schema["SisBBoxInflation"], 1.0);
    assert_eq!(schema["SisResultLimit"], 500);
    assert!(schema.get("SisBBoxResultLimit").is_none(), "SisBBoxResultLimit should not be in schema");
    assert!(schema["SisCareTypes"].is_object(), "SisCareTypes should be present");
    assert_eq!(schema["SisCareTypes"]["childminder"], 2);
    assert!(schema["SisCareTypeBits"].is_object(), "SisCareTypeBits should be present");
    assert_eq!(schema["SisCareTypeBits"]["childminder"], 4);

    // 2. Start sis-query HTTP server on a test port
    let port = 13001u16;
    let mut child = Command::new(sis_query_bin())
        .env("SIS_FILEPATH", &sis_file)
        .env("SIS_API_TYPE", "http")
        .env("SIS_BBOX_INFLATION", "1")
        .env("SIS_RESULT_LIMIT", "500")
        .env("SIS_PORT", port.to_string())
        .env("RUST_LOG", "info")
        .spawn()
        .expect("Failed to start sis-query");

    // 3. Query the server (with retries for startup)
    let url = format!(
        "http://127.0.0.1:{port}/api/spatial-query\
         ?pc_south=51.0&pc_west=-1.0&pc_north=52.0&pc_east=1.0\
         &pc_lat=51.5&pc_lon=-0.05\
         &map_south=50.0&map_west=-2.0&map_north=54.0&map_east=2.0"
    );

    let resp = get_with_retry(&url, 15);

    // Kill the server regardless of result
    child.kill().ok();
    child.wait().ok();

    // Clean up temp files
    std::fs::remove_dir_all(&tmp).ok();

    assert_eq!(resp.status(), 200);

    let body = resp.bytes().unwrap();
    assert!(body.len() >= 8, "Response should have at least a header");

    // Parse header
    let magic = u32::from_le_bytes(body[0..4].try_into().unwrap());
    assert_eq!(magic, 0x53495300, "Magic should be SIS\\0");

    let row_count = u32::from_le_bytes(body[4..8].try_into().unwrap());
    assert!(row_count > 0, "Should find providers in wide viewport");

    // Verify body size matches: 8 + 74 * N
    assert_eq!(
        body.len(),
        8 + 82 * row_count as usize,
        "Body size should match 8 + 82*N"
    );
}

#[test]
fn end_to_end_http_with_care_type_filter() {
    let tmp = std::env::temp_dir().join("sis_integration_ct_test");
    std::fs::create_dir_all(&tmp).unwrap();
    let sis_file = tmp.join("test.sis");
    let schema_file = tmp.join("sis_schema.json");

    // 1. Run sis-preprocess
    let status = Command::new(sis_preprocess_bin())
        .arg(fixture_path())
        .env("SIS_FILEPATH", &sis_file)
        .env("SIS_SCHEMA_JSON_PATH", &schema_file)
        .env("SIS_BBOX_INFLATION", "1")
        .env("SIS_RESULT_LIMIT", "500")
        .env("RUST_LOG", "info")
        .status()
        .expect("Failed to run sis-preprocess");

    assert!(status.success(), "sis-preprocess should exit 0");

    // 2. Start sis-query HTTP server on a test port
    let port = 13002u16;
    let mut child = Command::new(sis_query_bin())
        .env("SIS_FILEPATH", &sis_file)
        .env("SIS_API_TYPE", "http")
        .env("SIS_BBOX_INFLATION", "1")
        .env("SIS_RESULT_LIMIT", "500")
        .env("SIS_PORT", port.to_string())
        .env("RUST_LOG", "info")
        .spawn()
        .expect("Failed to start sis-query");

    // 3. Query with ct=4 (childminder only, bit 2)
    let url = format!(
        "http://127.0.0.1:{port}/api/spatial-query\
         ?pc_south=51.0&pc_west=-1.0&pc_north=52.0&pc_east=1.0\
         &pc_lat=51.5&pc_lon=-0.05\
         &map_south=50.0&map_west=-2.0&map_north=54.0&map_east=2.0\
         &ct=4"
    );

    let resp = get_with_retry(&url, 15);

    // Kill the server regardless of result
    child.kill().ok();
    child.wait().ok();

    // Clean up temp files
    std::fs::remove_dir_all(&tmp).ok();

    assert_eq!(resp.status(), 200);

    let body = resp.bytes().unwrap();
    assert!(body.len() >= 8, "Response should have at least a header");

    let row_count = u32::from_le_bytes(body[4..8].try_into().unwrap()) as usize;

    // All returned rows should have care_type=2 (childminder)
    let care_type_offset = 8 + 8 * row_count; // after provider_id column
    for i in 0..row_count {
        let ct = body[care_type_offset + i];
        assert_eq!(ct, 2, "With ct=4, all rows should be childminder (care_type=2), got {ct} at row {i}");
    }
}

#[tokio::test]
async fn lambda_router_returns_binary_response() {
    use axum::body::Body;
    use http_body_util::BodyExt;
    use spatial_index_service::query::{build_router, SisState};
    use tower::ServiceExt;

    let tmp = std::env::temp_dir().join("sis_lambda_test");
    std::fs::create_dir_all(&tmp).unwrap();
    let sis_file = tmp.join("test.sis");

    // 1. Preprocess fixture to .sis file
    let status = Command::new(sis_preprocess_bin())
        .arg(fixture_path())
        .env("SIS_FILEPATH", &sis_file)
        .env("SIS_SCHEMA_JSON_PATH", tmp.join("sis_schema.json"))
        .env("SIS_BBOX_INFLATION", "1")
        .env("SIS_RESULT_LIMIT", "500")
        .env("RUST_LOG", "info")
        .status()
        .expect("Failed to run sis-preprocess");

    assert!(status.success(), "sis-preprocess should exit 0");

    // 2. Load state and build the shared router
    let state = Arc::new(SisState::load(sis_file.to_str().unwrap(), 1.0, 500));
    let app = build_router(state, "*");

    // 3. Call the handler via oneshot (no network, no Lambda runtime)
    let request = axum::http::Request::builder()
        .uri(
            "/api/spatial-query\
             ?pc_south=51.0&pc_west=-1.0&pc_north=52.0&pc_east=1.0\
             &pc_lat=51.5&pc_lon=-0.05\
             &map_south=50.0&map_west=-2.0&map_north=54.0&map_east=2.0",
        )
        .body(Body::empty())
        .unwrap();

    let response = app.oneshot(request).await.unwrap();

    // Clean up temp files
    std::fs::remove_dir_all(&tmp).ok();

    assert_eq!(response.status(), 200);

    let content_type = response
        .headers()
        .get("content-type")
        .unwrap()
        .to_str()
        .unwrap();
    assert_eq!(content_type, "application/octet-stream");

    let body = response.into_body().collect().await.unwrap().to_bytes();
    assert!(body.len() >= 8, "Response should have at least a header");

    let magic = u32::from_le_bytes(body[0..4].try_into().unwrap());
    assert_eq!(magic, 0x53495300, "Magic should be SIS\\0");

    let row_count = u32::from_le_bytes(body[4..8].try_into().unwrap());
    assert!(row_count > 0, "Should find providers in wide viewport");

    assert_eq!(
        body.len(),
        8 + 82 * row_count as usize,
        "Body size should match 8 + 82*N"
    );
}

#[tokio::test]
async fn lambda_router_exact_viewport() {
    use axum::body::Body;
    use http_body_util::BodyExt;
    use spatial_index_service::query::{build_router, SisState};
    use tower::ServiceExt;

    let tmp = std::env::temp_dir().join("sis_lambda_exact_test");
    std::fs::create_dir_all(&tmp).unwrap();
    let sis_file = tmp.join("test.sis");

    // 1. Preprocess fixture to .sis file
    let status = Command::new(sis_preprocess_bin())
        .arg(fixture_path())
        .env("SIS_FILEPATH", &sis_file)
        .env("SIS_SCHEMA_JSON_PATH", tmp.join("sis_schema.json"))
        .env("SIS_BBOX_INFLATION", "1")
        .env("SIS_RESULT_LIMIT", "1")
        .env("RUST_LOG", "info")
        .status()
        .expect("Failed to run sis-preprocess");

    assert!(status.success(), "sis-preprocess should exit 0");

    // 2. Load state: limit=1 triggers hit with unified index
    let state = Arc::new(SisState::load(sis_file.to_str().unwrap(), 1.0, 1));
    let app = build_router(state, "*");

    // 3. Tight viewport where R crosses V boundary → EXACT path
    let request = axum::http::Request::builder()
        .uri(
            "/api/spatial-query\
             ?pc_south=51.4&pc_west=-0.2&pc_north=51.6&pc_east=0.1\
             &pc_lat=51.5&pc_lon=-0.05\
             &map_south=51.4&map_west=-0.2&map_north=51.6&map_east=0.1",
        )
        .body(Body::empty())
        .unwrap();

    let response = app.oneshot(request).await.unwrap();

    // Clean up temp files
    std::fs::remove_dir_all(&tmp).ok();

    assert_eq!(response.status(), 200);

    let body = response.into_body().collect().await.unwrap().to_bytes();
    assert!(body.len() >= 8, "Response should have at least a header");

    let magic = u32::from_le_bytes(body[0..4].try_into().unwrap());
    assert_eq!(
        magic, 0x53495301,
        "Magic should be SIS_MAGIC_EXACT (0x53495301) when limit hit and R crosses V"
    );
}

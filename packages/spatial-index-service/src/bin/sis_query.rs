use std::sync::Arc;

use spatial_index_service::config::{ApiType, SisConfig};
use spatial_index_service::query::{build_router, SisState};

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    let config = SisConfig::from_env();

    tracing::info!(filepath = %config.filepath, "Loading SIS store");
    let state = Arc::new(SisState::load(
        &config.filepath,
        config.bbox_inflation,
        config.result_limit,
    ));

    let app = build_router(state, &config.cors_origin);

    match config.api_type {
        ApiType::Lambda => {
            lambda_http::run(app).await.expect("Lambda runtime error");
        }
        ApiType::Http => {
            let port = std::env::var("SIS_PORT").unwrap_or_else(|_| "3001".into());
            let addr = format!("0.0.0.0:{port}");
            let listener = tokio::net::TcpListener::bind(&addr)
                .await
                .unwrap_or_else(|e| panic!("Failed to bind to {addr}: {e}"));

            tracing::info!(addr = %addr, "SIS query server listening");
            axum::serve(listener, app)
                .await
                .expect("Server error");
        }
    }
}

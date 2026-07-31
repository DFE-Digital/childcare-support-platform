use std::env;

pub struct SisConfig {
    pub api_type: ApiType,
    pub bbox_inflation: f64,
    pub result_limit: usize,
    pub filepath: String,
    pub schema_json_path: String,
    pub cors_origin: String,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ApiType {
    Http,
    Lambda,
}

impl SisConfig {
    pub fn from_env() -> Self {
        let api_type = match env::var("SIS_API_TYPE").unwrap_or_else(|_| "http".into()).as_str() {
            "lambda" => ApiType::Lambda,
            _ => ApiType::Http,
        };

        let bbox_inflation: f64 = env::var("SIS_BBOX_INFLATION")
            .unwrap_or_else(|_| "1".into())
            .parse()
            .expect("SIS_BBOX_INFLATION must be a number");

        let result_limit: usize = env::var("SIS_RESULT_LIMIT")
            .unwrap_or_else(|_| "500".into())
            .parse()
            .expect("SIS_RESULT_LIMIT must be an integer");

        let filepath =
            env::var("SIS_FILEPATH").unwrap_or_else(|_| "spatial_index.sis".into());

        let schema_json_path =
            env::var("SIS_SCHEMA_JSON_PATH").unwrap_or_else(|_| "sis_schema.json".into());

        let cors_origin =
            env::var("SIS_CORS_ORIGIN").unwrap_or_else(|_| "*".into());

        Self {
            api_type,
            bbox_inflation,
            result_limit,
            filepath,
            schema_json_path,
            cors_origin,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_defaults() {
        // Clear env vars to test defaults (unsafe in edition 2024)
        unsafe {
            env::remove_var("SIS_API_TYPE");
            env::remove_var("SIS_BBOX_INFLATION");
            env::remove_var("SIS_RESULT_LIMIT");
            env::remove_var("SIS_FILEPATH");
            env::remove_var("SIS_SCHEMA_JSON_PATH");
            env::remove_var("SIS_CORS_ORIGIN");
        }

        let config = SisConfig::from_env();
        assert_eq!(config.api_type, ApiType::Http);
        assert!((config.bbox_inflation - 1.0).abs() < f64::EPSILON);
        assert_eq!(config.result_limit, 500);
        assert_eq!(config.filepath, "spatial_index.sis");
        assert_eq!(config.schema_json_path, "sis_schema.json");
        assert_eq!(config.cors_origin, "*");
    }
}

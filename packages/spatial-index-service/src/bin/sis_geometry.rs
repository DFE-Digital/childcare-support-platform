use serde::{Deserialize, Serialize};
use spatial_index_service::index::inflate_rect;
use spatial_index_service::query::{circle_rect_boundary_intersects, haversine, viewport_within_circle};

#[derive(Deserialize)]
struct Input {
    #[serde(default)]
    haversine: Vec<HaversineInput>,
    #[serde(default)]
    inflate_rect: Vec<InflateRectInput>,
    #[serde(default)]
    circle_rect_boundary_intersects: Vec<CircleRectInput>,
    #[serde(default)]
    viewport_within_circle: Vec<CircleRectInput>,
}

#[derive(Deserialize)]
struct HaversineInput {
    lat1: f64,
    lon1: f64,
    lat2: f64,
    lon2: f64,
}

#[derive(Deserialize)]
struct InflateRectInput {
    south: f64,
    west: f64,
    north: f64,
    east: f64,
    inflation: f64,
}

#[derive(Deserialize)]
struct CircleRectInput {
    c_lat: f64,
    c_lon: f64,
    radius: f32,
    south: f64,
    west: f64,
    north: f64,
    east: f64,
}

#[derive(Serialize)]
struct Output {
    haversine: Vec<f32>,
    inflate_rect: Vec<[f32; 4]>,
    circle_rect_boundary_intersects: Vec<bool>,
    viewport_within_circle: Vec<bool>,
}

fn main() {
    let input: Input = serde_json::from_reader(std::io::stdin()).expect("Invalid JSON on stdin");

    let haversine_results: Vec<f32> = input
        .haversine
        .iter()
        .map(|h| haversine(h.lat1, h.lon1, h.lat2, h.lon2))
        .collect();

    let inflate_results: Vec<[f32; 4]> = input
        .inflate_rect
        .iter()
        .map(|r| {
            let (s, w, n, e) = inflate_rect(r.south, r.west, r.north, r.east, r.inflation);
            [s, w, n, e]
        })
        .collect();

    let circle_rect_results: Vec<bool> = input
        .circle_rect_boundary_intersects
        .iter()
        .map(|cr| {
            circle_rect_boundary_intersects(
                cr.c_lat, cr.c_lon, cr.radius, cr.south, cr.west, cr.north, cr.east,
            )
        })
        .collect();

    let viewport_within_results: Vec<bool> = input
        .viewport_within_circle
        .iter()
        .map(|cr| {
            viewport_within_circle(
                cr.c_lat, cr.c_lon, cr.radius, cr.south, cr.west, cr.north, cr.east,
            )
        })
        .collect();

    let output = Output {
        haversine: haversine_results,
        inflate_rect: inflate_results,
        circle_rect_boundary_intersects: circle_rect_results,
        viewport_within_circle: viewport_within_results,
    };

    serde_json::to_writer(std::io::stdout(), &output).expect("Failed to write JSON to stdout");
}

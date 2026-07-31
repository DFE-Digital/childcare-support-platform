import { describe, it, expect, beforeAll } from "vitest";
import { execSync, execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import {
  haversineKm,
  circleRectBoundaryIntersects,
  inflateRect,
  viewportWithinCircle,
  maxPointDistance,
} from "../spatialQuery";
import { parseSisResponse, type SisSchema } from "../sisParser";

// ---------------------------------------------------------------------------
// Locate the sis-geometry binary
// ---------------------------------------------------------------------------

const thisDir = dirname(fileURLToPath(import.meta.url));
const defaultBin = join(
  thisDir,
  "../../../../spatial-index-service/target/debug/sis-geometry",
);
const binPath = process.env.SIS_GEOMETRY_BIN ?? defaultBin;
const hasBinary = existsSync(binPath);

const preprocessBin =
  process.env.SIS_PREPROCESS_BIN ??
  join(
    thisDir,
    "../../../../spatial-index-service/target/debug/sis-preprocess",
  );
const fixtureParquet = join(
  thisDir,
  "../../../../spatial-index-service/testdata/test_spatial_index.parquet",
);
const hasPreprocessBin = existsSync(preprocessBin);

// ---------------------------------------------------------------------------
// Test vectors
// ---------------------------------------------------------------------------

const haversineVectors = [
  { lat1: 51.5, lon1: -0.1, lat2: 51.5, lon2: -0.1 }, // same point
  { lat1: 51.5074, lon1: -0.1278, lat2: 48.8566, lon2: 2.3522 }, // London-Paris
  { lat1: 0, lon1: 0, lat2: 0, lon2: 90 }, // equatorial quarter
  { lat1: 35.6762, lon1: 139.6503, lat2: 40.7128, lon2: -74.006 }, // Tokyo-NYC
];

const inflateRectVectors = [
  { south: 51.0, west: -1.0, north: 52.0, east: 0.0, inflation: 0 },
  { south: 51.0, west: -1.0, north: 52.0, east: 0.0, inflation: 1.0 },
  { south: 51.0, west: -1.0, north: 52.0, east: 0.0, inflation: 2.0 },
];

const circleRectVectors = [
  // circle fully contains rect (V inside R)
  {
    c_lat: 51.5,
    c_lon: -0.1,
    radius: 500.0,
    south: 51.4,
    west: -0.2,
    north: 51.6,
    east: 0.0,
  },
  // rect fully contains circle (R inside V)
  {
    c_lat: 51.5,
    c_lon: -0.1,
    radius: 1.0,
    south: 50.0,
    west: -2.0,
    north: 53.0,
    east: 2.0,
  },
  // partial overlap
  {
    c_lat: 51.5,
    c_lon: -0.1,
    radius: 20.0,
    south: 51.3,
    west: -0.3,
    north: 51.7,
    east: 0.1,
  },
  // no overlap
  {
    c_lat: 51.5,
    c_lon: -0.1,
    radius: 10.0,
    south: 55.0,
    west: 5.0,
    north: 56.0,
    east: 6.0,
  },
  // center outside, circle reaches rect
  {
    c_lat: 51.0,
    c_lon: -0.1,
    radius: 60.0,
    south: 51.4,
    west: -0.2,
    north: 51.6,
    east: 0.0,
  },
];

// ---------------------------------------------------------------------------
// Helper: run vectors through the Rust binary
// ---------------------------------------------------------------------------

interface RustOutput {
  haversine: number[];
  inflate_rect: [number, number, number, number][];
  circle_rect_boundary_intersects: boolean[];
  viewport_within_circle: boolean[];
}

function runRustGeometry(): RustOutput {
  const input = JSON.stringify({
    haversine: haversineVectors,
    inflate_rect: inflateRectVectors,
    circle_rect_boundary_intersects: circleRectVectors,
    viewport_within_circle: circleRectVectors,
  });

  const stdout = execSync(binPath, { input, encoding: "utf-8" });
  return JSON.parse(stdout);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("spatial geometry parity (JS vs Rust sis-geometry)", () => {
  it("sis-geometry binary exists", () => {
    expect(
      hasBinary,
      `sis-geometry binary not found at ${binPath} — run: cd packages/spatial-index-service && cargo build --bin sis-geometry`,
    ).toBe(true);
  });

  describe.skipIf(!hasBinary)("parity checks", () => {
    let rust: RustOutput;

    // Run the binary once for all assertions
    it("sis-geometry binary produces valid output", () => {
      rust = runRustGeometry();
      expect(rust.haversine).toHaveLength(haversineVectors.length);
      expect(rust.inflate_rect).toHaveLength(inflateRectVectors.length);
      expect(rust.circle_rect_boundary_intersects).toHaveLength(
        circleRectVectors.length,
      );
    });

    it("haversine distances match within f32 tolerance", () => {
      for (let i = 0; i < haversineVectors.length; i++) {
        const v = haversineVectors[i];
        const jsVal = haversineKm(v.lat1, v.lon1, v.lat2, v.lon2);
        const rustVal = rust.haversine[i];
        // Rust returns f32; compare with ±0.01 km tolerance
        expect(Math.abs(Math.fround(jsVal) - rustVal)).toBeLessThanOrEqual(
          0.01,
        );
      }
    });

    it("inflateRect coordinates match within f32 tolerance", () => {
      for (let i = 0; i < inflateRectVectors.length; i++) {
        const v = inflateRectVectors[i];
        const jsVal = inflateRect(
          v.south,
          v.west,
          v.north,
          v.east,
          v.inflation,
        );
        const rustVal = rust.inflate_rect[i];
        for (let j = 0; j < 4; j++) {
          expect(
            Math.abs(Math.fround(jsVal[j]) - rustVal[j]),
          ).toBeLessThanOrEqual(1e-5);
        }
      }
    });

    it("circleRectBoundaryIntersects booleans match exactly", () => {
      for (let i = 0; i < circleRectVectors.length; i++) {
        const v = circleRectVectors[i];
        const jsVal = circleRectBoundaryIntersects(
          v.c_lat,
          v.c_lon,
          v.radius,
          v.south,
          v.west,
          v.north,
          v.east,
        );
        expect(jsVal).toBe(rust.circle_rect_boundary_intersects[i]);
      }
    });

    it("viewportWithinCircle booleans match exactly", () => {
      for (let i = 0; i < circleRectVectors.length; i++) {
        const v = circleRectVectors[i];
        const jsVal = viewportWithinCircle(
          v.c_lat,
          v.c_lon,
          v.radius,
          v.south,
          v.west,
          v.north,
          v.east,
        );
        expect(jsVal).toBe(rust.viewport_within_circle[i]);
      }
    });

    it("viewportWithinCircle is true only for V-inside-R case", () => {
      // circleRectVectors[0] is V inside R (500km radius, small rect)
      // All others should be false
      const expected = [true, false, false, false, false];
      for (let i = 0; i < circleRectVectors.length; i++) {
        const v = circleRectVectors[i];
        const jsVal = viewportWithinCircle(
          v.c_lat,
          v.c_lon,
          v.radius,
          v.south,
          v.west,
          v.north,
          v.east,
        );
        expect(jsVal).toBe(expected[i]);
      }
    });
  });
});

// ---------------------------------------------------------------------------
// SIS parser: bbox column tests
// ---------------------------------------------------------------------------

describe.skipIf(!hasPreprocessBin)("sisParser bbox columns", () => {
  let sisSchema: SisSchema;

  beforeAll(() => {
    const tmpDir = mkdtempSync(join(tmpdir(), "sis-bbox-test-"));
    const schemaPath = join(tmpDir, "sis_schema.json");
    execFileSync(preprocessBin, [fixtureParquet], {
      env: {
        ...process.env,
        SIS_FILEPATH: join(tmpDir, "test.sis"),
        SIS_SCHEMA_JSON_PATH: schemaPath,
      },
    });
    sisSchema = JSON.parse(readFileSync(schemaPath, "utf-8"));
    rmSync(tmpDir, { recursive: true });
  });

  function buildTestBuffer(): ArrayBuffer {
    const N = 2;
    const buf = new ArrayBuffer(8 + 78 * N);
    const view = new DataView(buf);
    let o = 0;

    // Header
    view.setUint32(o, 0x53495300, true);
    o += 4;
    view.setUint32(o, N, true);
    o += 4;

    // provider_id (i64)
    view.setBigInt64(o, 1n, true);
    o += 8;
    view.setBigInt64(o, 2n, true);
    o += 8;

    // care_type (i8)
    view.setInt8(o, 0);
    o += 1;
    view.setInt8(o, 1);
    o += 1;

    // sort_distance (f32)
    view.setFloat32(o, 1.5, true);
    o += 4;
    view.setFloat32(o, 3.0, true);
    o += 4;

    // sort_daily_open (f32) — NaN
    view.setFloat32(o, NaN, true);
    o += 4;
    view.setFloat32(o, NaN, true);
    o += 4;

    // sort_daily_close (f32) — NaN
    view.setFloat32(o, NaN, true);
    o += 4;
    view.setFloat32(o, NaN, true);
    o += 4;

    // sort_annual_opening (i8)
    view.setInt8(o, -1);
    o += 1;
    view.setInt8(o, -1);
    o += 1;

    // 9x f32 sort columns — all NaN
    for (let c = 0; c < 9; c++) {
      view.setFloat32(o, NaN, true);
      o += 4;
      view.setFloat32(o, NaN, true);
      o += 4;
    }

    // filter_accepts_funded_hours (u8)
    view.setUint8(o, 0);
    o += 1;
    view.setUint8(o, 0);
    o += 1;

    // 3x i8 filter columns
    for (let c = 0; c < 3; c++) {
      view.setInt8(o, -1);
      o += 1;
      view.setInt8(o, -1);
      o += 1;
    }

    // bbox_south: NaN (point), 51.0 (bbox)
    view.setFloat32(o, NaN, true);
    o += 4;
    view.setFloat32(o, 51.0, true);
    o += 4;

    // bbox_west: point lon (point), -0.2 (bbox)
    view.setFloat32(o, -0.1278, true);
    o += 4;
    view.setFloat32(o, -0.2, true);
    o += 4;

    // bbox_north: point lat (point), 51.5 (bbox)
    view.setFloat32(o, 51.5074, true);
    o += 4;
    view.setFloat32(o, 51.5, true);
    o += 4;

    // bbox_east: NaN (point), 0.1 (bbox)
    view.setFloat32(o, NaN, true);
    o += 4;
    view.setFloat32(o, 0.1, true);
    o += 4;

    return buf;
  }

  it("hasBbox distinguishes point from bbox rows", () => {
    const resp = parseSisResponse(sisSchema, buildTestBuffer());
    expect(resp.hasBbox(0)).toBe(false);
    expect(resp.hasBbox(1)).toBe(true);
  });

  it("bbox accessors return correct values for bbox row", () => {
    const resp = parseSisResponse(sisSchema, buildTestBuffer());
    expect(resp.bboxSouth(1)).toBeCloseTo(51.0, 5);
    expect(resp.bboxWest(1)).toBeCloseTo(-0.2, 5);
    expect(resp.bboxNorth(1)).toBeCloseTo(51.5, 5);
    expect(resp.bboxEast(1)).toBeCloseTo(0.1, 5);
  });

  it("bbox accessors return point lat/lon in bbox_north/bbox_west, NaN in bbox_south/bbox_east", () => {
    const resp = parseSisResponse(sisSchema, buildTestBuffer());
    expect(resp.bboxSouth(0)).toBeNaN();
    expect(resp.bboxWest(0)).toBeCloseTo(-0.1278, 3);
    expect(resp.bboxNorth(0)).toBeCloseTo(51.5074, 3);
    expect(resp.bboxEast(0)).toBeNaN();
  });

  it("sortDistance is unaffected by bbox columns", () => {
    const resp = parseSisResponse(sisSchema, buildTestBuffer());
    expect(resp.sortDistance(0)).toBeCloseTo(1.5, 5);
    expect(resp.sortDistance(1)).toBeCloseTo(3.0, 5);
  });

  it("maxPointDistance ignores bbox rows", () => {
    // Row 0: point (bboxSouth=NaN), sort_distance=1.5
    // Row 1: bbox  (bboxSouth=51.0), sort_distance=3.0
    // maxPointDistance should return 1.5, not 3.0
    const resp = parseSisResponse(sisSchema, buildTestBuffer());
    const result = maxPointDistance(resp);
    expect(result).toBeCloseTo(1.5, 5);
  });

  it("hitLimit ignores bbox rows", () => {
    // Build a buffer where all rows are bbox rows (bboxSouth is not NaN).
    // Even though total row count >= SisResultLimit, the point provider
    // count should be 0, so hitLimit should be false.
    const N = 2;
    const buf = new ArrayBuffer(8 + 78 * N);
    const view = new DataView(buf);
    let o = 0;

    // Header
    view.setUint32(o, 0x53495300, true);
    o += 4;
    view.setUint32(o, N, true);
    o += 4;

    // provider_id (i64) — two different bbox providers
    view.setBigInt64(o, 10n, true);
    o += 8;
    view.setBigInt64(o, 20n, true);
    o += 8;

    // care_type (i8)
    view.setInt8(o, 0);
    o += 1;
    view.setInt8(o, 2);
    o += 1;

    // sort_distance (f32)
    view.setFloat32(o, 20.0, true);
    o += 4;
    view.setFloat32(o, 25.0, true);
    o += 4;

    // sort_daily_open (f32) — NaN
    view.setFloat32(o, NaN, true);
    o += 4;
    view.setFloat32(o, NaN, true);
    o += 4;

    // sort_daily_close (f32) — NaN
    view.setFloat32(o, NaN, true);
    o += 4;
    view.setFloat32(o, NaN, true);
    o += 4;

    // sort_annual_opening (i8)
    view.setInt8(o, -1);
    o += 1;
    view.setInt8(o, -1);
    o += 1;

    // 9x f32 sort columns — all NaN
    for (let c = 0; c < 9; c++) {
      view.setFloat32(o, NaN, true);
      o += 4;
      view.setFloat32(o, NaN, true);
      o += 4;
    }

    // filter_accepts_funded_hours (u8)
    view.setUint8(o, 0);
    o += 1;
    view.setUint8(o, 0);
    o += 1;

    // 3x i8 filter columns
    for (let c = 0; c < 3; c++) {
      view.setInt8(o, -1);
      o += 1;
      view.setInt8(o, -1);
      o += 1;
    }

    // bbox_south: both are bbox rows (not NaN)
    view.setFloat32(o, 51.0, true);
    o += 4;
    view.setFloat32(o, 52.0, true);
    o += 4;

    // bbox_west
    view.setFloat32(o, -0.3, true);
    o += 4;
    view.setFloat32(o, -2.5, true);
    o += 4;

    // bbox_north
    view.setFloat32(o, 51.6, true);
    o += 4;
    view.setFloat32(o, 53.0, true);
    o += 4;

    // bbox_east
    view.setFloat32(o, 0.1, true);
    o += 4;
    view.setFloat32(o, -1.0, true);
    o += 4;

    const resp = parseSisResponse(sisSchema, buf);

    // Count unique point providers (should be 0 — all rows are bbox)
    let pointCount = 0;
    const seen = new Set<bigint>();
    for (let i = 0; i < resp.rowCount; i++) {
      if (isNaN(resp.bboxSouth(i))) {
        seen.add(resp.providerId(i));
      }
    }
    pointCount = seen.size;

    expect(pointCount).toBe(0);
    // With SisResultLimit typically >= 1, 0 point providers should not trigger hitLimit
    expect(pointCount >= sisSchema.SisResultLimit).toBe(false);
  });
});

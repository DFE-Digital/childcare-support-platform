import { describe, it, expect } from "vitest";
import { capBboxByPointDistance, computeMissingBboxCount } from "../bboxCap";
import type {
  BBox,
  ProviderPoint,
  ProviderSearchEntry,
} from "@/lib/filterSortDedup";

function entry(id: string, miles: number, ladCode = 0): ProviderSearchEntry {
  return { providerId: id, distanceMiles: miles, ladCode };
}

describe("capBboxByPointDistance", () => {
  it("returns all point providers unchanged when no bbox providers", () => {
    const viewportIds = ["p1", "p2"];
    const entries = [entry("p1", 1), entry("p2", 3)];
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.0, lon: -0.1 }],
      ["p2", { lat: 51.1, lon: 0.0 }],
    ]);
    const bboxMap = new Map<string, BBox>();
    const result = capBboxByPointDistance(
      viewportIds,
      entries,
      pointMap,
      bboxMap,
    );
    expect(result).toEqual(["p1", "p2"]);
  });

  it("includes bbox provider within max point distance", () => {
    const viewportIds = ["p1", "b1"];
    const entries = [entry("p1", 5), entry("b1", 3)];
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.0, lon: 0.0 }],
    ]);
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
    ]);
    const result = capBboxByPointDistance(
      viewportIds,
      entries,
      pointMap,
      bboxMap,
    );
    expect(result).toEqual(["p1", "b1"]);
  });

  it("excludes bbox provider beyond max point distance", () => {
    const viewportIds = ["p1", "b1"];
    const entries = [entry("p1", 2), entry("b1", 10)];
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.0, lon: 0.0 }],
    ]);
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
    ]);
    const result = capBboxByPointDistance(
      viewportIds,
      entries,
      pointMap,
      bboxMap,
    );
    expect(result).toEqual(["p1"]);
  });

  it("excludes all bbox providers when no point providers in viewport", () => {
    const viewportIds = ["b1", "b2"];
    const entries = [entry("b1", 5), entry("b2", 10)];
    const pointMap = new Map<string, ProviderPoint>();
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
      ["b2", { south: 50.0, west: -2.0, north: 53.0, east: 1.0 }],
    ]);
    const result = capBboxByPointDistance(
      viewportIds,
      entries,
      pointMap,
      bboxMap,
    );
    expect(result).toEqual([]);
  });

  it("uses farthest point provider for the cap", () => {
    const viewportIds = ["p1", "p2", "b1", "b2"];
    const entries = [
      entry("p1", 2),
      entry("p2", 8),
      entry("b1", 5),
      entry("b2", 12),
    ];
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.0, lon: 0.0 }],
      ["p2", { lat: 51.5, lon: 0.1 }],
    ]);
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
      ["b2", { south: 50.0, west: -2.0, north: 53.0, east: 1.0 }],
    ]);
    const result = capBboxByPointDistance(
      viewportIds,
      entries,
      pointMap,
      bboxMap,
    );
    // maxPointDistance = 8, b1 (dist=5) included, b2 (dist=12) excluded
    expect(result).toEqual(["p1", "p2", "b1"]);
  });

  it("includes bbox at exactly the cap distance", () => {
    const viewportIds = ["p1", "b1"];
    const entries = [entry("p1", 5), entry("b1", 5)];
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.0, lon: 0.0 }],
    ]);
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
    ]);
    const result = capBboxByPointDistance(
      viewportIds,
      entries,
      pointMap,
      bboxMap,
    );
    expect(result).toEqual(["p1", "b1"]);
  });

  it("preserves unlocated providers (neither point nor bbox)", () => {
    const viewportIds = ["p1", "u1", "b1"];
    const entries = [entry("p1", 2), entry("u1", 3), entry("b1", 10)];
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.0, lon: 0.0 }],
    ]);
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
    ]);
    // u1 is not in pointMap or bboxMap — it passes through
    const result = capBboxByPointDistance(
      viewportIds,
      entries,
      pointMap,
      bboxMap,
    );
    expect(result).toEqual(["p1", "u1"]);
  });

  it("handles empty viewport", () => {
    const result = capBboxByPointDistance([], [], new Map(), new Map());
    expect(result).toEqual([]);
  });

  it("includes bbox beyond cap if fully contained in mapBounds", () => {
    const viewportIds = ["p1", "b1"];
    const entries = [entry("p1", 2), entry("b1", 10)];
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.0, lon: 0.0 }],
    ]);
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.1, west: -0.5, north: 51.3, east: 0.2 }],
    ]);
    const mapBounds: [number, number, number, number] = [50.0, -1.0, 52.0, 1.0];
    const result = capBboxByPointDistance(
      viewportIds,
      entries,
      pointMap,
      bboxMap,
      mapBounds,
    );
    expect(result).toEqual(["p1", "b1"]);
  });

  it("excludes bbox beyond cap if NOT fully contained in mapBounds", () => {
    const viewportIds = ["p1", "b1"];
    const entries = [entry("p1", 2), entry("b1", 10)];
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.0, lon: 0.0 }],
    ]);
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 49.0, west: -0.5, north: 51.3, east: 0.2 }],
    ]);
    const mapBounds: [number, number, number, number] = [50.0, -1.0, 52.0, 1.0];
    const result = capBboxByPointDistance(
      viewportIds,
      entries,
      pointMap,
      bboxMap,
      mapBounds,
    );
    expect(result).toEqual(["p1"]);
  });

  it("excludes bbox beyond cap if one edge exceeds mapBounds", () => {
    const viewportIds = ["p1", "b1"];
    const entries = [entry("p1", 2), entry("b1", 10)];
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.0, lon: 0.0 }],
    ]);
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.0, west: -0.5, north: 52.5, east: 0.2 }],
    ]);
    const mapBounds: [number, number, number, number] = [50.0, -1.0, 52.0, 1.0];
    const result = capBboxByPointDistance(
      viewportIds,
      entries,
      pointMap,
      bboxMap,
      mapBounds,
    );
    expect(result).toEqual(["p1"]);
  });

  it("falls back to distance-only when mapBounds not provided", () => {
    const viewportIds = ["p1", "b1"];
    const entries = [entry("p1", 2), entry("b1", 10)];
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.0, lon: 0.0 }],
    ]);
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.1, west: -0.5, north: 51.3, east: 0.2 }],
    ]);
    const result = capBboxByPointDistance(
      viewportIds,
      entries,
      pointMap,
      bboxMap,
    );
    expect(result).toEqual(["p1"]);
  });
});

describe("computeMissingBboxCount", () => {
  const LAD_BANES = 106000022;

  it("returns totalBboxOnly when no bbox from LA in capped viewport", () => {
    const capped = ["p1", "p2"];
    const entries = [entry("p1", 1, LAD_BANES), entry("p2", 2, LAD_BANES)];
    const bboxMap = new Map<string, BBox>();
    const stats = {
      childminder: { total: 77, bboxOnly: 48, insufficient: 38 },
    };
    const result = computeMissingBboxCount(
      capped,
      entries,
      bboxMap,
      LAD_BANES,
      stats,
      ["childminder"],
    );
    expect(result).toBe(48);
  });

  it("subtracts bbox providers from LA that are in capped viewport", () => {
    const capped = ["p1", "b1", "b2"];
    const entries = [
      entry("p1", 1, LAD_BANES),
      entry("b1", 2, LAD_BANES),
      entry("b2", 3, LAD_BANES),
    ];
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
      ["b2", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
    ]);
    const stats = {
      childminder: { total: 77, bboxOnly: 48, insufficient: 38 },
    };
    const result = computeMissingBboxCount(
      capped,
      entries,
      bboxMap,
      LAD_BANES,
      stats,
      ["childminder"],
    );
    expect(result).toBe(46);
  });

  it("only counts bbox providers matching the searched LA", () => {
    const LAD_BRISTOL = 106000023;
    const capped = ["b1", "b2"];
    const entries = [entry("b1", 2, LAD_BANES), entry("b2", 3, LAD_BRISTOL)];
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
      ["b2", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
    ]);
    const stats = {
      childminder: { total: 77, bboxOnly: 48, insufficient: 38 },
    };
    // Searching BANES — b1 matches, b2 doesn't
    const result = computeMissingBboxCount(
      capped,
      entries,
      bboxMap,
      LAD_BANES,
      stats,
      ["childminder"],
    );
    expect(result).toBe(47);
  });

  it("filters by selectedTypes when provided", () => {
    const capped: string[] = [];
    const entries: ProviderSearchEntry[] = [];
    const bboxMap = new Map<string, BBox>();
    const stats = {
      childminder: { total: 77, bboxOnly: 48, insufficient: 0 },
      private_nursery: { total: 50, bboxOnly: 10, insufficient: 0 },
    };
    const result = computeMissingBboxCount(
      capped,
      entries,
      bboxMap,
      LAD_BANES,
      stats,
      ["childminder"],
    );
    expect(result).toBe(48);
  });

  it("uses all types when selectedTypes is empty", () => {
    const capped: string[] = [];
    const entries: ProviderSearchEntry[] = [];
    const bboxMap = new Map<string, BBox>();
    const stats = {
      childminder: { total: 77, bboxOnly: 48, insufficient: 0 },
      private_nursery: { total: 50, bboxOnly: 10, insufficient: 0 },
    };
    const result = computeMissingBboxCount(
      capped,
      entries,
      bboxMap,
      LAD_BANES,
      stats,
      [],
    );
    expect(result).toBe(58);
  });

  it("returns 0 when providerStats has no bboxOnly", () => {
    const capped: string[] = [];
    const entries: ProviderSearchEntry[] = [];
    const bboxMap = new Map<string, BBox>();
    const stats = {
      childminder: { total: 77, bboxOnly: 0, insufficient: 0 },
    };
    const result = computeMissingBboxCount(
      capped,
      entries,
      bboxMap,
      LAD_BANES,
      stats,
      [],
    );
    expect(result).toBe(0);
  });

  it("never returns negative", () => {
    const capped = ["b1", "b2", "b3"];
    const entries = [
      entry("b1", 1, LAD_BANES),
      entry("b2", 2, LAD_BANES),
      entry("b3", 3, LAD_BANES),
    ];
    const bboxMap = new Map<string, BBox>([
      ["b1", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
      ["b2", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
      ["b3", { south: 51.0, west: -1.0, north: 52.0, east: 0.0 }],
    ]);
    // bboxOnly=2 but 3 are in viewport — shouldn't go negative
    const stats = { childminder: { total: 10, bboxOnly: 2, insufficient: 0 } };
    const result = computeMissingBboxCount(
      capped,
      entries,
      bboxMap,
      LAD_BANES,
      stats,
      ["childminder"],
    );
    expect(result).toBe(0);
  });
});

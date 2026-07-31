import { describe, it, expect } from "vitest";
import { filterProviderIdsInViewport } from "../viewportFilter";
import type { BBox, ProviderPoint } from "@/lib/filterSortDedup";

// Viewport: south=51.0, west=-0.5, north=51.5, east=0.5
const bounds: [number, number, number, number] = [51.0, -0.5, 51.5, 0.5];

describe("filterProviderIdsInViewport", () => {
  it("includes a point provider inside viewport", () => {
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.25, lon: 0.0 }],
    ]);
    const result = filterProviderIdsInViewport(
      ["p1"],
      bounds,
      new Map(),
      pointMap,
    );
    expect(result).toEqual(["p1"]);
  });

  it("excludes a point provider outside viewport", () => {
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 52.0, lon: 0.0 }],
    ]);
    const result = filterProviderIdsInViewport(
      ["p1"],
      bounds,
      new Map(),
      pointMap,
    );
    expect(result).toEqual([]);
  });

  it("includes a bbox provider that overlaps viewport", () => {
    // Provider bbox: south=51.0, west=-0.5, north=52.0, east=0.5
    // Overlaps viewport — included
    const bboxMap = new Map<string, BBox>([
      ["p1", { south: 51.0, west: -0.5, north: 52.0, east: 0.5 }],
    ]);
    const result = filterProviderIdsInViewport(
      ["p1"],
      bounds,
      bboxMap,
      new Map(),
    );
    expect(result).toEqual(["p1"]);
  });

  it("includes a bbox provider with small overlap", () => {
    // Provider bbox: south=51.4, west=-0.5, north=56.4, east=0.5
    // Only a sliver intersects the viewport, but any intersection counts
    const bboxMap = new Map<string, BBox>([
      ["p1", { south: 51.4, west: -0.5, north: 56.4, east: 0.5 }],
    ]);
    const result = filterProviderIdsInViewport(
      ["p1"],
      bounds,
      bboxMap,
      new Map(),
    );
    expect(result).toEqual(["p1"]);
  });

  it("excludes a bbox provider completely outside viewport", () => {
    const bboxMap = new Map<string, BBox>([
      ["p1", { south: 54.0, west: -0.5, north: 56.0, east: 0.5 }],
    ]);
    const result = filterProviderIdsInViewport(
      ["p1"],
      bounds,
      bboxMap,
      new Map(),
    );
    expect(result).toEqual([]);
  });

  it("handles mixed point and bbox providers", () => {
    const pointMap = new Map<string, ProviderPoint>([
      ["p1", { lat: 51.25, lon: 0.0 }],
      ["p2", { lat: 52.0, lon: 0.0 }],
    ]);
    const bboxMap = new Map<string, BBox>([
      ["p3", { south: 51.0, west: -0.5, north: 52.0, east: 0.5 }],
    ]);
    const result = filterProviderIdsInViewport(
      ["p1", "p2", "p3"],
      bounds,
      bboxMap,
      pointMap,
    );
    expect(result).toEqual(["p1", "p3"]);
  });

  it("excludes unlocated providers (no entry in either map)", () => {
    const result = filterProviderIdsInViewport(
      ["p1"],
      bounds,
      new Map(),
      new Map(),
    );
    expect(result).toEqual([]);
  });
});

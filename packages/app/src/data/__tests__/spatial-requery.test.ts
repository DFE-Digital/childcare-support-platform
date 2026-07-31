import { describe, it, expect, beforeEach } from "vitest";
import {
  needsRequery,
  clearCache,
  _setCacheForTest,
  inflateRect,
} from "../spatialQuery";
const schema = {
  SisBBoxInflation: 1.0,
};

const pcBbox: [number, number, number, number] = [-0.2, 51.4, 0.1, 51.6];
const pcCentroid: [number, number] = [-0.05, 51.5]; // [lon, lat]
const viewport: [number, number, number, number] = [51.4, -0.2, 51.6, 0.1]; // [south, west, north, east]

function makeInflatedRect(
  vp: [number, number, number, number],
): [number, number, number, number] {
  return inflateRect(vp[0], vp[1], vp[2], vp[3], schema.SisBBoxInflation);
}

describe("needsRequery", () => {
  beforeEach(() => {
    clearCache();
  });

  it("1: returns true when cache is empty", () => {
    expect(needsRequery(pcBbox, pcCentroid, viewport)).toBe(true);
  });

  it("2: returns true when postcode bbox changed", () => {
    _setCacheForTest({
      postcodeBbox: pcBbox,
      postcodeCentroid: pcCentroid,
      inflatedRect: makeInflatedRect(viewport),
      mapViewport: viewport,
      inflated: true,
      hitLimit: false,
      radiusKm: 0,
      careTypeMask: 0,
    });
    const newPcBbox: [number, number, number, number] = [-0.3, 51.3, 0.2, 51.7];
    expect(needsRequery(newPcBbox, pcCentroid, viewport)).toBe(true);
  });

  it("3: returns true when postcode centroid changed", () => {
    _setCacheForTest({
      postcodeBbox: pcBbox,
      postcodeCentroid: pcCentroid,
      inflatedRect: makeInflatedRect(viewport),
      mapViewport: viewport,
      inflated: true,
      hitLimit: false,
      radiusKm: 0,
      careTypeMask: 0,
    });
    const newCentroid: [number, number] = [0.0, 52.0];
    expect(needsRequery(pcBbox, newCentroid, viewport)).toBe(true);
  });

  it("4: non-inflated cache, same viewport → false", () => {
    _setCacheForTest({
      postcodeBbox: pcBbox,
      postcodeCentroid: pcCentroid,
      inflatedRect: makeInflatedRect(viewport),
      mapViewport: viewport,
      inflated: false,
      hitLimit: false,
      radiusKm: 0,
      careTypeMask: 0,
    });
    expect(needsRequery(pcBbox, pcCentroid, viewport)).toBe(false);
  });

  it("5: non-inflated cache, different viewport → true", () => {
    _setCacheForTest({
      postcodeBbox: pcBbox,
      postcodeCentroid: pcCentroid,
      inflatedRect: makeInflatedRect(viewport),
      mapViewport: viewport,
      inflated: false,
      hitLimit: false,
      radiusKm: 0,
      careTypeMask: 0,
    });
    const newVp: [number, number, number, number] = [51.3, -0.3, 51.7, 0.2];
    expect(needsRequery(pcBbox, pcCentroid, newVp)).toBe(true);
  });

  it("6: inflated cache, V still within I, no limit → false", () => {
    _setCacheForTest({
      postcodeBbox: pcBbox,
      postcodeCentroid: pcCentroid,
      inflatedRect: makeInflatedRect(viewport),
      mapViewport: viewport,
      inflated: true,
      hitLimit: false,
      radiusKm: 0,
      careTypeMask: 0,
    });
    // Slightly smaller viewport — still within inflated rect
    const smallVp: [number, number, number, number] = [
      51.42, -0.18, 51.58, 0.08,
    ];
    expect(needsRequery(pcBbox, pcCentroid, smallVp)).toBe(false);
  });

  it("7: inflated cache, V left I → true", () => {
    _setCacheForTest({
      postcodeBbox: pcBbox,
      postcodeCentroid: pcCentroid,
      inflatedRect: makeInflatedRect(viewport),
      mapViewport: viewport,
      inflated: true,
      hitLimit: false,
      radiusKm: 0,
      careTypeMask: 0,
    });
    // Viewport way outside the inflated rect
    const farVp: [number, number, number, number] = [55.0, 5.0, 56.0, 6.0];
    expect(needsRequery(pcBbox, pcCentroid, farVp)).toBe(true);
  });

  it("8: inflated, limit hit, V within R → false", () => {
    // R = 500 km, V is tiny near the centroid → V ⊆ R
    _setCacheForTest({
      postcodeBbox: pcBbox,
      postcodeCentroid: pcCentroid,
      inflatedRect: makeInflatedRect(viewport),
      mapViewport: viewport,
      inflated: true,
      hitLimit: true,
      radiusKm: 500,
      careTypeMask: 0,
    });
    // Small viewport near centroid — well within R and within I
    const smallVp: [number, number, number, number] = [51.45, -0.1, 51.55, 0.0];
    expect(needsRequery(pcBbox, pcCentroid, smallVp)).toBe(false);
  });

  it("9: inflated, limit hit, V partially overlaps R (not within) → true", () => {
    // R = 14 km from centroid [lon=-0.05, lat=51.5]
    // Viewport extends well beyond R in some directions
    _setCacheForTest({
      postcodeBbox: pcBbox,
      postcodeCentroid: pcCentroid,
      inflatedRect: makeInflatedRect(viewport),
      mapViewport: viewport,
      inflated: true,
      hitLimit: true,
      radiusKm: 14,
      careTypeMask: 0,
    });
    // Viewport with corners outside 14 km but still within inflated rect
    const bigVp: [number, number, number, number] = [51.3, -0.15, 51.7, 0.05];
    expect(needsRequery(pcBbox, pcCentroid, bigVp)).toBe(true);
  });

  it("10: inflated, limit hit, V disjoint from R (pan-away regression) → true", () => {
    // R = 14 km from centroid [lon=-0.05, lat=51.5] near London
    // V is in Scotland — completely outside R
    // This is the exact topology of the original pan-away-from-postcode bug
    _setCacheForTest({
      postcodeBbox: pcBbox,
      postcodeCentroid: pcCentroid,
      inflatedRect: [-10, -20, 60, 20], // huge inflated rect that contains Scotland
      mapViewport: viewport,
      inflated: true,
      hitLimit: true,
      radiusKm: 14,
      careTypeMask: 0,
    });
    const scotlandVp: [number, number, number, number] = [55.0, 5.0, 56.0, 6.0];
    expect(needsRequery(pcBbox, pcCentroid, scotlandVp)).toBe(true);
  });
});

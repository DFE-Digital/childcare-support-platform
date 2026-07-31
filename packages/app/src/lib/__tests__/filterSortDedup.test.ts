import { describe, it, expect } from "vitest";
import { filterSortDedup } from "../filterSortDedup";
import type { SisResponse } from "@/data/sisParser";

/** Build a mock SisResponse backed by plain arrays.
 *
 * The `bbox` field models a true bbox provider (hasBbox=true, all 4 coords).
 * The `point` field models a point provider: bbox_north=lat, bbox_west=lon,
 * bbox_south=NaN, bbox_east=NaN (hasBbox=false).
 * Omitting both models an unlocated provider (all NaN).
 */
function mockSis(
  rows: {
    providerId: bigint;
    distance: number;
    fundedHours: boolean;
    minMonths: number;
    minYears: number;
    maxYears: number;
    costAll?: number;
    graduates?: number;
    turnover?: number;
    dailyOpen?: number;
    dailyClose?: number;
    annualOpening?: number;
    ofsted?: number;
    bbox?: { south: number; west: number; north: number; east: number };
    point?: { lat: number; lon: number };
  }[],
): SisResponse {
  return {
    rowCount: rows.length,
    columns: [],
    buffer: new ArrayBuffer(0),
    inflated: true,
    providerId: (r) => rows[r].providerId,
    careType: () => 0,
    sortDistance: (r) => rows[r].distance,
    sortDailyOpen: (r) => rows[r].dailyOpen ?? NaN,
    sortDailyClose: (r) => rows[r].dailyClose ?? NaN,
    sortAnnualOpening: (r) => rows[r].annualOpening ?? NaN,
    sortOfsted: (r) => rows[r].ofsted ?? NaN,
    sortGraduates: (r) => rows[r].graduates ?? NaN,
    sortTurnover: (r) => rows[r].turnover ?? NaN,
    sortCostAll: (r) => rows[r].costAll ?? NaN,
    sortCostUnder2: () => NaN,
    sortCostAge2: () => NaN,
    sortCostAge3to4: () => NaN,
    sortCostAge2plus: () => NaN,
    sortCostAge5plus: () => NaN,
    filterAcceptsFundedHours: (r) => rows[r].fundedHours,
    filterEligibleMinMonths: (r) => rows[r].minMonths,
    filterEligibleMinYears: (r) => rows[r].minYears,
    filterEligibleMaxYears: (r) => rows[r].maxYears,
    hasBbox: (r) => !!rows[r].bbox,
    bboxSouth: (r) => rows[r].bbox?.south ?? NaN,
    bboxWest: (r) => rows[r].bbox?.west ?? rows[r].point?.lon ?? NaN,
    bboxNorth: (r) => rows[r].bbox?.north ?? rows[r].point?.lat ?? NaN,
    bboxEast: (r) => rows[r].bbox?.east ?? NaN,
    ladCode: () => 0,
  };
}

describe("filterSortDedup", () => {
  it("returns all rows sorted by distance ascending with no filters", () => {
    const sis = mockSis([
      {
        providerId: 1n,
        distance: 5,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
      },
      {
        providerId: 2n,
        distance: 2,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
      },
      {
        providerId: 3n,
        distance: 8,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
      },
    ]);
    const { entries } = filterSortDedup(sis, [], false, "distance");
    expect(entries.map((e) => e.providerId)).toEqual(["p2", "p1", "p3"]);
  });

  it("filters to only funded hours providers", () => {
    const sis = mockSis([
      {
        providerId: 1n,
        distance: 1,
        fundedHours: true,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
      },
      {
        providerId: 2n,
        distance: 2,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
      },
      {
        providerId: 3n,
        distance: 3,
        fundedHours: true,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
      },
    ]);
    const { entries } = filterSortDedup(sis, [], true, "distance");
    expect(entries.map((e) => e.providerId)).toEqual(["p1", "p3"]);
  });

  it("filters by child age eligibility", () => {
    const sis = mockSis([
      // Accepts 0-35 months (minMonths=0, maxYears=2 → hi = 35)
      {
        providerId: 1n,
        distance: 1,
        fundedHours: false,
        minMonths: 0,
        minYears: -1,
        maxYears: 2,
      },
      // Accepts 36-59 months (minYears=3 → lo=36, maxYears=4 → hi=59)
      {
        providerId: 2n,
        distance: 2,
        fundedHours: false,
        minMonths: -1,
        minYears: 3,
        maxYears: 4,
      },
      // Accepts all ages (no bounds set)
      {
        providerId: 3n,
        distance: 3,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
      },
    ]);
    // Child is 24 months old
    const { entries } = filterSortDedup(sis, [24], false, "distance");
    // Provider 1 (0-35) matches, provider 2 (36-59) doesn't, provider 3 (0-999) matches
    expect(entries.map((e) => e.providerId)).toEqual(["p1", "p3"]);
  });

  it("deduplicates by provider_id keeping first (best sort)", () => {
    const sis = mockSis([
      {
        providerId: 1n,
        distance: 2,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
      },
      {
        providerId: 1n,
        distance: 5,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
      },
      {
        providerId: 2n,
        distance: 3,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
      },
    ]);
    const { entries } = filterSortDedup(sis, [], false, "distance");
    expect(entries.map((e) => e.providerId)).toEqual(["p1", "p2"]);
    // Distance should be from the first (closest) row
    expect(entries[0].distanceMiles).toBeCloseTo(2 * 0.621371, 4);
  });

  it("sorts by lowest_cost ascending with NaN at bottom", () => {
    const sis = mockSis([
      {
        providerId: 1n,
        distance: 1,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        costAll: 10,
      },
      {
        providerId: 2n,
        distance: 2,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        costAll: NaN,
      },
      {
        providerId: 3n,
        distance: 3,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        costAll: 5,
      },
    ]);
    const { entries } = filterSortDedup(sis, [], false, "lowest_cost");
    expect(entries.map((e) => e.providerId)).toEqual(["p3", "p1", "p2"]);
  });

  it("sorts by most_graduate descending with NaN at bottom", () => {
    const sis = mockSis([
      {
        providerId: 1n,
        distance: 1,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        graduates: 50,
      },
      {
        providerId: 2n,
        distance: 2,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        graduates: 80,
      },
      {
        providerId: 3n,
        distance: 3,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        graduates: NaN,
      },
    ]);
    const { entries } = filterSortDedup(sis, [], false, "most_graduate");
    expect(entries.map((e) => e.providerId)).toEqual(["p2", "p1", "p3"]);
  });

  it("populates bboxMap for rows with bbox data", () => {
    const bbox = { south: 51.0, west: -0.5, north: 51.5, east: 0.0 };
    const sis = mockSis([
      {
        providerId: 1n,
        distance: 1,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        bbox,
      },
      {
        providerId: 2n,
        distance: 2,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
      },
    ]);
    const { bboxMap } = filterSortDedup(sis, [], false, "distance");
    expect(bboxMap.get("p1")).toEqual(bbox);
    expect(bboxMap.has("p2")).toBe(false);
  });

  it("populates pointMap for point providers", () => {
    const sis = mockSis([
      {
        providerId: 1n,
        distance: 1,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        point: { lat: 51.5, lon: -0.1 },
      },
      {
        providerId: 2n,
        distance: 2,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        point: { lat: 52.0, lon: 0.3 },
      },
    ]);
    const { pointMap, bboxMap } = filterSortDedup(sis, [], false, "distance");
    expect(pointMap.get("p1")).toEqual({ lat: 51.5, lon: -0.1 });
    expect(pointMap.get("p2")).toEqual({ lat: 52.0, lon: 0.3 });
    expect(bboxMap.size).toBe(0);
  });

  it("excludes unlocated providers from both pointMap and bboxMap", () => {
    const sis = mockSis([
      {
        providerId: 1n,
        distance: 1,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        // no bbox, no point → unlocated
      },
    ]);
    const { pointMap, bboxMap } = filterSortDedup(sis, [], false, "distance");
    expect(pointMap.size).toBe(0);
    expect(bboxMap.size).toBe(0);
  });

  it("separates point and bbox providers into correct maps", () => {
    const sis = mockSis([
      {
        providerId: 1n,
        distance: 1,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        point: { lat: 51.5, lon: -0.1 },
      },
      {
        providerId: 2n,
        distance: 2,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        bbox: { south: 51.0, west: -0.5, north: 52.0, east: 0.5 },
      },
      {
        providerId: 3n,
        distance: 3,
        fundedHours: false,
        minMonths: -1,
        minYears: -1,
        maxYears: -1,
        // unlocated
      },
    ]);
    const { pointMap, bboxMap } = filterSortDedup(sis, [], false, "distance");
    expect(pointMap.has("p1")).toBe(true);
    expect(bboxMap.has("p1")).toBe(false);
    expect(bboxMap.has("p2")).toBe(true);
    expect(pointMap.has("p2")).toBe(false);
    expect(pointMap.has("p3")).toBe(false);
    expect(bboxMap.has("p3")).toBe(false);
  });
});

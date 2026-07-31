import { describe, it, expect } from "vitest";
import { distanceBand, childAgeBands } from "../providerAnalytics";

describe("distanceBand", () => {
  it("returns unknown for undefined", () => {
    expect(distanceBand(undefined)).toBe("unknown");
  });

  it("returns <1mi for 0", () => {
    expect(distanceBand(0)).toBe("<1mi");
  });

  it("returns <1mi for 0.99", () => {
    expect(distanceBand(0.99)).toBe("<1mi");
  });

  it("returns 1-3mi for 1", () => {
    expect(distanceBand(1)).toBe("1-3mi");
  });

  it("returns 1-3mi for 2.9", () => {
    expect(distanceBand(2.9)).toBe("1-3mi");
  });

  it("returns 3-5mi for 3", () => {
    expect(distanceBand(3)).toBe("3-5mi");
  });

  it("returns 5-10mi for 5", () => {
    expect(distanceBand(5)).toBe("5-10mi");
  });

  it("returns 10+mi for 10", () => {
    expect(distanceBand(10)).toBe("10+mi");
  });

  it("returns 10+mi for 100", () => {
    expect(distanceBand(100)).toBe("10+mi");
  });
});

describe("childAgeBands", () => {
  it("returns empty for empty input", () => {
    expect(childAgeBands([])).toEqual([]);
  });

  it("returns 0-4 for child under 5", () => {
    expect(childAgeBands([24])).toEqual(["0-4"]);
  });

  it("returns 5+ for child 5 or over", () => {
    expect(childAgeBands([72])).toEqual(["5+"]);
  });

  it("returns both bands for mixed ages", () => {
    expect(childAgeBands([24, 72])).toEqual(["0-4", "5+"]);
  });

  it("deduplicates when both children under 5", () => {
    expect(childAgeBands([12, 36])).toEqual(["0-4"]);
  });

  it("59 months is under 5 (boundary)", () => {
    expect(childAgeBands([59])).toEqual(["0-4"]);
  });

  it("60 months is 5+ (boundary)", () => {
    expect(childAgeBands([60])).toEqual(["5+"]);
  });

  it("result is sorted alphabetically", () => {
    const result = childAgeBands([72, 24]);
    expect(result).toEqual(["0-4", "5+"]);
  });
});

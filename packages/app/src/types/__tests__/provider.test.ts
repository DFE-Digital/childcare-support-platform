import { describe, it, expect } from "vitest";
import { getOfstedRatingLabel } from "../provider";
import type { OfstedInfo } from "../provider";

describe("getOfstedRatingLabel", () => {
  it("returns legacyRating for ungraded_confirmed framework", () => {
    const ofsted: OfstedInfo = {
      framework: "ungraded_confirmed",
      inspectionDate: "2021-10-07",
      legacyRating: "Good",
    };
    expect(getOfstedRatingLabel(ofsted)).toBe("Good");
  });

  it("returns legacyRating for legacy framework", () => {
    const ofsted: OfstedInfo = {
      framework: "legacy",
      inspectionDate: "2020-01-15",
      legacyRating: "Outstanding",
    };
    expect(getOfstedRatingLabel(ofsted)).toBe("Outstanding");
  });

  it("returns null for legacy_transition", () => {
    const ofsted: OfstedInfo = {
      framework: "legacy_transition",
      inspectionDate: "2023-06-01",
      safeguardingMet: true,
      legacySubGrades: { qualityOfEducation: "Good" },
    };
    expect(getOfstedRatingLabel(ofsted)).toBeNull();
  });

  it("returns null when no ofsted data", () => {
    expect(getOfstedRatingLabel(null)).toBeNull();
    expect(getOfstedRatingLabel(undefined)).toBeNull();
  });
});

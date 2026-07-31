import { describe, it, expect } from "vitest";
import {
  getDailyOpeningSpan,
  getDailyOpeningHours,
  getLongestAnnualWeeks,
} from "../providerCardHelpers";
import type { Provider } from "@/types/provider";
import type { ProviderCareType } from "@bsil/calculator";

function makeCareType(
  overrides: Partial<ProviderCareType> & { type: string },
): ProviderCareType {
  return {
    fees: {},
    additionalCharges: [],
    eligibleAttendeesOnly: false,
    ...overrides,
  };
}

function makeProvider(careTypes: ProviderCareType[]): Provider {
  return {
    id: "p1",
    name: "Test Provider",
    address: { line1: "", line2: "", city: "", postcode: "" },
    distanceMiles: 1,
    phone: "",
    email: "",
    website: "",
    careTypes,
  };
}

const nursery = makeCareType({
  type: "private_nursery",
  openingHours: [{ days: "Mon-Fri", open: "07:45", close: "17:30" }],
  operatingWeeksPerYear: 51,
});

const breakfast = makeCareType({
  type: "breakfast_club",
  openingHours: [{ days: "Mon-Fri", open: "07:45", close: "08:45" }],
  operatingWeeksPerYear: 38,
});

const noHours = makeCareType({
  type: "after_school_club",
  operatingWeeksPerYear: 38,
});

const provider = makeProvider([nursery, breakfast]);

describe("getDailyOpeningSpan", () => {
  it("returns span across all care types when no filter is active", () => {
    expect(getDailyOpeningSpan(provider, [])).toBe("07:45 to 17:30");
  });

  it("narrows span to matching care type when filtered", () => {
    expect(getDailyOpeningSpan(provider, ["breakfast_club"])).toBe(
      "07:45 to 08:45",
    );
  });

  it("returns \u2013 when filter matches no care types", () => {
    expect(getDailyOpeningSpan(provider, ["holiday_club"])).toBe("\u2013");
  });

  it("returns \u2013 when no care type has opening hours", () => {
    const p = makeProvider([noHours]);
    expect(getDailyOpeningSpan(p, [])).toBe("\u2013");
  });
});

describe("getDailyOpeningHours", () => {
  it("returns total hours across all care types when no filter", () => {
    // 07:45 to 17:30 = 9.75 hours
    expect(getDailyOpeningHours(provider, [])).toBeCloseTo(9.75);
  });

  it("returns hours for only the filtered care type", () => {
    // 07:45 to 08:45 = 1 hour
    expect(getDailyOpeningHours(provider, ["breakfast_club"])).toBeCloseTo(1);
  });

  it("returns null when filter matches no care types", () => {
    expect(getDailyOpeningHours(provider, ["holiday_club"])).toBeNull();
  });

  it("returns null when no care type has opening hours", () => {
    const p = makeProvider([noHours]);
    expect(getDailyOpeningHours(p, [])).toBeNull();
  });
});

describe("getLongestAnnualWeeks", () => {
  it("returns max weeks across all care types when no filter", () => {
    expect(getLongestAnnualWeeks(provider, [])).toBe(51);
  });

  it("returns weeks for only the filtered care type", () => {
    expect(getLongestAnnualWeeks(provider, ["breakfast_club"])).toBe(38);
  });

  it("returns 0 when filter matches no care types", () => {
    expect(getLongestAnnualWeeks(provider, ["holiday_club"])).toBe(0);
  });

  it("returns max among multiple matching care types", () => {
    expect(
      getLongestAnnualWeeks(provider, ["private_nursery", "breakfast_club"]),
    ).toBe(51);
  });
});

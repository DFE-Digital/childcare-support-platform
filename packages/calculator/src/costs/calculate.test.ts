import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { ChildcareSelection, ChildData } from "../types/family.js";
import type { ProviderCareType } from "../types/provider.js";
import type { PostcodeAreaCosts } from "../types/costs.js";
import type { Scheme, SchemesData } from "../types/scheme.js";
import type { ChildEntitlement } from "../types/entitlement.js";
import { getAgeBand } from "./age-band.js";
import { resolveFeesForSelection, extractCost } from "./fee-lookup.js";
import { calculateChildcareFees } from "./gross-cost.js";
import { calculateAdditionalCharges } from "./additional-charges.js";
import {
  determineFundedHoursPerWeek,
  calculateFundedHoursReduction,
} from "./funded-hours.js";
import { calculateGovernmentSupport } from "./government-support.js";
import { getRoundFn } from "./rounding.js";
import { calculateCosts } from "./calculate.js";
import { calculateEntitlements } from "../entitlement/calculate.js";

const dataDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../app/src/data",
);

const providersDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../data-pipeline/data/placeholder-providers",
);
const providers: Array<{
  id: string;
  name: string;
  careTypes: ProviderCareType[];
}> = readdirSync(providersDir)
  .filter((f) => f.endsWith(".json"))
  .map((f) => JSON.parse(readFileSync(join(providersDir, f), "utf-8")));

const schemesData: SchemesData = JSON.parse(
  readFileSync(join(dataDir, "schemes.json"), "utf-8"),
);
const schemes: Scheme[] = schemesData.schemes;

// Synthetic cost fixture with stable round numbers for unit tests.
// This avoids coupling tests to real exported cost data that changes over time.
const MOCK_COSTS: PostcodeAreaCosts = {
  laName: "Test LA",
  regionName: "Test Region",
  nationName: "England",
  lastUpdated: "2026-04",
  averageCosts: {
    private_nursery: {
      fees: {
        under2: { perHour: { mean: 9, lower: 7, upper: 11, area: "la" } },
        age2: { perHour: { mean: 8, lower: 6, upper: 10, area: "la" } },
        age3to4: { perHour: { mean: 7, lower: 5, upper: 9, area: "la" } },
      },
      sessionHours: { morning: 5, afternoon: 5, fullDay: 10 },
      operatingWeeksPerYear: 50,
      additionalCharges: [
        {
          item: "Meals",
          cost: { mean: 3, lower: 2, upper: 4, area: "la" },
          unit: "per day",
          description: "Lunch",
        },
        {
          item: "Consumables",
          cost: 2,
          unit: "per week",
          description: "Nappies etc",
        },
      ],
    },
    school_based_nursery: {
      fees: {
        age2: { perHour: { mean: 8, lower: 6, upper: 10, area: "la" } },
        age3to4: { perHour: { mean: 7, lower: 5, upper: 9, area: "la" } },
      },
      sessionHours: { morning: 3.25, afternoon: 3.25 },
      operatingWeeksPerYear: 38,
      additionalCharges: [
        {
          item: "Meals",
          cost: { mean: 3, lower: 2, upper: 4, area: "la" },
          unit: "per day",
          description: "Lunch",
        },
      ],
    },
    childminder: {
      fees: {
        under2: { perHour: { mean: 7, lower: 5, upper: 9, area: "la" } },
        age2: { perHour: { mean: 6, lower: 4, upper: 8, area: "la" } },
        age3to4: { perHour: { mean: 5.5, lower: 4, upper: 7, area: "la" } },
      },
      additionalCharges: [
        {
          item: "Meals",
          cost: 2.5,
          unit: "per day",
          description: "Lunch",
        },
      ],
    },
    breakfast_club: {
      fees: {
        all: { perHour: { mean: 6, lower: 5, upper: 7, area: "la" } },
      },
      sessionHours: { session: 1 },
      operatingWeeksPerYear: 38,
      additionalCharges: [],
    },
    free_breakfast_club: {
      fees: {
        all: { perHour: { mean: 0, lower: 0, upper: 0, area: "la" } },
      },
      sessionHours: { session: 1 },
      operatingWeeksPerYear: 38,
      additionalCharges: [],
    },
    after_school_club: {
      fees: {
        all: { perHour: { mean: 5, lower: 4, upper: 6, area: "la" } },
      },
      sessionHours: { session: 2.5 },
      operatingWeeksPerYear: 38,
      additionalCharges: [
        {
          item: "Snack",
          cost: 1,
          unit: "per session",
          description: "After school snack",
        },
      ],
    },
    holiday_club: {
      fees: {
        all: { perHour: { mean: 6, lower: 5, upper: 7, area: "la" } },
      },
      sessionHours: { day: 7 },
      additionalCharges: [
        {
          item: "Lunch",
          cost: 3,
          unit: "per day",
          description: "Packed lunch",
        },
      ],
    },
  },
  governmentFundingRates: {
    under2: { perHour: 12 },
    age2: { perHour: 8 },
    age3to4: { perHour: 5.5 },
  },
};

const REF = new Date(2026, 1, 22); // 2026-02-22

// --- Age band tests ---

describe("getAgeBand", () => {
  it("returns under2 for 23-month-old", () => {
    const child: ChildData = {
      id: 1,
      firstName: "Thomas",
      birthMonth: 3,
      birthYear: 2024,
      hasSEND: false,
      sendDetails: null,
      isFostered: false,
      hasEHCP: false,
      hasLeftCareForAdoptionOrSpecialGuardianship: false,
      childcareSelections: [],
    };
    expect(getAgeBand(child, REF)).toBe("under2");
  });

  it("returns age2 for 24-month-old", () => {
    const child: ChildData = {
      id: 1,
      firstName: "Test",
      birthMonth: 2,
      birthYear: 2024,
      hasSEND: false,
      sendDetails: null,
      isFostered: false,
      hasEHCP: false,
      hasLeftCareForAdoptionOrSpecialGuardianship: false,
      childcareSelections: [],
    };
    expect(getAgeBand(child, REF)).toBe("age2");
  });

  it("returns age3to4 for 36-month-old", () => {
    const child: ChildData = {
      id: 1,
      firstName: "Test",
      birthMonth: 2,
      birthYear: 2023,
      hasSEND: false,
      sendDetails: null,
      isFostered: false,
      hasEHCP: false,
      hasLeftCareForAdoptionOrSpecialGuardianship: false,
      childcareSelections: [],
    };
    expect(getAgeBand(child, REF)).toBe("age3to4");
  });

  it("returns age3to4 for 4-year-old", () => {
    const child: ChildData = {
      id: 1,
      firstName: "Maya",
      birthMonth: 1,
      birthYear: 2022,
      hasSEND: false,
      sendDetails: null,
      isFostered: false,
      hasEHCP: false,
      hasLeftCareForAdoptionOrSpecialGuardianship: false,
      childcareSelections: [],
    };
    expect(getAgeBand(child, REF)).toBe("age3to4");
  });
});

// --- Gross cost tests ---

describe("calculateChildcareFees", () => {
  it("private nursery: Thomas scenario (5 mornings + 3 afternoons × £55 × 51 weeks)", () => {
    const selection: ChildcareSelection = {
      id: 1,
      careType: "private_nursery",
      sessions: { morning: { daysPerWeek: 5 }, afternoon: { daysPerWeek: 3 } },
      providerId: "p1358070129789077173",
    };
    const fees = resolveFeesForSelection(
      selection,
      "under2",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    expect(result.total).toBe(22440);
  });

  it("school-based nursery: Kaurs/Maya (8 sessions × £26 × 38 weeks)", () => {
    const selection: ChildcareSelection = {
      id: 1,
      careType: "school_based_nursery",
      sessions: { morning: { daysPerWeek: 5 }, afternoon: { daysPerWeek: 3 } },
      providerId: "p7612815013616358484",
    };
    const fees = resolveFeesForSelection(
      selection,
      "age3to4",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    expect(result.total).toBe(7904);
  });

  it("private nursery: weeksPerYear override (5 mornings × £55 × 42 weeks)", () => {
    const selection: ChildcareSelection = {
      id: 1,
      careType: "private_nursery",
      sessions: { morning: { daysPerWeek: 5 } },
      providerId: "p1358070129789077173",
      weeksPerYear: 42,
    };
    const fees = resolveFeesForSelection(
      selection,
      "under2",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    // 5 mornings × £55 × 42 weeks = 11550
    expect(result.total).toBe(11550);
    expect(result.weeksPerYear).toBe(42);
  });

  it("school-based nursery: weeksPerYear override (8 sessions × £26 × 30 weeks)", () => {
    const selection: ChildcareSelection = {
      id: 1,
      careType: "school_based_nursery",
      sessions: { morning: { daysPerWeek: 5 }, afternoon: { daysPerWeek: 3 } },
      providerId: "p7612815013616358484",
      weeksPerYear: 30,
    };
    const fees = resolveFeesForSelection(
      selection,
      "age3to4",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    // (5 × £26 + 3 × £26) × 30 = 208 × 30 = 6240
    expect(result.total).toBe(6240);
    expect(result.weeksPerYear).toBe(30);
  });

  it("private nursery: sessionHours override changes weeklyHours and effectiveHourlyRate", () => {
    const selection: ChildcareSelection = {
      id: 1,
      careType: "private_nursery",
      sessions: { morning: { daysPerWeek: 5 }, afternoon: { daysPerWeek: 3 } },
      sessionHours: { morning: 3, afternoon: 2.5 },
      providerId: "p1358070129789077173",
    };
    const fees = resolveFeesForSelection(
      selection,
      "under2",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    // fees unchanged: 5×55 + 3×55 = 440/week × 51 = 22440
    expect(result.total).toBe(22440);
    // weeklyHours: 5×3 + 3×2.5 = 22.5 (not 5×5 + 3×5 = 40)
    expect(result.weeklyHours).toBe(22.5);
    expect(result.effectiveHourlyRate).toBeCloseTo(440 / 22.5);
  });

  it("private nursery: partial sessionHours override (only morning)", () => {
    const selection: ChildcareSelection = {
      id: 1,
      careType: "private_nursery",
      sessions: { morning: { daysPerWeek: 5 }, afternoon: { daysPerWeek: 3 } },
      sessionHours: { morning: 4 },
      providerId: "p1358070129789077173",
    };
    const fees = resolveFeesForSelection(
      selection,
      "under2",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    // morning uses 4 (override), afternoon uses 5 (from fees.sessionHours)
    // weeklyHours: 5×4 + 3×5 = 35
    expect(result.weeklyHours).toBe(35);
    expect(result.effectiveHourlyRate).toBeCloseTo(440 / 35);
  });

  it("childminder provider: Nguyens/Lily (35 hrs × £7.50 × 44 weeks, age2plus fallback)", () => {
    const selection: ChildcareSelection = {
      id: 1,
      careType: "childminder",
      hoursPerWeek: 35,
      weeksPerYear: 44,
      providerId: "p2364030839202207152",
    };
    // Provider has fees keyed under "age2plus" — the fallback from "age2" should find it
    const fees = resolveFeesForSelection(
      selection,
      "age2",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    expect(result.total).toBe(11550);
  });

  it("childminder provider: age3to4 also falls back to age2plus", () => {
    const selection: ChildcareSelection = {
      id: 1,
      careType: "childminder",
      hoursPerWeek: 35,
      weeksPerYear: 44,
      providerId: "p2364030839202207152",
    };
    const fees = resolveFeesForSelection(
      selection,
      "age3to4",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    // Same rate as age2 via age2plus fallback: 35 × £7.50 × 44 = £11,550
    expect(result.total).toBe(11550);
  });

  it("breakfast club: area average (5 × £6 × 38 weeks = £1,140)", () => {
    // MOCK_COSTS breakfast_club: £6/hr × 1hr session = £6/session
    // 5 days × £6 × 38 weeks = £1,140
    const selection: ChildcareSelection = {
      id: 1,
      careType: "breakfast_club",
      daysPerWeek: 5,
      providerId: null,
    };
    const fees = resolveFeesForSelection(
      selection,
      "age3to4",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    expect(result.total).toBe(1140);
  });

  it("free breakfast club: £0", () => {
    const selection: ChildcareSelection = {
      id: 1,
      careType: "free_breakfast_club",
      daysPerWeek: 5,
      providerId: "p673888428820612136",
    };
    const fees = resolveFeesForSelection(
      selection,
      "age3to4",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    expect(result.total).toBe(0);
  });

  it("after-school club: area average (3 × £12.50 × 38 weeks = £1,425)", () => {
    // MOCK_COSTS after_school_club: £5/hr × 2.5hr session = £12.50/session
    // 3 days × £12.50 × 38 weeks = £1,425
    const selection: ChildcareSelection = {
      id: 1,
      careType: "after_school_club",
      daysPerWeek: 3,
      providerId: null,
    };
    const fees = resolveFeesForSelection(
      selection,
      "age3to4",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    expect(result.total).toBe(1425);
  });

  it("holiday club: area average (20 days × £42 = £840)", () => {
    // MOCK_COSTS holiday_club: £6/hr × 7hr day = £42/day
    // 20 days × £42 = £840
    const selection: ChildcareSelection = {
      id: 1,
      careType: "holiday_club",
      daysPerYear: 20,
      providerId: null,
    };
    const fees = resolveFeesForSelection(
      selection,
      "age3to4",
      providers,
      MOCK_COSTS,
    );
    const result = calculateChildcareFees(selection, fees);
    expect(result.total).toBe(840);
  });
});

// --- Funded hours tests ---

describe("determineFundedHoursPerWeek", () => {
  function makeEntitlement(
    eligible: Record<string, boolean>,
  ): ChildEntitlement {
    return {
      childId: 1,
      childName: "Test",
      schemes: Object.entries(eligible).map(([schemeId, isEligible]) => ({
        schemeId,
        eligible: isEligible,
        reasons: [],
        caveats: [],
      })),
    };
  }

  it("30-hour entitlement for age 3-4 → 30 hours", () => {
    const ent = makeEntitlement({
      "30_hours_working_families": true,
      "15_hours_universal": true,
    });
    const result = determineFundedHoursPerWeek(ent, "age3to4");
    expect(result).toEqual([
      { hoursPerWeek: 30, schemeName: "30 hours working families" },
    ]);
  });

  it("30-hour entitlement for under 2 → 30 hours (Sep 2025 expansion)", () => {
    const ent = makeEntitlement({
      "30_hours_working_families": true,
    });
    const result = determineFundedHoursPerWeek(ent, "under2");
    expect(result).toEqual([
      { hoursPerWeek: 30, schemeName: "30 hours working families" },
    ]);
  });

  it("age 2 eligible for both → 30 hours stacked (2YO first, WF fills remainder)", () => {
    const ent = makeEntitlement({
      "30_hours_working_families": true,
      "15_hours_2_year_olds": true,
    });
    const result = determineFundedHoursPerWeek(ent, "age2");
    expect(result).toEqual([
      {
        hoursPerWeek: 15,
        schemeName: "15 hours early learning for 2-year-olds",
      },
      { hoursPerWeek: 15, schemeName: "30 hours working families" },
    ]);
    expect(result.reduce((sum, a) => sum + a.hoursPerWeek, 0)).toBe(30);
  });

  it("age 2 eligible for 30 Hours WF only → 30 hours (Sep 2025 expansion)", () => {
    const ent = makeEntitlement({
      "30_hours_working_families": true,
      "15_hours_2_year_olds": false,
    });
    const result = determineFundedHoursPerWeek(ent, "age2");
    expect(result).toEqual([
      { hoursPerWeek: 30, schemeName: "30 hours working families" },
    ]);
  });

  it("15-hour universal only", () => {
    const ent = makeEntitlement({
      "30_hours_working_families": false,
      "15_hours_universal": true,
    });
    const result = determineFundedHoursPerWeek(ent, "age3to4");
    expect(result).toEqual([
      { hoursPerWeek: 15, schemeName: "15 hours universal entitlement" },
    ]);
  });

  it("15-hour 2-year-olds only", () => {
    const ent = makeEntitlement({
      "30_hours_working_families": false,
      "15_hours_2_year_olds": true,
    });
    const result = determineFundedHoursPerWeek(ent, "age2");
    expect(result).toEqual([
      {
        hoursPerWeek: 15,
        schemeName: "15 hours early learning for 2-year-olds",
      },
    ]);
  });

  it("no funded hours for ineligible child", () => {
    const ent = makeEntitlement({
      "30_hours_working_families": false,
      "15_hours_universal": false,
      "15_hours_2_year_olds": false,
    });
    const result = determineFundedHoursPerWeek(ent, "under2");
    expect(result).toEqual([]);
  });
});

describe("calculateFundedHoursReduction", () => {
  it("Thomas: 15 hrs × £11.00/hr, gov £12 → saving £6,270", () => {
    // Provider rate £55/session / 5 hrs = £11.00/hr
    // Gov rate under2 = £12 → no shortfall (provider rate < gov rate)
    // Saving = 15 × min(11, 12) × 38 = 15 × 11 × 38 = 6,270
    const result = calculateFundedHoursReduction(
      15,
      "30 hours working families",
      "under2",
      11.0,
      40, // weeklyHours > 15, so capped at 15
      "private_nursery",
      MOCK_COSTS,
    );
    expect(result).not.toBeNull();
    expect(result!.breakdown.savingToParent).toBe(6270);
    expect(result!.breakdown.shortfallPerHour).toBe(0);
    expect(result!.hoursUsed).toBe(15);
  });

  it("Kaurs/Maya: 30h entitlement but 24 weekly hours — funded hours are free", () => {
    // Provider rate: £26/session / 3 hrs = £8.667/hr
    // Gov rate age3to4 = £5.50 (used as gate only, not to cap saving)
    // Actual funded = min(30, 24) = 24
    // Saving = 24 × 8.667 × 38 = 7,904 (funded hours fully free)
    // Shortfall = 0 (policy: funded hours are free at point of use)
    const effectiveRate = 26.0 / 3;
    const result = calculateFundedHoursReduction(
      30,
      "30 hours working families",
      "age3to4",
      effectiveRate,
      24,
      "school_based_nursery",
      MOCK_COSTS,
    );
    expect(result).not.toBeNull();
    expect(result!.breakdown.savingToParent).toBeCloseTo(7904, 0);
    expect(result!.breakdown.shortfallPerHour).toBe(0);
    expect(result!.hoursUsed).toBe(24);
  });

  it("Priya/Amir: 15 hrs, age 2, gov £8 — no shortfall", () => {
    // Provider rate: £22/session / 3.5 hrs = £6.2857/hr
    // Gov rate age2 = £8
    // Saving = 15 × min(6.2857, 8) × 38 = 15 × 6.2857 × 38 = 3,582.86
    // Shortfall = 0 (provider rate < gov rate)
    const effectiveRate = 22.0 / 3.5;
    const result = calculateFundedHoursReduction(
      15,
      "15 hours early learning for 2-year-olds",
      "age2",
      effectiveRate,
      17.5, // 5 mornings × 3.5 hrs
      "school_based_nursery",
      MOCK_COSTS,
    );
    expect(result).not.toBeNull();
    expect(result!.breakdown.savingToParent).toBeCloseTo(3582.86, 0);
    expect(result!.breakdown.shortfallPerHour).toBe(0);
  });

  it("returns null for breakfast club (not eligible for funded hours)", () => {
    const result = calculateFundedHoursReduction(
      15,
      "test",
      "age3to4",
      6.5,
      5,
      "breakfast_club",
      MOCK_COSTS,
    );
    expect(result).toBeNull();
  });

  it("returns null when no funded hours remaining", () => {
    const result = calculateFundedHoursReduction(
      0,
      "test",
      "age3to4",
      8.0,
      20,
      "private_nursery",
      MOCK_COSTS,
    );
    expect(result).toBeNull();
  });

  it("stacked 30h pool: all 25h funded at £6.29/hr, gov £8 → saving = 25 × £6.29 × 38", () => {
    // Mirrors Sunderland rates: provider £22/session ÷ 3.5h = £6.29/hr, gov age2 = £8/hr
    // With 30h pool (stacked), 25h of 25h weekly hours are funded (all)
    const effectiveRate = 22.0 / 3.5;
    const result = calculateFundedHoursReduction(
      30, // stacked pool
      "15 hours early learning for 2-year-olds; Working parent entitlement (age 2)",
      "age2",
      effectiveRate,
      25, // 5 full days × 5h
      "school_based_nursery",
      MOCK_COSTS,
    );
    expect(result).not.toBeNull();
    // saving = 25 × min(6.2857, 8) × 38 = 25 × 6.2857 × 38 ≈ 5,971.43
    expect(result!.breakdown.savingToParent).toBeCloseTo(
      25 * effectiveRate * 38,
      0,
    );
    expect(result!.hoursUsed).toBe(25);

    // Compare: with only 15h pool, only 15h funded → saving would be 15 × 6.2857 × 38 ≈ 3,582.86
    const result15 = calculateFundedHoursReduction(
      15, // non-stacked pool
      "15 hours early learning for 2-year-olds",
      "age2",
      effectiveRate,
      25,
      "school_based_nursery",
      MOCK_COSTS,
    );
    expect(result!.breakdown.savingToParent).toBeGreaterThan(
      result15!.breakdown.savingToParent,
    );
  });
});

// --- Government support tests ---

describe("calculateGovernmentSupport", () => {
  function makeChildEntitlement(
    eligible: Record<string, boolean>,
  ): ChildEntitlement {
    return {
      childId: 1,
      childName: "Test",
      schemes: Object.entries(eligible).map(([schemeId, isEligible]) => ({
        schemeId,
        eligible: isEligible,
        reasons: [],
        caveats: [],
      })),
    };
  }

  it("TFC capped at £2,000 (Brennans: £13,260 eligible → 20% = £2,652 → capped)", () => {
    const children = [
      {
        child: {
          id: 1,
          firstName: "Isla",
          birthMonth: 11,
          birthYear: 2025,
          hasSEND: false,
          sendDetails: null,
          isFostered: false,
          hasEHCP: false,
          hasLeftCareForAdoptionOrSpecialGuardianship: false,
          childcareSelections: [],
        } as ChildData,
        entitlement: makeChildEntitlement({ tax_free_childcare: true }),
        childcareFees: 13260,
        fundedHoursSaving: 0,
      },
    ];
    const result = calculateGovernmentSupport(children, schemes, false);
    expect(result.taxFreeChildcare).not.toBeNull();
    expect(result.taxFreeChildcare!.savingToParent).toBe(2000);
    expect(result.ucChildcare).toBeNull();
  });

  it("TFC disabled cap £4,000 (Kaurs/Rajan)", () => {
    const children = [
      {
        child: {
          id: 1,
          firstName: "Rajan",
          birthMonth: 8,
          birthYear: 2015,
          hasSEND: true,
          sendDetails: null,
          isFostered: false,
          hasEHCP: false,
          hasLeftCareForAdoptionOrSpecialGuardianship: false,
          childcareSelections: [],
        } as ChildData,
        entitlement: makeChildEntitlement({ tax_free_childcare: true }),
        childcareFees: 25000, // high enough to exceed £4,000 cap
        fundedHoursSaving: 0,
      },
    ];
    const result = calculateGovernmentSupport(children, schemes, false);
    expect(result.taxFreeChildcare).not.toBeNull();
    expect(result.taxFreeChildcare!.savingToParent).toBe(4000);
  });

  it("TFC null for UC family", () => {
    const children = [
      {
        child: {
          id: 1,
          firstName: "Test",
          birthMonth: 1,
          birthYear: 2023,
          hasSEND: false,
          sendDetails: null,
          isFostered: false,
          hasEHCP: false,
          hasLeftCareForAdoptionOrSpecialGuardianship: false,
          childcareSelections: [],
        } as ChildData,
        entitlement: makeChildEntitlement({
          tax_free_childcare: false,
          universal_credit_childcare: true,
        }),
        childcareFees: 5000,
        fundedHoursSaving: 0,
      },
    ];
    const result = calculateGovernmentSupport(children, schemes, true);
    expect(result.taxFreeChildcare).toBeNull();
  });

  it("TFC null for £100k+ family (Clarkes)", () => {
    const children = [
      {
        child: {
          id: 1,
          firstName: "Olivia",
          birthMonth: 11,
          birthYear: 2022,
          hasSEND: false,
          sendDetails: null,
          isFostered: false,
          hasEHCP: false,
          hasLeftCareForAdoptionOrSpecialGuardianship: false,
          childcareSelections: [],
        } as ChildData,
        entitlement: makeChildEntitlement({ tax_free_childcare: false }),
        childcareFees: 9180,
        fundedHoursSaving: 3112.2,
      },
    ];
    const result = calculateGovernmentSupport(children, schemes, false);
    expect(result.taxFreeChildcare).toBeNull();
  });

  it("UC 85% reimbursement (Priya)", () => {
    const children = [
      {
        child: {
          id: 1,
          firstName: "Amir",
          birthMonth: 3,
          birthYear: 2024,
          hasSEND: false,
          sendDetails: null,
          isFostered: false,
          hasEHCP: false,
          hasLeftCareForAdoptionOrSpecialGuardianship: false,
          childcareSelections: [],
        } as ChildData,
        entitlement: makeChildEntitlement({
          universal_credit_childcare: true,
        }),
        childcareFees: 4180,
        fundedHoursSaving: 3582.86,
      },
      {
        child: {
          id: 2,
          firstName: "Zara",
          birthMonth: 5,
          birthYear: 2018,
          hasSEND: false,
          sendDetails: null,
          isFostered: false,
          hasEHCP: false,
          hasLeftCareForAdoptionOrSpecialGuardianship: false,
          childcareSelections: [],
        } as ChildData,
        entitlement: makeChildEntitlement({
          universal_credit_childcare: true,
        }),
        childcareFees: 2452,
        fundedHoursSaving: 0,
      },
    ];
    const result = calculateGovernmentSupport(children, schemes, true);
    expect(result.ucChildcare).not.toBeNull();
    // Total eligible = (4180 - 3582.86) + 2452 = 3049.14
    // Monthly = 3049.14 / 12 = 254.095
    // Monthly reimbursement = 254.095 × 0.85 = 215.98 (under cap of 1768.94)
    // Annual = 215.98 × 12 = 2591.76
    expect(result.ucChildcare!.savingToParent).toBeCloseTo(2592, 0);
    expect(result.taxFreeChildcare).toBeNull();
  });

  it("UC null for non-UC family", () => {
    const children = [
      {
        child: {
          id: 1,
          firstName: "Test",
          birthMonth: 1,
          birthYear: 2023,
          hasSEND: false,
          sendDetails: null,
          isFostered: false,
          hasEHCP: false,
          hasLeftCareForAdoptionOrSpecialGuardianship: false,
          childcareSelections: [],
        } as ChildData,
        entitlement: makeChildEntitlement({ tax_free_childcare: true }),
        childcareFees: 5000,
        fundedHoursSaving: 0,
      },
    ];
    const result = calculateGovernmentSupport(children, schemes, false);
    expect(result.ucChildcare).toBeNull();
  });
});

// --- nearest10 rounding: per-child split invariant ---

describe("nearest10: UC per-child allocations sum to total", () => {
  function makeChildEntitlement(
    childId: number,
    eligible: Record<string, boolean>,
  ): ChildEntitlement {
    return {
      childId,
      childName: `Child${childId}`,
      schemes: Object.entries(eligible).map(([schemeId, isEligible]) => ({
        schemeId,
        eligible: isEligible,
        reasons: [],
        caveats: [],
      })),
    };
  }

  it("two-child UC split: per-child UC sums to family UC total", () => {
    const roundFn = getRoundFn("nearest10");
    const children = [
      {
        child: {
          id: 1,
          firstName: "A",
          birthMonth: 3,
          birthYear: 2024,
          hasSEND: false,
          sendDetails: null,
          isFostered: false,
          hasEHCP: false,
          hasLeftCareForAdoptionOrSpecialGuardianship: false,
          childcareSelections: [],
        } as ChildData,
        entitlement: makeChildEntitlement(1, {
          universal_credit_childcare: true,
        }),
        childcareFees: 4180,
        fundedHoursSaving: 3580,
      },
      {
        child: {
          id: 2,
          firstName: "B",
          birthMonth: 5,
          birthYear: 2018,
          hasSEND: false,
          sendDetails: null,
          isFostered: false,
          hasEHCP: false,
          hasLeftCareForAdoptionOrSpecialGuardianship: false,
          childcareSelections: [],
        } as ChildData,
        entitlement: makeChildEntitlement(2, {
          universal_credit_childcare: true,
        }),
        childcareFees: 2450,
        fundedHoursSaving: 0,
      },
    ];
    const result = calculateGovernmentSupport(children, schemes, true, roundFn);

    expect(result.ucChildcare).not.toBeNull();
    const total = result.ucChildcare!.savingToParent;
    const perChildSum = result.perChild.reduce((s, p) => s + p.uc, 0);

    // Per-child allocations must sum exactly to the family total
    expect(perChildSum).toBe(total);
    // All values must be multiples of 10
    expect(total % 10).toBe(0);
    for (const p of result.perChild) {
      expect(p.uc % 10).toBe(0);
    }
  });
});

// --- Additional charges tests ---

describe("calculateAdditionalCharges", () => {
  it("Thomas nursery: meals + consumables", () => {
    const selection: ChildcareSelection = {
      id: 1,
      careType: "private_nursery",
      sessions: { morning: { daysPerWeek: 5 }, afternoon: { daysPerWeek: 3 } },
      providerId: "p1358070129789077173",
    };
    const fees = resolveFeesForSelection(
      selection,
      "under2",
      providers,
      MOCK_COSTS,
    );
    const result = calculateAdditionalCharges(selection, fees);
    // Meals: 5 days × £3.50 × 51 weeks = £892.50
    // Consumables: £2.25 × 51 weeks = £114.75
    // Total: £1,007.25
    expect(result.total).toBeCloseTo(1007.25, 2);
  });
});

// --- extractCost variant tests ---

describe("extractCost", () => {
  const triad = { mean: 10, lower: 8, upper: 12, area: "la" as const };

  it("extracts mean by default", () => {
    expect(extractCost(triad)).toBe(10);
  });

  it("extracts lower when variant is lower", () => {
    expect(extractCost(triad, "lower")).toBe(8);
  });

  it("extracts upper when variant is upper", () => {
    expect(extractCost(triad, "upper")).toBe(12);
  });

  it("extracts mean when variant is mean", () => {
    expect(extractCost(triad, "mean")).toBe(10);
  });

  it("returns scalar unchanged regardless of variant", () => {
    expect(extractCost(5.0, "lower")).toBe(5.0);
    expect(extractCost(5.0, "upper")).toBe(5.0);
    expect(extractCost(5.0, "mean")).toBe(5.0);
    expect(extractCost(5.0)).toBe(5.0);
  });
});

// --- Fee variant tests ---

describe("resolveFeesForSelection with fee variants", () => {
  // Area-average nursery selection (no provider)
  const nurserySelection: ChildcareSelection = {
    id: 1,
    careType: "private_nursery",
    providerId: null,
    sessions: { fullDay: { daysPerWeek: 3 } },
  };

  // Area-average childminder selection
  const childminderSelection: ChildcareSelection = {
    id: 2,
    careType: "childminder",
    providerId: null,
    hoursPerWeek: 30,
    weeksPerYear: 50,
  };

  it("area-average nursery: upper fees > mean fees > lower fees", () => {
    const lower = resolveFeesForSelection(
      nurserySelection,
      "under2",
      providers,
      MOCK_COSTS,
      "lower",
    );
    const mean = resolveFeesForSelection(
      nurserySelection,
      "under2",
      providers,
      MOCK_COSTS,
      "mean",
    );
    const upper = resolveFeesForSelection(
      nurserySelection,
      "under2",
      providers,
      MOCK_COSTS,
      "upper",
    );

    expect(lower.fullDay!).toBeLessThan(mean.fullDay!);
    expect(mean.fullDay!).toBeLessThan(upper.fullDay!);
    expect(lower.morningSession!).toBeLessThan(mean.morningSession!);
    expect(mean.morningSession!).toBeLessThan(upper.morningSession!);
  });

  it("area-average childminder: upper perHour > mean perHour > lower perHour", () => {
    const lower = resolveFeesForSelection(
      childminderSelection,
      "under2",
      providers,
      MOCK_COSTS,
      "lower",
    );
    const mean = resolveFeesForSelection(
      childminderSelection,
      "under2",
      providers,
      MOCK_COSTS,
      "mean",
    );
    const upper = resolveFeesForSelection(
      childminderSelection,
      "under2",
      providers,
      MOCK_COSTS,
      "upper",
    );

    expect(lower.perHour!).toBeLessThan(mean.perHour!);
    expect(mean.perHour!).toBeLessThan(upper.perHour!);
  });

  it("provider-based selection: fees identical across all variants", () => {
    const providerSelection: ChildcareSelection = {
      id: 1,
      careType: "private_nursery",
      providerId: providers[0]?.id ?? "test",
      sessions: { fullDay: { daysPerWeek: 3 } },
    };

    const lower = resolveFeesForSelection(
      providerSelection,
      "under2",
      providers,
      MOCK_COSTS,
      "lower",
    );
    const mean = resolveFeesForSelection(
      providerSelection,
      "under2",
      providers,
      MOCK_COSTS,
      "mean",
    );
    const upper = resolveFeesForSelection(
      providerSelection,
      "under2",
      providers,
      MOCK_COSTS,
      "upper",
    );

    expect(lower.fullDay).toBe(mean.fullDay);
    expect(mean.fullDay).toBe(upper.fullDay);
  });
});

// --- Childminder area-average tests (regression: was returning £0) ---

describe("childminder area-average fees", () => {
  const cmSelectionAge2: ChildcareSelection = {
    id: 1,
    careType: "childminder",
    providerId: null,
    hoursPerWeek: 20,
    weeksPerYear: 50,
  };

  it("age2 child gets non-zero fees from area averages", () => {
    const fees = resolveFeesForSelection(
      cmSelectionAge2,
      "age2",
      providers,
      MOCK_COSTS,
    );
    expect(fees.perHour).toBe(6); // MOCK_COSTS childminder age2 mean
    const result = calculateChildcareFees(cmSelectionAge2, fees);
    // 20 hrs × £6 × 50 weeks = £6,000
    expect(result.total).toBe(6000);
  });

  it("age3to4 child gets non-zero fees from area averages", () => {
    const fees = resolveFeesForSelection(
      cmSelectionAge2,
      "age3to4",
      providers,
      MOCK_COSTS,
    );
    expect(fees.perHour).toBe(5.5); // MOCK_COSTS childminder age3to4 mean
    const result = calculateChildcareFees(cmSelectionAge2, fees);
    // 20 hrs × £5.50 × 50 weeks = £5,500
    expect(result.total).toBe(5500);
  });

  it("under2 child gets non-zero fees from area averages", () => {
    const fees = resolveFeesForSelection(
      cmSelectionAge2,
      "under2",
      providers,
      MOCK_COSTS,
    );
    expect(fees.perHour).toBe(7); // MOCK_COSTS childminder under2 mean
  });

  it("rateDetails are populated for area-average childminder selection", () => {
    const child: ChildData = {
      id: 1,
      firstName: "TestChild",
      birthMonth: 2,
      birthYear: 2024, // age2 at REF
      hasSEND: false,
      sendDetails: null,
      isFostered: false,
      hasEHCP: false,
      hasLeftCareForAdoptionOrSpecialGuardianship: false,
      childcareSelections: [
        {
          id: 1,
          careType: "childminder",
          providerId: null,
          hoursPerWeek: 20,
          weeksPerYear: 50,
        },
      ],
    };

    const person = {
      firstName: "Parent",
      workingStatus: "earning_above_nmw" as const,
      isApprentice: false,
      firstYearApprentice: null,
      isSelfEmployed: false,
      selfEmployedLessThanTwelveMonths: null,
      ageBracket: "21+" as const,
      residencyStatus: "british_irish_citizen" as const,
      receivesQualifyingAllowance: null,
      startingWorkNextMonth: null,
      hasLimitedCapacityForWork: null,
      hasNationalInsuranceNumber: true,
      isStudying: false,
      studyLevel: null,
      isFullTimeStudent: null,
      courseIsPubliclyFunded: null,
      eligibleForStudentFinance: null,
    };
    const data = {
      schemaVersion: 1,
      children: [child],
      user: person,
      partner: person,
      household: { hasPartner: true },
      ucIncomeBelowThreshold: false,
      nrpfIncomeUnderThreshold: 0,
      nrpfSavingsUnderLimit: 0,
      qualifyingBenefits: [],
      location: { postcode: "OX2 0AA", ladCodes: ["E07000178"] },
      shortlistedProviders: [] as string[],
    };

    const entitlements = calculateEntitlements(data, schemes, REF);
    const result = calculateCosts({
      data,
      schemes,
      entitlements,
      providers,
      areaCosts: MOCK_COSTS,
      referenceDate: REF,
    });

    const sel =
      result.children[0].selections?.[0] ??
      result.children[0].termTimeCare?.selections?.[0] ??
      result.children[0].yearRoundCare?.selections?.[0];
    expect(sel).toBeDefined();
    expect(sel!.calculation.step1_childcareFees.total).toBeGreaterThan(0);
    expect(sel!.feeSource.rateDetails).toBeDefined();
    expect(sel!.feeSource.rateDetails!.length).toBeGreaterThan(0);
  });
});

// --- Structural validation: MOCK_COSTS keys match real exported data ---

describe("MOCK_COSTS structural validation", () => {
  const projectRoot = join(
    dirname(fileURLToPath(import.meta.url)),
    "../../../..",
  );
  const fixturesLadDir = join(
    dirname(fileURLToPath(import.meta.url)),
    "../__fixtures__/costs/lad",
  );
  const exportedDir = existsSync(join(projectRoot, "exported_data/app/lad"))
    ? join(projectRoot, "exported_data/app/lad")
    : existsSync(join(projectRoot, ".docker-data/app/lad"))
      ? join(projectRoot, ".docker-data/app/lad")
      : fixturesLadDir;

  it("MOCK_COSTS age band keys match real data for shared care types", () => {
    // Load a sample of real cost files (or synthetic fixtures in CI)
    const files = readdirSync(exportedDir).filter((f) => f.endsWith(".json"));
    if (files.length === 0) return; // no cost data available — skip

    // Collect age band keys per care type from real data
    const realAgeBandsByCareType = new Map<string, Set<string>>();
    for (const f of files.slice(0, 10)) {
      const data: PostcodeAreaCosts = JSON.parse(
        readFileSync(join(exportedDir, f), "utf-8"),
      );
      for (const [careType, careData] of Object.entries(data.averageCosts)) {
        if (!careData || typeof careData !== "object" || !("fees" in careData))
          continue;
        const existing = realAgeBandsByCareType.get(careType) ?? new Set();
        for (const band of Object.keys(
          (careData as { fees: Record<string, unknown> }).fees,
        )) {
          existing.add(band);
        }
        realAgeBandsByCareType.set(careType, existing);
      }
    }

    // For care types that appear in both MOCK_COSTS and real data,
    // verify MOCK_COSTS age bands are a subset of real age bands.
    for (const [ct, careData] of Object.entries(MOCK_COSTS.averageCosts)) {
      const realBands = realAgeBandsByCareType.get(ct);
      if (!realBands) continue; // care type not in real data (e.g. clubs) — skip
      if (!careData || !("fees" in careData)) continue;
      for (const band of Object.keys(
        (careData as { fees: Record<string, unknown> }).fees,
      )) {
        expect(
          realBands.has(band),
          `MOCK_COSTS age band "${band}" in "${ct}" not found in real data (found: ${[...realBands].join(", ")})`,
        ).toBe(true);
      }
    }
  });
});

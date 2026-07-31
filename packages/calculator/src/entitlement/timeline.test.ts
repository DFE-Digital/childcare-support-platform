import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type {
  LocalStorageData,
  PersonData,
  ChildData,
} from "../types/family.js";
import type { Scheme, SchemesData } from "../types/scheme.js";
import { calculateTimeline } from "./timeline.js";

const schemesPath = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../app/src/data/schemes.json",
);
const schemesData: SchemesData = JSON.parse(readFileSync(schemesPath, "utf-8"));
const schemes: Scheme[] = schemesData.schemes;

// Reference date: 2026-04-21
const REF = new Date(2026, 3, 21);

function validPerson(overrides: Partial<PersonData> = {}): PersonData {
  return {
    isApprentice: false,
    firstYearApprentice: null,
    isSelfEmployed: false,
    selfEmployedLessThanTwelveMonths: null,
    ageBracket: "21+",
    workingStatus: "earning_above_nmw",
    receivesQualifyingAllowance: null,
    startingWorkNextMonth: null,
    hasLimitedCapacityForWork: null,
    hasNationalInsuranceNumber: true,
    residencyStatus: "british_irish_citizen",
    isStudying: false,
    studyLevel: null,
    isFullTimeStudent: null,
    courseIsPubliclyFunded: null,
    eligibleForStudentFinance: null,
    ...overrides,
  };
}

function validChild(overrides: Partial<ChildData> = {}): ChildData {
  return {
    id: 1,
    firstName: "TestChild",
    birthMonth: 3,
    birthYear: 2023,
    hasSEND: false,
    sendDetails: null,
    isFostered: false,
    hasEHCP: false,
    hasLeftCareForAdoptionOrSpecialGuardianship: false,
    childcareSelections: [],
    ...overrides,
  };
}

function validFamily(
  overrides: Partial<LocalStorageData> = {},
): LocalStorageData {
  return {
    schemaVersion: 2,
    location: { postcode: "OX2 0AA", ladCodes: ["E07000178"] },
    household: { hasPartner: true },
    user: validPerson(),
    partner: validPerson(),
    ucIncomeBelowThreshold: false,
    nrpfIncomeUnderThreshold: 0,
    nrpfSavingsUnderLimit: 0,
    qualifyingBenefits: [],
    children: [validChild()],
    shortlistedProviders: [],
    ...overrides,
  };
}

function getTransition(
  result: ReturnType<typeof calculateTimeline>,
  childIndex: number,
  schemeId: string,
  direction: "gain" | "loss",
) {
  return result.children[childIndex].transitions.find(
    (t) => t.schemeId === schemeId && t.direction === direction,
  );
}

describe("calculateTimeline", () => {
  describe("child aged 6 months — gains 30h at 9 months", () => {
    // Born Oct 2025 → 6 months at REF (Apr 2026), turns 9 months Jul 2026
    const data = validFamily({
      children: [validChild({ birthMonth: 10, birthYear: 2025 })],
    });
    const result = calculateTimeline(data, schemes, REF);

    it("gains 30_hours_working_families", () => {
      const t = getTransition(result, 0, "30_hours_working_families", "gain");
      expect(t).toBeDefined();
      expect(t!.effectiveDate.getMonth()).toBe(6); // July (0-based)
      expect(t!.effectiveDate.getFullYear()).toBe(2026);
      expect(t!.ageAtTransitionMonths).toBe(9);
    });

    it("does not lose any schemes", () => {
      const losses = result.children[0].transitions.filter(
        (t) => t.direction === "loss",
      );
      expect(losses).toHaveLength(0);
    });
  });

  describe("child aged 22 months — gains 15h-2yo at term after 2nd birthday", () => {
    // Born Jun 2024 → 22 months at REF (Apr 2026), turns 2 Jun 2026
    // Next term after Jun is Sep 2026
    // 15h-2yo requires qualifying benefits or child-specific grounds (fostered/DLA/EHCP/adoption)
    const data = validFamily({
      qualifyingBenefits: ["esa"],
      children: [validChild({ birthMonth: 6, birthYear: 2024 })],
    });
    const result = calculateTimeline(data, schemes, REF);

    it("gains 15_hours_2_year_olds", () => {
      const t = getTransition(result, 0, "15_hours_2_year_olds", "gain");
      expect(t).toBeDefined();
      expect(t!.effectiveDate.getMonth()).toBe(8); // September (0-based)
      expect(t!.effectiveDate.getFullYear()).toBe(2026);
    });
  });

  describe("child aged 2y 10m — loses 15h-2yo, gains 15h-universal", () => {
    // Born Jun 2023 → 2y 10m at REF (Apr 2026), turns 3 Jun 2026
    // 15h-2yo requires qualifying benefits; needs esa to be eligible at baseline
    // isEligibleFor15Hours2YO: eligibleFrom = nextTermStart(2025,6) = Sep 2025 ✓
    //   eligibleUntil = nextTermStart(2026,6) = Sep 2026
    // So at baseline (Apr 2026) child IS eligible for 15h-2yo.
    // At Sep 2026 child is no longer eligible → loss.
    //
    // 15h-universal: nextTermStart(2026,6) = Sep 2026 — gain at Sep (term following 3rd birthday).
    const data = validFamily({
      qualifyingBenefits: ["esa"],
      children: [validChild({ birthMonth: 6, birthYear: 2023 })],
    });
    const result = calculateTimeline(data, schemes, REF);

    it("loses 15_hours_2_year_olds", () => {
      const t = getTransition(result, 0, "15_hours_2_year_olds", "loss");
      expect(t).toBeDefined();
      expect(t!.effectiveDate.getMonth()).toBe(8); // September
    });

    it("gains 15_hours_universal", () => {
      const t = getTransition(result, 0, "15_hours_universal", "gain");
      expect(t).toBeDefined();
      // nextTermStart(2026, 6) = Sep 2026 — term following 3rd birthday
      expect(t!.effectiveDate.getMonth()).toBe(8); // September (0-based)
    });
  });

  describe("child 3y 10m born Jun — school-age transition in Sep", () => {
    // Born Jun 2022 → 3y 10m at REF (Apr 2026), ageYears = 3
    // schoolStartYear: turnsFourYear=2026, birthMonth=6 (<9), so schoolStartYear=2026
    // schoolStartDate = Sep 1 2026 → isPreSchool=true at baseline
    // At Sep 2026: ageYears = floor(52/12) = 4 → gains wraparound + breakfast, loses 30h + universal
    const data = validFamily({
      children: [validChild({ birthMonth: 6, birthYear: 2022 })],
    });
    const result = calculateTimeline(data, schemes, REF);

    it("loses 30_hours_working_families at school age", () => {
      const t = getTransition(result, 0, "30_hours_working_families", "loss");
      expect(t).toBeDefined();
      expect(t!.effectiveDate.getMonth()).toBe(8); // September
      expect(t!.effectiveDate.getFullYear()).toBe(2026);
    });

    it("loses 15_hours_universal at school age", () => {
      const t = getTransition(result, 0, "15_hours_universal", "loss");
      expect(t).toBeDefined();
      expect(t!.effectiveDate.getMonth()).toBe(8); // September
    });

    it("gains wraparound_childcare at school start (Sep)", () => {
      const t = getTransition(result, 0, "wraparound_childcare", "gain");
      expect(t).toBeDefined();
      expect(t!.effectiveDate.getMonth()).toBe(8); // September
      expect(t!.effectiveDate.getFullYear()).toBe(2026);
    });

    it("gains free_breakfast_clubs at school start (Sep)", () => {
      const t = getTransition(result, 0, "free_breakfast_clubs", "gain");
      expect(t).toBeDefined();
      expect(t!.effectiveDate.getMonth()).toBe(8); // September
    });
  });

  describe("child aged 7 — no transitions within 12 months", () => {
    // Born Mar 2019 → 7y 1m at REF
    const data = validFamily({
      children: [validChild({ birthMonth: 3, birthYear: 2019 })],
    });
    const result = calculateTimeline(data, schemes, REF);

    it("has no transitions", () => {
      expect(result.children[0].transitions).toHaveLength(0);
    });
  });

  describe("horizonMonths parameter", () => {
    // Born Oct 2025 → 6 months at REF, gains 30h at month 9 (Jul 2026 = 3 months out)
    const data = validFamily({
      children: [validChild({ birthMonth: 10, birthYear: 2025 })],
    });

    it("6-month horizon includes the transition", () => {
      const result = calculateTimeline(data, schemes, REF, 6);
      const t = getTransition(result, 0, "30_hours_working_families", "gain");
      expect(t).toBeDefined();
    });

    it("2-month horizon excludes the transition", () => {
      const result = calculateTimeline(data, schemes, REF, 2);
      const t = getTransition(result, 0, "30_hours_working_families", "gain");
      expect(t).toBeUndefined();
    });
  });

  describe("parent-circumstance-only schemes produce no transitions", () => {
    // Non-studying parents — care_to_learn and learner_support stay ineligible
    const data = validFamily({
      children: [validChild({ birthMonth: 3, birthYear: 2024 })],
    });
    const result = calculateTimeline(data, schemes, REF);

    it("no care_to_learn transitions", () => {
      const gains = result.children[0].transitions.filter(
        (t) => t.schemeId === "care_to_learn",
      );
      expect(gains).toHaveLength(0);
    });

    it("no learner_support transitions", () => {
      const gains = result.children[0].transitions.filter(
        (t) => t.schemeId === "learner_support",
      );
      expect(gains).toHaveLength(0);
    });
  });

  describe("transitions are sorted chronologically", () => {
    // Child that will have multiple transitions at different dates
    // Born Oct 2025 → gains 30h at Jul 2026 (9 months)
    const data = validFamily({
      children: [validChild({ birthMonth: 10, birthYear: 2025 })],
    });
    const result = calculateTimeline(data, schemes, REF);
    const transitions = result.children[0].transitions;

    it("transitions are in date order", () => {
      for (let i = 1; i < transitions.length; i++) {
        expect(transitions[i].effectiveDate.getTime()).toBeGreaterThanOrEqual(
          transitions[i - 1].effectiveDate.getTime(),
        );
      }
    });
  });
});

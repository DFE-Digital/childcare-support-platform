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
import { calculateEntitlements } from "./calculate.js";

const schemesPath = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../app/src/data/schemes.json",
);
const schemesData: SchemesData = JSON.parse(readFileSync(schemesPath, "utf-8"));
const schemes: Scheme[] = schemesData.schemes;

// Reference date: 2026-02-22
const REF = new Date(2026, 1, 22);

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

function getScheme(
  result: ReturnType<typeof calculateEntitlements>,
  childIndex: number,
  schemeId: string,
) {
  return result.children[childIndex].schemes.find(
    (s) => s.schemeId === schemeId,
  );
}

describe("calculateEntitlements", () => {
  describe("working couple, child aged 2", () => {
    const data = validFamily({
      children: [validChild({ birthMonth: 3, birthYear: 2024 })], // ~23 months at ref
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("eligible for 30h (child ≥9mo, pre-school, both working)", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        true,
      );
    });

    it("eligible for TFC", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("ineligible for 15h universal (under 3)", () => {
      expect(getScheme(result, 0, "15_hours_universal")?.eligible).toBe(false);
    });

    it("ineligible for 15h 2yo (not on benefits)", () => {
      // Working couple not on UC — no known qualifying route
      expect(getScheme(result, 0, "15_hours_2_year_olds")?.eligible).toBe(
        false,
      );
    });

    it("ineligible for UC childcare (not on UC)", () => {
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        false,
      );
    });
  });

  describe("working couple, child aged 3", () => {
    const data = validFamily({
      children: [validChild({ birthMonth: 6, birthYear: 2022 })], // age 3
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("eligible for 30h", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        true,
      );
    });

    it("eligible for 15h universal", () => {
      expect(getScheme(result, 0, "15_hours_universal")?.eligible).toBe(true);
    });

    it("eligible for TFC", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });
  });

  describe("single parent not working on UC, child aged 2", () => {
    const data = validFamily({
      household: { hasPartner: false },
      user: validPerson({
        workingStatus: "not_working",
        receivesQualifyingAllowance: false,
      }),
      partner: null,
      qualifyingBenefits: ["universal_credit"],
      ucIncomeBelowThreshold: true,
      children: [validChild({ birthMonth: 10, birthYear: 2023 })], // born Oct 2023, turns 2 Oct 2025, eligible from Jan 2026
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("eligible for 15h 2yo via UC route", () => {
      expect(getScheme(result, 0, "15_hours_2_year_olds")?.eligible).toBe(true);
    });

    it("ineligible for 30h (not working)", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    it("ineligible for TFC (on UC)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });

    it("ineligible for UC childcare (not working)", () => {
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        false,
      );
    });
  });

  describe("single parent on income-related ESA, child aged 2", () => {
    const data = validFamily({
      household: { hasPartner: false },
      user: validPerson({
        workingStatus: "not_working",
        receivesQualifyingAllowance: false,
      }),
      partner: null,
      qualifyingBenefits: ["esa"],
      children: [validChild({ birthMonth: 10, birthYear: 2023 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("eligible for 15h 2yo via ESA route", () => {
      const scheme = getScheme(result, 0, "15_hours_2_year_olds");
      expect(scheme?.eligible).toBe(true);
      expect(scheme?.reasons?.some((r) => r.includes("ESA"))).toBe(true);
    });

    it("not eligible for TFC (not working)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });
  });

  describe("UC family with income above threshold, child aged 2", () => {
    const data = validFamily({
      household: { hasPartner: false },
      user: validPerson({
        workingStatus: "not_working",
        receivesQualifyingAllowance: false,
      }),
      partner: null,
      qualifyingBenefits: ["universal_credit"],
      ucIncomeBelowThreshold: false,
      children: [validChild({ birthMonth: 10, birthYear: 2023 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("not eligible via UC route (income above threshold)", () => {
      const scheme = getScheme(result, 0, "15_hours_2_year_olds");
      expect(scheme?.reasons?.some((r) => r.includes("Universal Credit"))).toBe(
        false,
      );
    });
  });

  describe("income over £100k", () => {
    const data = validFamily({
      user: validPerson({ workingStatus: "income_over_100k" }),
      partner: validPerson({ workingStatus: "income_over_100k" }),
      children: [validChild({ birthMonth: 6, birthYear: 2022 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("ineligible for 30h", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    it("ineligible for TFC", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });

    it("still eligible for 15h universal", () => {
      expect(getScheme(result, 0, "15_hours_universal")?.eligible).toBe(true);
    });
  });

  describe("on Universal Credit", () => {
    const data = validFamily({
      household: { hasPartner: false },
      user: validPerson({ workingStatus: "earning_below_nmw" }),
      partner: null,
      qualifyingBenefits: ["universal_credit"],
      children: [validChild({ birthMonth: 6, birthYear: 2022 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("ineligible for TFC", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });

    it("eligible for UC childcare (working)", () => {
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        true,
      );
    });
  });

  describe("UC childcare age cutoff (1 Sep after 16th birthday)", () => {
    const ucSingleParent = {
      household: { hasPartner: false },
      user: validPerson({ workingStatus: "earning_above_nmw" }),
      partner: null,
      qualifyingBenefits: ["universal_credit"],
    };

    it("born Jan-Aug: eligible before 1 Sep of year they turn 16", () => {
      // Born March 2010, turns 16 in March 2026, cutoff 1 Sep 2026
      const data = validFamily({
        ...ucSingleParent,
        children: [validChild({ birthMonth: 3, birthYear: 2010 })],
      });
      const ref = new Date(2026, 7, 31); // 31 Aug 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        true,
      );
    });

    it("born Jan-Aug: ineligible from 1 Sep of year they turn 16", () => {
      const data = validFamily({
        ...ucSingleParent,
        children: [validChild({ birthMonth: 3, birthYear: 2010 })],
      });
      const ref = new Date(2026, 8, 1); // 1 Sep 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        false,
      );
      expect(
        getScheme(result, 0, "universal_credit_childcare")?.reasons,
      ).toContainEqual(
        expect.stringContaining("31 August after their 16th birthday"),
      );
    });

    it("born Sep-Dec: eligible before 1 Sep of year after they turn 16", () => {
      // Born Oct 2009, turns 16 in Oct 2025, cutoff 1 Sep 2026
      const data = validFamily({
        ...ucSingleParent,
        children: [validChild({ birthMonth: 10, birthYear: 2009 })],
      });
      const ref = new Date(2026, 7, 31); // 31 Aug 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        true,
      );
    });

    it("born Sep-Dec: ineligible from 1 Sep of year after they turn 16", () => {
      const data = validFamily({
        ...ucSingleParent,
        children: [validChild({ birthMonth: 10, birthYear: 2009 })],
      });
      const ref = new Date(2026, 8, 1); // 1 Sep 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        false,
      );
    });
  });

  describe("TFC age cutoff (1 Sep after 11th birthday, 16th if disabled)", () => {
    const tfcSingleParent = {
      household: { hasPartner: false },
      user: validPerson({ workingStatus: "earning_above_nmw" }),
      partner: null,
      qualifyingBenefits: [],
    };

    it("born Jan-Aug: eligible before 1 Sep of year they turn 11", () => {
      // Born March 2015, turns 11 March 2026, cutoff 1 Sep 2026
      const data = validFamily({
        ...tfcSingleParent,
        children: [validChild({ birthMonth: 3, birthYear: 2015 })],
      });
      const ref = new Date(2026, 7, 31); // 31 Aug 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("born Jan-Aug: ineligible from 1 Sep of year they turn 11", () => {
      const data = validFamily({
        ...tfcSingleParent,
        children: [validChild({ birthMonth: 3, birthYear: 2015 })],
      });
      const ref = new Date(2026, 8, 1); // 1 Sep 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
      expect(
        getScheme(result, 0, "tax_free_childcare")?.reasons,
      ).toContainEqual(
        expect.stringContaining("31 August after their 11th birthday"),
      );
    });

    it("born Sep-Dec: eligible before 1 Sep of year after they turn 11", () => {
      // Born Oct 2014, turns 11 Oct 2025, cutoff 1 Sep 2026
      const data = validFamily({
        ...tfcSingleParent,
        children: [validChild({ birthMonth: 10, birthYear: 2014 })],
      });
      const ref = new Date(2026, 7, 31); // 31 Aug 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("born Sep-Dec: ineligible from 1 Sep of year after they turn 11", () => {
      const data = validFamily({
        ...tfcSingleParent,
        children: [validChild({ birthMonth: 10, birthYear: 2014 })],
      });
      const ref = new Date(2026, 8, 1); // 1 Sep 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });

    it("disabled, born Jan-Aug: eligible before 1 Sep of year they turn 16", () => {
      // Born March 2010, turns 16 March 2026, cutoff 1 Sep 2026
      const data = validFamily({
        ...tfcSingleParent,
        children: [
          validChild({
            birthMonth: 3,
            birthYear: 2010,
            hasSEND: true,
            sendDetails: {
              receivesDLA: true,
              receivesPIP: false,
              isRegisteredBlind: false,
            },
          }),
        ],
      });
      const ref = new Date(2026, 7, 31); // 31 Aug 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("disabled, born Jan-Aug: ineligible from 1 Sep of year they turn 16", () => {
      const data = validFamily({
        ...tfcSingleParent,
        children: [
          validChild({
            birthMonth: 3,
            birthYear: 2010,
            hasSEND: true,
            sendDetails: {
              receivesDLA: true,
              receivesPIP: false,
              isRegisteredBlind: false,
            },
          }),
        ],
      });
      const ref = new Date(2026, 8, 1); // 1 Sep 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
      expect(
        getScheme(result, 0, "tax_free_childcare")?.reasons,
      ).toContainEqual(
        expect.stringContaining("31 August after their 16th birthday"),
      );
    });

    it("disabled, born Sep-Dec: eligible before 1 Sep of year after they turn 16", () => {
      // Born Oct 2009, turns 16 Oct 2025, cutoff 1 Sep 2026
      const data = validFamily({
        ...tfcSingleParent,
        children: [
          validChild({
            birthMonth: 10,
            birthYear: 2009,
            hasSEND: true,
            sendDetails: {
              receivesDLA: true,
              receivesPIP: false,
              isRegisteredBlind: false,
            },
          }),
        ],
      });
      const ref = new Date(2026, 7, 31); // 31 Aug 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("disabled, born Sep-Dec: ineligible from 1 Sep of year after they turn 16", () => {
      const data = validFamily({
        ...tfcSingleParent,
        children: [
          validChild({
            birthMonth: 10,
            birthYear: 2009,
            hasSEND: true,
            sendDetails: {
              receivesDLA: true,
              receivesPIP: false,
              isRegisteredBlind: false,
            },
          }),
        ],
      });
      const ref = new Date(2026, 8, 1); // 1 Sep 2026
      const result = calculateEntitlements(data, schemes, ref);
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });
  });

  describe("fostered child and UC childcare", () => {
    const ucSingleParent = {
      household: { hasPartner: false },
      user: validPerson({ workingStatus: "earning_above_nmw" }),
      partner: null,
      qualifyingBenefits: ["universal_credit"],
    };

    it("fostered child is ineligible for UC childcare", () => {
      const data = validFamily({
        ...ucSingleParent,
        children: [
          validChild({ birthMonth: 6, birthYear: 2022, isFostered: true }),
        ],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        false,
      );
      expect(
        getScheme(result, 0, "universal_credit_childcare")?.reasons,
      ).toContainEqual(expect.stringContaining("foster"));
    });

    it("non-fostered child is eligible for UC childcare", () => {
      const data = validFamily({
        ...ucSingleParent,
        children: [
          validChild({ birthMonth: 6, birthYear: 2022, isFostered: false }),
        ],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        true,
      );
    });
  });

  describe("fostered child and TFC", () => {
    const tfcSingleParent = {
      household: { hasPartner: false },
      user: validPerson({ workingStatus: "earning_above_nmw" }),
      partner: null,
      qualifyingBenefits: [],
    };

    it("fostered child is ineligible for TFC", () => {
      const data = validFamily({
        ...tfcSingleParent,
        children: [
          validChild({ birthMonth: 6, birthYear: 2022, isFostered: true }),
        ],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
      expect(
        getScheme(result, 0, "tax_free_childcare")?.reasons,
      ).toContainEqual(expect.stringContaining("foster"));
    });

    it("non-fostered child is eligible for TFC", () => {
      const data = validFamily({
        ...tfcSingleParent,
        children: [
          validChild({ birthMonth: 6, birthYear: 2022, isFostered: false }),
        ],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });
  });

  describe("UC childcare: starting work next month", () => {
    it("single parent not working but starting soon → UC childcare eligible", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: validPerson({
          workingStatus: "not_working",
          startingWorkNextMonth: true,
        }),
        partner: null,
        qualifyingBenefits: ["universal_credit"],
        children: [validChild({ birthMonth: 6, birthYear: 2022 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        true,
      );
    });

    it("single parent not working, not starting soon → UC childcare ineligible", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: validPerson({
          workingStatus: "not_working",
          startingWorkNextMonth: false,
        }),
        partner: null,
        qualifyingBenefits: ["universal_credit"],
        children: [validChild({ birthMonth: 6, birthYear: 2022 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        false,
      );
      expect(
        getScheme(result, 0, "universal_credit_childcare")?.reasons,
      ).toContainEqual(expect.stringContaining("not working"));
    });

    it("couple: one not working but starting soon → no 'neither working' reason", () => {
      const data = validFamily({
        household: { hasPartner: true },
        user: validPerson({ workingStatus: "earning_above_nmw" }),
        partner: validPerson({
          workingStatus: "not_working",
          startingWorkNextMonth: true,
        }),
        qualifyingBenefits: ["universal_credit"],
        children: [validChild({ birthMonth: 6, birthYear: 2022 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        true,
      );
    });

    it("couple: one works, other has LCW → UC childcare eligible", () => {
      const data = validFamily({
        household: { hasPartner: true },
        user: validPerson({ workingStatus: "earning_above_nmw" }),
        partner: validPerson({
          workingStatus: "not_working",
          hasLimitedCapacityForWork: true,
        }),
        qualifyingBenefits: ["universal_credit"],
        children: [validChild({ birthMonth: 6, birthYear: 2022 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      const uc = getScheme(result, 0, "universal_credit_childcare");
      expect(uc?.eligible).toBe(true);
      expect(uc?.caveats.map((c) => c.code)).not.toContain(
        "limited_capability_for_work",
      );
    });

    it("couple: one works, other has LCW false → UC childcare ineligible", () => {
      const data = validFamily({
        household: { hasPartner: true },
        user: validPerson({ workingStatus: "earning_above_nmw" }),
        partner: validPerson({
          workingStatus: "not_working",
          hasLimitedCapacityForWork: false,
        }),
        qualifyingBenefits: ["universal_credit"],
        children: [validChild({ birthMonth: 6, birthYear: 2022 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      const uc = getScheme(result, 0, "universal_credit_childcare");
      expect(uc?.eligible).toBe(false);
      expect(uc?.reasons).toContainEqual(
        expect.stringContaining("partner is not working"),
      );
    });

    it("couple: one works, other has LCW null → UC childcare ineligible", () => {
      const data = validFamily({
        household: { hasPartner: true },
        user: validPerson({ workingStatus: "earning_above_nmw" }),
        partner: validPerson({
          workingStatus: "not_working",
          hasLimitedCapacityForWork: null,
        }),
        qualifyingBenefits: ["universal_credit"],
        children: [validChild({ birthMonth: 6, birthYear: 2022 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      const uc = getScheme(result, 0, "universal_credit_childcare");
      expect(uc?.eligible).toBe(false);
      expect(uc?.reasons).toContainEqual(
        expect.stringContaining("partner is not working"),
      );
    });

    it("couple: user has LCW, partner works → UC childcare eligible", () => {
      const data = validFamily({
        household: { hasPartner: true },
        user: validPerson({
          workingStatus: "not_working",
          hasLimitedCapacityForWork: true,
        }),
        partner: validPerson({ workingStatus: "earning_above_nmw" }),
        qualifyingBenefits: ["universal_credit"],
        children: [validChild({ birthMonth: 6, birthYear: 2022 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        true,
      );
    });
  });

  describe("non-working partner", () => {
    const data = validFamily({
      partner: validPerson({
        workingStatus: "not_working",
        receivesQualifyingAllowance: null,
      }),
      children: [validChild({ birthMonth: 6, birthYear: 2024 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("ineligible for 30h (partner not working)", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    it("ineligible for TFC (partner not working)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });
  });

  describe("Carer's Allowance partner exception", () => {
    const data = validFamily({
      partner: validPerson({
        workingStatus: "not_working",
        receivesQualifyingAllowance: true,
      }),
      children: [validChild({ birthMonth: 6, birthYear: 2022 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("eligible for 30h", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        true,
      );
    });

    it("eligible for TFC", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("includes Carer's Allowance caveat", () => {
      const scheme = getScheme(result, 0, "30_hours_working_families");
      expect(scheme?.caveats).toContainEqual(
        expect.objectContaining({ code: "partner_carers_allowance_exemption" }),
      );
    });
  });

  describe("self-employed < 12 months", () => {
    const data = validFamily({
      user: validPerson({
        isSelfEmployed: true,
        selfEmployedLessThanTwelveMonths: true,
        workingStatus: "earning_below_nmw",
      }),
      children: [validChild({ birthMonth: 6, birthYear: 2022 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("includes startup period caveat for 30h", () => {
      const scheme = getScheme(result, 0, "30_hours_working_families");
      expect(scheme?.caveats).toContainEqual(
        expect.objectContaining({ code: "user_self_employed_startup" }),
      );
    });

    it("includes startup period caveat for TFC", () => {
      const scheme = getScheme(result, 0, "tax_free_childcare");
      expect(scheme?.caveats).toContainEqual(
        expect.objectContaining({ code: "user_self_employed_startup" }),
      );
    });
  });

  describe("NRPF residency", () => {
    it("ineligible for 30h when both parents NRPF", () => {
      const data = validFamily({
        user: validPerson({ residencyStatus: "no_recourse_to_public_funds" }),
        partner: validPerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        children: [validChild({ birthMonth: 10, birthYear: 2023 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    it("eligible for 15h 2yo when income and savings confirmed", () => {
      const data = validFamily({
        user: validPerson({ residencyStatus: "no_recourse_to_public_funds" }),
        partner: validPerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        nrpfIncomeUnderThreshold: 26500, // outside London, 1 child
        nrpfSavingsUnderLimit: 16000,
        children: [validChild({ birthMonth: 10, birthYear: 2023 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      const scheme = getScheme(result, 0, "15_hours_2_year_olds");
      expect(scheme?.eligible).toBe(true);
      expect(scheme?.reasons).toContainEqual(
        expect.stringContaining("NRPF route"),
      );
      expect(scheme?.caveats).toHaveLength(0);
    });

    it("ineligible for 15h 2yo when income above threshold", () => {
      const data = validFamily({
        user: validPerson({ residencyStatus: "no_recourse_to_public_funds" }),
        partner: validPerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        nrpfIncomeUnderThreshold: 0,
        nrpfSavingsUnderLimit: 16000,
        children: [validChild({ birthMonth: 10, birthYear: 2023 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      const scheme = getScheme(result, 0, "15_hours_2_year_olds");
      expect(scheme?.eligible).toBe(false);
    });

    it("ineligible for 15h 2yo when savings above limit", () => {
      const data = validFamily({
        user: validPerson({ residencyStatus: "no_recourse_to_public_funds" }),
        partner: validPerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        nrpfIncomeUnderThreshold: 26500,
        nrpfSavingsUnderLimit: 0,
        children: [validChild({ birthMonth: 10, birthYear: 2023 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      const scheme = getScheme(result, 0, "15_hours_2_year_olds");
      expect(scheme?.eligible).toBe(false);
      expect(scheme?.caveats).toContainEqual(
        expect.objectContaining({ code: "nrpf_savings_above_limit" }),
      );
    });

    it("uses London threshold for E09 LAD codes", () => {
      const data = validFamily({
        location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] },
        user: validPerson({ residencyStatus: "no_recourse_to_public_funds" }),
        partner: validPerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        nrpfIncomeUnderThreshold: 34500, // London, 1 child
        nrpfSavingsUnderLimit: 16000,
        children: [validChild({ birthMonth: 10, birthYear: 2023 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      const scheme = getScheme(result, 0, "15_hours_2_year_olds");
      expect(scheme?.eligible).toBe(true);
      expect(scheme?.reasons).toContainEqual(expect.stringContaining("34,500"));
    });

    it("uses 2+ children threshold outside London", () => {
      const data = validFamily({
        user: validPerson({ residencyStatus: "no_recourse_to_public_funds" }),
        partner: validPerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        nrpfIncomeUnderThreshold: 30600, // outside London, 2+ children
        nrpfSavingsUnderLimit: 16000,
        children: [
          validChild({ id: 1, birthMonth: 10, birthYear: 2023 }),
          validChild({ id: 2, birthMonth: 6, birthYear: 2022 }),
        ],
      });
      const result = calculateEntitlements(data, schemes, REF);
      const scheme = getScheme(result, 0, "15_hours_2_year_olds");
      expect(scheme?.eligible).toBe(true);
      expect(scheme?.reasons).toContainEqual(expect.stringContaining("30,600"));
    });

    it("rejects stale threshold after location change", () => {
      const data = validFamily({
        location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] }, // London
        user: validPerson({ residencyStatus: "no_recourse_to_public_funds" }),
        partner: validPerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        nrpfIncomeUnderThreshold: 26500, // stale: non-London threshold
        nrpfSavingsUnderLimit: 16000,
        children: [validChild({ birthMonth: 10, birthYear: 2023 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      const scheme = getScheme(result, 0, "15_hours_2_year_olds");
      expect(scheme?.eligible).toBe(false);
    });

    it("ineligible for TFC (no parent has public funds access)", () => {
      const data = validFamily({
        user: validPerson({ residencyStatus: "no_recourse_to_public_funds" }),
        partner: validPerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        children: [validChild({ birthMonth: 10, birthYear: 2023 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
      expect(
        getScheme(result, 0, "tax_free_childcare")?.reasons,
      ).toContainEqual(expect.stringContaining("access to public funds"));
    });
  });

  describe("one parent NRPF, other has eligible residency", () => {
    const data = validFamily({
      user: validPerson({ residencyStatus: "british_irish_citizen" }),
      partner: validPerson({ residencyStatus: "no_recourse_to_public_funds" }),
      children: [validChild({ birthMonth: 6, birthYear: 2022 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("does not trigger NRPF income route", () => {
      const scheme = getScheme(result, 0, "15_hours_2_year_olds");
      expect(scheme?.caveats?.some((c) => c.code.includes("nrpf"))).toBeFalsy();
      expect(
        scheme?.reasons?.some((r: string) => r.includes("NRPF")),
      ).toBeFalsy();
    });

    it("eligible for TFC (at least one parent has access)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("includes caveat about which parent must apply", () => {
      expect(
        getScheme(result, 0, "tax_free_childcare")?.caveats,
      ).toContainEqual(
        expect.objectContaining({ code: "apply_with_public_funds_parent" }),
      );
    });
  });

  describe("child under 9 months", () => {
    const data = validFamily({
      children: [validChild({ birthMonth: 11, birthYear: 2025 })], // 3 months
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("ineligible for 30h", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    it("eligible for TFC", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("ineligible for 15h universal (under 3)", () => {
      expect(getScheme(result, 0, "15_hours_universal")?.eligible).toBe(false);
    });
  });

  describe("child with disability", () => {
    const data = validFamily({
      children: [
        validChild({
          birthMonth: 8,
          birthYear: 2015,
          hasSEND: true,
          sendDetails: {
            receivesDLA: true,
            receivesPIP: false,
            isRegisteredBlind: false,
          },
        }), // ~10yo
      ],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("eligible for TFC (extended to 16)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("TFC descriptionParams has higher annualCap for disabled child", () => {
      expect(
        getScheme(result, 0, "tax_free_childcare")?.descriptionParams,
      ).toEqual({ annualCap: "4,000" });
    });

    it("eligible for wraparound (extended to 18)", () => {
      expect(getScheme(result, 0, "wraparound_childcare")?.eligible).toBe(true);
    });

    it("eligible for breakfast clubs (age 4–11)", () => {
      expect(getScheme(result, 0, "free_breakfast_clubs")?.eligible).toBe(true);
    });
  });

  describe("school-age child (age 6)", () => {
    const data = validFamily({
      children: [validChild({ birthMonth: 9, birthYear: 2019 })], // ~6yo
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("ineligible for 30h (school age)", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    it("ineligible for 15h universal (school age)", () => {
      expect(getScheme(result, 0, "15_hours_universal")?.eligible).toBe(false);
    });

    it("eligible for wraparound", () => {
      expect(getScheme(result, 0, "wraparound_childcare")?.eligible).toBe(true);
    });

    it("eligible for breakfast clubs", () => {
      expect(getScheme(result, 0, "free_breakfast_clubs")?.eligible).toBe(true);
    });

    it("eligible for TFC", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });
  });

  describe("child age 12+ (non-disabled)", () => {
    const data = validFamily({
      children: [validChild({ birthMonth: 4, birthYear: 2013 })], // ~12yo
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("ineligible for TFC (over 11)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });

    it("eligible for wraparound (≤14)", () => {
      expect(getScheme(result, 0, "wraparound_childcare")?.eligible).toBe(true);
    });

    it("ineligible for breakfast clubs (over 11)", () => {
      expect(getScheme(result, 0, "free_breakfast_clubs")?.eligible).toBe(
        false,
      );
    });
  });

  describe("child age 15 (non-disabled)", () => {
    const data = validFamily({
      children: [validChild({ birthMonth: 4, birthYear: 2011 })], // ~14yo (14 years 10 months)
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("eligible for wraparound (≤14)", () => {
      expect(getScheme(result, 0, "wraparound_childcare")?.eligible).toBe(true);
    });
  });

  describe("HAF (Holiday Activities and Food)", () => {
    it("eligible when school-age child and family on UC", () => {
      const data = validFamily({
        children: [validChild({ birthMonth: 9, birthYear: 2019 })], // ~6yo
        qualifyingBenefits: ["universal_credit"],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "haf")?.eligible).toBe(true);
    });

    it("eligible when school-age child and family on ESA", () => {
      const data = validFamily({
        children: [validChild({ birthMonth: 9, birthYear: 2019 })],
        qualifyingBenefits: ["esa"],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "haf")?.eligible).toBe(true);
    });

    it("eligible when school-age child and family on Pension Credit", () => {
      const data = validFamily({
        children: [validChild({ birthMonth: 9, birthYear: 2019 })],
        qualifyingBenefits: ["pension_credit"],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "haf")?.eligible).toBe(true);
    });

    it("ineligible when school-age child but no qualifying benefit", () => {
      const data = validFamily({
        children: [validChild({ birthMonth: 9, birthYear: 2019 })],
        qualifyingBenefits: [],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "haf")?.eligible).toBe(false);
    });

    it("ineligible when child under school age", () => {
      const data = validFamily({
        children: [validChild({ birthMonth: 3, birthYear: 2024 })], // ~2yo
        qualifyingBenefits: ["universal_credit"],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "haf")?.eligible).toBe(false);
    });

    it("ineligible when child over 16", () => {
      const data = validFamily({
        children: [validChild({ birthMonth: 1, birthYear: 2008 })], // ~18yo
        qualifyingBenefits: ["universal_credit"],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "haf")?.eligible).toBe(false);
    });
  });

  describe("apprentice with lower earnings threshold", () => {
    const data = validFamily({
      household: { hasPartner: false },
      user: validPerson({
        isApprentice: true,
        firstYearApprentice: true,
        ageBracket: "18-20",
        workingStatus: "earning_above_apprentice_nmw",
      }),
      partner: null,
      children: [validChild({ birthMonth: 3, birthYear: 2025 })], // ~11mo
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("eligible for 30h", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        true,
      );
    });

    it("eligible for TFC", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });
  });

  describe("non-UK location", () => {
    const data = validFamily({
      location: { postcode: "OX2 0AA", ladCodes: ["X99999"] },
      children: [validChild({ birthMonth: 6, birthYear: 2022 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("ineligible for TFC", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });

    it("includes UK residency reason for TFC", () => {
      expect(
        getScheme(result, 0, "tax_free_childcare")?.reasons,
      ).toContainEqual(expect.stringContaining("live in the UK"));
    });

    it("ineligible for 30h", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    it("includes England reason for 30h", () => {
      expect(
        getScheme(result, 0, "30_hours_working_families")?.reasons,
      ).toContainEqual(expect.stringContaining("live in England"));
    });

    it("ineligible for 15h universal", () => {
      expect(getScheme(result, 0, "15_hours_universal")?.eligible).toBe(false);
    });

    it("includes England reason for 15h universal", () => {
      expect(
        getScheme(result, 0, "15_hours_universal")?.reasons,
      ).toContainEqual(expect.stringContaining("live in England"));
    });

    it("includes UK reason for UC childcare", () => {
      expect(
        getScheme(result, 0, "universal_credit_childcare")?.reasons,
      ).toContainEqual(expect.stringContaining("live in the UK"));
    });
  });

  describe("non-England UK location (Scotland)", () => {
    const data = validFamily({
      location: { postcode: "EH1 1AA", ladCodes: ["S12000036"] },
      children: [validChild({ birthMonth: 6, birthYear: 2022 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("ineligible for 30h (not England)", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    it("includes England reason for 30h", () => {
      expect(
        getScheme(result, 0, "30_hours_working_families")?.reasons,
      ).toContainEqual(expect.stringContaining("live in England"));
    });

    it("ineligible for 15h universal (not England)", () => {
      expect(getScheme(result, 0, "15_hours_universal")?.eligible).toBe(false);
    });

    it("ineligible for 15h 2yo (not England)", () => {
      const data2yo = validFamily({
        location: { postcode: "EH1 1AA", ladCodes: ["S12000036"] },
        qualifyingBenefits: ["universal_credit"],
        children: [validChild({ birthMonth: 1, birthYear: 2024 })],
      });
      const result2yo = calculateEntitlements(data2yo, schemes, REF);
      const scheme = getScheme(result2yo, 0, "15_hours_2_year_olds");
      expect(scheme?.eligible).toBe(false);
      expect(scheme?.reasons).toContainEqual(
        expect.stringContaining("England"),
      );
    });

    it("still eligible for TFC (UK is sufficient)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("no UK location reason for UC childcare (Scotland is UK)", () => {
      expect(
        getScheme(result, 0, "universal_credit_childcare")?.reasons,
      ).not.toContainEqual(expect.stringContaining("live in the UK"));
    });
  });

  describe("empty ladCodes", () => {
    const data = validFamily({
      location: { postcode: "OX2 0AA", ladCodes: [] },
      children: [validChild({ birthMonth: 6, birthYear: 2022 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("ineligible for TFC (no UK location)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });

    it("ineligible for 30h (no England location)", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    it("ineligible for 15h universal (no England location)", () => {
      expect(getScheme(result, 0, "15_hours_universal")?.eligible).toBe(false);
    });

    it("includes UK reason for UC childcare", () => {
      expect(
        getScheme(result, 0, "universal_credit_childcare")?.reasons,
      ).toContainEqual(expect.stringContaining("live in the UK"));
    });
  });

  // REF = 2026-02-22
  // Term boundaries: 1 Sep, 1 Jan, 1 Apr
  // Eligible from: start of term FOLLOWING child's 2nd birthday
  // Eligible until: start of term FOLLOWING child's 3rd birthday
  describe("15h 2yo — term-based age eligibility", () => {
    const ucFamily = (birthMonth: number, birthYear: number) =>
      validFamily({
        qualifyingBenefits: ["universal_credit"],
        ucIncomeBelowThreshold: true,
        children: [validChild({ birthMonth, birthYear })],
      });

    it("born Oct 2023 — eligible (turns 2 Oct 2025, eligible from Jan 2026)", () => {
      const scheme = getScheme(
        calculateEntitlements(ucFamily(10, 2023), schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(true);
    });

    it("born Dec 2023 — eligible (turns 2 Dec 2025, eligible from Jan 2026)", () => {
      const scheme = getScheme(
        calculateEntitlements(ucFamily(12, 2023), schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(true);
    });

    it("born Jun 2023 — eligible (turns 2 Jun 2025, eligible from Sep 2025)", () => {
      const scheme = getScheme(
        calculateEntitlements(ucFamily(6, 2023), schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(true);
    });

    it("born Mar 2023 — eligible (turns 2 Mar 2025, eligible from Apr 2025; turns 3 Mar 2026, eligible until Apr 2026)", () => {
      const scheme = getScheme(
        calculateEntitlements(ucFamily(3, 2023), schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(true);
    });

    it("born Feb 2024 — not yet eligible (turns 2 Feb 2026, eligible from Apr 2026)", () => {
      const scheme = getScheme(
        calculateEntitlements(ucFamily(2, 2024), schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(false);
      expect(scheme?.reasons).toContainEqual(
        expect.stringContaining("April 2026"),
      );
    });

    it("born Jan 2024 — not yet eligible (turns 2 Jan 2026, eligible from Apr 2026)", () => {
      const scheme = getScheme(
        calculateEntitlements(ucFamily(1, 2024), schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(false);
      expect(scheme?.reasons).toContainEqual(
        expect.stringContaining("April 2026"),
      );
    });

    it("born Sep 2022 — too old (turns 3 Sep 2025, eligible until Jan 2026, REF is Feb 2026)", () => {
      const scheme = getScheme(
        calculateEntitlements(ucFamily(9, 2022), schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(false);
      expect(scheme?.reasons).toContainEqual(
        expect.stringContaining("3 or older"),
      );
    });

    it("born Aug 2022 — too old (turns 3 Aug 2025, eligible until Sep 2025)", () => {
      const scheme = getScheme(
        calculateEntitlements(ucFamily(8, 2022), schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(false);
      expect(scheme?.reasons).toContainEqual(
        expect.stringContaining("3 or older"),
      );
    });
  });

  describe("15h 2yo — fostered and DLA auto-eligibility", () => {
    it("fostered child is automatically eligible (no income caveats)", () => {
      const data = validFamily({
        qualifyingBenefits: [],
        children: [
          validChild({ birthMonth: 10, birthYear: 2023, isFostered: true }),
        ],
      });
      const scheme = getScheme(
        calculateEntitlements(data, schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(true);
      expect(scheme?.reasons).toContainEqual(
        expect.stringContaining("looked-after"),
      );
      expect(scheme?.caveats).toHaveLength(0);
    });

    it("child receiving DLA is automatically eligible (no income caveats)", () => {
      const data = validFamily({
        qualifyingBenefits: [],
        children: [
          validChild({
            birthMonth: 10,
            birthYear: 2023,
            hasSEND: true,
            sendDetails: {
              receivesDLA: true,
              receivesPIP: false,
              isRegisteredBlind: false,
            },
          }),
        ],
      });
      const scheme = getScheme(
        calculateEntitlements(data, schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(true);
      expect(scheme?.reasons).toContainEqual(
        expect.stringContaining("Disability Living Allowance"),
      );
      expect(scheme?.caveats).toHaveLength(0);
    });

    it("hasSEND with PIP only does not auto-qualify (falls through to income routes)", () => {
      const data = validFamily({
        qualifyingBenefits: [],
        children: [
          validChild({
            birthMonth: 10,
            birthYear: 2023,
            hasSEND: true,
            sendDetails: {
              receivesDLA: false,
              receivesPIP: true,
              isRegisteredBlind: false,
            },
          }),
        ],
      });
      const scheme = getScheme(
        calculateEntitlements(data, schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(false);
    });

    it("hasSEND with none-of-the-above does not auto-qualify", () => {
      const data = validFamily({
        qualifyingBenefits: [],
        children: [
          validChild({
            birthMonth: 10,
            birthYear: 2023,
            hasSEND: true,
            sendDetails: {
              receivesDLA: false,
              receivesPIP: false,
              isRegisteredBlind: false,
            },
          }),
        ],
      });
      const scheme = getScheme(
        calculateEntitlements(data, schemes, REF),
        0,
        "15_hours_2_year_olds",
      );
      expect(scheme?.eligible).toBe(false);
    });
  });

  // --- Study scheme tests (information-only) ---

  describe("Care to Learn", () => {
    const studyingFEParent = (
      overrides: Partial<PersonData> = {},
    ): PersonData =>
      validPerson({
        ageBracket: "18-20",
        isStudying: true,
        studyLevel: "further_education",
        courseIsPubliclyFunded: true,
        ...overrides,
      });

    it("eligible: young parent studying publicly-funded FE in England", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEParent(),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "care_to_learn")?.eligible).toBe(true);
    });

    it("eligible: 16-17 parent studying school/sixth form", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEParent({
          ageBracket: "16-17",
          studyLevel: "school_sixth_form",
        }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "care_to_learn")?.eligible).toBe(true);
    });

    it("includes age caveat when eligible", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEParent(),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      const scheme = getScheme(result, 0, "care_to_learn");
      expect(scheme?.caveats).toContainEqual(
        expect.objectContaining({ code: "care_to_learn_age_caveat" }),
      );
    });

    it("ineligible: parent is 21+", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEParent({ ageBracket: "21+" }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "care_to_learn")?.eligible).toBe(false);
      expect(getScheme(result, 0, "care_to_learn")?.reasons).toContainEqual(
        expect.stringContaining("under 20"),
      );
    });

    it("ineligible: parent is not studying", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: validPerson({ ageBracket: "18-20" }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "care_to_learn")?.eligible).toBe(false);
      expect(getScheme(result, 0, "care_to_learn")?.reasons).toContainEqual(
        expect.stringContaining("No parent is currently studying"),
      );
    });

    it("ineligible: studying HE (wrong level)", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEParent({ studyLevel: "higher_education" }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "care_to_learn")?.eligible).toBe(false);
      expect(getScheme(result, 0, "care_to_learn")?.reasons).toContainEqual(
        expect.stringContaining("school, sixth form, or further education"),
      );
    });

    it("ineligible: course not publicly funded", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEParent({ courseIsPubliclyFunded: false }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "care_to_learn")?.eligible).toBe(false);
      expect(getScheme(result, 0, "care_to_learn")?.reasons).toContainEqual(
        expect.stringContaining("not publicly funded"),
      );
    });

    it("ineligible: parent is an apprentice", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEParent({ isApprentice: true }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "care_to_learn")?.eligible).toBe(false);
    });

    it("ineligible: not in England", () => {
      const data = validFamily({
        location: { postcode: "EH1 1AA", ladCodes: ["S12000036"] },
        household: { hasPartner: false },
        user: studyingFEParent(),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "care_to_learn")?.eligible).toBe(false);
      expect(getScheme(result, 0, "care_to_learn")?.reasons).toContainEqual(
        expect.stringContaining("England"),
      );
    });

    it("ineligible: NRPF residency", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEParent({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "care_to_learn")?.eligible).toBe(false);
      expect(getScheme(result, 0, "care_to_learn")?.reasons).toContainEqual(
        expect.stringContaining("residency"),
      );
    });

    it("eligible via partner: user is 21+ but partner is young and studying FE", () => {
      const data = validFamily({
        household: { hasPartner: true },
        user: validPerson({ ageBracket: "21+" }),
        partner: studyingFEParent(),
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "care_to_learn")?.eligible).toBe(true);
    });
  });

  describe("Learner Support", () => {
    const studyingFEAdult = (overrides: Partial<PersonData> = {}): PersonData =>
      validPerson({
        ageBracket: "21+",
        isStudying: true,
        studyLevel: "further_education",
        ...overrides,
      });

    it("eligible: parent 21+ studying FE", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEAdult(),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "learner_support")?.eligible).toBe(true);
    });

    it("eligible: parent 18-20 studying FE", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEAdult({ ageBracket: "18-20" }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "learner_support")?.eligible).toBe(true);
    });

    it("includes age caveat when eligible", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEAdult(),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      const scheme = getScheme(result, 0, "learner_support");
      expect(scheme?.caveats).toContainEqual(
        expect.objectContaining({ code: "learner_support_age_caveat" }),
      );
    });

    it("ineligible: not studying", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: validPerson({ ageBracket: "21+" }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "learner_support")?.eligible).toBe(false);
      expect(getScheme(result, 0, "learner_support")?.reasons).toContainEqual(
        expect.stringContaining("No parent is currently studying"),
      );
    });

    it("ineligible: studying HE (wrong level)", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEAdult({ studyLevel: "higher_education" }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "learner_support")?.eligible).toBe(false);
      expect(getScheme(result, 0, "learner_support")?.reasons).toContainEqual(
        expect.stringContaining("further education"),
      );
    });

    it("ineligible: studying school/sixth form (wrong level)", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEAdult({ studyLevel: "school_sixth_form" }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "learner_support")?.eligible).toBe(false);
      expect(getScheme(result, 0, "learner_support")?.reasons).toContainEqual(
        expect.stringContaining("further education"),
      );
    });

    it("ineligible: parent 16-17 (too young)", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingFEAdult({ ageBracket: "16-17" }),
        partner: null,
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "learner_support")?.eligible).toBe(false);
      expect(getScheme(result, 0, "learner_support")?.reasons).toContainEqual(
        expect.stringContaining("19 or over"),
      );
    });

    it("eligible via partner: user not studying, partner studying FE", () => {
      const data = validFamily({
        household: { hasPartner: true },
        user: validPerson(),
        partner: studyingFEAdult(),
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "learner_support")?.eligible).toBe(true);
    });
  });

  describe("Childcare Grant", () => {
    const studyingHEParent = (
      overrides: Partial<PersonData> = {},
    ): PersonData =>
      validPerson({
        isStudying: true,
        studyLevel: "higher_education",
        isFullTimeStudent: true,
        eligibleForStudentFinance: true,
        ...overrides,
      });

    it("eligible: full-time HE student with student finance, child under 15, England", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingHEParent(),
        partner: null,
        children: [validChild({ birthMonth: 6, birthYear: 2015 })], // ~10yo
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "childcare_grant")?.eligible).toBe(true);
    });

    it("includes income caveat when eligible", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingHEParent(),
        partner: null,
        children: [validChild({ birthMonth: 6, birthYear: 2015 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      const scheme = getScheme(result, 0, "childcare_grant");
      expect(scheme?.caveats).toContainEqual(
        expect.objectContaining({ code: "childcare_grant_income_caveat" }),
      );
    });

    it("ineligible: not full-time", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingHEParent({ isFullTimeStudent: false }),
        partner: null,
        children: [validChild({ birthMonth: 6, birthYear: 2015 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "childcare_grant")?.eligible).toBe(false);
      expect(getScheme(result, 0, "childcare_grant")?.reasons).toContainEqual(
        expect.stringContaining("full-time"),
      );
    });

    it("ineligible: not eligible for student finance", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingHEParent({ eligibleForStudentFinance: false }),
        partner: null,
        children: [validChild({ birthMonth: 6, birthYear: 2015 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "childcare_grant")?.eligible).toBe(false);
      expect(getScheme(result, 0, "childcare_grant")?.reasons).toContainEqual(
        expect.stringContaining("student finance"),
      );
    });

    it("ineligible: child aged 15+ (non-SEND)", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingHEParent(),
        partner: null,
        children: [validChild({ birthMonth: 6, birthYear: 2010 })], // ~15yo
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "childcare_grant")?.eligible).toBe(false);
      expect(getScheme(result, 0, "childcare_grant")?.reasons).toContainEqual(
        expect.stringContaining("15 or older"),
      );
    });

    it("eligible: SEND child aged 16 (under 17 threshold)", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingHEParent(),
        partner: null,
        children: [
          validChild({
            birthMonth: 6,
            birthYear: 2010, // ~15yo
            hasSEND: true,
            sendDetails: {
              receivesDLA: true,
              receivesPIP: false,
              isRegisteredBlind: false,
            },
          }),
        ],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "childcare_grant")?.eligible).toBe(true);
    });

    it("ineligible: SEND child aged 17+", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingHEParent(),
        partner: null,
        children: [
          validChild({
            birthMonth: 6,
            birthYear: 2008, // ~17yo
            hasSEND: true,
            sendDetails: {
              receivesDLA: true,
              receivesPIP: false,
              isRegisteredBlind: false,
            },
          }),
        ],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "childcare_grant")?.eligible).toBe(false);
      expect(getScheme(result, 0, "childcare_grant")?.reasons).toContainEqual(
        expect.stringContaining("17 or older"),
      );
    });

    it("ineligible: not in England", () => {
      const data = validFamily({
        location: { postcode: "EH1 1AA", ladCodes: ["S12000036"] },
        household: { hasPartner: false },
        user: studyingHEParent(),
        partner: null,
        children: [validChild({ birthMonth: 6, birthYear: 2015 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "childcare_grant")?.eligible).toBe(false);
      expect(getScheme(result, 0, "childcare_grant")?.reasons).toContainEqual(
        expect.stringContaining("England"),
      );
    });

    it("ineligible: not studying", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: validPerson(),
        partner: null,
        children: [validChild({ birthMonth: 6, birthYear: 2015 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "childcare_grant")?.eligible).toBe(false);
      expect(getScheme(result, 0, "childcare_grant")?.reasons).toContainEqual(
        expect.stringContaining("No parent is currently studying"),
      );
    });

    it("ineligible: studying FE (wrong level)", () => {
      const data = validFamily({
        household: { hasPartner: false },
        user: studyingHEParent({ studyLevel: "further_education" }),
        partner: null,
        children: [validChild({ birthMonth: 6, birthYear: 2015 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "childcare_grant")?.eligible).toBe(false);
      expect(getScheme(result, 0, "childcare_grant")?.reasons).toContainEqual(
        expect.stringContaining("higher education"),
      );
    });

    it("eligible via partner: user not studying, partner is qualifying HE student", () => {
      const data = validFamily({
        household: { hasPartner: true },
        user: validPerson(),
        partner: studyingHEParent(),
        children: [validChild({ birthMonth: 6, birthYear: 2015 })],
      });
      const result = calculateEntitlements(data, schemes, REF);
      expect(getScheme(result, 0, "childcare_grant")?.eligible).toBe(true);
    });
  });

  describe("non-studying families are ineligible for all study schemes", () => {
    const data = validFamily({
      children: [validChild({ birthMonth: 6, birthYear: 2022 })],
    });
    const result = calculateEntitlements(data, schemes, REF);

    it("ineligible for Care to Learn", () => {
      expect(getScheme(result, 0, "care_to_learn")?.eligible).toBe(false);
    });

    it("ineligible for Learner Support", () => {
      expect(getScheme(result, 0, "learner_support")?.eligible).toBe(false);
    });

    it("ineligible for Childcare Grant", () => {
      expect(getScheme(result, 0, "childcare_grant")?.eligible).toBe(false);
    });
  });
});

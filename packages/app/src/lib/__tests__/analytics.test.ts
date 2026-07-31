import { describe, it, expect } from "vitest";
import type { FormLocalStorageData } from "@/types/formData";
import {
  getLocationProps,
  getPartnerProps,
  getImmigrationProps,
  getWorkingProps,
  getBenefitsProps,
  getChildrenProps,
  getChildcareProps,
} from "../analytics";

function makeFormData(
  overrides: Partial<FormLocalStorageData> = {},
): FormLocalStorageData {
  return {
    schemaVersion: 7,
    location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] },
    household: { hasPartner: null },
    user: {
      isApprentice: null,
      firstYearApprentice: null,
      isSelfEmployed: null,
      selfEmployedLessThanTwelveMonths: null,
      ageBracket: null,
      workingStatus: null,
      receivesQualifyingAllowance: null,
      startingWorkNextMonth: null,
      hasLimitedCapacityForWork: null,
      hasNationalInsuranceNumber: null,
      residencyStatus: null,
      isStudying: null,
      studyLevel: null,
      isFullTimeStudent: null,
      courseIsPubliclyFunded: null,
      eligibleForStudentFinance: null,
    },
    partner: null,
    qualifyingBenefits: null,
    ucIncomeBelowThreshold: null,
    nrpfIncomeUnderThreshold: null,
    nrpfSavingsUnderLimit: null,
    children: [],
    shortlistedProviders: [],
    ...overrides,
  };
}

describe("getLocationProps", () => {
  it("returns first English LAD code", () => {
    const form = makeFormData({
      location: { postcode: "SW1A 1AA", ladCodes: ["E09000033", "E10000025"] },
    });
    expect(getLocationProps(form, 7)).toEqual({
      lad25cd: "E09000033",
      iod_decile: 7,
    });
  });

  it("falls back to non-English code when no E-prefix exists", () => {
    const form = makeFormData({
      location: { postcode: "AB1 0AA", ladCodes: ["S12000033"] },
    });
    expect(getLocationProps(form)).toEqual({
      lad25cd: "S12000033",
      iod_decile: null,
    });
  });

  it("returns null when no LAD codes exist", () => {
    const form = makeFormData({
      location: { postcode: "", ladCodes: [] },
    });
    expect(getLocationProps(form)).toEqual({
      lad25cd: null,
      iod_decile: null,
    });
  });

  it("passes through iodDecile", () => {
    const form = makeFormData();
    expect(getLocationProps(form, 3).iod_decile).toBe(3);
  });

  it("returns iod_decile null when not provided", () => {
    const form = makeFormData();
    expect(getLocationProps(form).iod_decile).toBeNull();
  });
});

describe("getPartnerProps", () => {
  it("returns true when has partner", () => {
    const form = makeFormData({ household: { hasPartner: true } });
    expect(getPartnerProps(form)).toEqual({ has_partner: true });
  });

  it("returns false when no partner", () => {
    const form = makeFormData({ household: { hasPartner: false } });
    expect(getPartnerProps(form)).toEqual({ has_partner: false });
  });

  it("returns false when null", () => {
    const form = makeFormData({ household: { hasPartner: null } });
    expect(getPartnerProps(form)).toEqual({ has_partner: false });
  });
});

describe("getImmigrationProps", () => {
  it("british_irish_citizen is settled", () => {
    const form = makeFormData();
    form.user.residencyStatus = "british_irish_citizen";
    expect(getImmigrationProps(form)).toEqual({ settled_in_uk: true });
  });

  it("settled_status is settled", () => {
    const form = makeFormData();
    form.user.residencyStatus = "settled_status";
    expect(getImmigrationProps(form)).toEqual({ settled_in_uk: true });
  });

  it("pre_settled_status is not settled", () => {
    const form = makeFormData();
    form.user.residencyStatus = "pre_settled_status";
    expect(getImmigrationProps(form)).toEqual({ settled_in_uk: false });
  });

  it("no_recourse_to_public_funds is not settled", () => {
    const form = makeFormData();
    form.user.residencyStatus = "no_recourse_to_public_funds";
    expect(getImmigrationProps(form)).toEqual({ settled_in_uk: false });
  });

  it("null is not settled", () => {
    const form = makeFormData();
    expect(getImmigrationProps(form)).toEqual({ settled_in_uk: false });
  });

  it("never exposes the raw status value", () => {
    const form = makeFormData();
    form.user.residencyStatus = "pre_settled_status";
    const result = getImmigrationProps(form);
    expect(Object.values(result)).not.toContain("pre_settled_status");
  });
});

describe("getWorkingProps", () => {
  it("user earning above NMW is working", () => {
    const form = makeFormData();
    form.user.workingStatus = "earning_above_nmw";
    expect(getWorkingProps(form).working).toBe(true);
  });

  it("user not_working is not working", () => {
    const form = makeFormData();
    form.user.workingStatus = "not_working";
    expect(getWorkingProps(form).working).toBe(false);
  });

  it("user null status is not working", () => {
    const form = makeFormData();
    expect(getWorkingProps(form).working).toBe(false);
  });

  it("partner working makes household working", () => {
    const form = makeFormData();
    form.user.workingStatus = "not_working";
    form.partner = { ...form.user, workingStatus: "earning_below_nmw" };
    expect(getWorkingProps(form).working).toBe(true);
  });

  it("partner null does not affect result", () => {
    const form = makeFormData();
    form.user.workingStatus = "earning_above_nmw";
    form.partner = null;
    expect(getWorkingProps(form).working).toBe(true);
  });

  it("passes through is_studying", () => {
    const form = makeFormData();
    form.user.isStudying = true;
    expect(getWorkingProps(form).is_studying).toBe(true);
  });

  it("is_studying defaults to false when null", () => {
    const form = makeFormData();
    expect(getWorkingProps(form).is_studying).toBe(false);
  });

  it("never exposes income band or specific working status", () => {
    const form = makeFormData();
    form.user.workingStatus = "income_over_100k";
    const result = getWorkingProps(form);
    expect(Object.values(result)).not.toContain("income_over_100k");
  });
});

describe("getBenefitsProps", () => {
  it("universal_credit means receives benefits", () => {
    const form = makeFormData({ qualifyingBenefits: ["universal_credit"] });
    expect(getBenefitsProps(form)).toEqual({ receives_benefits: true });
  });

  it("multiple benefits means receives benefits", () => {
    const form = makeFormData({
      qualifyingBenefits: ["universal_credit", "pension_credit"],
    });
    expect(getBenefitsProps(form)).toEqual({ receives_benefits: true });
  });

  it("[none] means does not receive benefits", () => {
    const form = makeFormData({ qualifyingBenefits: ["none"] });
    expect(getBenefitsProps(form)).toEqual({ receives_benefits: false });
  });

  it("empty array means does not receive benefits", () => {
    const form = makeFormData({ qualifyingBenefits: [] });
    expect(getBenefitsProps(form)).toEqual({ receives_benefits: false });
  });

  it("null means does not receive benefits", () => {
    const form = makeFormData({ qualifyingBenefits: null });
    expect(getBenefitsProps(form)).toEqual({ receives_benefits: false });
  });

  it("never exposes which specific benefits", () => {
    const form = makeFormData({
      qualifyingBenefits: ["universal_credit", "esa"],
    });
    const result = getBenefitsProps(form);
    expect(Object.values(result)).not.toContain("universal_credit");
    expect(Object.values(result)).not.toContain("esa");
  });
});

describe("getChildrenProps", () => {
  it("returns child_count capped at 3", () => {
    const form = makeFormData({
      children: [
        {
          id: 1,
          firstName: "",
          birthMonth: 1,
          birthYear: 2024,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [],
        },
        {
          id: 2,
          firstName: "",
          birthMonth: 6,
          birthYear: 2023,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [],
        },
        {
          id: 3,
          firstName: "",
          birthMonth: 3,
          birthYear: 2022,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [],
        },
        {
          id: 4,
          firstName: "",
          birthMonth: 9,
          birthYear: 2021,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [],
        },
      ],
    });
    expect(getChildrenProps(form).child_count).toBe(3);
  });

  it("youngest under 5 years returns 0-4 band", () => {
    const now = new Date();
    const form = makeFormData({
      children: [
        {
          id: 1,
          firstName: "",
          birthMonth: now.getMonth() + 1,
          birthYear: now.getFullYear() - 2,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [],
        },
      ],
    });
    expect(getChildrenProps(form).youngest_band).toBe("0-4");
  });

  it("youngest 5+ years returns 5+ band", () => {
    const now = new Date();
    const form = makeFormData({
      children: [
        {
          id: 1,
          firstName: "",
          birthMonth: now.getMonth() + 1,
          birthYear: now.getFullYear() - 6,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [],
        },
      ],
    });
    expect(getChildrenProps(form).youngest_band).toBe("5+");
  });

  it("no birth data defaults to 5+", () => {
    const form = makeFormData({
      children: [
        {
          id: 1,
          firstName: "",
          birthMonth: null,
          birthYear: null,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [],
        },
      ],
    });
    expect(getChildrenProps(form).youngest_band).toBe("5+");
  });

  it("never exposes child names, exact birth dates, SEND, or foster status", () => {
    const form = makeFormData({
      children: [
        {
          id: 1,
          firstName: "Alice",
          birthMonth: 3,
          birthYear: 2022,
          hasSEND: true,
          sendDetails: {
            receivesDLA: true,
            receivesPIP: false,
            isRegisteredBlind: false,
          },
          isFostered: true,
          hasEHCP: true,
          hasLeftCareForAdoptionOrSpecialGuardianship: true,
          childcareSelections: [],
        },
      ],
    });
    const result = getChildrenProps(form);
    const values = JSON.stringify(result);
    expect(values).not.toContain("Alice");
    expect(values).not.toContain("2022");
    expect(values).not.toContain("DLA");
    expect(values).not.toContain("foster");
    expect(values).not.toContain("EHCP");
  });
});

describe("getChildcareProps", () => {
  it("deduplicates care types across children", () => {
    const form = makeFormData({
      children: [
        {
          id: 1,
          firstName: "",
          birthMonth: 1,
          birthYear: 2023,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [
            { id: 1, careType: "private_nursery" as const, providerId: null },
          ],
        },
        {
          id: 2,
          firstName: "",
          birthMonth: 6,
          birthYear: 2022,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [
            { id: 2, careType: "private_nursery" as const, providerId: null },
          ],
        },
      ],
    });
    expect(getChildcareProps(form).care_types_sought).toEqual([
      "private_nursery",
    ]);
  });

  it("sorts care types alphabetically", () => {
    const form = makeFormData({
      children: [
        {
          id: 1,
          firstName: "",
          birthMonth: 1,
          birthYear: 2023,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [
            { id: 1, careType: "childminder" as const, providerId: null },
            { id: 2, careType: "breakfast_club" as const, providerId: null },
          ],
        },
      ],
    });
    expect(getChildcareProps(form).care_types_sought).toEqual([
      "breakfast_club",
      "childminder",
    ]);
  });

  it("returns empty array when no selections", () => {
    const form = makeFormData({ children: [] });
    expect(getChildcareProps(form).care_types_sought).toEqual([]);
  });

  it("never exposes provider IDs", () => {
    const form = makeFormData({
      children: [
        {
          id: 1,
          firstName: "",
          birthMonth: 1,
          birthYear: 2023,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [
            {
              id: 1,
              careType: "childminder" as const,
              providerId: "provider-abc-123",
            },
          ],
        },
      ],
    });
    const result = getChildcareProps(form);
    const values = JSON.stringify(result);
    expect(values).not.toContain("provider-abc-123");
  });
});

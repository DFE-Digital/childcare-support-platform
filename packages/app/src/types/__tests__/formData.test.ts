import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { validateFormData, normaliseFormData } from "../formData";
import type { FormLocalStorageData, FormChildData } from "../formData";
import type { ChildcareSelection } from "@bsil/calculator";

// Pin to March 2026 so age calculations are deterministic
const NOW = new Date(2026, 2, 15);

const ALL_LABELS = [
  "Living situation",
  "Immigration status",
  "Working situation",
  "Benefits",
  "Your children",
  "Childcare arrangements",
];

function makePerson(
  overrides: Partial<FormLocalStorageData["user"]> = {},
): FormLocalStorageData["user"] {
  return {
    isApprentice: false,
    firstYearApprentice: null,
    isSelfEmployed: false,
    selfEmployedLessThanTwelveMonths: null,
    ageBracket: "21+",
    workingStatus: "earning_above_nmw",
    receivesQualifyingAllowance: false,
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

function sel(careType: string): ChildcareSelection {
  return {
    id: 1,
    careType: careType as ChildcareSelection["careType"],
    providerId: null,
  };
}

/** Build a child born `ageMonths` months before NOW */
function makeChild(
  ageMonths: number,
  selections: ChildcareSelection[] = [],
  id = 1,
): FormChildData {
  const totalMonths = NOW.getFullYear() * 12 + (NOW.getMonth() + 1) - ageMonths;
  const birthYear = Math.floor((totalMonths - 1) / 12);
  const birthMonth = totalMonths - birthYear * 12;
  return {
    id,
    firstName: `Child ${id}`,
    birthMonth,
    birthYear,
    hasSEND: false,
    sendDetails: null,
    isFostered: false,
    hasEHCP: false,
    hasLeftCareForAdoptionOrSpecialGuardianship: false,
    childcareSelections: selections,
  };
}

function makeForm(
  overrides: Partial<FormLocalStorageData> = {},
): FormLocalStorageData {
  return {
    schemaVersion: 1,
    location: { postcode: "OX1 1AA", ladCodes: ["E07000178"] },
    household: { hasPartner: false },
    user: makePerson(),
    partner: null,
    ucIncomeBelowThreshold: null,
    nrpfIncomeUnderThreshold: null,
    nrpfSavingsUnderLimit: null,
    qualifyingBenefits: [],
    children: [makeChild(36)],
    shortlistedProviders: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.useFakeTimers({ now: NOW });
});

afterEach(() => {
  vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// Living situation
// ---------------------------------------------------------------------------
describe("Living situation", () => {
  it("valid when hasPartner is false", () => {
    const result = validateFormData(
      makeForm({ household: { hasPartner: false } }),
      ALL_LABELS,
    );
    expect(result).not.toContain("Living situation");
  });

  it("valid when hasPartner is true", () => {
    const result = validateFormData(
      makeForm({
        household: { hasPartner: true },
        partner: makePerson(),
      }),
      ALL_LABELS,
    );
    expect(result).not.toContain("Living situation");
  });

  it("invalid when hasPartner is null", () => {
    const result = validateFormData(
      makeForm({ household: { hasPartner: null } }),
      ALL_LABELS,
    );
    expect(result).toContain("Living situation");
  });

  it("skipped when label not in stepLabels", () => {
    const result = validateFormData(
      makeForm({ household: { hasPartner: null } }),
      ALL_LABELS.filter((l) => l !== "Living situation"),
    );
    expect(result).not.toContain("Living situation");
  });
});

// ---------------------------------------------------------------------------
// Immigration status
// ---------------------------------------------------------------------------
describe("Immigration status", () => {
  it("valid when user has residencyStatus and NI number", () => {
    const result = validateFormData(makeForm(), ALL_LABELS);
    expect(result).not.toContain("Immigration status");
  });

  it("invalid when user residencyStatus is null", () => {
    const result = validateFormData(
      makeForm({ user: makePerson({ residencyStatus: null }) }),
      ALL_LABELS,
    );
    expect(result).toContain("Immigration status");
  });

  it("invalid when user hasNationalInsuranceNumber is null", () => {
    const result = validateFormData(
      makeForm({ user: makePerson({ hasNationalInsuranceNumber: null }) }),
      ALL_LABELS,
    );
    expect(result).toContain("Immigration status");
  });

  it("valid when no partner and partner fields are null", () => {
    const result = validateFormData(
      makeForm({ household: { hasPartner: false }, partner: null }),
      ALL_LABELS,
    );
    expect(result).not.toContain("Immigration status");
  });

  it("invalid when hasPartner and partner residencyStatus is null", () => {
    const result = validateFormData(
      makeForm({
        household: { hasPartner: true },
        partner: makePerson({ residencyStatus: null }),
      }),
      ALL_LABELS,
    );
    expect(result).toContain("Immigration status");
  });

  it("invalid when hasPartner and partner NI number is null", () => {
    const result = validateFormData(
      makeForm({
        household: { hasPartner: true },
        partner: makePerson({ hasNationalInsuranceNumber: null }),
      }),
      ALL_LABELS,
    );
    expect(result).toContain("Immigration status");
  });
});

// ---------------------------------------------------------------------------
// Working situation
// ---------------------------------------------------------------------------
describe("Working situation", () => {
  it("valid when user has all required fields", () => {
    const result = validateFormData(makeForm(), ALL_LABELS);
    expect(result).not.toContain("Working situation");
  });

  it("invalid when user isApprentice is null", () => {
    const result = validateFormData(
      makeForm({ user: makePerson({ isApprentice: null }) }),
      ALL_LABELS,
    );
    expect(result).toContain("Working situation");
  });

  it("invalid when user workingStatus is null", () => {
    const result = validateFormData(
      makeForm({ user: makePerson({ workingStatus: null }) }),
      ALL_LABELS,
    );
    expect(result).toContain("Working situation");
  });

  it("invalid when user is not apprentice and isSelfEmployed is null", () => {
    const result = validateFormData(
      makeForm({
        user: makePerson({ isApprentice: false, isSelfEmployed: null }),
      }),
      ALL_LABELS,
    );
    expect(result).toContain("Working situation");
  });

  it("valid when user is apprentice (isSelfEmployed not checked)", () => {
    const result = validateFormData(
      makeForm({
        user: makePerson({ isApprentice: true, isSelfEmployed: null }),
      }),
      ALL_LABELS,
    );
    expect(result).not.toContain("Working situation");
  });

  it("invalid when hasPartner and partner has null working fields", () => {
    const result = validateFormData(
      makeForm({
        household: { hasPartner: true },
        partner: makePerson({ workingStatus: null }),
      }),
      ALL_LABELS,
    );
    expect(result).toContain("Working situation");
  });
});

// ---------------------------------------------------------------------------
// Benefits
// ---------------------------------------------------------------------------
describe("Benefits", () => {
  it("valid when qualifyingBenefits is empty array", () => {
    const result = validateFormData(
      makeForm({ qualifyingBenefits: [] }),
      ALL_LABELS,
    );
    expect(result).not.toContain("Benefits");
  });

  it("valid when qualifyingBenefits has selections", () => {
    const result = validateFormData(
      makeForm({ qualifyingBenefits: ["universal_credit"] }),
      ALL_LABELS,
    );
    expect(result).not.toContain("Benefits");
  });

  it("invalid when qualifyingBenefits is null", () => {
    const result = validateFormData(
      makeForm({ qualifyingBenefits: null }),
      ALL_LABELS,
    );
    expect(result).toContain("Benefits");
  });

  it("invalid when all parents NRPF and real benefits selected", () => {
    const result = validateFormData(
      makeForm({
        user: makePerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        qualifyingBenefits: ["universal_credit"],
      }),
      ALL_LABELS,
    );
    expect(result).toContain("Benefits");
  });

  it("valid when all parents NRPF and only 'none' selected", () => {
    const result = validateFormData(
      makeForm({
        user: makePerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        qualifyingBenefits: ["none"],
      }),
      ALL_LABELS,
    );
    expect(result).not.toContain("Benefits");
  });

  it("valid when only one parent NRPF with benefits", () => {
    const result = validateFormData(
      makeForm({
        household: { hasPartner: true },
        user: makePerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        partner: makePerson({
          residencyStatus: "british_irish_citizen",
        }),
        qualifyingBenefits: ["universal_credit"],
      }),
      ALL_LABELS,
    );
    expect(result).not.toContain("Benefits");
  });
});

// ---------------------------------------------------------------------------
// Your children
// ---------------------------------------------------------------------------
describe("Your children", () => {
  it("valid when children have all required fields", () => {
    const result = validateFormData(makeForm(), ALL_LABELS);
    expect(result).not.toContain("Your children");
  });

  it("invalid when children array is empty", () => {
    const result = validateFormData(makeForm({ children: [] }), ALL_LABELS);
    expect(result).toContain("Your children");
  });

  it("invalid when a child has null birthMonth", () => {
    const child = makeChild(36);
    child.birthMonth = null;
    const result = validateFormData(
      makeForm({ children: [child] }),
      ALL_LABELS,
    );
    expect(result).toContain("Your children");
  });

  it("invalid when a child has null birthYear", () => {
    const child = makeChild(36);
    child.birthYear = null;
    const result = validateFormData(
      makeForm({ children: [child] }),
      ALL_LABELS,
    );
    expect(result).toContain("Your children");
  });

  it("invalid when a child has null hasSEND", () => {
    const child = makeChild(36);
    child.hasSEND = null;
    const result = validateFormData(
      makeForm({ children: [child] }),
      ALL_LABELS,
    );
    expect(result).toContain("Your children");
  });

  it("invalid when a child has null isFostered", () => {
    const child = makeChild(36);
    child.isFostered = null;
    const result = validateFormData(
      makeForm({ children: [child] }),
      ALL_LABELS,
    );
    expect(result).toContain("Your children");
  });

  it("invalid when all parents NRPF with eligible 2yo and nrpfIncomeUnderThreshold is null", () => {
    const child = makeChild(30); // ~2.5yo, term-eligible
    child.hasEHCP = false;
    child.hasLeftCareForAdoptionOrSpecialGuardianship = false;
    const result = validateFormData(
      makeForm({
        user: makePerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        children: [child],
        nrpfIncomeUnderThreshold: null,
        nrpfSavingsUnderLimit: 16000,
      }),
      ALL_LABELS,
    );
    expect(result).toContain("Your children");
  });

  it("invalid when all parents NRPF with eligible 2yo and nrpfSavingsUnderLimit is null", () => {
    const child = makeChild(30);
    child.hasEHCP = false;
    child.hasLeftCareForAdoptionOrSpecialGuardianship = false;
    const result = validateFormData(
      makeForm({
        user: makePerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        children: [child],
        nrpfIncomeUnderThreshold: 26500,
        nrpfSavingsUnderLimit: null,
      }),
      ALL_LABELS,
    );
    expect(result).toContain("Your children");
  });

  it("valid when only one parent NRPF (no NRPF questions required)", () => {
    const child = makeChild(30);
    child.hasEHCP = false;
    child.hasLeftCareForAdoptionOrSpecialGuardianship = false;
    const result = validateFormData(
      makeForm({
        household: { hasPartner: true },
        user: makePerson({
          residencyStatus: "no_recourse_to_public_funds",
        }),
        partner: makePerson({
          residencyStatus: "british_irish_citizen",
        }),
        children: [child],
        nrpfIncomeUnderThreshold: null,
        nrpfSavingsUnderLimit: null,
      }),
      ALL_LABELS,
    );
    expect(result).not.toContain("Your children");
  });
});

// ---------------------------------------------------------------------------
// Childcare arrangements
// ---------------------------------------------------------------------------
describe("Childcare arrangements", () => {
  it("valid when at least one estimatable child has a selection", () => {
    const form = makeForm({
      children: [makeChild(36, [sel("private_nursery")])],
    });
    const result = validateFormData(form, ALL_LABELS);
    expect(result).not.toContain("Childcare arrangements");
  });

  it("invalid when no estimatable child has any selections", () => {
    const form = makeForm({
      children: [makeChild(36, [])],
    });
    const result = validateFormData(form, ALL_LABELS);
    expect(result).toContain("Childcare arrangements");
  });

  it("invalid when only big kids (60+ months) have selections", () => {
    const form = makeForm({
      children: [makeChild(36, [], 1), makeChild(72, [sel("childminder")], 2)],
    });
    const result = validateFormData(form, ALL_LABELS);
    expect(result).toContain("Childcare arrangements");
  });

  it("valid when big kids have no selections but a young child does", () => {
    const form = makeForm({
      children: [
        makeChild(36, [sel("private_nursery")], 1),
        makeChild(72, [], 2),
      ],
    });
    const result = validateFormData(form, ALL_LABELS);
    expect(result).not.toContain("Childcare arrangements");
  });

  it("valid when all children are big kids (no estimatable children)", () => {
    const form = makeForm({
      children: [makeChild(72, [], 1), makeChild(84, [], 2)],
    });
    const result = validateFormData(form, ALL_LABELS);
    expect(result).not.toContain("Childcare arrangements");
  });

  it("skipped when label not in stepLabels", () => {
    const form = makeForm({
      children: [makeChild(36, [])],
    });
    const result = validateFormData(
      form,
      ALL_LABELS.filter((l) => l !== "Childcare arrangements"),
    );
    expect(result).not.toContain("Childcare arrangements");
  });
});

// ---------------------------------------------------------------------------
// normaliseFormData
// ---------------------------------------------------------------------------
describe("normaliseFormData", () => {
  // --- strips ineligible selections ---

  it("strips private_nursery from a 60+ month child", () => {
    const form = makeForm({
      children: [makeChild(72, [sel("private_nursery")])],
    });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([]);
  });

  it("strips school_based_nursery from a child under 24 months", () => {
    const form = makeForm({
      children: [makeChild(23, [sel("school_based_nursery")])],
    });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([]);
  });

  it("strips school_based_nursery from a 60+ month child", () => {
    const form = makeForm({
      children: [makeChild(60, [sel("school_based_nursery")])],
    });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([]);
  });

  it("strips breakfast_club from a child under 48 months", () => {
    const form = makeForm({
      children: [makeChild(47, [sel("breakfast_club")])],
    });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([]);
  });

  it("strips after_school_club from a child under 48 months", () => {
    const form = makeForm({
      children: [makeChild(30, [sel("after_school_club")])],
    });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([]);
  });

  it("strips holiday_club from a child under 48 months", () => {
    const form = makeForm({ children: [makeChild(12, [sel("holiday_club")])] });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([]);
  });

  // --- keeps eligible selections ---

  it("keeps childminder at any age", () => {
    const s = sel("childminder");
    const form = makeForm({ children: [makeChild(12, [s])] });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([s]);

    const form2 = makeForm({ children: [makeChild(72, [s])] });
    const result2 = normaliseFormData(form2);
    expect(result2.children[0].childcareSelections).toEqual([s]);
  });

  it("keeps private_nursery on a 59-month child (boundary)", () => {
    const s = sel("private_nursery");
    const form = makeForm({ children: [makeChild(59, [s])] });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([s]);
  });

  it("keeps school_based_nursery on a 24-month child (boundary)", () => {
    const s = sel("school_based_nursery");
    const form = makeForm({ children: [makeChild(24, [s])] });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([s]);
  });

  it("keeps breakfast_club on a 48-month child (boundary)", () => {
    const s = sel("breakfast_club");
    const form = makeForm({ children: [makeChild(48, [s])] });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([s]);
  });

  // --- edge cases ---

  it("preserves children with null birth fields (no filtering)", () => {
    const s = sel("private_nursery");
    const child = makeChild(36, [s]);
    child.birthMonth = null;
    child.birthYear = null;
    const form = makeForm({ children: [child] });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([s]);
  });

  it("preserves children with no selections", () => {
    const form = makeForm({ children: [makeChild(72, [])] });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([]);
  });

  it("only strips from the affected child, not siblings", () => {
    const validSel = sel("private_nursery");
    const staleSel = sel("private_nursery");
    const young = makeChild(36, [validSel], 1);
    const old = makeChild(72, [staleSel], 2);
    const form = makeForm({ children: [young, old] });
    const result = normaliseFormData(form);
    expect(result.children[0].childcareSelections).toEqual([validSel]);
    expect(result.children[1].childcareSelections).toEqual([]);
  });

  it("preserves all other fields on the form", () => {
    const form = makeForm({
      children: [makeChild(72, [sel("private_nursery")])],
    });
    const result = normaliseFormData(form);
    expect(result.location).toEqual(form.location);
    expect(result.household).toEqual(form.household);
    expect(result.user).toEqual(form.user);
    expect(result.qualifyingBenefits).toEqual(form.qualifyingBenefits);
    expect(result.children[0].firstName).toEqual(form.children[0].firstName);
    expect(result.children[0].birthMonth).toEqual(form.children[0].birthMonth);
    expect(result.children[0].birthYear).toEqual(form.children[0].birthYear);
    expect(result.children[0].hasSEND).toEqual(form.children[0].hasSEND);
  });
});

// ---------------------------------------------------------------------------
// Cross-cutting
// ---------------------------------------------------------------------------
describe("multiple steps invalid", () => {
  it("returns multiple labels when several steps are invalid", () => {
    const result = validateFormData(
      makeForm({
        household: { hasPartner: null },
        qualifyingBenefits: null,
        children: [],
      }),
      ALL_LABELS,
    );
    expect(result).toContain("Living situation");
    expect(result).toContain("Benefits");
    expect(result).toContain("Your children");
  });

  it("returns empty array when all data is valid", () => {
    const form = makeForm({
      children: [makeChild(36, [sel("private_nursery")])],
    });
    const result = validateFormData(form, ALL_LABELS);
    expect(result).toEqual([]);
  });
});

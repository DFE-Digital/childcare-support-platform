import { describe, it, expect } from "vitest";
import type {
  LocalStorageData,
  PersonData,
  ChildData,
} from "../types/family.js";
import { validateLocalStorageData } from "./household.js";

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
    firstName: "Thomas",
    birthMonth: 3,
    birthYear: 2024,
    hasSEND: false,
    sendDetails: null,
    isFostered: false,
    hasEHCP: false,
    hasLeftCareForAdoptionOrSpecialGuardianship: false,
    childcareSelections: [
      {
        id: 1,
        careType: "private_nursery",
        sessions: {
          morning: { daysPerWeek: 5 },
          afternoon: { daysPerWeek: 3 },
        },
        providerId: "provider_1",
      },
    ],
    ...overrides,
  };
}

function validHousehold(
  overrides: Partial<LocalStorageData> = {},
): LocalStorageData {
  return {
    schemaVersion: 2,
    location: { postcode: "OX2 0AA", ladCodes: ["E07000178"] },
    household: { hasPartner: true },
    user: validPerson(),
    partner: validPerson(),
    qualifyingBenefits: [],
    ucIncomeBelowThreshold: false,
    nrpfIncomeUnderThreshold: 0,
    nrpfSavingsUnderLimit: 0,
    children: [validChild()],
    shortlistedProviders: ["provider_1"],
    ...overrides,
  };
}

describe("validateLocalStorageData", () => {
  it("accepts a valid two-parent household (thomas-and-emily pattern)", () => {
    const data = validHousehold({
      children: [
        validChild(),
        validChild({
          id: 2,
          firstName: "Emily",
          birthMonth: 9,
          birthYear: 2019,
          childcareSelections: [
            {
              id: 1,
              careType: "breakfast_club",
              daysPerWeek: 5,
              providerId: null,
            },
            {
              id: 2,
              careType: "after_school_club",
              daysPerWeek: 3,
              providerId: null,
            },
            {
              id: 3,
              careType: "childminder",
              hoursPerWeek: 7,
              weeksPerYear: 44,
              providerId: "provider_5",
            },
            {
              id: 4,
              careType: "holiday_club",
              daysPerYear: 20,
              providerId: null,
            },
          ],
        }),
      ],
    });
    const result = validateLocalStorageData(data);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it("accepts a valid single-parent household (priya pattern)", () => {
    const data = validHousehold({
      household: { hasPartner: false },
      partner: null,
      qualifyingBenefits: ["universal_credit"],
      user: validPerson({ workingStatus: "earning_below_nmw" }),
      children: [
        validChild({
          firstName: "Amir",
          childcareSelections: [
            {
              id: 1,
              careType: "school_based_nursery",
              sessions: { morning: { daysPerWeek: 5 } },
              providerId: "provider_2",
            },
          ],
        }),
      ],
    });
    const result = validateLocalStorageData(data);
    expect(result.valid).toBe(true);
  });

  it("accepts a household with carers allowance partner (nguyens pattern)", () => {
    const data = validHousehold({
      user: validPerson(),
      partner: validPerson({
        workingStatus: "not_working",
        receivesQualifyingAllowance: true,
      }),
      children: [
        validChild({
          firstName: "Lily",
          birthMonth: 6,
          birthYear: 2022,
          childcareSelections: [
            {
              id: 1,
              careType: "childminder",
              hoursPerWeek: 35,
              weeksPerYear: 44,
              providerId: "provider_6",
            },
          ],
        }),
      ],
    });
    const result = validateLocalStorageData(data);
    expect(result.valid).toBe(true);
  });

  it("rejects partner present when hasPartner is false", () => {
    const data = validHousehold({
      household: { hasPartner: false },
      partner: validPerson(),
    });
    const result = validateLocalStorageData(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "partner",
      message: "must be null when hasPartner is false",
    });
  });

  it("rejects partner null when hasPartner is true", () => {
    const data = validHousehold({
      household: { hasPartner: true },
      partner: null,
    });
    const result = validateLocalStorageData(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "partner",
      message: "must be present when hasPartner is true",
    });
  });

  it("rejects empty children array", () => {
    const data = validHousehold({ children: [] });
    const result = validateLocalStorageData(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "children",
      message: "must have at least one child",
    });
  });

  it("nests user validation errors with 'user' prefix", () => {
    const data = validHousehold({
      user: validPerson({ isApprentice: true, firstYearApprentice: null }),
    });
    const result = validateLocalStorageData(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "user.firstYearApprentice",
      message: "must be a boolean when isApprentice is true",
    });
  });

  it("nests partner validation errors with 'partner' prefix", () => {
    const data = validHousehold({
      partner: validPerson({
        isSelfEmployed: true,
        selfEmployedLessThanTwelveMonths: null,
      }),
    });
    const result = validateLocalStorageData(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "partner.selfEmployedLessThanTwelveMonths",
      message: "must be a boolean when isSelfEmployed is true",
    });
  });

  it("nests child validation errors with indexed path", () => {
    const data = validHousehold({
      children: [validChild(), validChild({ id: 2, firstName: "" })],
    });
    const result = validateLocalStorageData(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "children[1].firstName",
      message: "must not be empty",
    });
  });

  it("nests deeply through child → childcareSelection", () => {
    const data = validHousehold({
      children: [
        validChild({
          childcareSelections: [
            {
              id: 1,
              careType: "childminder",
              hoursPerWeek: 51,
              weeksPerYear: 44,
              providerId: null,
            },
          ],
        }),
      ],
    });
    const result = validateLocalStorageData(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "children[0].childcareSelections[0].hoursPerWeek",
      message: "must be between 1 and 50",
    });
  });

  it("accumulates errors from multiple sources", () => {
    const data = validHousehold({
      household: { hasPartner: true },
      partner: null,
      children: [validChild({ firstName: "" })],
      user: validPerson({ isApprentice: true, firstYearApprentice: null }),
    });
    const result = validateLocalStorageData(data);
    expect(result.valid).toBe(false);
    // partner missing + user.firstYearApprentice + children[0].firstName
    expect(result.errors.length).toBeGreaterThanOrEqual(3);
  });
});

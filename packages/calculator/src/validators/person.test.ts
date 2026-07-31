import { describe, it, expect } from "vitest";
import type { PersonData } from "../types/family.js";
import { validatePersonData } from "./person.js";

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

describe("validatePersonData", () => {
  it("accepts a valid non-apprentice, non-self-employed person", () => {
    const result = validatePersonData(validPerson());
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it("accepts a valid apprentice", () => {
    const result = validatePersonData(
      validPerson({
        isApprentice: true,
        firstYearApprentice: true,
        ageBracket: "18-20",
      }),
    );
    expect(result.valid).toBe(true);
  });

  it("accepts a valid self-employed person", () => {
    const result = validatePersonData(
      validPerson({
        isSelfEmployed: true,
        selfEmployedLessThanTwelveMonths: false,
      }),
    );
    expect(result.valid).toBe(true);
  });

  it("rejects firstYearApprentice=true when isApprentice is false", () => {
    const result = validatePersonData(
      validPerson({ isApprentice: false, firstYearApprentice: true }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "firstYearApprentice",
      message: "must be null when isApprentice is false",
    });
  });

  it("rejects firstYearApprentice=null when isApprentice is true", () => {
    const result = validatePersonData(
      validPerson({ isApprentice: true, firstYearApprentice: null }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "firstYearApprentice",
      message: "must be a boolean when isApprentice is true",
    });
  });

  it("rejects selfEmployedLessThanTwelveMonths=false when isSelfEmployed is false", () => {
    const result = validatePersonData(
      validPerson({
        isSelfEmployed: false,
        selfEmployedLessThanTwelveMonths: false,
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "selfEmployedLessThanTwelveMonths",
      message: "must be null when isSelfEmployed is false",
    });
  });

  it("rejects selfEmployedLessThanTwelveMonths=null when isSelfEmployed is true", () => {
    const result = validatePersonData(
      validPerson({
        isSelfEmployed: true,
        selfEmployedLessThanTwelveMonths: null,
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "selfEmployedLessThanTwelveMonths",
      message: "must be a boolean when isSelfEmployed is true",
    });
  });

  it("accepts ageBracket=null for a first-year apprentice", () => {
    const result = validatePersonData(
      validPerson({
        isApprentice: true,
        firstYearApprentice: true,
        ageBracket: null,
      }),
    );
    expect(result.valid).toBe(true);
  });

  it("accepts a valid ageBracket for a first-year apprentice", () => {
    const result = validatePersonData(
      validPerson({
        isApprentice: true,
        firstYearApprentice: true,
        ageBracket: "18-20",
      }),
    );
    expect(result.valid).toBe(true);
  });

  it("rejects ageBracket=null for a non-apprentice", () => {
    const result = validatePersonData(validPerson({ ageBracket: null }));
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe("ageBracket");
  });

  it("rejects ageBracket=null for a non-first-year apprentice", () => {
    const result = validatePersonData(
      validPerson({
        isApprentice: true,
        firstYearApprentice: false,
        ageBracket: null,
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe("ageBracket");
  });

  it("rejects an invalid ageBracket", () => {
    const result = validatePersonData(
      validPerson({ ageBracket: "25-30" as PersonData["ageBracket"] }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe("ageBracket");
  });

  it("rejects an invalid workingStatus", () => {
    const result = validatePersonData(
      validPerson({ workingStatus: "retired" as PersonData["workingStatus"] }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe("workingStatus");
  });

  it("rejects an invalid residencyStatus", () => {
    const result = validatePersonData(
      validPerson({
        residencyStatus: "tourist" as PersonData["residencyStatus"],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe("residencyStatus");
  });

  it("accepts receivesQualifyingAllowance=true when workingStatus is not_working", () => {
    const result = validatePersonData(
      validPerson({
        workingStatus: "not_working",
        receivesQualifyingAllowance: true,
      }),
    );
    expect(result.valid).toBe(true);
  });

  it("accepts receivesQualifyingAllowance=false when workingStatus is not_working", () => {
    const result = validatePersonData(
      validPerson({
        workingStatus: "not_working",
        receivesQualifyingAllowance: false,
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('rejects receivesQualifyingAllowance=false when workingStatus is not "not_working"', () => {
    const result = validatePersonData(
      validPerson({
        workingStatus: "earning_above_nmw",
        receivesQualifyingAllowance: false,
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "receivesQualifyingAllowance",
      message: 'must be null when workingStatus is not "not_working"',
    });
  });

  it("rejects receivesQualifyingAllowance=null when workingStatus is not_working", () => {
    const result = validatePersonData(
      validPerson({
        workingStatus: "not_working",
        receivesQualifyingAllowance: null,
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "receivesQualifyingAllowance",
      message: 'must be a boolean when workingStatus is "not_working"',
    });
  });

  it("collects multiple errors at once", () => {
    const result = validatePersonData(
      validPerson({
        isApprentice: true,
        firstYearApprentice: null,
        isSelfEmployed: true,
        selfEmployedLessThanTwelveMonths: null,
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveLength(2);
  });
});

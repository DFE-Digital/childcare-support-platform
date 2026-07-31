import { describe, it, expect } from "vitest";
import type { ChildData } from "../types/family.js";
import { validateChildData } from "./child.js";

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

describe("validateChildData", () => {
  it("accepts a valid child", () => {
    const result = validateChildData(validChild());
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it("accepts a child with multiple care selections", () => {
    const result = validateChildData(
      validChild({
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
    );
    expect(result.valid).toBe(true);
  });

  it("rejects an empty firstName", () => {
    const result = validateChildData(validChild({ firstName: "" }));
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "firstName",
      message: "must not be empty",
    });
  });

  it("rejects a whitespace-only firstName", () => {
    const result = validateChildData(validChild({ firstName: "   " }));
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe("firstName");
  });

  it("rejects birthMonth below 1", () => {
    const result = validateChildData(validChild({ birthMonth: 0 }));
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "birthMonth",
      message: "must be between 1 and 12",
    });
  });

  it("rejects birthMonth above 12", () => {
    const result = validateChildData(validChild({ birthMonth: 13 }));
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe("birthMonth");
  });

  it("rejects birthYear below 2010", () => {
    const result = validateChildData(validChild({ birthYear: 2009 }));
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe("birthYear");
  });

  it("rejects birthYear above current year", () => {
    const currentYear = new Date().getFullYear();
    const result = validateChildData(
      validChild({ birthYear: currentYear + 1 }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe("birthYear");
  });

  it("nests childcare selection errors with correct path", () => {
    const result = validateChildData(
      validChild({
        childcareSelections: [
          {
            id: 1,
            careType: "private_nursery",
            sessions: { morning: { daysPerWeek: 7 } },
            providerId: null,
          },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "childcareSelections[0].sessions.morning.daysPerWeek",
      message: "must be between 1 and 5",
    });
  });

  it("collects errors from multiple selections with correct indices", () => {
    const result = validateChildData(
      validChild({
        childcareSelections: [
          {
            id: 1,
            careType: "breakfast_club",
            daysPerWeek: 5,
            providerId: null,
          },
          {
            id: 2,
            careType: "childminder",
            hoursPerWeek: 51,
            weeksPerYear: 44,
            providerId: null,
          },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toMatch(/^childcareSelections\[1\]/);
  });
});

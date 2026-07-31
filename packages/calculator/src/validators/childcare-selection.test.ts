import { describe, it, expect } from "vitest";
import type { ChildcareSelection } from "../types/family.js";
import { validateChildcareSelection } from "./childcare-selection.js";

function sel(
  overrides: Partial<ChildcareSelection> & {
    careType: ChildcareSelection["careType"];
  },
): ChildcareSelection {
  return { id: 1, providerId: null, ...overrides };
}

describe("validateChildcareSelection", () => {
  describe("session-based care types (private_nursery, school_based_nursery)", () => {
    it("accepts a valid private_nursery selection with morning + afternoon sessions", () => {
      const result = validateChildcareSelection(
        sel({
          careType: "private_nursery",
          sessions: {
            morning: { daysPerWeek: 5 },
            afternoon: { daysPerWeek: 3 },
          },
        }),
      );
      expect(result.valid).toBe(true);
    });

    it("accepts a valid school_based_nursery with morning sessions only", () => {
      const result = validateChildcareSelection(
        sel({
          careType: "school_based_nursery",
          sessions: { morning: { daysPerWeek: 5 } },
        }),
      );
      expect(result.valid).toBe(true);
    });

    it("rejects missing sessions", () => {
      const result = validateChildcareSelection(
        sel({ careType: "private_nursery" }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors).toContainEqual({
        path: "sessions",
        message: "is required for session-based care types",
      });
    });

    it("rejects empty sessions object", () => {
      const result = validateChildcareSelection(
        sel({ careType: "private_nursery", sessions: {} }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors[0].path).toBe("sessions");
    });

    it("rejects daysPerWeek out of range in a session", () => {
      const result = validateChildcareSelection(
        sel({
          careType: "private_nursery",
          sessions: { morning: { daysPerWeek: 6 } },
        }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors).toContainEqual({
        path: "sessions.morning.daysPerWeek",
        message: "must be between 1 and 5",
      });
    });

    it("rejects forbidden fields on session-based types", () => {
      const result = validateChildcareSelection(
        sel({
          careType: "private_nursery",
          sessions: { morning: { daysPerWeek: 3 } },
          hoursPerWeek: 20,
        }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors).toContainEqual({
        path: "hoursPerWeek",
        message: "must not be present for private_nursery",
      });
    });
  });

  describe("childminder", () => {
    it("accepts a valid childminder selection", () => {
      const result = validateChildcareSelection(
        sel({ careType: "childminder", hoursPerWeek: 7, weeksPerYear: 44 }),
      );
      expect(result.valid).toBe(true);
    });

    it("rejects missing hoursPerWeek", () => {
      const result = validateChildcareSelection(
        sel({ careType: "childminder", weeksPerYear: 44 }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors[0].path).toBe("hoursPerWeek");
    });

    it("rejects missing weeksPerYear", () => {
      const result = validateChildcareSelection(
        sel({ careType: "childminder", hoursPerWeek: 7 }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors[0].path).toBe("weeksPerYear");
    });

    it("rejects hoursPerWeek out of range", () => {
      const result = validateChildcareSelection(
        sel({ careType: "childminder", hoursPerWeek: 51, weeksPerYear: 44 }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors).toContainEqual({
        path: "hoursPerWeek",
        message: "must be between 1 and 50",
      });
    });

    it("rejects weeksPerYear out of range", () => {
      const result = validateChildcareSelection(
        sel({ careType: "childminder", hoursPerWeek: 7, weeksPerYear: 53 }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors).toContainEqual({
        path: "weeksPerYear",
        message: "must be between 1 and 52",
      });
    });

    it("rejects sessions on childminder", () => {
      const result = validateChildcareSelection(
        sel({
          careType: "childminder",
          hoursPerWeek: 7,
          weeksPerYear: 44,
          sessions: { morning: { daysPerWeek: 3 } },
        }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors).toContainEqual({
        path: "sessions",
        message: "must not be present for childminder",
      });
    });
  });

  describe("weekly club types (breakfast_club, free_breakfast_club, after_school_club)", () => {
    it("accepts a valid breakfast_club", () => {
      const result = validateChildcareSelection(
        sel({ careType: "breakfast_club", daysPerWeek: 5 }),
      );
      expect(result.valid).toBe(true);
    });

    it("accepts a valid free_breakfast_club", () => {
      const result = validateChildcareSelection(
        sel({ careType: "free_breakfast_club", daysPerWeek: 5 }),
      );
      expect(result.valid).toBe(true);
    });

    it("accepts a valid after_school_club", () => {
      const result = validateChildcareSelection(
        sel({ careType: "after_school_club", daysPerWeek: 3 }),
      );
      expect(result.valid).toBe(true);
    });

    it("rejects missing daysPerWeek", () => {
      const result = validateChildcareSelection(
        sel({ careType: "breakfast_club" }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors[0].path).toBe("daysPerWeek");
    });

    it("rejects daysPerWeek out of range", () => {
      const result = validateChildcareSelection(
        sel({ careType: "after_school_club", daysPerWeek: 0 }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors).toContainEqual({
        path: "daysPerWeek",
        message: "must be between 1 and 5",
      });
    });

    it("rejects forbidden fields on club types", () => {
      const result = validateChildcareSelection(
        sel({ careType: "breakfast_club", daysPerWeek: 5, hoursPerWeek: 10 }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors).toContainEqual({
        path: "hoursPerWeek",
        message: "must not be present for breakfast_club",
      });
    });
  });

  describe("holiday_club", () => {
    it("accepts a valid holiday_club", () => {
      const result = validateChildcareSelection(
        sel({ careType: "holiday_club", daysPerYear: 20 }),
      );
      expect(result.valid).toBe(true);
    });

    it("rejects missing daysPerYear", () => {
      const result = validateChildcareSelection(
        sel({ careType: "holiday_club" }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors[0].path).toBe("daysPerYear");
    });

    it("rejects daysPerYear out of range", () => {
      const result = validateChildcareSelection(
        sel({ careType: "holiday_club", daysPerYear: 61 }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors).toContainEqual({
        path: "daysPerYear",
        message: "must be between 1 and 60",
      });
    });

    it("rejects forbidden fields on holiday_club", () => {
      const result = validateChildcareSelection(
        sel({ careType: "holiday_club", daysPerYear: 20, daysPerWeek: 5 }),
      );
      expect(result.valid).toBe(false);
      expect(result.errors).toContainEqual({
        path: "daysPerWeek",
        message: "must not be present for holiday_club",
      });
    });
  });

  it("rejects an invalid careType", () => {
    const result = validateChildcareSelection(
      sel({ careType: "nanny" as ChildcareSelection["careType"] }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors[0].path).toBe("careType");
  });
});

import type { ChildcareSelection } from "../types/family.js";
import { CARE_TYPE_IDS } from "../types/family.js";
import type { ValidationError, ValidationResult } from "./validation-result.js";
import { ok, fail } from "./validation-result.js";

function mustBeAbsent(
  selection: ChildcareSelection,
  fields: (keyof ChildcareSelection)[],
  errors: ValidationError[],
): void {
  for (const field of fields) {
    if (selection[field] !== undefined) {
      errors.push({
        path: field,
        message: `must not be present for ${selection.careType}`,
      });
    }
  }
}

function validateSessionBased(selection: ChildcareSelection): ValidationResult {
  const errors: ValidationError[] = [];

  mustBeAbsent(
    selection,
    ["hoursPerWeek", "weeksPerYear", "daysPerWeek", "daysPerYear"],
    errors,
  );

  if (!selection.sessions) {
    errors.push({
      path: "sessions",
      message: "is required for session-based care types",
    });
    return fail(errors);
  }

  const { morning, afternoon, fullDay } = selection.sessions;
  if (!morning && !afternoon && !fullDay) {
    errors.push({
      path: "sessions",
      message: "must have at least one of morning, afternoon, or fullDay",
    });
  }

  for (const [name, session] of Object.entries(selection.sessions)) {
    if (session && (session.daysPerWeek < 1 || session.daysPerWeek > 5)) {
      errors.push({
        path: `sessions.${name}.daysPerWeek`,
        message: "must be between 1 and 5",
      });
    }
  }

  if (errors.length > 0) return fail(errors);
  return ok();
}

function validateChildminder(selection: ChildcareSelection): ValidationResult {
  const errors: ValidationError[] = [];

  mustBeAbsent(selection, ["sessions", "daysPerWeek", "daysPerYear"], errors);

  if (selection.hoursPerWeek === undefined) {
    errors.push({
      path: "hoursPerWeek",
      message: "is required for childminder",
    });
  } else if (selection.hoursPerWeek < 1 || selection.hoursPerWeek > 50) {
    errors.push({ path: "hoursPerWeek", message: "must be between 1 and 50" });
  }

  if (selection.weeksPerYear === undefined) {
    errors.push({
      path: "weeksPerYear",
      message: "is required for childminder",
    });
  } else if (selection.weeksPerYear < 1 || selection.weeksPerYear > 52) {
    errors.push({ path: "weeksPerYear", message: "must be between 1 and 52" });
  }

  if (errors.length > 0) return fail(errors);
  return ok();
}

function validateClubWeekly(selection: ChildcareSelection): ValidationResult {
  const errors: ValidationError[] = [];

  mustBeAbsent(
    selection,
    ["sessions", "hoursPerWeek", "weeksPerYear", "daysPerYear"],
    errors,
  );

  if (selection.daysPerWeek === undefined) {
    errors.push({
      path: "daysPerWeek",
      message: `is required for ${selection.careType}`,
    });
  } else if (selection.daysPerWeek < 1 || selection.daysPerWeek > 5) {
    errors.push({ path: "daysPerWeek", message: "must be between 1 and 5" });
  }

  if (errors.length > 0) return fail(errors);
  return ok();
}

function validateHolidayClub(selection: ChildcareSelection): ValidationResult {
  const errors: ValidationError[] = [];

  mustBeAbsent(
    selection,
    ["sessions", "hoursPerWeek", "weeksPerYear", "daysPerWeek"],
    errors,
  );

  if (selection.daysPerYear === undefined) {
    errors.push({
      path: "daysPerYear",
      message: "is required for holiday_club",
    });
  } else if (selection.daysPerYear < 1 || selection.daysPerYear > 60) {
    errors.push({ path: "daysPerYear", message: "must be between 1 and 60" });
  }

  if (errors.length > 0) return fail(errors);
  return ok();
}

export function validateChildcareSelection(
  selection: ChildcareSelection,
): ValidationResult {
  if (!(CARE_TYPE_IDS as readonly string[]).includes(selection.careType)) {
    return fail([
      {
        path: "careType",
        message: `must be one of: ${CARE_TYPE_IDS.join(", ")}`,
      },
    ]);
  }

  switch (selection.careType) {
    case "private_nursery":
    case "school_based_nursery":
      return validateSessionBased(selection);
    case "childminder":
      return validateChildminder(selection);
    case "breakfast_club":
    case "free_breakfast_club":
    case "after_school_club":
      return validateClubWeekly(selection);
    case "holiday_club":
      return validateHolidayClub(selection);
  }
}

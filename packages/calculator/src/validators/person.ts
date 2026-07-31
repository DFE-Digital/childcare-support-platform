import type { PersonData } from "../types/family.js";
import {
  AGE_BRACKETS,
  WORKING_STATUSES,
  RESIDENCY_STATUSES,
} from "../types/family.js";
import type { ValidationResult } from "./validation-result.js";
import { ok, fail } from "./validation-result.js";

export function validatePersonData(person: PersonData): ValidationResult {
  const errors = [];

  if (!person.isApprentice && person.firstYearApprentice !== null) {
    errors.push({
      path: "firstYearApprentice",
      message: "must be null when isApprentice is false",
    });
  }
  if (person.isApprentice && typeof person.firstYearApprentice !== "boolean") {
    errors.push({
      path: "firstYearApprentice",
      message: "must be a boolean when isApprentice is true",
    });
  }

  if (
    !person.isSelfEmployed &&
    person.selfEmployedLessThanTwelveMonths !== null
  ) {
    errors.push({
      path: "selfEmployedLessThanTwelveMonths",
      message: "must be null when isSelfEmployed is false",
    });
  }
  if (
    person.isSelfEmployed &&
    typeof person.selfEmployedLessThanTwelveMonths !== "boolean"
  ) {
    errors.push({
      path: "selfEmployedLessThanTwelveMonths",
      message: "must be a boolean when isSelfEmployed is true",
    });
  }

  const ageBracketRequired = !(
    person.isApprentice && person.firstYearApprentice
  );
  if (ageBracketRequired) {
    if (
      person.ageBracket === null ||
      !(AGE_BRACKETS as readonly string[]).includes(person.ageBracket)
    ) {
      errors.push({
        path: "ageBracket",
        message: `must be one of: ${AGE_BRACKETS.join(", ")}`,
      });
    }
  } else if (
    person.ageBracket !== null &&
    !(AGE_BRACKETS as readonly string[]).includes(person.ageBracket)
  ) {
    errors.push({
      path: "ageBracket",
      message: `must be null or one of: ${AGE_BRACKETS.join(", ")}`,
    });
  }

  if (!(WORKING_STATUSES as readonly string[]).includes(person.workingStatus)) {
    errors.push({
      path: "workingStatus",
      message: `must be one of: ${WORKING_STATUSES.join(", ")}`,
    });
  }

  if (
    !(RESIDENCY_STATUSES as readonly string[]).includes(person.residencyStatus)
  ) {
    errors.push({
      path: "residencyStatus",
      message: `must be one of: ${RESIDENCY_STATUSES.join(", ")}`,
    });
  }

  if (
    person.workingStatus !== "not_working" &&
    person.receivesQualifyingAllowance !== null
  ) {
    errors.push({
      path: "receivesQualifyingAllowance",
      message: 'must be null when workingStatus is not "not_working"',
    });
  }
  if (
    person.workingStatus === "not_working" &&
    typeof person.receivesQualifyingAllowance !== "boolean"
  ) {
    errors.push({
      path: "receivesQualifyingAllowance",
      message: 'must be a boolean when workingStatus is "not_working"',
    });
  }

  if (errors.length > 0) return fail(errors);
  return ok();
}

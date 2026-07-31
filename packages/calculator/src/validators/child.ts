import type { ChildData } from "../types/family.js";
import type { ValidationResult } from "./validation-result.js";
import { ok, fail, merge, nest } from "./validation-result.js";
import { validateChildcareSelection } from "./childcare-selection.js";

const CURRENT_YEAR = new Date().getFullYear();

export function validateChildData(child: ChildData): ValidationResult {
  const errors = [];

  if (!child.firstName || child.firstName.trim() === "") {
    errors.push({ path: "firstName", message: "must not be empty" });
  }

  if (child.birthMonth < 1 || child.birthMonth > 12) {
    errors.push({ path: "birthMonth", message: "must be between 1 and 12" });
  }

  if (child.birthYear < 2010 || child.birthYear > CURRENT_YEAR) {
    errors.push({
      path: "birthYear",
      message: `must be between 2010 and ${CURRENT_YEAR}`,
    });
  }

  const selectionResults = child.childcareSelections.map((sel, i) =>
    nest(`childcareSelections[${i}]`, validateChildcareSelection(sel)),
  );

  return merge(errors.length > 0 ? fail(errors) : ok(), ...selectionResults);
}

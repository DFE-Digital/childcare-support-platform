import type { LocalStorageData } from "../types/family.js";
import type { ValidationResult } from "./validation-result.js";
import { ok, fail, merge, nest } from "./validation-result.js";
import { validatePersonData } from "./person.js";
import { validateChildData } from "./child.js";

export function validateLocalStorageData(
  data: LocalStorageData,
): ValidationResult {
  const errors = [];

  if (!data.household.hasPartner && data.partner !== null) {
    errors.push({
      path: "partner",
      message: "must be null when hasPartner is false",
    });
  }

  if (data.household.hasPartner && data.partner === null) {
    errors.push({
      path: "partner",
      message: "must be present when hasPartner is true",
    });
  }

  if (data.children.length === 0) {
    errors.push({
      path: "children",
      message: "must have at least one child",
    });
  }

  const userResult = nest("user", validatePersonData(data.user));

  const partnerResult =
    data.household.hasPartner && data.partner !== null
      ? nest("partner", validatePersonData(data.partner))
      : ok();

  const childResults = data.children.map((child, i) =>
    nest(`children[${i}]`, validateChildData(child)),
  );

  return merge(
    errors.length > 0 ? fail(errors) : ok(),
    userResult,
    partnerResult,
    ...childResults,
  );
}

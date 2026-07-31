import type { EntitlementResult } from "../types/entitlement.js";
import type { ValidationError, ValidationResult } from "./validation-result.js";
import { ok, fail, merge, nest } from "./validation-result.js";

export function validateEntitlementResult(
  result: EntitlementResult,
): ValidationResult {
  const errors: ValidationError[] = [];

  if (!Array.isArray(result.children)) {
    errors.push({ path: "children", message: "must be an array" });
    return fail(errors);
  }

  if (result.children.length === 0) {
    errors.push({
      path: "children",
      message: "must have at least one child",
    });
    return fail(errors);
  }

  const childResults = result.children.map((child, i) => {
    const childErrors = [];

    if (typeof child.childId !== "number") {
      childErrors.push({ path: "childId", message: "must be a number" });
    }

    if (typeof child.childName !== "string" || child.childName.length === 0) {
      childErrors.push({
        path: "childName",
        message: "must be a non-empty string",
      });
    }

    if (!Array.isArray(child.schemes)) {
      childErrors.push({ path: "schemes", message: "must be an array" });
      return nest(`children[${i}]`, fail(childErrors));
    }

    const schemeResults = child.schemes.map((scheme, j) => {
      const schemeErrors = [];

      if (typeof scheme.schemeId !== "string" || scheme.schemeId.length === 0) {
        schemeErrors.push({
          path: "schemeId",
          message: "must be a non-empty string",
        });
      }

      if (typeof scheme.eligible !== "boolean") {
        schemeErrors.push({
          path: "eligible",
          message: "must be a boolean",
        });
      }

      if (!Array.isArray(scheme.reasons)) {
        schemeErrors.push({ path: "reasons", message: "must be an array" });
      }

      if (!Array.isArray(scheme.caveats)) {
        schemeErrors.push({ path: "caveats", message: "must be an array" });
      }

      return nest(
        `schemes[${j}]`,
        schemeErrors.length > 0 ? fail(schemeErrors) : ok(),
      );
    });

    return nest(
      `children[${i}]`,
      merge(
        childErrors.length > 0 ? fail(childErrors) : ok(),
        ...schemeResults,
      ),
    );
  });

  return merge(errors.length > 0 ? fail(errors) : ok(), ...childResults);
}

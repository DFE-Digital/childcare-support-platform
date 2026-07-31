import { describe, it, expect } from "vitest";
import { validateEntitlementResult } from "./entitlement.js";
import type { EntitlementResult } from "../types/entitlement.js";

function validResult(
  overrides: Partial<EntitlementResult> = {},
): EntitlementResult {
  return {
    children: [
      {
        childId: 1,
        childName: "TestChild",
        schemes: [
          {
            schemeId: "30_hours_working_families",
            eligible: true,
            reasons: ["Both parents working."],
            caveats: [],
          },
        ],
      },
    ],
    ...overrides,
  };
}

describe("validateEntitlementResult", () => {
  it("accepts a valid result", () => {
    const result = validateEntitlementResult(validResult());
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it("rejects empty children array", () => {
    const result = validateEntitlementResult(validResult({ children: [] }));
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "children",
      message: "must have at least one child",
    });
  });

  it("rejects missing childName", () => {
    const data = validResult();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (data.children[0] as any).childName = "";
    const result = validateEntitlementResult(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "children[0].childName",
      message: "must be a non-empty string",
    });
  });

  it("rejects non-boolean eligible", () => {
    const data = validResult();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (data.children[0].schemes[0] as any).eligible = "yes";
    const result = validateEntitlementResult(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "children[0].schemes[0].eligible",
      message: "must be a boolean",
    });
  });

  it("rejects non-array reasons", () => {
    const data = validResult();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (data.children[0].schemes[0] as any).reasons = "string";
    const result = validateEntitlementResult(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "children[0].schemes[0].reasons",
      message: "must be an array",
    });
  });

  it("rejects non-array caveats", () => {
    const data = validResult();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (data.children[0].schemes[0] as any).caveats = null;
    const result = validateEntitlementResult(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "children[0].schemes[0].caveats",
      message: "must be an array",
    });
  });

  it("rejects empty schemeId", () => {
    const data = validResult();
    data.children[0].schemes[0].schemeId = "";
    const result = validateEntitlementResult(data);
    expect(result.valid).toBe(false);
    expect(result.errors).toContainEqual({
      path: "children[0].schemes[0].schemeId",
      message: "must be a non-empty string",
    });
  });

  it("accumulates errors from multiple children", () => {
    const data = validResult({
      children: [
        {
          childId: 1,
          childName: "",
          schemes: [],
        },
        {
          childId: 2,
          childName: "",
          schemes: [],
        },
      ],
    });
    const result = validateEntitlementResult(data);
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThanOrEqual(2);
  });
});

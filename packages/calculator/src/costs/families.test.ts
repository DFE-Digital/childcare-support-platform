import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { LocalStorageData } from "../types/family.js";
import type { Scheme, SchemesData } from "../types/scheme.js";
import type { ProviderCareType } from "../types/provider.js";
import type { PostcodeAreaCosts } from "../types/costs.js";
import { calculateEntitlements } from "../entitlement/calculate.js";
import { calculateCosts, calculateCostRange } from "./calculate.js";
import type { CostCalculatorInput } from "./calculate.js";
import type {
  FamilyCostResult,
  CostRangeResult,
} from "../types/cost-result.js";

const dataDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../app/src/data",
);
const familiesDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../__fixtures__/families",
);

const schemesData: SchemesData = JSON.parse(
  readFileSync(join(dataDir, "schemes.json"), "utf-8"),
);
const schemes: Scheme[] = schemesData.schemes;

const providersDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../data-pipeline/data/placeholder-providers",
);
const providers: Array<{
  id: string;
  name: string;
  careTypes: ProviderCareType[];
}> = readdirSync(providersDir)
  .filter((f) => f.endsWith(".json"))
  .map((f) => JSON.parse(readFileSync(join(providersDir, f), "utf-8")));

const exportedDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../exported_data/app",
);
const fixturesDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../__fixtures__/costs",
);
const costsDir = existsSync(join(exportedDir, "lad"))
  ? join(exportedDir, "lad")
  : join(fixturesDir, "lad");
const inwardDirPath = existsSync(join(exportedDir, "inward"))
  ? join(exportedDir, "inward")
  : join(fixturesDir, "inward");

function getAreaCosts(postcode: string): PostcodeAreaCosts | null {
  const [outward, inward] = postcode.split(" ");
  if (!outward) return null;
  try {
    const inwardData = JSON.parse(
      readFileSync(join(inwardDirPath, `${outward}.json`), "utf-8"),
    );
    const laIndex = inwardData._ as string[];
    const entryKey = inward ?? Object.keys(inwardData).find((k) => k !== "_");
    const entry = entryKey ? inwardData[entryKey] : null;
    if (!entry || entry.a === undefined || !laIndex) return null;
    const indices: number[] = entry.a;
    for (const idx of indices) {
      const laCode = laIndex[idx];
      try {
        return JSON.parse(
          readFileSync(join(costsDir, `${laCode}.json`), "utf-8"),
        );
      } catch {
        continue;
      }
    }
    return null;
  } catch {
    return null;
  }
}

interface FixtureFamily {
  description: string;
  localStorage: LocalStorageData;
  costEstimate: Record<string, unknown>;
}

function loadFixture(filename: string): FixtureFamily {
  return JSON.parse(readFileSync(join(familiesDir, filename), "utf-8"));
}

function runCalculator(
  fixture: FixtureFamily,
  refDate: Date,
): FamilyCostResult {
  const data = fixture.localStorage;
  const entitlements = calculateEntitlements(data, schemes, refDate);
  const areaCosts = getAreaCosts(data.location.postcode);

  const input: CostCalculatorInput = {
    data,
    schemes,
    entitlements,
    providers,
    areaCosts,
    referenceDate: refDate,
  };

  return calculateCosts(input);
}

describe("arithmetic invariants across all families", () => {
  const fixtureFiles = readdirSync(familiesDir).filter((f) =>
    f.endsWith(".json"),
  );
  const ref = new Date(2026, 1, 22);

  /** Collect all CostSelections for a child regardless of grouping. */
  function allSelections(child: FamilyCostResult["children"][number]) {
    return [
      ...(child.selections ?? []),
      ...(child.termTimeCare?.selections ?? []),
      ...(child.yearRoundCare?.selections ?? []),
    ];
  }

  for (const file of fixtureFiles) {
    describe(file.replace(".json", ""), () => {
      const fixture = loadFixture(file);
      const result = runCalculator(fixture, ref);
      const { familyTotal, children } = result;

      // --- Selection-level invariants ---
      for (const child of children) {
        for (const sel of allSelections(child)) {
          const calc = sel.calculation;
          const fundedReduction =
            calc.step3_fundedHoursReduction?.savingToParent ?? 0;

          it(`${child.child} sel#${sel.selectionId}: estimatedAnnualCostToParent == gross - funded + additional`, () => {
            expect(calc.estimatedAnnualCostToParent).toBe(
              calc.step1_childcareFees.total -
                fundedReduction +
                calc.step4_additionalCharges.total,
            );
          });
        }
      }

      // --- Child-level invariants ---
      for (const child of children) {
        const sels = allSelections(child);

        it(`${child.child}: grossCost == sum of selections' (gross + additional)`, () => {
          const expected = sels.reduce(
            (sum, s) =>
              sum +
              s.calculation.step1_childcareFees.total +
              s.calculation.step4_additionalCharges.total,
            0,
          );
          expect(child.total.grossCost).toBe(expected);
        });

        it(`${child.child}: support.total == fundedHours + tfc + uc`, () => {
          const { fundedHours, taxFreeChildcare, ucChildcare, total } =
            child.total.support;
          expect(total).toBe(fundedHours + taxFreeChildcare + ucChildcare);
        });

        it(`${child.child}: costToFamily == grossCost - support.total`, () => {
          expect(child.total.costToFamily).toBe(
            child.total.grossCost - child.total.support.total,
          );
        });
      }

      // --- Family-level invariants ---
      it("totalCostOfChildcare.total == childcareFees + additionalCharges", () => {
        expect(familyTotal.totalCostOfChildcare.total).toBe(
          familyTotal.totalCostOfChildcare.childcareFees +
            familyTotal.totalCostOfChildcare.additionalCharges,
        );
      });

      it("childcareFees == sum of all selections' step1 fees", () => {
        const expected = children.reduce(
          (sum, child) =>
            sum +
            allSelections(child).reduce(
              (s, sel) => s + sel.calculation.step1_childcareFees.total,
              0,
            ),
          0,
        );
        expect(familyTotal.totalCostOfChildcare.childcareFees).toBe(expected);
      });

      it("additionalCharges == sum of all selections' step4 charges", () => {
        const expected = children.reduce(
          (sum, child) =>
            sum +
            allSelections(child).reduce(
              (s, sel) => s + sel.calculation.step4_additionalCharges.total,
              0,
            ),
          0,
        );
        expect(familyTotal.totalCostOfChildcare.additionalCharges).toBe(
          expected,
        );
      });

      it("totalSavingToParent == fundedHours + tfc + uc savings", () => {
        const fh =
          familyTotal.totalGovernmentSupport.fundedHours?.savingToParent ?? 0;
        const tfc =
          familyTotal.totalGovernmentSupport.taxFreeChildcare?.savingToParent ??
          0;
        const uc =
          familyTotal.totalGovernmentSupport.ucChildcare?.savingToParent ?? 0;
        expect(familyTotal.totalGovernmentSupport.totalSavingToParent).toBe(
          fh + tfc + uc,
        );
      });

      it("estimatedAnnualCostToFamily == totalCost - totalSaving", () => {
        expect(familyTotal.estimatedAnnualCostToFamily).toBe(
          familyTotal.totalCostOfChildcare.total -
            familyTotal.totalGovernmentSupport.totalSavingToParent,
        );
      });

      // --- Cross-level consistency ---
      it("sum of children's grossCost == family totalCostOfChildcare.total", () => {
        const childrenTotal = children.reduce(
          (sum, c) => sum + c.total.grossCost,
          0,
        );
        expect(childrenTotal).toBe(familyTotal.totalCostOfChildcare.total);
      });

      if (familyTotal.totalGovernmentSupport.fundedHours !== null) {
        it("sum of children's fundedHours == family funded hours saving", () => {
          const childrenFH = children.reduce(
            (sum, c) => sum + c.total.support.fundedHours,
            0,
          );
          expect(childrenFH).toBe(
            familyTotal.totalGovernmentSupport.fundedHours!.savingToParent,
          );
        });
      }

      // --- Sanity checks: non-negative values ---
      it("all childcare fees and additional charges are non-negative", () => {
        for (const child of children) {
          for (const sel of allSelections(child)) {
            expect(
              sel.calculation.step1_childcareFees.total,
            ).toBeGreaterThanOrEqual(0);
            expect(
              sel.calculation.step4_additionalCharges.total,
            ).toBeGreaterThanOrEqual(0);
          }
        }
      });

      it("all support amounts are non-negative", () => {
        for (const child of children) {
          expect(child.total.support.fundedHours).toBeGreaterThanOrEqual(0);
          expect(child.total.support.taxFreeChildcare).toBeGreaterThanOrEqual(
            0,
          );
          expect(child.total.support.ucChildcare).toBeGreaterThanOrEqual(0);
        }
      });

      it("estimatedAnnualCostToFamily is non-negative", () => {
        expect(familyTotal.estimatedAnnualCostToFamily).toBeGreaterThanOrEqual(
          0,
        );
      });
    });
  }
});

// ---------------------------------------------------------------------------
// Stacked entitlement: regression test for funded hours stacking
// ---------------------------------------------------------------------------

describe("stacked-entitlement: funded hours stacking for age-2 child", () => {
  const ref = new Date(2026, 1, 22);
  const fixture = loadFixture("stacked-entitlement.json");
  const result = runCalculator(fixture, ref);

  function allSelections(child: FamilyCostResult["children"][number]) {
    return [
      ...(child.selections ?? []),
      ...(child.termTimeCare?.selections ?? []),
      ...(child.yearRoundCare?.selections ?? []),
    ];
  }

  it("age-2 child gets more than 15h worth of funded saving (stacked pool)", () => {
    const child = result.children[0];
    const sels = allSelections(child);
    const totalFundedSaving = sels.reduce(
      (sum, s) =>
        sum + (s.calculation.step3_fundedHoursReduction?.savingToParent ?? 0),
      0,
    );
    // Pennywell age-2 rate: £22/session, 3.5h session → £6.29/hr
    // With only 15h funded: saving = 15 × 6.29 × 38 = £3,585.30
    // With stacked 30h: 28h used (5 mornings + 3 afternoons) → saving > 15h-only
    expect(totalFundedSaving).toBeGreaterThan(15 * (22 / 3.5) * 38);
  });

  it("funded hours scheme name includes both entitlements", () => {
    const child = result.children[0];
    const sels = allSelections(child);
    const fundedSel = sels.find(
      (s) => s.calculation.step3_fundedHoursReduction,
    );
    expect(fundedSel).toBeDefined();
    expect(fundedSel!.calculation.step3_fundedHoursReduction!.scheme).toContain(
      "15 hours early learning for 2-year-olds",
    );
    expect(fundedSel!.calculation.step3_fundedHoursReduction!.scheme).toContain(
      "30 hours working families",
    );
  });
});

// ---------------------------------------------------------------------------
// Cost range invariants
// ---------------------------------------------------------------------------

function runCostRange(fixture: FixtureFamily, refDate: Date): CostRangeResult {
  const data = fixture.localStorage;
  const entitlements = calculateEntitlements(data, schemes, refDate);
  const areaCosts = getAreaCosts(data.location.postcode);

  return calculateCostRange({
    data,
    schemes,
    entitlements,
    providers,
    areaCosts,
    referenceDate: refDate,
  });
}

describe("cost range invariants across all families", () => {
  const fixtureFiles = readdirSync(familiesDir).filter((f) =>
    f.endsWith(".json"),
  );
  const ref = new Date(2026, 1, 22);

  for (const file of fixtureFiles) {
    const familyName = file.replace(".json", "");

    describe(familyName, () => {
      const fixture = loadFixture(file);
      const rangeResult = runCostRange(fixture, ref);
      const { lower, mean, upper, range } = rangeResult;

      it("gross cost ordering: lower <= mean <= upper", () => {
        expect(
          lower.familyTotal.totalCostOfChildcare.total,
        ).toBeLessThanOrEqual(mean.familyTotal.totalCostOfChildcare.total);
        expect(mean.familyTotal.totalCostOfChildcare.total).toBeLessThanOrEqual(
          upper.familyTotal.totalCostOfChildcare.total,
        );
      });

      it("net cost ordering: lower <= mean <= upper", () => {
        expect(
          lower.familyTotal.estimatedAnnualCostToFamily,
        ).toBeLessThanOrEqual(mean.familyTotal.estimatedAnnualCostToFamily);
        expect(
          mean.familyTotal.estimatedAnnualCostToFamily,
        ).toBeLessThanOrEqual(upper.familyTotal.estimatedAnnualCostToFamily);
      });

      it("range.lower and range.upper match the respective full results", () => {
        expect(range.lower).toBe(lower.familyTotal.estimatedAnnualCostToFamily);
        expect(range.upper).toBe(upper.familyTotal.estimatedAnnualCostToFamily);
      });

      it("mean result matches standalone calculateCosts (backward compat)", () => {
        const standalone = runCalculator(fixture, ref);
        expect(mean.familyTotal.estimatedAnnualCostToFamily).toBe(
          standalone.familyTotal.estimatedAnnualCostToFamily,
        );
      });

      it("all three bounds produce non-negative cost to family", () => {
        expect(
          lower.familyTotal.estimatedAnnualCostToFamily,
        ).toBeGreaterThanOrEqual(0);
        expect(
          mean.familyTotal.estimatedAnnualCostToFamily,
        ).toBeGreaterThanOrEqual(0);
        expect(
          upper.familyTotal.estimatedAnnualCostToFamily,
        ).toBeGreaterThanOrEqual(0);
      });

      it("if range has a spread, lower < upper", () => {
        if (range.lower !== range.upper) {
          expect(range.lower).toBeLessThan(range.upper);
        }
      });
    });
  }
});

// ---------------------------------------------------------------------------
// rateDetails population tests
// ---------------------------------------------------------------------------

function allSelectionsFromResult(result: FamilyCostResult) {
  return result.children.flatMap((child) => [
    ...(child.selections ?? []),
    ...(child.termTimeCare?.selections ?? []),
    ...(child.yearRoundCare?.selections ?? []),
  ]);
}

describe("rateDetails on FeeSource", () => {
  const ref = new Date(2026, 1, 22);

  it("provider selections have no rateDetails", () => {
    const fixture = loadFixture("brennans.json");
    const result = runCalculator(fixture, ref);
    const sels = allSelectionsFromResult(result);

    for (const sel of sels) {
      expect(sel.feeSource.rateDetails).toBeUndefined();
    }
  });

  it("rateDetails have correct ordering: lower <= mean <= upper", () => {
    const fixture = loadFixture("thomas-and-emily.json");
    const result = runCalculator(fixture, ref);
    const sels = allSelectionsFromResult(result);

    for (const sel of sels) {
      if (!sel.feeSource.rateDetails) continue;
      for (const rd of sel.feeSource.rateDetails) {
        expect(rd.lower).toBeLessThanOrEqual(rd.mean);
        expect(rd.mean).toBeLessThanOrEqual(rd.upper);
      }
    }
  });
});

import { describe, it, expect } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  calculateEntitlements,
  calculateCosts,
  calculateCostRange,
} from "@bsil/calculator";
import type {
  LocalStorageData,
  Scheme,
  SchemesData,
  ProviderCareType,
  PostcodeAreaCosts,
  FamilyCostResult,
  CostRangeResult,
  CostCalculatorInput,
} from "@bsil/calculator";
import { FamilyTotalSummary } from "../FamilyTotalSummary";
import { ChildCostBreakdown } from "../ChildCostBreakdown";

// ---------------------------------------------------------------------------
// Data loading — mirrors the calculator's own test setup
// ---------------------------------------------------------------------------

const __dir = dirname(fileURLToPath(import.meta.url));
const dataDir = join(__dir, "../../../data");
const familiesDir = join(
  __dir,
  "../../../../../../packages/calculator/src/__fixtures__/families",
);
const providersDir = join(
  __dir,
  "../../../../../../packages/data-pipeline/data/placeholder-providers",
);

const schemesData: SchemesData = JSON.parse(
  readFileSync(join(dataDir, "schemes.json"), "utf-8"),
);
const schemes: Scheme[] = schemesData.schemes;

const providers: Array<{
  id: string;
  name: string;
  careTypes: ProviderCareType[];
}> = readdirSync(providersDir)
  .filter((f) => f.endsWith(".json"))
  .map((f) => JSON.parse(readFileSync(join(providersDir, f), "utf-8")));

const exportedDir = join(__dir, "../../../../../../exported_data/app");
const costsDir = join(exportedDir, "lad");
const inwardDir = join(exportedDir, "inward");

function getAreaCosts(postcode: string): PostcodeAreaCosts | null {
  const [outward, inward] = postcode.split(" ");
  if (!outward || !inward) return null;
  try {
    const inwardData = JSON.parse(
      readFileSync(join(inwardDir, `${outward}.json`), "utf-8"),
    );
    const laIndex = inwardData._ as string[];
    const entry = inwardData[inward];
    if (!entry || entry.a === undefined || !laIndex) return null;
    const indices: number[] = entry.a;
    for (const idx of indices) {
      const laCode = laIndex[idx];
      const costPath = join(costsDir, `${laCode}.json`);
      try {
        return JSON.parse(readFileSync(costPath, "utf-8"));
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
    rounding: "nearest10",
  };

  return calculateCosts(input);
}

// ---------------------------------------------------------------------------
// Currency parser — extracts a number from the formatted text in the DOM
// ---------------------------------------------------------------------------

function parseCurrency(text: string): number {
  const cleaned = text.trim();
  // Matches: "£1,234", "£1,234.56", "-£1,234.56", "−£1,234.56", "-£0.00", "£0"
  const match = cleaned.match(/^([−-]?)£([\d,]+(?:\.\d+)?)$/);
  if (!match) {
    throw new Error(`Unrecognised currency format: "${cleaned}"`);
  }
  const sign = match[1] ? -1 : 1;
  const value = parseFloat(match[2].replace(/,/g, ""));
  return sign * value;
}

/** Round to 2dp — eliminates IEEE 754 noise when summing parsed 2dp values. */
function round2(x: number): number {
  return Math.round(x * 100) / 100;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getAllSelections(child: FamilyCostResult["children"][number]) {
  return [
    ...(child.selections ?? []),
    ...(child.termTimeCare?.selections ?? []),
    ...(child.yearRoundCare?.selections ?? []),
  ];
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const fixtureFiles = readdirSync(familiesDir).filter((f) =>
  f.endsWith(".json"),
);
const ref = new Date(2026, 1, 22);

describe("UI arithmetic invariants", () => {
  for (const file of fixtureFiles) {
    const familyName = file.replace(".json", "");

    describe(familyName, () => {
      const fixture = loadFixture(file);
      const result = runCalculator(fixture, ref);
      const { familyTotal, children } = result;
      const isUC =
        fixture.localStorage.qualifyingBenefits.includes("universal_credit");

      // =================================================================
      // FamilyTotalSummary invariants
      // =================================================================
      describe("FamilyTotalSummary", () => {
        it("F1: headline figure equals 'Estimated cost' figure", () => {
          const { getByTestId } = render(
            <FamilyTotalSummary
              familyTotal={familyTotal}
              period="yearly"
              onPeriodChange={() => {}}
            />,
          );

          const headline = parseCurrency(
            getByTestId("family-pays-headline").textContent!,
          );
          const familyPays = parseCurrency(
            getByTestId("family-pays").textContent!,
          );

          expect(headline).toBe(familyPays);

          cleanup();
        });

        it("F2: total costs − support entries = family pays", () => {
          const { getByTestId, queryByTestId } = render(
            <FamilyTotalSummary
              familyTotal={familyTotal}
              period="yearly"
              onPeriodChange={() => {}}
            />,
          );

          const totalCost = parseCurrency(
            getByTestId("family-total-cost").textContent!,
          );
          const fundedHours = queryByTestId("family-support-funded-hours")
            ? parseCurrency(
                queryByTestId("family-support-funded-hours")!.textContent!,
              )
            : 0;
          const tfc = queryByTestId("family-support-tfc")
            ? parseCurrency(queryByTestId("family-support-tfc")!.textContent!)
            : 0;
          const uc = queryByTestId("family-support-uc")
            ? parseCurrency(queryByTestId("family-support-uc")!.textContent!)
            : 0;
          const familyPays = parseCurrency(
            getByTestId("family-pays").textContent!,
          );

          // Support amounts are displayed with a "-" prefix, so parseCurrency
          // returns negative values. We add them (which subtracts).
          const computed = round2(totalCost + fundedHours + tfc + uc);
          expect(computed).toBe(familyPays);

          cleanup();
        });

        it("F3: support rows only rendered when non-zero", () => {
          const { queryByTestId } = render(
            <FamilyTotalSummary
              familyTotal={familyTotal}
              period="yearly"
              onPeriodChange={() => {}}
            />,
          );

          const gov = familyTotal.totalGovernmentSupport;

          if (!gov.fundedHours || gov.fundedHours.savingToParent === 0) {
            expect(queryByTestId("family-support-funded-hours")).toBeNull();
          } else {
            expect(queryByTestId("family-support-funded-hours")).not.toBeNull();
          }

          if (
            !gov.taxFreeChildcare ||
            gov.taxFreeChildcare.savingToParent === 0
          ) {
            expect(queryByTestId("family-support-tfc")).toBeNull();
          } else {
            expect(queryByTestId("family-support-tfc")).not.toBeNull();
          }

          if (!gov.ucChildcare || gov.ucChildcare.savingToParent === 0) {
            expect(queryByTestId("family-support-uc")).toBeNull();
          } else {
            expect(queryByTestId("family-support-uc")).not.toBeNull();
          }

          cleanup();
        });
      });

      // =================================================================
      // ChildCostBreakdown — per-child
      // =================================================================
      for (let ci = 0; ci < children.length; ci++) {
        const child = children[ci];
        const inputChild = fixture.localStorage.children[ci];
        const childName = child.child;
        const selections = getAllSelections(child);

        describe(`ChildCostBreakdown — ${childName}`, () => {
          // ---------------------------------------------------------------
          // S1: selection-level invariant
          // ---------------------------------------------------------------
          for (const sel of selections) {
            const calc = sel.calculation;
            const hasBreakdown =
              !!calc.step3_fundedHoursReduction ||
              calc.step4_additionalCharges.total > 0;

            if (hasBreakdown) {
              it(`S1: sel#${sel.selectionId} childcare fees − funded + additional = total`, () => {
                const { getByTestId, queryByTestId } = render(
                  <ChildCostBreakdown
                    childData={child}
                    inputChild={inputChild}
                    isUC={isUC}
                    period="yearly"
                  />,
                );

                const id = sel.selectionId;
                const childcareFees = parseCurrency(
                  getByTestId(`sel-${id}-childcare-fees`).textContent!,
                );
                const funded = queryByTestId(`sel-${id}-funded-hours`)
                  ? parseCurrency(
                      queryByTestId(`sel-${id}-funded-hours`)!.textContent!,
                    )
                  : 0;
                const additional = queryByTestId(`sel-${id}-additional`)
                  ? parseCurrency(
                      queryByTestId(`sel-${id}-additional`)!.textContent!,
                    )
                  : 0;
                const total = parseCurrency(
                  getByTestId(`sel-${id}-total`).textContent!,
                );

                // funded is displayed as "-£X.XX" so parseCurrency returns negative
                const computed = round2(childcareFees + funded + additional);
                expect(computed).toBe(total);

                cleanup();
              });
            } else {
              it(`S1: sel#${sel.selectionId} total matches estimatedAnnualCostToParent`, () => {
                const { getByTestId } = render(
                  <ChildCostBreakdown
                    childData={child}
                    inputChild={inputChild}
                    isUC={isUC}
                    period="yearly"
                  />,
                );

                const id = sel.selectionId;
                const total = parseCurrency(
                  getByTestId(`sel-${id}-total`).textContent!,
                );
                expect(total).toBe(round2(calc.estimatedAnnualCostToParent));

                cleanup();
              });
            }
          }

          // ---------------------------------------------------------------
          // N1: non-negative cost invariant (per selection)
          // ---------------------------------------------------------------
          for (const sel of selections) {
            it(`N1: sel#${sel.selectionId} estimatedAnnualCostToParent >= 0`, () => {
              expect(
                sel.calculation.estimatedAnnualCostToParent,
              ).toBeGreaterThanOrEqual(0);
            });
          }

          // ---------------------------------------------------------------
          // N2: non-negative cost invariant (per child)
          // ---------------------------------------------------------------
          it(`N2: costToFamily >= 0`, () => {
            expect(child.total.costToFamily).toBeGreaterThanOrEqual(0);
          });

          // ---------------------------------------------------------------
          // C1: child summary invariant
          // ---------------------------------------------------------------
          it(`C1: subtotal − TFC − UC = cost to family`, () => {
            const { getByTestId, queryByTestId } = render(
              <ChildCostBreakdown
                childData={child}
                inputChild={inputChild}
                isUC={isUC}
                period="yearly"
              />,
            );

            const subtotal = parseCurrency(
              getByTestId(`child-${childName}-subtotal`).textContent!,
            );
            const tfc = queryByTestId(`child-${childName}-tfc`)
              ? parseCurrency(
                  queryByTestId(`child-${childName}-tfc`)!.textContent!,
                )
              : 0;
            const uc = queryByTestId(`child-${childName}-uc`)
              ? parseCurrency(
                  queryByTestId(`child-${childName}-uc`)!.textContent!,
                )
              : 0;
            const costToFamily = parseCurrency(
              getByTestId(`child-${childName}-cost-to-family`).textContent!,
            );

            // tfc, uc are displayed as "-£X.XX" → negative from parser
            const computed = round2(subtotal + tfc + uc);
            expect(computed).toBe(costToFamily);

            cleanup();
          });
        });
      }

      // =================================================================
      // Cross-component consistency
      // =================================================================
      describe("cross-component consistency", () => {
        it("X1: sum of children 'cost to family' = family 'Estimated cost'", () => {
          // Render FamilyTotalSummary to get family-pays
          const familyRender = render(
            <FamilyTotalSummary
              familyTotal={familyTotal}
              period="yearly"
              onPeriodChange={() => {}}
            />,
          );
          const familyPays = parseCurrency(
            familyRender.getByTestId("family-pays").textContent!,
          );
          cleanup();

          // Render each child independently and sum cost-to-family
          let childrenSum = 0;
          for (let ci = 0; ci < children.length; ci++) {
            const childRender = render(
              <ChildCostBreakdown
                childData={children[ci]}
                inputChild={fixture.localStorage.children[ci]}
                isUC={isUC}
                period="yearly"
              />,
            );
            childrenSum += parseCurrency(
              childRender.getByTestId(
                `child-${children[ci].child}-cost-to-family`,
              ).textContent!,
            );
            cleanup();
          }

          expect(round2(childrenSum)).toBe(familyPays);
        });

        it("X2: sum of children subtotals + funded hours = family 'Total childcare costs'", () => {
          // Render FamilyTotalSummary to get family-total-cost
          const familyRender = render(
            <FamilyTotalSummary
              familyTotal={familyTotal}
              period="yearly"
              onPeriodChange={() => {}}
            />,
          );
          const totalCost = parseCurrency(
            familyRender.getByTestId("family-total-cost").textContent!,
          );
          cleanup();

          // Render each child independently and sum subtotals
          let childrenSubtotalSum = 0;
          for (let ci = 0; ci < children.length; ci++) {
            const childRender = render(
              <ChildCostBreakdown
                childData={children[ci]}
                inputChild={fixture.localStorage.children[ci]}
                isUC={isUC}
                period="yearly"
              />,
            );
            childrenSubtotalSum += parseCurrency(
              childRender.getByTestId(`child-${children[ci].child}-subtotal`)
                .textContent!,
            );
            cleanup();
          }

          // Child subtotals have funded hours already deducted, so add them back
          const fundedHours =
            familyTotal.totalGovernmentSupport.fundedHours?.savingToParent ?? 0;
          expect(round2(childrenSubtotalSum + fundedHours)).toBe(totalCost);
        });
      });
    });
  }
});

// ---------------------------------------------------------------------------
// Cost range display tests
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
    rounding: "nearest10",
  });
}

describe("FamilyTotalSummary cost range display", () => {
  it("shows range message when lower !== upper", () => {
    const fixture = loadFixture("thomas-and-emily.json");
    const rangeResult = runCostRange(fixture, ref);

    // Force a spread to test the range display UI
    const costRange = {
      lower: rangeResult.range.lower - 100,
      upper: rangeResult.range.upper + 100,
    };

    const { getByTestId } = render(
      <FamilyTotalSummary
        familyTotal={rangeResult.mean.familyTotal}
        costRange={costRange}
        period="yearly"
        onPeriodChange={() => {}}
      />,
    );

    const message = getByTestId("cost-range-message");
    expect(message).not.toBeNull();

    const lower = parseCurrency(getByTestId("cost-range-lower").textContent!);
    const upper = parseCurrency(getByTestId("cost-range-upper").textContent!);
    expect(lower).toBe(Math.round(costRange.lower));
    expect(upper).toBe(Math.round(costRange.upper));

    cleanup();
  });

  it("hides range message when costRange not provided", () => {
    const fixture = loadFixture("thomas-and-emily.json");
    const rangeResult = runCostRange(fixture, ref);

    const { queryByTestId } = render(
      <FamilyTotalSummary
        familyTotal={rangeResult.mean.familyTotal}
        period="yearly"
        onPeriodChange={() => {}}
      />,
    );

    expect(queryByTestId("cost-range-message")).toBeNull();

    cleanup();
  });

  it("hides range message when lower === upper (provider-only)", () => {
    const fixture = loadFixture("brennans.json");
    const rangeResult = runCostRange(fixture, ref);

    // Sanity: provider-only fixture should collapse
    expect(rangeResult.range.lower).toBe(rangeResult.range.upper);

    const { queryByTestId } = render(
      <FamilyTotalSummary
        familyTotal={rangeResult.mean.familyTotal}
        costRange={rangeResult.range}
        period="yearly"
        onPeriodChange={() => {}}
      />,
    );

    expect(queryByTestId("cost-range-message")).toBeNull();

    cleanup();
  });
});

describe("Explainer modal triggers", () => {
  it("rate info icon shown for area-average selections with rateDetails", () => {
    const fixture = loadFixture("thomas-and-emily.json");
    const result = runCalculator(fixture, ref);
    const isUC =
      fixture.localStorage.qualifyingBenefits.includes("universal_credit");

    for (let ci = 0; ci < result.children.length; ci++) {
      const child = result.children[ci];
      const sels = getAllSelections(child);
      const areaAvgWithDetails = sels.filter(
        (s) =>
          s.feeSource.type === "area_average" &&
          s.feeSource.rateDetails &&
          s.feeSource.rateDetails.length > 0,
      );

      if (areaAvgWithDetails.length === 0) continue;

      const { queryByTestId } = render(
        <ChildCostBreakdown
          childData={child}
          inputChild={fixture.localStorage.children[ci]}
          isUC={isUC}
          period="yearly"
        />,
      );

      for (const sel of areaAvgWithDetails) {
        expect(
          queryByTestId(`sel-${sel.selectionId}-rate-info`),
        ).not.toBeNull();
      }

      cleanup();
    }
  });

  it("rate info icon hidden for provider-only selections", () => {
    const fixture = loadFixture("brennans.json");
    const result = runCalculator(fixture, ref);
    const isUC =
      fixture.localStorage.qualifyingBenefits.includes("universal_credit");

    for (let ci = 0; ci < result.children.length; ci++) {
      const child = result.children[ci];
      const sels = getAllSelections(child);

      const { queryByTestId } = render(
        <ChildCostBreakdown
          childData={child}
          inputChild={fixture.localStorage.children[ci]}
          isUC={isUC}
          period="yearly"
        />,
      );

      for (const sel of sels) {
        expect(queryByTestId(`sel-${sel.selectionId}-rate-info`)).toBeNull();
      }

      cleanup();
    }
  });
});

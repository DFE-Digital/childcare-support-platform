import type { Scheme } from "../types/scheme.js";
import type { ChildEntitlement } from "../types/entitlement.js";
import type { SupportEntry } from "../types/cost-result.js";
import type { ChildData } from "../types/family.js";
import { getRoundFn } from "./rounding.js";

interface ChildCostSummary {
  child: ChildData;
  entitlement: ChildEntitlement;
  childcareFees: number;
  fundedHoursSaving: number;
}

export interface PerChildSupport {
  childId: number;
  tfc: number;
  uc: number;
}

export interface GovernmentSupportResult {
  taxFreeChildcare: SupportEntry | null;
  ucChildcare: SupportEntry | null;
  perChild: PerChildSupport[];
}

export function calculateGovernmentSupport(
  children: ChildCostSummary[],
  schemes: Scheme[],
  universalCredit: boolean,
  roundFn: (x: number) => number = getRoundFn("precise"),
): GovernmentSupportResult {
  // Initialise per-child entries for every child
  const perChildMap = new Map<number, { tfc: number; uc: number }>();
  for (const { child } of children) {
    perChildMap.set(child.id, { tfc: 0, uc: 0 });
  }

  if (universalCredit) {
    const ucResult = calculateUCChildcare(
      children,
      schemes,
      perChildMap,
      roundFn,
    );
    return {
      taxFreeChildcare: null,
      ucChildcare: ucResult,
      perChild: mapToArray(perChildMap),
    };
  }

  const tfcResult = calculateTFC(children, schemes, perChildMap, roundFn);
  return {
    taxFreeChildcare: tfcResult,
    ucChildcare: null,
    perChild: mapToArray(perChildMap),
  };
}

function mapToArray(
  m: Map<number, { tfc: number; uc: number }>,
): PerChildSupport[] {
  return Array.from(m.entries()).map(([childId, v]) => ({
    childId,
    tfc: v.tfc,
    uc: v.uc,
  }));
}

function calculateTFC(
  children: ChildCostSummary[],
  schemes: Scheme[],
  perChildMap: Map<number, { tfc: number; uc: number }>,
  roundFn: (x: number) => number,
): SupportEntry | null {
  const tfcScheme = schemes.find((s) => s.id === "tax_free_childcare");
  if (!tfcScheme) return null;

  const topUpRate = tfcScheme.topUpRate ?? 0.25;
  const effectiveRate = topUpRate / (1 + topUpRate); // 0.25/1.25 = 0.20
  const standardCap = tfcScheme.maxGovernmentContributionPerYear ?? 2000;
  const disabledCap =
    tfcScheme.maxGovernmentContributionPerYearDisabled ?? 4000;

  let totalSaving = 0;
  const childNotes: string[] = [];
  let eligibleCount = 0;

  for (const {
    child,
    entitlement,
    childcareFees,
    fundedHoursSaving,
  } of children) {
    // Check if this child is eligible for TFC
    const tfcEntitlement = entitlement.schemes.find(
      (s) => s.schemeId === "tax_free_childcare",
    );
    if (!tfcEntitlement?.eligible) continue;

    eligibleCount++;

    const cap = child.hasSEND ? disabledCap : standardCap;
    const eligibleCosts = childcareFees - fundedHoursSaving;
    const uncappedSaving = eligibleCosts * effectiveRate;
    const saving = roundFn(Math.min(uncappedSaving, cap));

    totalSaving += saving;

    // Record per-child TFC allocation
    const entry = perChildMap.get(child.id);
    if (entry) entry.tfc = saving;

    if (uncappedSaving > cap) {
      childNotes.push(
        `${child.firstName}: £${saving.toFixed(0)} (capped at £${cap.toLocaleString()})`,
      );
    }
  }

  if (eligibleCount === 0) return null;

  const note =
    childNotes.length > 0
      ? childNotes.join(". ")
      : `${eligibleCount} child${eligibleCount > 1 ? "ren" : ""} eligible`;

  return {
    scheme: "Tax-Free Childcare",
    savingToParent: totalSaving,
    note,
  };
}

function calculateUCChildcare(
  children: ChildCostSummary[],
  schemes: Scheme[],
  perChildMap: Map<number, { tfc: number; uc: number }>,
  roundFn: (x: number) => number,
): SupportEntry | null {
  const ucScheme = schemes.find((s) => s.id === "universal_credit_childcare");
  if (!ucScheme) return null;

  const reimbursementRate = ucScheme.reimbursementRate ?? 0.85;

  // Count eligible children and track per-child eligible costs
  let eligibleCount = 0;
  let totalEligibleCosts = 0;
  const childEligibleCosts: Array<{ childId: number; eligible: number }> = [];

  for (const {
    child,
    entitlement,
    childcareFees,
    fundedHoursSaving,
  } of children) {
    const ucEntitlement = entitlement.schemes.find(
      (s) => s.schemeId === "universal_credit_childcare",
    );
    if (!ucEntitlement?.eligible) continue;

    eligibleCount++;
    const eligible = childcareFees - fundedHoursSaving;
    totalEligibleCosts += eligible;
    childEligibleCosts.push({ childId: child.id, eligible });
  }

  if (eligibleCount === 0) return null;

  const monthlyCap =
    eligibleCount === 1
      ? (ucScheme.maxPerMonthOneChild ?? 1031.88)
      : (ucScheme.maxPerMonthTwoOrMore ?? 1768.94);

  const monthlyEligible = totalEligibleCosts / 12;
  const monthlyReimbursement = Math.min(
    monthlyEligible * reimbursementRate,
    monthlyCap,
  );
  const annualSaving = roundFn(monthlyReimbursement * 12);

  // Allocate proportionally to each child, with remainder correction on last
  let allocatedSoFar = 0;
  for (let i = 0; i < childEligibleCosts.length; i++) {
    const { childId, eligible } = childEligibleCosts[i];
    const proportion =
      totalEligibleCosts > 0 ? eligible / totalEligibleCosts : 0;
    const entry = perChildMap.get(childId);
    if (entry) {
      if (i < childEligibleCosts.length - 1) {
        const childAlloc = roundFn(annualSaving * proportion);
        entry.uc = childAlloc;
        allocatedSoFar += childAlloc;
      } else {
        // Last child gets the remainder to ensure exact sum
        entry.uc = roundFn(annualSaving - allocatedSoFar);
      }
    }
  }

  const capped = monthlyEligible * reimbursementRate > monthlyCap;
  const note = capped
    ? `Capped at £${monthlyCap.toFixed(2)}/month`
    : `${(reimbursementRate * 100).toFixed(0)}% of eligible costs`;

  return {
    scheme: "Universal Credit childcare",
    savingToParent: annualSaving,
    note,
  };
}

import type { ChildEntitlement } from "../types/entitlement.js";
import type { PostcodeAreaCosts } from "../types/costs.js";
import type { CareTypeId } from "../types/family.js";
import type { FundedAgeBand } from "./age-band.js";

export interface FundedHoursAllocation {
  hoursPerWeek: number;
  schemeName: string;
}

export interface FundedHoursBreakdown {
  savingToParent: number;
  scheme: string;
  fundedHoursPerWeek: number;
  actualFundedHours: number;
  governmentFundingRate: number;
  shortfallPerHour: number;
}

const FUNDED_HOURS_WEEKS = 38;

const ELIGIBLE_CARE_TYPES: ReadonlySet<CareTypeId> = new Set([
  "private_nursery",
  "school_based_nursery",
  "childminder",
]);

/**
 * Determine funded hours per week from entitlement results.
 *
 * From September 2025, 30 Hours Working Families provides the full 30 hours
 * for all eligible ages (9 months to school age). For age-2 children, the
 * 15 Hours 2YO (disadvantage) entitlement can stack with 30 Hours WF, but
 * the total is capped at 30 hours. The disadvantage entitlement is listed
 * first (applied before the working parent hours), per policy guidance —
 * it is not contingent on work status, so it is preserved if the parent
 * stops working.
 */
export function determineFundedHoursPerWeek(
  childEntitlement: ChildEntitlement,
  ageBand: FundedAgeBand,
): FundedHoursAllocation[] {
  const allocations: FundedHoursAllocation[] = [];

  const isEligible = (schemeId: string) =>
    childEntitlement.schemes.some((s) => s.schemeId === schemeId && s.eligible);

  const has15Hours2YO = isEligible("15_hours_2_year_olds");
  const has30HoursWF = isEligible("30_hours_working_families");
  const has15HoursUniversal = isEligible("15_hours_universal");

  // 1. 15 Hours 2-Year-Olds (disadvantage) — applied first for age 2
  if (ageBand === "age2" && has15Hours2YO) {
    allocations.push({
      hoursPerWeek: 15,
      schemeName: "15 hours early learning for 2-year-olds",
    });
  }

  // 2. 30 Hours Working Families — full 30 hours from September 2025 for
  //    all age bands. When stacked with 15 Hours 2YO (above), the working
  //    parent allocation is reduced so the total does not exceed 30.
  if (has30HoursWF) {
    const alreadyAllocated = allocations.reduce(
      (sum, a) => sum + a.hoursPerWeek,
      0,
    );
    const wfHours = Math.max(30 - alreadyAllocated, 0);
    if (wfHours > 0) {
      allocations.push({
        hoursPerWeek: wfHours,
        schemeName: "30 hours working families",
      });
    }
  } else if (has15HoursUniversal) {
    // 3. 15 Hours Universal — only if not eligible for 30 Hours WF
    allocations.push({
      hoursPerWeek: 15,
      schemeName: "15 hours universal entitlement",
    });
  }

  return allocations;
}

/**
 * Calculate funded hours reduction for a single selection.
 * Returns null if care type is not eligible for funded hours.
 */
export function calculateFundedHoursReduction(
  fundedHoursRemaining: number,
  schemeName: string,
  ageBand: FundedAgeBand,
  effectiveHourlyRate: number,
  weeklyHours: number,
  careType: CareTypeId,
  areaCosts: PostcodeAreaCosts | null,
  selectionWeeksPerYear?: number,
): { breakdown: FundedHoursBreakdown; hoursUsed: number } | null {
  if (!ELIGIBLE_CARE_TYPES.has(careType)) return null;
  if (fundedHoursRemaining <= 0) return null;
  if (weeklyHours <= 0) return null;

  const govRate = getGovernmentFundingRate(ageBand, areaCosts);
  if (govRate <= 0) return null;

  const actualFundedHours = Math.min(fundedHoursRemaining, weeklyHours);

  // Funded hours saving cannot exceed the weeks the child actually attends
  const applicableWeeks = Math.min(
    FUNDED_HOURS_WEEKS,
    selectionWeeksPerYear ?? FUNDED_HOURS_WEEKS,
  );

  const shortfallPerHour = 0;
  const savingPerHour = effectiveHourlyRate;
  const savingToParent = actualFundedHours * savingPerHour * applicableWeeks;

  return {
    breakdown: {
      savingToParent,
      scheme: schemeName,
      fundedHoursPerWeek: actualFundedHours,
      actualFundedHours,
      governmentFundingRate: govRate,
      shortfallPerHour,
    },
    hoursUsed: actualFundedHours,
  };
}

function getGovernmentFundingRate(
  ageBand: FundedAgeBand,
  areaCosts: PostcodeAreaCosts | null,
): number {
  if (!areaCosts) return 0;
  const rates = areaCosts.governmentFundingRates;
  switch (ageBand) {
    case "under2":
      return rates.under2?.perHour ?? 0;
    case "age2":
      return rates.age2?.perHour ?? 0;
    case "age3to4":
      return rates.age3to4?.perHour ?? 0;
  }
}

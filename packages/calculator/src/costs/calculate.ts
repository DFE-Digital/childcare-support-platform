import type {
  LocalStorageData,
  ChildData,
  ChildcareSelection,
  CareTypeId,
} from "../types/family.js";
import type { Scheme } from "../types/scheme.js";
import type {
  EntitlementResult,
  ChildEntitlement,
} from "../types/entitlement.js";
import type { ProviderCareType } from "../types/provider.js";
import type { PostcodeAreaCosts } from "../types/costs.js";
import type {
  RateDetail,
  FeeSource,
  CostSelection,
  ChildCostData,
  ChildSupportBreakdown,
  FamilyTotal,
  FamilyCostResult,
  CostRangeResult,
  SupportEntry,
} from "../types/cost-result.js";
import type { ResolvedFees, FeeVariant } from "./fee-lookup.js";
import { getAgeBand } from "./age-band.js";
import type { AgeBand } from "./age-band.js";
import { resolveFeesForSelection } from "./fee-lookup.js";
import { calculateChildcareFees } from "./gross-cost.js";
import { calculateAdditionalCharges } from "./additional-charges.js";
import {
  determineFundedHoursPerWeek,
  calculateFundedHoursReduction,
} from "./funded-hours.js";
import { calculateGovernmentSupport } from "./government-support.js";
import { getRoundFn } from "./rounding.js";
import type { RoundingMode } from "./rounding.js";

export interface CostCalculatorInput {
  data: LocalStorageData;
  schemes: Scheme[];
  entitlements: EntitlementResult;
  providers: Array<{ id: string; name: string; careTypes: ProviderCareType[] }>;
  areaCosts: PostcodeAreaCosts | null;
  referenceDate: Date;
  rounding?: RoundingMode;
  feeVariant?: FeeVariant;
  includeAdditionalCharges?: boolean;
}

const TERM_TIME_CARE_TYPES: ReadonlySet<CareTypeId> = new Set([
  "breakfast_club",
  "free_breakfast_club",
  "after_school_club",
  "school_based_nursery",
]);

const YEAR_ROUND_CARE_TYPES: ReadonlySet<CareTypeId> = new Set([
  "childminder",
  "holiday_club",
  "private_nursery",
]);

function formatRate(amount: number): string {
  return "£" + amount.toFixed(2);
}

function formatHours(decimal: number): string {
  const hours = Math.floor(decimal);
  const minutes = Math.round((decimal - hours) * 60);
  if (minutes === 0) return `${hours} hour${hours !== 1 ? "s" : ""}`;
  if (hours === 0) return `${minutes} minute${minutes !== 1 ? "s" : ""}`;
  return `${hours} hour${hours !== 1 ? "s" : ""} ${minutes} minute${minutes !== 1 ? "s" : ""}`;
}

function buildRateDescription(
  careType: CareTypeId,
  fees: ResolvedFees,
  customSessionHours?: { morning?: number; afternoon?: number },
  sessions?: {
    morning?: { daysPerWeek: number };
    afternoon?: { daysPerWeek: number };
    fullDay?: { daysPerWeek: number };
  },
): string {
  const parts: string[] = [];

  const sh = fees.sessionHours;
  switch (careType) {
    case "private_nursery":
    case "school_based_nursery": {
      const morningHours = customSessionHours?.morning ?? sh?.morning;
      const afternoonHours = customSessionHours?.afternoon ?? sh?.afternoon;
      const morningFee =
        customSessionHours?.morning != null && fees.perHour != null
          ? fees.perHour * customSessionHours.morning
          : fees.morningSession;
      const afternoonFee =
        customSessionHours?.afternoon != null && fees.perHour != null
          ? fees.perHour * customSessionHours.afternoon
          : fees.afternoonSession;

      const hasFullDay = !sessions || (sessions.fullDay?.daysPerWeek ?? 0) > 0;
      const hasMorning = !sessions || (sessions.morning?.daysPerWeek ?? 0) > 0;
      const hasAfternoon =
        !sessions || (sessions.afternoon?.daysPerWeek ?? 0) > 0;

      if (hasFullDay && fees.fullDay)
        parts.push(
          `${formatRate(fees.fullDay)} per full day${sh?.fullDay ? ` (${formatHours(sh.fullDay)})` : ""}`,
        );
      if (hasMorning && morningFee)
        parts.push(
          `${formatRate(morningFee)} per morning${morningHours ? ` (${formatHours(morningHours)})` : ""}`,
        );
      if (hasAfternoon && afternoonFee)
        parts.push(
          `${formatRate(afternoonFee)} per afternoon${afternoonHours ? ` (${formatHours(afternoonHours)})` : ""}`,
        );
      break;
    }
    case "childminder":
      if (fees.perHour) parts.push(`${formatRate(fees.perHour)} per hour`);
      break;
    case "breakfast_club":
    case "after_school_club":
      if (fees.perSession)
        parts.push(`${formatRate(fees.perSession)} per session`);
      break;
    case "free_breakfast_club":
      parts.push("no cost");
      break;
    case "holiday_club":
      if (fees.perDay) parts.push(`${formatRate(fees.perDay)} per day`);
      break;
  }

  return parts.join(", ");
}

function buildFeeSource(
  sel: {
    providerId: string | null;
    careType: CareTypeId;
    sessionHours?: { morning?: number; afternoon?: number };
    sessions?: {
      morning?: { daysPerWeek: number };
      afternoon?: { daysPerWeek: number };
      fullDay?: { daysPerWeek: number };
    };
  },
  fees: ResolvedFees,
  providers: Array<{ id: string; name: string }>,
  areaCosts: PostcodeAreaCosts | null,
): FeeSource {
  const rates = buildRateDescription(
    sel.careType,
    fees,
    sel.sessionHours,
    sel.sessions,
  );

  if (sel.providerId) {
    const provider = providers.find((p) => p.id === sel.providerId);
    return {
      type: "provider",
      providerName: provider?.name,
      rates,
    };
  }

  const baseSessionHours = fees.sessionHours;
  const hasFullDay = (sel.sessions?.fullDay?.daysPerWeek ?? 0) > 0;
  const sessionHours = sel.sessionHours
    ? {
        morning: sel.sessionHours.morning ?? baseSessionHours?.morning ?? 5,
        afternoon:
          sel.sessionHours.afternoon ?? baseSessionHours?.afternoon ?? 5,
        ...(hasFullDay && baseSessionHours?.fullDay != null
          ? { fullDay: baseSessionHours.fullDay }
          : {}),
      }
    : baseSessionHours
      ? {
          morning: baseSessionHours.morning,
          afternoon: baseSessionHours.afternoon,
          ...(hasFullDay && baseSessionHours.fullDay != null
            ? { fullDay: baseSessionHours.fullDay }
            : {}),
        }
      : undefined;

  return {
    type: "area_average",
    costArea: fees.costArea,
    laName: areaCosts?.laName,
    regionName: areaCosts?.regionName,
    nationName: areaCosts?.nationName,
    rates,
    sessionHours,
  };
}

const RATE_FIELDS: Array<{
  key: keyof ResolvedFees;
  label: string;
}> = [
  { key: "fullDay", label: "Full day" },
  { key: "morningSession", label: "Morning" },
  { key: "afternoonSession", label: "Afternoon" },
  { key: "perHour", label: "Per hour" },
  { key: "perSession", label: "Per session" },
  { key: "perDay", label: "Per day" },
];

function buildRateDetails(
  sel: ChildcareSelection,
  ageBand: AgeBand,
  providers: Array<{ id: string; name: string; careTypes: ProviderCareType[] }>,
  areaCosts: PostcodeAreaCosts,
): RateDetail[] {
  const variants: FeeVariant[] = ["lower", "mean", "upper"];
  const feesByVariant = Object.fromEntries(
    variants.map((v) => [
      v,
      resolveFeesForSelection(sel, ageBand, providers, areaCosts, v),
    ]),
  ) as Record<FeeVariant, ResolvedFees>;

  const details: RateDetail[] = [];

  for (const { key, label } of RATE_FIELDS) {
    const mean = feesByVariant.mean[key];
    if (typeof mean === "number" && mean > 0) {
      details.push({
        label,
        mean,
        lower: (feesByVariant.lower[key] as number) ?? mean,
        upper: (feesByVariant.upper[key] as number) ?? mean,
      });
    }
  }

  return details;
}

export function calculateCosts(input: CostCalculatorInput): FamilyCostResult {
  const { data, schemes, entitlements, providers, areaCosts, referenceDate } =
    input;
  const roundFn = getRoundFn(input.rounding ?? "precise");

  const childCalcResults: Array<{
    child: ChildData;
    result: ChildCalculationResult;
    entitlement: ChildEntitlement;
  }> = [];

  let familyChildcareFees = 0;
  let familyAdditionalCharges = 0;
  let familyFundedHoursSaving = 0;

  for (const child of data.children) {
    const childEntitlement = entitlements.children.find(
      (c) => c.childId === child.id,
    );
    if (!childEntitlement) continue;

    const result = calculateChildCosts(
      child,
      childEntitlement,
      providers,
      areaCosts,
      referenceDate,
      roundFn,
      input.feeVariant,
      input.includeAdditionalCharges,
    );

    childCalcResults.push({ child, result, entitlement: childEntitlement });

    familyChildcareFees += result.childcareFees;
    familyAdditionalCharges += result.additionalChargesTotal;
    familyFundedHoursSaving += result.fundedHoursSaving;
  }

  // Government support (TFC or UC)
  const childCostSummaries = childCalcResults.map(
    ({ child, result, entitlement }) => ({
      child,
      entitlement,
      childcareFees: result.childcareFees,
      fundedHoursSaving: result.fundedHoursSaving,
    }),
  );

  const govSupport = calculateGovernmentSupport(
    childCostSummaries,
    schemes,
    data.qualifyingBenefits.includes("universal_credit"),
    roundFn,
  );

  // Build child results with per-child support allocations
  const childResults: ChildCostData[] = childCalcResults.map(
    ({ child, result }) => {
      const perChild = govSupport.perChild.find((p) => p.childId === child.id);
      const support: ChildSupportBreakdown = {
        fundedHours: result.fundedHoursSaving,
        taxFreeChildcare: perChild?.tfc ?? 0,
        ucChildcare: perChild?.uc ?? 0,
        total:
          result.fundedHoursSaving + (perChild?.tfc ?? 0) + (perChild?.uc ?? 0),
      };
      return finalizeChildCostData(result.costData, support);
    },
  );

  // Funded hours support entry
  const fundedHoursEntry: SupportEntry | null =
    familyFundedHoursSaving > 0
      ? buildFundedHoursSupportEntry(childResults, familyFundedHoursSaving)
      : null;

  const totalSavingToParent =
    familyFundedHoursSaving +
    (govSupport.taxFreeChildcare?.savingToParent ?? 0) +
    (govSupport.ucChildcare?.savingToParent ?? 0);

  const totalCost = familyChildcareFees + familyAdditionalCharges;

  const familyTotal: FamilyTotal = {
    totalCostOfChildcare: {
      childcareFees: familyChildcareFees,
      additionalCharges: familyAdditionalCharges,
      total: totalCost,
    },
    totalGovernmentSupport: {
      fundedHours: fundedHoursEntry,
      taxFreeChildcare: govSupport.taxFreeChildcare,
      ucChildcare: govSupport.ucChildcare,
      totalSavingToParent,
    },
    estimatedAnnualCostToFamily: totalCost - totalSavingToParent,
  };

  return { children: childResults, familyTotal };
}

export function calculateCostRange(
  input: CostCalculatorInput,
): CostRangeResult {
  const lower = calculateCosts({ ...input, feeVariant: "lower" });
  const mean = calculateCosts({ ...input, feeVariant: "mean" });
  const upper = calculateCosts({ ...input, feeVariant: "upper" });

  return {
    mean,
    lower,
    upper,
    range: {
      lower: lower.familyTotal.estimatedAnnualCostToFamily,
      upper: upper.familyTotal.estimatedAnnualCostToFamily,
    },
  };
}

interface ChildCalculationResult {
  costData: ChildCostData;
  childcareFees: number;
  additionalChargesTotal: number;
  fundedHoursSaving: number;
}

function calculateChildCosts(
  child: ChildData,
  childEntitlement: ChildEntitlement,
  providers: Array<{ id: string; name: string; careTypes: ProviderCareType[] }>,
  areaCosts: PostcodeAreaCosts | null,
  referenceDate: Date,
  roundFn: (x: number) => number,
  feeVariant?: FeeVariant,
  includeAdditionalCharges?: boolean,
): ChildCalculationResult {
  const ageBand = getAgeBand(child, referenceDate);

  // Determine funded hours pool for this child (may be stacked for age-2)
  const fundedAllocations = determineFundedHoursPerWeek(
    childEntitlement,
    ageBand,
  );
  const totalFundedHours = fundedAllocations.reduce(
    (sum, a) => sum + a.hoursPerWeek,
    0,
  );
  const combinedSchemeName = fundedAllocations
    .map((a) => a.schemeName)
    .join("; ");
  let fundedHoursRemaining = totalFundedHours;

  let childFees = 0;
  let childAdditional = 0;
  let childFundedSaving = 0;
  const allSelections: Array<{
    selection: CostSelection;
    careType: CareTypeId;
  }> = [];

  for (const sel of child.childcareSelections) {
    const careType = sel.careType as CareTypeId;
    // Resolve fees
    const fees = resolveFeesForSelection(
      sel,
      ageBand,
      providers,
      areaCosts,
      feeVariant,
    );

    // Childcare fees
    const selFees = calculateChildcareFees(sel, fees);
    const roundedFees = roundFn(selFees.total);
    childFees += roundedFees;

    // Additional charges
    const additional =
      includeAdditionalCharges !== false
        ? calculateAdditionalCharges(sel, fees)
        : { total: 0, estimated: false };
    const roundedAdditional = roundFn(additional.total);
    childAdditional += roundedAdditional;

    // Funded hours reduction
    const fundedResult = calculateFundedHoursReduction(
      fundedHoursRemaining,
      combinedSchemeName,
      ageBand,
      selFees.effectiveHourlyRate,
      selFees.weeklyHours,
      careType,
      areaCosts,
      selFees.weeksPerYear,
    );

    let fundedBreakdown: CostSelection["calculation"]["step3_fundedHoursReduction"] =
      null;
    let roundedFundedSaving = 0;
    if (fundedResult) {
      fundedHoursRemaining -= fundedResult.hoursUsed;
      roundedFundedSaving = roundFn(fundedResult.breakdown.savingToParent);
      childFundedSaving += roundedFundedSaving;
      fundedBreakdown = {
        savingToParent: roundedFundedSaving,
        scheme: fundedResult.breakdown.scheme,
      };
    }

    const estimatedAnnualCostToParent =
      roundedFees - roundedFundedSaving + roundedAdditional;

    const feeSource = buildFeeSource(
      {
        providerId: sel.providerId,
        careType,
        sessionHours: sel.sessionHours,
        sessions: sel.sessions,
      },
      fees,
      providers,
      areaCosts,
    );

    if (!sel.providerId && areaCosts) {
      feeSource.rateDetails = buildRateDetails(
        sel,
        ageBand,
        providers,
        areaCosts,
      );
    }

    allSelections.push({
      selection: {
        selectionId: sel.id,
        careType: sel.careType,
        feeSource,
        weeksPerYear: selFees.weeksPerYear,
        calculation: {
          step1_childcareFees: { total: roundedFees },
          step3_fundedHoursReduction: fundedBreakdown,
          step4_additionalCharges: {
            total: roundedAdditional,
            estimated: additional.estimated,
          },
          estimatedAnnualCostToParent,
        },
      },
      careType,
    });
  }

  // Group selections into term-time / year-round if child has mixed care
  const costData = groupSelections(child, allSelections);

  return {
    costData,
    childcareFees: childFees,
    additionalChargesTotal: childAdditional,
    fundedHoursSaving: childFundedSaving,
  };
}

function groupSelections(
  child: ChildData,
  allSelections: Array<{
    selection: CostSelection;
    careType: CareTypeId;
  }>,
): ChildCostData {
  const hasTermTime = allSelections.some((s) =>
    TERM_TIME_CARE_TYPES.has(s.careType),
  );
  const hasYearRound = allSelections.some((s) =>
    YEAR_ROUND_CARE_TYPES.has(s.careType),
  );
  const hasMixed = hasTermTime && hasYearRound;

  // grossCost = sum of (gross fees + additional charges) per selection
  const grossCost = allSelections.reduce(
    (sum, s) =>
      sum +
      s.selection.calculation.step1_childcareFees.total +
      s.selection.calculation.step4_additionalCharges.total,
    0,
  );

  // Support is placeholder — populated later via finalizeChildCostData
  const placeholderSupport: ChildSupportBreakdown = {
    fundedHours: 0,
    taxFreeChildcare: 0,
    ucChildcare: 0,
    total: 0,
  };

  const base: ChildCostData = {
    child: child.firstName,
    total: {
      grossCost,
      support: placeholderSupport,
      costToFamily: grossCost,
    },
  };

  if (hasMixed) {
    // Split into term-time and year-round groups
    const termTimeSelections = allSelections
      .filter((s) => TERM_TIME_CARE_TYPES.has(s.careType))
      .map((s) => s.selection);
    const yearRoundSelections = allSelections
      .filter((s) => YEAR_ROUND_CARE_TYPES.has(s.careType))
      .map((s) => s.selection);

    return {
      ...base,
      termTimeCare: { weeks: 38, selections: termTimeSelections },
      yearRoundCare: { selections: yearRoundSelections },
    };
  }

  // All selections in flat array
  return {
    ...base,
    selections: allSelections.map((s) => s.selection),
  };
}

/** Fill in the real per-child support breakdown once government support is known. */
function finalizeChildCostData(
  costData: ChildCostData,
  support: ChildSupportBreakdown,
): ChildCostData {
  return {
    ...costData,
    total: {
      ...costData.total,
      support,
      costToFamily: costData.total.grossCost - support.total,
    },
  };
}

function buildFundedHoursSupportEntry(
  childResults: ChildCostData[],
  totalSaving: number,
): SupportEntry {
  // Collect scheme names from children who have funded hours
  const schemeNames: string[] = [];
  for (const child of childResults) {
    const allSelections = [
      ...(child.selections ?? []),
      ...(child.termTimeCare?.selections ?? []),
      ...(child.yearRoundCare?.selections ?? []),
    ];
    for (const sel of allSelections) {
      if (sel.calculation.step3_fundedHoursReduction) {
        const scheme = sel.calculation.step3_fundedHoursReduction.scheme;
        if (!schemeNames.includes(scheme)) {
          schemeNames.push(scheme);
        }
      }
    }
  }

  return {
    scheme: schemeNames.join("; "),
    savingToParent: totalSaving,
    note: `Funded hours across ${schemeNames.length} scheme${schemeNames.length > 1 ? "s" : ""}`,
  };
}

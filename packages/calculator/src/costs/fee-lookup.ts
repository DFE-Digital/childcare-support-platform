import type { ProviderCareType, AdditionalCharge } from "../types/provider.js";
import type {
  PostcodeAreaCosts,
  AverageCostsCareType,
  CostTriad,
  CostArea,
} from "../types/costs.js";
import type { ChildcareSelection, CareTypeId } from "../types/family.js";
import type { AgeBand } from "./age-band.js";

export type FeeVariant = "lower" | "mean" | "upper";

export interface ResolvedFees {
  morningSession?: number;
  afternoonSession?: number;
  fullDay?: number;
  perSession?: number;
  perDay?: number;
  perHour?: number;
  sessionHours?: { morning: number; afternoon: number; fullDay?: number };
  operatingWeeksPerYear: number;
  additionalCharges: AdditionalCharge[];
  costArea?: CostArea;
}

export function resolveFeesForSelection(
  selection: ChildcareSelection,
  ageBand: AgeBand,
  providers: Array<{
    id: string;
    name: string;
    careTypes: ProviderCareType[];
  }>,
  areaCosts: PostcodeAreaCosts | null,
  variant: FeeVariant = "mean",
): ResolvedFees {
  // Try provider-specific fees first
  if (selection.providerId) {
    const provider = providers.find((p) => p.id === selection.providerId);
    if (provider) {
      const careType = provider.careTypes.find(
        (ct) => ct.type === selection.careType,
      );
      if (careType) {
        return resolveFromProvider(careType, ageBand, selection.careType);
      }
    }
  }

  // Fall back to area averages
  if (areaCosts) {
    return resolveFromAreaCosts(
      areaCosts,
      selection.careType,
      ageBand,
      variant,
    );
  }

  // No data available — return zero fees
  return {
    operatingWeeksPerYear: 38,
    additionalCharges: [],
  };
}

function resolveFromProvider(
  careType: ProviderCareType,
  ageBand: AgeBand,
  careTypeId: CareTypeId,
): ResolvedFees {
  // For clubs and holiday, fees may be flat (not nested under age bands).
  // Provider JSON may have { "perSession": 14.50 } at root of fees object
  // rather than { "age3to4": { "perSession": 14.50 } }.
  const flatFees = careType.fees as Record<string, unknown>;

  if (
    careTypeId === "breakfast_club" ||
    careTypeId === "free_breakfast_club" ||
    careTypeId === "after_school_club"
  ) {
    const perSession =
      typeof flatFees.perSession === "number"
        ? flatFees.perSession
        : (careType.fees[ageBand]?.perSession ?? 0);
    return {
      perSession,
      operatingWeeksPerYear: careType.operatingWeeksPerYear ?? 38,
      additionalCharges: careType.additionalCharges,
    };
  }

  if (careTypeId === "holiday_club") {
    const perDay =
      typeof flatFees.perDay === "number"
        ? flatFees.perDay
        : (careType.fees[ageBand]?.perDay ?? 0);
    return {
      perDay,
      operatingWeeksPerYear: careType.operatingWeeksPerYear ?? 52,
      additionalCharges: careType.additionalCharges,
    };
  }

  // Age-banded care types (nursery, childminder)
  // Providers may use "age2plus" to cover both age2 and age3to4.
  const fees =
    careType.fees[ageBand] ??
    (ageBand === "age2" || ageBand === "age3to4"
      ? careType.fees["age2plus"]
      : undefined) ??
    {};

  return {
    morningSession: fees.morningSession,
    afternoonSession: fees.afternoonSession,
    fullDay: fees.fullDay,
    perHour: fees.perHour,
    perSession: fees.perSession,
    perDay: fees.perDay,
    sessionHours: careType.sessionHours,
    operatingWeeksPerYear: careType.operatingWeeksPerYear ?? 50,
    additionalCharges: careType.additionalCharges,
  };
}

export function extractCost(
  cost: number | CostTriad,
  variant: FeeVariant = "mean",
): number {
  return typeof cost === "number" ? cost : cost[variant];
}

function resolveAdditionalCharges(
  charges: AverageCostsCareType["additionalCharges"],
  variant: FeeVariant = "mean",
): AdditionalCharge[] {
  return charges.map((c) => ({
    item: c.item,
    cost: extractCost(c.cost, variant),
    unit: c.unit,
    description: c.description,
  }));
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

function resolveFromAreaCosts(
  areaCosts: PostcodeAreaCosts,
  careTypeId: CareTypeId,
  ageBand: AgeBand,
  variant: FeeVariant = "mean",
): ResolvedFees {
  const areaData = areaCosts.averageCosts[careTypeId] as
    | AverageCostsCareType
    | undefined;

  if (!areaData) {
    return { operatingWeeksPerYear: 38, additionalCharges: [] };
  }

  const charges = resolveAdditionalCharges(
    areaData.additionalCharges ?? [],
    variant,
  );

  // Clubs: fees keyed under "all" (not age-banded), convert to perSession
  if (
    careTypeId === "breakfast_club" ||
    careTypeId === "free_breakfast_club" ||
    careTypeId === "after_school_club"
  ) {
    const triad = areaData.fees["all"]?.perHour;
    const hourlyRate = triad?.[variant] ?? 0;
    const sessionDuration = areaData.sessionHours?.session ?? 1;
    return {
      perSession: round2(hourlyRate * sessionDuration),
      operatingWeeksPerYear: areaData.operatingWeeksPerYear ?? 38,
      additionalCharges: charges,
      costArea: triad?.area,
    };
  }

  // Holiday club: fees keyed under "all", convert to perDay
  if (careTypeId === "holiday_club") {
    const triad = areaData.fees["all"]?.perHour;
    const hourlyRate = triad?.[variant] ?? 0;
    const dayDuration = areaData.sessionHours?.day ?? 7;
    return {
      perDay: round2(hourlyRate * dayDuration),
      operatingWeeksPerYear: 52,
      additionalCharges: charges,
      costArea: triad?.area,
    };
  }

  // Age-banded care types (nursery, childminder)
  const bandFees = areaData.fees?.[ageBand];
  const hourlyRate = bandFees?.perHour?.[variant] ?? 0;
  const costArea = bandFees?.perHour?.area;

  // Childminder: return perHour directly
  if (careTypeId === "childminder") {
    return {
      perHour: hourlyRate,
      operatingWeeksPerYear: areaData.operatingWeeksPerYear ?? 50,
      additionalCharges: charges,
      costArea,
    };
  }

  // Nurseries: convert hourly to session fees using sessionHours from data
  const sh = areaData.sessionHours;
  const sessionHours: { morning: number; afternoon: number; fullDay?: number } =
    {
      morning: sh?.morning ?? 5,
      afternoon: sh?.afternoon ?? 5,
      ...(sh?.fullDay != null ? { fullDay: sh.fullDay } : {}),
    };

  return {
    morningSession: round2(hourlyRate * sessionHours.morning),
    afternoonSession: round2(hourlyRate * sessionHours.afternoon),
    ...(sessionHours.fullDay != null
      ? { fullDay: round2(hourlyRate * sessionHours.fullDay) }
      : {}),
    perHour: hourlyRate,
    sessionHours,
    operatingWeeksPerYear: areaData.operatingWeeksPerYear ?? 50,
    additionalCharges: charges,
    costArea,
  };
}

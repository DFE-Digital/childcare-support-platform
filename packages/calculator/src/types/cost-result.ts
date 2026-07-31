import type { CostArea } from "./costs.js";

export interface RateDetail {
  label: string;
  mean: number;
  lower: number;
  upper: number;
}

export interface SessionHours {
  morning: number;
  afternoon: number;
  fullDay?: number;
}

export interface FeeSource {
  type: "provider" | "area_average";
  providerName?: string;
  costArea?: CostArea;
  laName?: string;
  regionName?: string;
  nationName?: string;
  rates: string;
  rateDetails?: RateDetail[];
  sessionHours?: SessionHours;
}

export interface CostSelection {
  selectionId: number;
  careType: string;
  feeSource: FeeSource;
  weeksPerYear: number;
  calculation: {
    step1_childcareFees: { total: number };
    step3_fundedHoursReduction: {
      savingToParent: number;
      scheme: string;
    } | null;
    step4_additionalCharges: { total: number; estimated: boolean };
    estimatedAnnualCostToParent: number;
  };
}

export interface ChildSupportBreakdown {
  fundedHours: number;
  taxFreeChildcare: number;
  ucChildcare: number;
  total: number;
}

export interface ChildCostData {
  child: string;
  selections?: CostSelection[];
  termTimeCare?: { weeks: number; selections: CostSelection[] };
  yearRoundCare?: { selections: CostSelection[] };
  total: {
    grossCost: number;
    support: ChildSupportBreakdown;
    costToFamily: number;
  };
}

export interface SupportEntry {
  scheme: string;
  savingToParent: number;
  note: string;
}

export interface FamilyTotal {
  totalCostOfChildcare: {
    childcareFees: number;
    additionalCharges: number;
    total: number;
  };
  totalGovernmentSupport: {
    fundedHours: SupportEntry | null;
    taxFreeChildcare: SupportEntry | null;
    ucChildcare: SupportEntry | null;
    totalSavingToParent: number;
  };
  estimatedAnnualCostToFamily: number;
}

export interface FamilyCostResult {
  children: ChildCostData[];
  familyTotal: FamilyTotal;
}

export interface CostRangeResult {
  mean: FamilyCostResult;
  lower: FamilyCostResult;
  upper: FamilyCostResult;
  range: { lower: number; upper: number };
}

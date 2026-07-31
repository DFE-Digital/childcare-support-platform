export type CostArea = "la" | "region" | "national" | "insufficient";

export interface CostTriad {
  mean: number;
  lower: number;
  upper: number;
  area: CostArea;
}

export interface AverageCostsFees {
  [ageBandOrKey: string]: {
    perHour: CostTriad;
  };
}

export interface AverageCostsCareType {
  fees: AverageCostsFees;
  sessionHours?: {
    morning?: number;
    afternoon?: number;
    fullDay?: number;
    session?: number;
    day?: number;
  };
  operatingWeeksPerYear?: number;
  additionalCharges: Array<{
    item: string;
    cost: number | CostTriad;
    unit: string;
    description: string;
  }>;
}

export interface GovernmentFundingRate {
  perHour: number;
}

export interface FamilyInformationService {
  url: string;
}

export interface ProviderStatEntry {
  total: number;
  bboxOnly: number;
  insufficient: number;
}

export interface PostcodeAreaCosts {
  laName: string;
  regionName: string;
  nationName: string;
  lastUpdated: string;
  averageCosts: Record<string, AverageCostsCareType>;
  governmentFundingRates: {
    under2?: GovernmentFundingRate;
    age2?: GovernmentFundingRate;
    age3to4?: GovernmentFundingRate;
  };
  familyInformationServices?: FamilyInformationService[];
  showBetaWarning?: boolean;
  providerStats?: Record<string, ProviderStatEntry>;
  laBounds?: { south: number; west: number; north: number; east: number };
}

export interface AverageCosts {
  postcodeAreas: Record<string, PostcodeAreaCosts>;
}

export interface PostcodeLookup {
  description: string;
  postcodes: Record<
    string,
    {
      area: string;
      localAuthority: string;
    }
  >;
}

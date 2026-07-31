export interface ProviderFees {
  [ageBand: string]: {
    morningSession?: number;
    afternoonSession?: number;
    fullDay?: number;
    perSession?: number;
    perDay?: number;
    perHour?: number;
  };
}

export interface AdditionalCharge {
  item: string;
  cost: number;
  unit: string;
  description: string;
}

export interface EligibleAgeRange {
  minMonths?: number;
  minYears?: number;
  maxYears?: number;
}

export interface MinimumCommitment {
  amount?: number;
  unitPerWeek?: "full_days" | "sessions" | "hours";
  duration?: "half_term" | "term" | "year";
}

export interface WaitingListEntry {
  weeks?: number;
  months?: number;
}

export interface ProviderCareType {
  type: string;
  openingHours?: { days: string; open: string; close: string }[];
  operatingWeeksPerYear?: number;
  fees: ProviderFees;
  additionalCharges: AdditionalCharge[];
  sessionHours?: { morning: number; afternoon: number; fullDay: number };
  eligibleAgeRange?: EligibleAgeRange;
  eligibleAttendeesOnly: boolean;
  eligibleInstitutions?: string[];
  eligibleOther?: string[];
  fundedHoursAccepted?: boolean;
  waitingList?: Record<string, WaitingListEntry> | null;
  minimumCommitment?: MinimumCommitment | false;
  notes?: { type: "tick" | "warn"; description: string }[];
  website?: string;
  fisUrl?: string;
}

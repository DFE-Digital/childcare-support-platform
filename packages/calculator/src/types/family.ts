export const AGE_BRACKETS = ["16-17", "18-20", "21+"] as const;
export type AgeBracket = (typeof AGE_BRACKETS)[number];

export const STUDY_LEVELS = [
  "school_sixth_form",
  "further_education",
  "higher_education",
] as const;
export type StudyLevel = (typeof STUDY_LEVELS)[number];

export const WORKING_STATUSES = [
  "earning_above_nmw",
  "earning_above_apprentice_nmw",
  "earning_below_nmw",
  "not_working",
  "income_over_100k",
] as const;
export type WorkingStatus = (typeof WORKING_STATUSES)[number];

export const RESIDENCY_STATUSES = [
  "british_irish_citizen",
  "settled_status",
  "pre_settled_status",
  "permission_to_access_public_funds",
  "no_recourse_to_public_funds",
  "other",
] as const;
export type ResidencyStatus = (typeof RESIDENCY_STATUSES)[number];

export const CARE_TYPE_IDS = [
  "private_nursery",
  "school_based_nursery",
  "childminder",
  "breakfast_club",
  "free_breakfast_club",
  "after_school_club",
  "holiday_club",
] as const;
export type CareTypeId = (typeof CARE_TYPE_IDS)[number];

export interface PersonData {
  isApprentice: boolean;
  firstYearApprentice: boolean | null;
  isSelfEmployed: boolean;
  selfEmployedLessThanTwelveMonths: boolean | null;
  ageBracket: AgeBracket | null;
  workingStatus: WorkingStatus;
  receivesQualifyingAllowance: boolean | null;
  startingWorkNextMonth: boolean | null;
  hasLimitedCapacityForWork: boolean | null;
  hasNationalInsuranceNumber: boolean;
  residencyStatus: ResidencyStatus;
  isStudying: boolean;
  studyLevel: StudyLevel | null;
  isFullTimeStudent: boolean | null;
  courseIsPubliclyFunded: boolean | null;
  eligibleForStudentFinance: boolean | null;
}

export interface ChildcareSelection {
  id: number;
  careType: CareTypeId;
  sessions?: {
    morning?: { daysPerWeek: number };
    afternoon?: { daysPerWeek: number };
    fullDay?: { daysPerWeek: number };
  };
  sessionHours?: { morning?: number; afternoon?: number };
  daysPerWeek?: number;
  hoursPerWeek?: number;
  weeksPerYear?: number;
  daysPerYear?: number;
  providerId: string | null;
}

export interface SENDDetails {
  receivesDLA: boolean;
  receivesPIP: boolean;
  isRegisteredBlind: boolean;
}

export interface ChildData {
  id: number;
  firstName: string;
  birthMonth: number;
  birthYear: number;
  hasSEND: boolean;
  sendDetails: SENDDetails | null;
  isFostered: boolean;
  hasEHCP: boolean;
  hasLeftCareForAdoptionOrSpecialGuardianship: boolean;
  childcareSelections: ChildcareSelection[];
}

export interface LocalStorageData {
  schemaVersion: number;
  location: { postcode: string; ladCodes: string[] };
  household: { hasPartner: boolean };
  user: PersonData;
  partner: PersonData | null;
  ucIncomeBelowThreshold: boolean;
  nrpfIncomeUnderThreshold: number;
  nrpfSavingsUnderLimit: number;
  qualifyingBenefits: string[];
  children: ChildData[];
  shortlistedProviders: string[];
}

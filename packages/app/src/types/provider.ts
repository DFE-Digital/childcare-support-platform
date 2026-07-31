import type { ProviderCareType } from "@bsil/calculator";

export type {
  ProviderFees,
  AdditionalCharge,
  EligibleAgeRange,
  MinimumCommitment,
  WaitingListEntry,
  ProviderCareType,
} from "@bsil/calculator";

export interface ProviderAddress {
  line1: string;
  line2: string;
  city: string;
  postcode: string;
}

export interface OfstedLegacy {
  framework: "legacy";
  inspectionDate: string;
  legacyRating: string;
  safeguardingMet?: boolean;
  legacySubGrades?: Record<string, string>;
}

export interface OfstedUngradedConfirmed {
  framework: "ungraded_confirmed";
  inspectionDate: string;
  legacyRating: string;
}

export interface OfstedLegacyTransition {
  framework: "legacy_transition";
  inspectionDate: string;
  safeguardingMet: boolean;
  legacySubGrades: Record<string, string>;
}

export interface OfstedReportCard {
  framework: "report_card";
  inspectionDate: string;
  safeguardingMet: boolean;
  achievement?: string;
  curriculumAndTeaching?: string;
  behaviourAttitudesRoutines?: string;
  childrensWelfareWellbeing?: string;
  inclusion?: string;
  leadershipAndGovernance?: string;
  attendanceAndBehaviour?: string;
  personalDevelopmentWellbeing?: string;
  earlyYears?: string;
  ccrMet?: boolean;
  vcrMet?: boolean;
}

export type OfstedInfo =
  | OfstedLegacy
  | OfstedUngradedConfirmed
  | OfstedLegacyTransition
  | OfstedReportCard;

export interface CmaInfo {
  agency: string;
  qaGrading?: string;
  inspectionDate?: string;
}

// --- Report card constants ---

export const REPORT_CARD_GRADES = [
  { grade: "Exceptional", colour: "#0176E0", rank: 0 },
  { grade: "Strong standard", colour: "#33903C", rank: 1 },
  { grade: "Expected standard", colour: "#5CD168", rank: 2 },
  { grade: "Needs attention", colour: "#FF8341", rank: 3 },
  { grade: "Urgent improvement", colour: "#CE1E02", rank: 4 },
] as const;

export type ReportCardGrade = (typeof REPORT_CARD_GRADES)[number]["grade"];

const gradeColourMap: Record<string, string> = Object.fromEntries(
  REPORT_CARD_GRADES.map((g) => [g.grade, g.colour]),
);

const gradeRankMap: Record<string, number> = Object.fromEntries(
  REPORT_CARD_GRADES.map((g) => [g.grade, g.rank]),
);

export const REPORT_CARD_JUDGEMENT_FIELDS: [string, string][] = [
  ["achievement", "Achievement"],
  ["curriculumAndTeaching", "Curriculum and teaching"],
  ["behaviourAttitudesRoutines", "Behaviour, attitudes and routines"],
  ["childrensWelfareWellbeing", "Children\u2019s welfare and wellbeing"],
  ["inclusion", "Inclusion"],
  ["attendanceAndBehaviour", "Attendance and behaviour"],
  ["personalDevelopmentWellbeing", "Personal development and wellbeing"],
  ["leadershipAndGovernance", "Leadership and governance"],
  ["earlyYears", "Early years"],
];

export const REPORT_CARD_BOOLEANS: [string, string][] = [
  ["safeguardingMet", "Safeguarding standards"],
  ["ccrMet", "Compulsory Childcare Register"],
  ["vcrMet", "Voluntary Childcare Register"],
];

export function getReportCardGradeColour(grade: string): string {
  return gradeColourMap[grade] ?? "#9ca3af";
}

export function getReportCardGradeRank(grade: string): number {
  return gradeRankMap[grade] ?? 99;
}

export interface ReportCardJudgement {
  field: string;
  label: string;
  grade: string;
  colour: string;
  rank: number;
}

export interface ReportCardBoolean {
  field: string;
  label: string;
  met: boolean;
}

export function getReportCardJudgements(
  ofsted: OfstedReportCard,
): ReportCardJudgement[] {
  const results: ReportCardJudgement[] = [];
  for (const [field, label] of REPORT_CARD_JUDGEMENT_FIELDS) {
    const grade = (ofsted as unknown as Record<string, unknown>)[field];
    if (typeof grade === "string") {
      results.push({
        field,
        label,
        grade,
        colour: getReportCardGradeColour(grade),
        rank: getReportCardGradeRank(grade),
      });
    }
  }
  return results;
}

export function getReportCardBooleans(
  ofsted: OfstedReportCard,
): ReportCardBoolean[] {
  const results: ReportCardBoolean[] = [];
  for (const [field, label] of REPORT_CARD_BOOLEANS) {
    const value = (ofsted as unknown as Record<string, unknown>)[field];
    if (typeof value === "boolean") {
      results.push({ field, label, met: value });
    }
  }
  return results;
}

export interface StaffInfo {
  graduatePercentage?: number;
  turnoverPercentage?: number;
}

export interface FacilitiesInfo {
  hasGarden: boolean;
  hasKitchen: boolean;
}

export interface BoundingBox {
  geoType: string;
  geoCode: string;
  north?: number;
  south?: number;
  east?: number;
  west?: number;
}

export interface Provider {
  id: string;
  name: string;
  institutionType?: string | null;
  lad25cd?: string | null;
  address: ProviderAddress;
  latitude?: number;
  longitude?: number;
  boundingBox?: BoundingBox;
  distanceMiles: number;
  phone: string;
  email: string;
  website: string;
  fisUrl?: string;
  ofsted?: OfstedInfo | null;
  cma?: CmaInfo | null;
  careTypes: ProviderCareType[];
  staff?: StaffInfo;
  facilities?: FacilitiesInfo;
  registeredPlaces?: number | null;
}

/**
 * Extract a human-readable Ofsted rating label from the (possibly absent) ofsted data.
 * For legacy inspections, returns the legacyRating directly.
 * For legacy_transition, derives from the worst sub-grade.
 * For report_card, returns a placeholder until the new UI is built.
 */
export function getOfstedRatingLabel(
  ofsted?: OfstedInfo | null,
): string | null {
  if (!ofsted) return null;

  if (
    ofsted.framework === "legacy" ||
    ofsted.framework === "ungraded_confirmed"
  ) {
    return ofsted.legacyRating;
  }

  if (ofsted.framework === "legacy_transition") {
    return null;
  }

  // report_card — derive from worst sub-judgement
  const judgements = getReportCardJudgements(ofsted);
  if (judgements.length === 0) return null;
  let worst = 0;
  for (const j of judgements) {
    worst = Math.max(worst, j.rank);
  }
  return REPORT_CARD_GRADES[worst]?.grade ?? null;
}

/**
 * Map a rating label to a numeric rank for sorting (lower = better).
 * Returns 9 for unknown/unranked values.
 */
export function getOfstedSortRank(ofsted?: OfstedInfo | null): number {
  const label = getOfstedRatingLabel(ofsted);
  if (!label) return 9;
  const rank: Record<string, number> = {
    // Legacy grades
    Outstanding: 0,
    Good: 1,
    "Requires Improvement": 2,
    "Needs Attention": 2,
    Inadequate: 3,
    "Urgent Improvement": 3,
    // Report card grades (mapped to equivalent tiers)
    Exceptional: 0,
    "Strong standard": 1,
    "Expected standard": 1,
    "Needs attention": 2,
    "Urgent improvement": 3,
  };
  return rank[label] ?? 9;
}

/**
 * Map a rating label to tailwind colour classes for badges.
 */
export function getOfstedBadgeClasses(label: string | null): string {
  if (!label) return "bg-zinc-100 text-zinc-600";
  // Legacy
  if (label === "Outstanding") return "bg-green-50 text-green-800";
  if (label === "Inadequate" || label === "Urgent Improvement")
    return "bg-red-50 text-red-800";
  if (label === "Requires Improvement" || label === "Needs Attention")
    return "bg-amber-50 text-amber-800";
  if (label === "Good") return "bg-lime-50 text-lime-800";
  // Report card — use the grade colour system
  if (label in gradeColourMap) return "text-white";
  return "bg-lime-50 text-lime-800";
}

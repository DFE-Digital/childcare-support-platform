import type { ChildcareSelection, CareTypeId } from "../types/family.js";
import type { ResolvedFees } from "./fee-lookup.js";

export interface ChildcareFeesResult {
  total: number;
  effectiveHourlyRate: number;
  weeklyHours: number;
  weeksPerYear: number;
}

export function calculateChildcareFees(
  selection: ChildcareSelection,
  fees: ResolvedFees,
): ChildcareFeesResult {
  switch (selection.careType as CareTypeId) {
    case "private_nursery":
    case "school_based_nursery":
      return calculateNurseryFees(selection, fees);
    case "childminder":
      return calculateChildminderFees(selection, fees);
    case "breakfast_club":
    case "after_school_club":
      return calculateClubFees(selection, fees);
    case "free_breakfast_club":
      return {
        total: 0,
        effectiveHourlyRate: 0,
        weeklyHours: 0,
        weeksPerYear: 38,
      };
    case "holiday_club":
      return calculateHolidayClubFees(selection, fees);
    default:
      return {
        total: 0,
        effectiveHourlyRate: 0,
        weeklyHours: 0,
        weeksPerYear: 0,
      };
  }
}

function calculateNurseryFees(
  selection: ChildcareSelection,
  fees: ResolvedFees,
): ChildcareFeesResult {
  const weeks = selection.weeksPerYear ?? fees.operatingWeeksPerYear;
  const sessions = selection.sessions ?? {};
  const morningDays = sessions.morning?.daysPerWeek ?? 0;
  const afternoonDays = sessions.afternoon?.daysPerWeek ?? 0;
  const fullDayDays = sessions.fullDay?.daysPerWeek ?? 0;

  const morningFee = fees.morningSession ?? 0;
  const afternoonFee = fees.afternoonSession ?? 0;
  const fullDayFee = fees.fullDay ?? 0;

  const weeklyFee =
    morningDays * morningFee +
    afternoonDays * afternoonFee +
    fullDayDays * fullDayFee;

  const total = weeklyFee * weeks;

  // Calculate weekly hours for effective hourly rate
  const morningHours =
    selection.sessionHours?.morning ?? fees.sessionHours?.morning ?? 5;
  const afternoonHours =
    selection.sessionHours?.afternoon ?? fees.sessionHours?.afternoon ?? 5;
  const fullDayHours = fees.sessionHours?.fullDay ?? 0;

  const weeklyHours =
    morningDays * morningHours +
    afternoonDays * afternoonHours +
    fullDayDays * fullDayHours;

  const effectiveHourlyRate = weeklyHours > 0 ? weeklyFee / weeklyHours : 0;

  return { total, effectiveHourlyRate, weeklyHours, weeksPerYear: weeks };
}

function calculateChildminderFees(
  selection: ChildcareSelection,
  fees: ResolvedFees,
): ChildcareFeesResult {
  const hoursPerWeek = selection.hoursPerWeek ?? 0;
  const weeksPerYear = selection.weeksPerYear ?? fees.operatingWeeksPerYear;
  const perHour = fees.perHour ?? 0;

  const total = hoursPerWeek * perHour * weeksPerYear;

  return {
    total,
    effectiveHourlyRate: perHour,
    weeklyHours: hoursPerWeek,
    weeksPerYear,
  };
}

function calculateClubFees(
  selection: ChildcareSelection,
  fees: ResolvedFees,
): ChildcareFeesResult {
  const daysPerWeek = selection.daysPerWeek ?? 0;
  const perSession = fees.perSession ?? 0;
  const weeks = 38; // Term-time only

  const total = daysPerWeek * perSession * weeks;

  return {
    total,
    effectiveHourlyRate: perSession,
    weeklyHours: daysPerWeek,
    weeksPerYear: weeks,
  };
}

function calculateHolidayClubFees(
  selection: ChildcareSelection,
  fees: ResolvedFees,
): ChildcareFeesResult {
  const daysPerYear = selection.daysPerYear ?? 0;
  const perDay = fees.perDay ?? 0;

  const total = daysPerYear * perDay;

  return {
    total,
    effectiveHourlyRate: perDay,
    weeklyHours: 0,
    weeksPerYear: 0,
  };
}

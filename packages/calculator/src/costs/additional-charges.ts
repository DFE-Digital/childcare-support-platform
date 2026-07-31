import type { ChildcareSelection, CareTypeId } from "../types/family.js";
import type { ResolvedFees } from "./fee-lookup.js";

export interface AdditionalChargesResult {
  total: number;
  items: Array<{ item: string; amount: number }>;
  estimated: boolean;
}

export function calculateAdditionalCharges(
  selection: ChildcareSelection,
  fees: ResolvedFees,
): AdditionalChargesResult {
  const items: Array<{ item: string; amount: number }> = [];
  let total = 0;
  let estimated = false;

  // Detect if we need to estimate attendance days for per-day charges
  const careType = selection.careType as CareTypeId;
  if (
    careType === "childminder" &&
    !selection.daysPerWeek &&
    selection.hoursPerWeek &&
    fees.additionalCharges.some((c) => c.unit === "per day")
  ) {
    estimated = true;
  }

  for (const charge of fees.additionalCharges) {
    const amount = annualizeCharge(charge.cost, charge.unit, selection, fees);
    if (amount > 0) {
      items.push({ item: charge.item, amount });
      total += amount;
    }
  }

  return { total, items, estimated };
}

function annualizeCharge(
  cost: number,
  unit: string,
  selection: ChildcareSelection,
  fees: ResolvedFees,
): number {
  const careType = selection.careType as CareTypeId;

  switch (unit) {
    case "per day": {
      const daysPerYear = getAttendanceDaysPerYear(selection, fees, careType);
      return cost * daysPerYear;
    }
    case "per week": {
      const weeks = getOperatingWeeks(selection, fees, careType);
      return cost * weeks;
    }
    case "per session": {
      const sessionsPerYear = getSessionsPerYear(selection, fees, careType);
      return cost * sessionsPerYear;
    }
    default:
      return 0;
  }
}

function getAttendanceDaysPerYear(
  selection: ChildcareSelection,
  fees: ResolvedFees,
  careType: CareTypeId,
): number {
  if (careType === "holiday_club") {
    return selection.daysPerYear ?? 0;
  }

  if (careType === "childminder") {
    const weeksPerYear = selection.weeksPerYear ?? fees.operatingWeeksPerYear;
    if (selection.daysPerWeek) {
      return selection.daysPerWeek * weeksPerYear;
    }
    // Estimate attendance days from weekly hours.
    // Typical childminder: ~6 usable hours per attendance day.
    if (selection.hoursPerWeek) {
      const estimatedDaysPerWeek = Math.min(
        5,
        Math.ceil(selection.hoursPerWeek / 6),
      );
      return estimatedDaysPerWeek * weeksPerYear;
    }
    return 0;
  }

  // Session-based: count total session days per week
  const sessions = selection.sessions;
  if (sessions) {
    const daysPerWeek = Math.max(
      sessions.morning?.daysPerWeek ?? 0,
      sessions.afternoon?.daysPerWeek ?? 0,
      sessions.fullDay?.daysPerWeek ?? 0,
    );
    const weeks = fees.operatingWeeksPerYear;
    return daysPerWeek * weeks;
  }

  // daysPerWeek-based (clubs)
  if (selection.daysPerWeek) {
    const weeks = getOperatingWeeks(selection, fees, careType);
    return selection.daysPerWeek * weeks;
  }

  return 0;
}

function getOperatingWeeks(
  selection: ChildcareSelection,
  fees: ResolvedFees,
  careType: CareTypeId,
): number {
  if (
    careType === "breakfast_club" ||
    careType === "free_breakfast_club" ||
    careType === "after_school_club"
  ) {
    return 38;
  }

  if (careType === "childminder") {
    return selection.weeksPerYear ?? fees.operatingWeeksPerYear;
  }

  return fees.operatingWeeksPerYear;
}

function getSessionsPerYear(
  selection: ChildcareSelection,
  fees: ResolvedFees,
  careType: CareTypeId,
): number {
  if (
    careType === "breakfast_club" ||
    careType === "free_breakfast_club" ||
    careType === "after_school_club"
  ) {
    return (selection.daysPerWeek ?? 0) * 38;
  }

  // Nursery: count all sessions
  const sessions = selection.sessions;
  if (sessions) {
    const totalSessionsPerWeek =
      (sessions.morning?.daysPerWeek ?? 0) +
      (sessions.afternoon?.daysPerWeek ?? 0) +
      (sessions.fullDay?.daysPerWeek ?? 0);
    return totalSessionsPerWeek * fees.operatingWeeksPerYear;
  }

  return 0;
}

import type { ChildData } from "../types/family.js";

export function getChildAgeInMonths(
  child: ChildData,
  referenceDate: Date,
): number {
  const refYear = referenceDate.getFullYear();
  const refMonth = referenceDate.getMonth() + 1;
  return (refYear - child.birthYear) * 12 + (refMonth - child.birthMonth);
}

export function getChildAgeInYears(
  child: ChildData,
  referenceDate: Date,
): number {
  return Math.floor(getChildAgeInMonths(child, referenceDate) / 12);
}

/** Returns the start date of the next term after the given month/year. */
export function nextTermStart(year: number, month: number): Date {
  // Term starts: Sep 1, Jan 1, Apr 1
  if (month >= 9) return new Date(year + 1, 0, 1); // Jan 1
  if (month >= 4) return new Date(year, 8, 1); // Sep 1
  return new Date(year, 3, 1); // Apr 1
}

export function formatTermDate(date: Date): string {
  return date.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

export function isPreSchool(child: ChildData, referenceDate: Date): boolean {
  const ageMonths = getChildAgeInMonths(child, referenceDate);
  if (ageMonths < 48) return true; // under 4
  const turnsFourYear = child.birthYear + 4;
  let schoolStartYear: number;
  if (child.birthMonth >= 9) {
    schoolStartYear = turnsFourYear + 1;
  } else {
    schoolStartYear = turnsFourYear;
  }
  const schoolStartDate = new Date(schoolStartYear, 8, 1); // September 1st
  return referenceDate < schoolStartDate;
}

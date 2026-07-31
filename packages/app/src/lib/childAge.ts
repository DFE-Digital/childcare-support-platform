export const BIG_KID_MONTHS = 60;

export function getChildAgeMonths(
  birthMonth: number,
  birthYear: number,
): number {
  const now = new Date();
  return (
    (now.getFullYear() - birthYear) * 12 + (now.getMonth() + 1 - birthMonth)
  );
}

function nextTermStartDate(year: number, month: number): Date {
  if (month >= 9) return new Date(year + 1, 0, 1);
  if (month >= 4) return new Date(year, 8, 1);
  return new Date(year, 3, 1);
}

export function isTermEligible2YO(
  birthMonth: number,
  birthYear: number,
): boolean {
  const now = new Date();
  const eligibleFrom = nextTermStartDate(birthYear + 2, birthMonth);
  const eligibleUntil = nextTermStartDate(birthYear + 3, birthMonth);
  return now >= eligibleFrom && now < eligibleUntil;
}

export function formatAge(birthMonth: number, birthYear: number): string {
  const now = new Date();
  let years = now.getFullYear() - birthYear;
  if (now.getMonth() + 1 < birthMonth) years--;
  if (years < 1) {
    const months =
      (now.getFullYear() - birthYear) * 12 + (now.getMonth() + 1 - birthMonth);
    return months <= 1 ? "1 month" : `${months} months`;
  }
  return years === 1 ? "1 year old" : `${years} years old`;
}

export function areAllChildrenBigKids(
  children: ReadonlyArray<{
    birthMonth: number | null;
    birthYear: number | null;
  }>,
): boolean {
  return (
    children.length > 0 &&
    children.every(
      (c) =>
        c.birthMonth !== null &&
        c.birthYear !== null &&
        getChildAgeMonths(c.birthMonth, c.birthYear) >= BIG_KID_MONTHS,
    )
  );
}

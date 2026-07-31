import type { Provider } from "@/types/provider";

export function getDailyOpeningSpan(
  provider: Provider,
  selectedTypes: string[],
): string {
  const careTypes =
    selectedTypes.length > 0
      ? provider.careTypes.filter((ct) => selectedTypes.includes(ct.type))
      : provider.careTypes;
  let earliestOpen: string | null = null;
  let latestClose: string | null = null;
  for (const ct of careTypes) {
    if (ct.openingHours) {
      for (const oh of ct.openingHours) {
        if (!earliestOpen || oh.open < earliestOpen) earliestOpen = oh.open;
        if (!latestClose || oh.close > latestClose) latestClose = oh.close;
      }
    }
  }
  if (!earliestOpen || !latestClose) return "\u2013";
  return `${earliestOpen} to ${latestClose}`;
}

export function getDailyOpeningHours(
  provider: Provider,
  selectedTypes: string[],
): number | null {
  const careTypes =
    selectedTypes.length > 0
      ? provider.careTypes.filter((ct) => selectedTypes.includes(ct.type))
      : provider.careTypes;
  let earliestOpen: string | null = null;
  let latestClose: string | null = null;
  for (const ct of careTypes) {
    if (ct.openingHours) {
      for (const oh of ct.openingHours) {
        if (!earliestOpen || oh.open < earliestOpen) earliestOpen = oh.open;
        if (!latestClose || oh.close > latestClose) latestClose = oh.close;
      }
    }
  }
  if (!earliestOpen || !latestClose) return null;
  const [oh, om] = earliestOpen.split(":").map(Number);
  const [ch, cm] = latestClose.split(":").map(Number);
  return (ch * 60 + cm - (oh * 60 + om)) / 60;
}

export function getLongestAnnualWeeks(
  provider: Provider,
  selectedTypes: string[],
): number {
  const careTypes =
    selectedTypes.length > 0
      ? provider.careTypes.filter((ct) => selectedTypes.includes(ct.type))
      : provider.careTypes;
  let max = 0;
  for (const ct of careTypes) {
    if (ct.operatingWeeksPerYear != null && ct.operatingWeeksPerYear > max)
      max = ct.operatingWeeksPerYear;
  }
  return max;
}

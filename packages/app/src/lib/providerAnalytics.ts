export function distanceBand(miles: number | undefined): string {
  if (miles == null) return "unknown";
  if (miles < 1) return "<1mi";
  if (miles < 3) return "1-3mi";
  if (miles < 5) return "3-5mi";
  if (miles < 10) return "5-10mi";
  return "10+mi";
}

export function childAgeBands(agesMonths: number[]): string[] {
  if (agesMonths.length === 0) return [];
  const bands = new Set<string>();
  for (const m of agesMonths) {
    bands.add(m < 60 ? "0-4" : "5+");
  }
  return [...bands].sort();
}

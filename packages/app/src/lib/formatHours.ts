export function formatHoursMinutes(decimal: number): string {
  const hours = Math.floor(decimal);
  const minutes = Math.round((decimal - hours) * 60);
  if (minutes === 0) return `${hours} hour${hours !== 1 ? "s" : ""}`;
  if (hours === 0) return `${minutes} minute${minutes !== 1 ? "s" : ""}`;
  return `${hours} hour${hours !== 1 ? "s" : ""} ${minutes} minute${minutes !== 1 ? "s" : ""}`;
}

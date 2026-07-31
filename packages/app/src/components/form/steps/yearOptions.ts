export function yearOptions(
  birthMonth: number | null,
): Array<{ value: string; label: string }> {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  const opts = [];
  for (let y = currentYear; y >= currentYear - 18; y--) {
    if (birthMonth !== null) {
      const totalMonths = (currentYear - y) * 12 + (currentMonth - birthMonth);
      if (totalMonths < 0) continue;
      const years = Math.floor(totalMonths / 12);
      const months = totalMonths % 12;
      const parts = [];
      if (years > 0) parts.push(`${years} yr${years !== 1 ? "s" : ""}`);
      if (months > 0 || years === 0) {
        const moLabel = years === 0 ? "month" : "mo";
        parts.push(`${months} ${moLabel}${months !== 1 ? "s" : ""}`);
      }
      opts.push({ value: String(y), label: `${y} (${parts.join(" ")})` });
    } else {
      opts.push({ value: String(y), label: String(y) });
    }
  }
  return opts;
}

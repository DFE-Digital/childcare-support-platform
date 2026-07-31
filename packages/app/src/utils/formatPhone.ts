/** Format a digits-only UK phone number for display. */
export function formatUKPhone(digits: string): string {
  if (digits.length !== 11 || !digits.startsWith("0")) return digits;

  // 02x: London / major cities → 0XX XXXX XXXX
  if (digits.startsWith("02"))
    return `${digits.slice(0, 3)} ${digits.slice(3, 7)} ${digits.slice(7)}`;

  // 01x1 / 011x: cities with 4-digit area codes → 0XXX XXX XXXX
  if (/^01[1-9]1|^011[3-8]/.test(digits))
    return `${digits.slice(0, 4)} ${digits.slice(4, 7)} ${digits.slice(7)}`;

  // 01xxx / 07xxx: geographic + mobile → 0XXXX XXXXXX
  if (digits.startsWith("01") || digits.startsWith("07"))
    return `${digits.slice(0, 5)} ${digits.slice(5)}`;

  // 03xx / 08xx / 09xx → 0XXX XXX XXXX
  return `${digits.slice(0, 4)} ${digits.slice(4, 7)} ${digits.slice(7)}`;
}

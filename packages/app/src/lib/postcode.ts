const FULL_RE = /^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$/i;
const PREFIX_RE = /^[A-Z]{1,2}(\d[A-Z\d]?(\s?\d[A-Z]{0,2})?)?$/i;

export function normalisePostcode(input: string): string {
  const raw = input.trim().toUpperCase().replace(/\s+/g, "");
  if (raw.length <= 3) return raw;
  return `${raw.slice(0, -3)} ${raw.slice(-3)}`;
}

export function isPostcodeFormatValid(
  input: string,
  complete = false,
): boolean {
  const s = input.trim().toUpperCase().replace(/\s+/g, " ");
  if (!s) return false;
  if (complete) return FULL_RE.test(s);
  return PREFIX_RE.test(s);
}

const CROWN_DEPENDENCY_PREFIXES = ["JE", "GY", "IM", "BF"];

export function isCrownDependency(normalised: string): boolean {
  const [outward] = normalised.split(" ");
  return CROWN_DEPENDENCY_PREFIXES.some((p) => outward.startsWith(p));
}

import type { ChildData } from "../types/family.js";
import { getChildAgeInMonths } from "../entitlement/calculate.js";

/** All age bands in the data model (matches Prisma FeeRate.ageBand enum). */
export type AgeBand =
  | "all"
  | "under2"
  | "age2"
  | "age3to4"
  | "age2plus"
  | "age5plus";

/** Subset of age bands that have government funding rates. */
export type FundedAgeBand = "under2" | "age2" | "age3to4";

export function getAgeBand(child: ChildData, refDate: Date): FundedAgeBand {
  const months = getChildAgeInMonths(child, refDate);
  if (months < 24) return "under2";
  if (months < 36) return "age2";
  return "age3to4";
}

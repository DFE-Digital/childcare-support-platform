import type { AgeBracket } from "./types/family.js";

export const NMW_HOURLY: Record<AgeBracket, number> = {
  "21+": 12.71,
  "18-20": 10.85,
  "16-17": 8.0,
};

export const NMW_HOURS_PER_WEEK = 16;

export const NMW_WEEKLY: Record<AgeBracket, number> = {
  "21+": NMW_HOURLY["21+"] * NMW_HOURS_PER_WEEK,
  "18-20": NMW_HOURLY["18-20"] * NMW_HOURS_PER_WEEK,
  "16-17": NMW_HOURLY["16-17"] * NMW_HOURS_PER_WEEK,
};

export const APPRENTICE_BRACKET: AgeBracket = "16-17";

export function nmwForPeriod(bracket: AgeBracket) {
  const weekly = NMW_WEEKLY[bracket];
  return {
    weekly: +weekly.toFixed(2),
    monthly: +((weekly * 52) / 12).toFixed(2),
    quarterly: +(weekly * 13).toFixed(2),
    annual: +(weekly * 52).toFixed(2),
  };
}

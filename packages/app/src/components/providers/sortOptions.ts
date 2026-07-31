import { featureFlags } from "@/hooks/useFeatureFlags";

const { showFees, showMetrics, showSortDaily, showSortAnnual } = featureFlags;

export type SortOption =
  | "distance"
  | "lowest_cost"
  | "most_graduate"
  | "lowest_turnover"
  | "longest_daily"
  | "longest_annual"
  | "best_ofsted";

export const sortOptions: { value: SortOption; label: string }[] = [
  { value: "distance", label: "Distance from {postcode}" },
  ...(showFees
    ? [{ value: "lowest_cost" as const, label: "Lowest cost" }]
    : []),
  ...(showMetrics
    ? [
        { value: "most_graduate" as const, label: "Most graduate staff" },
        { value: "lowest_turnover" as const, label: "Lowest staff turnover" },
      ]
    : []),
  ...(showSortDaily
    ? [{ value: "longest_daily" as const, label: "Longest daily opening" }]
    : []),
  ...(showSortAnnual
    ? [{ value: "longest_annual" as const, label: "Longest annual opening" }]
    : []),
  { value: "best_ofsted", label: "Best inspection rating" },
];

export const sortDescriptions: Record<SortOption, string> = {
  distance: "Sorted by proximity to your postcode (nearest first).",
  lowest_cost:
    "Sorted by hourly rate (cheapest first). Based on fees submitted to the local authority — may not be current. Confirm directly with the provider.",
  most_graduate:
    "Sorted by the percentage of staff holding a degree-level or above qualification (highest first).",
  lowest_turnover:
    "Sorted by staff turnover rate (lowest first). Lower turnover generally indicates a more stable team.",
  longest_daily: "Sorted by the total hours available per day (longest first).",
  longest_annual:
    "Sorted by weeks per year that the provider is open (most first). Year-round providers appear before term-time only.",
  best_ofsted:
    "Sorted by inspection rating (best first). Includes Ofsted ratings and CMA quality assurance gradings. The new Ofsted grading system (from September 2025) does not include an overall rating — providers on the new system are ranked by their lowest individual judgement.",
};

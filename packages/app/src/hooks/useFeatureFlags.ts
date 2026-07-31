/**
 * Feature flags derived from VITE_FEATURE_* env vars.
 *
 * Usage:
 *   1. Add `readonly VITE_FEATURE_FOO: string | undefined;` to src/env.d.ts
 *   2. Add `foo: flag("VITE_FEATURE_FOO"),` to the flags object below
 *   3. Consume: `const { foo } = featureFlags;` (module scope)
 *      or: `const { foo } = useFeatureFlags();` (inside components)
 *   4. Set at build time: `VITE_FEATURE_FOO=true vite build`
 *
 * Flags are resolved once at module load (Vite inlines them at build time),
 * so there is no runtime cost or re-render overhead.
 */

function flag(key: string): boolean {
  // import.meta.env values are statically replaced by Vite at build time.
  // We index into the env object so each flag doesn't need its own line of
  // import.meta.env access — Vite's `envPrefix` still controls exposure.
  return (import.meta.env[key] as string | undefined) === "true";
}

export const featureFlags = {
  // Add feature flags here, e.g.:
  // costCalculator: flag("VITE_FEATURE_COST_CALCULATOR"),
  showMetrics: flag("VITE_FEATURE_METRICS"),
  showFees: flag("VITE_FEATURE_FEES"),
  showEligibility: flag("VITE_FEATURE_ELIGIBILITY"),
  showAvailability: flag("VITE_FEATURE_AVAILABILITY"),
  showNotes: flag("VITE_FEATURE_NOTES"),
  showSortDaily: flag("VITE_FEATURE_SORT_DAILY"),
  showSortAnnual: flag("VITE_FEATURE_SORT_ANNUAL"),
  noBigKidEstimates: flag("VITE_FEATURE_NO_BIG_KID_ESTIMATES"),
  noProviderEstimates: flag("VITE_FEATURE_NO_PROVIDER_ESTIMATES"),
  noAdditionalCharges: flag("VITE_FEATURE_NO_ADDITIONAL_CHARGES"),
  showFundedHoursFilter: flag("VITE_FEATURE_FUNDED_HOURS_FILTER"),
} as const;

export type FeatureFlags = typeof featureFlags;

export function useFeatureFlags(): FeatureFlags {
  return featureFlags;
}

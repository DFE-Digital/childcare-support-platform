/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Feature flags — set to "true" to enable, absent or any other value to disable.
  // Add new flags here as: readonly VITE_FEATURE_<NAME>: string | undefined;

  // METRICS flag to put the site into a mode that assumes that providers are
  // sending us compulsory data submissions, eg where it's reasonable to highlight the absence
  // of metric fields like hasGarden
  readonly VITE_FEATURE_METRICS: string | undefined;

  // FEES flag allows the UI to show fee data
  readonly VITE_FEATURE_FEES: string | undefined;

  readonly VITE_FEATURE_ELIGIBILITY: string | undefined;

  readonly VITE_FEATURE_AVAILABILITY: string | undefined;

  readonly VITE_FEATURE_NOTES: string | undefined;

  readonly VITE_FEATURE_SORT_DAILY: string | undefined;

  readonly VITE_FEATURE_SORT_ANNUAL: string | undefined;

  // NO_BIG_KID_ESTIMATES: hide cost estimation for children >= 5 until reliable
  // average cost data is available for older age groups
  readonly VITE_FEATURE_NO_BIG_KID_ESTIMATES: string | undefined;

  // NO_PROVIDER_ESTIMATES: always use average costs, hide the shortlisted
  // provider dropdown from the childcare arrangements step
  readonly VITE_FEATURE_NO_PROVIDER_ESTIMATES: string | undefined;

  // NO_ADDITIONAL_CHARGES: exclude additional charges (meals, nappies etc.)
  // from cost estimates until data quality improves
  readonly VITE_FEATURE_NO_ADDITIONAL_CHARGES: string | undefined;

  // FUNDED_HOURS_FILTER: show the "Accepts funded hours" filter in the
  // provider search. Hidden by default until data quality improves.
  readonly VITE_FEATURE_FUNDED_HOURS_FILTER: string | undefined;
}

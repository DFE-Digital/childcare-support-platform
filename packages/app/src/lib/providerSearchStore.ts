import type {
  CostDisplayMode,
  SortOption,
} from "@/components/providers/ProviderFilters";

export interface ProviderSearchSnapshot {
  postcode: string;
  searchedPostcode: string;
  selectedTypes: string[];
  selectedChildren: string[];
  shortlistedOnly: boolean;
  costDisplayMode: CostDisplayMode;
  includeAdditionalCharges: boolean;
  sortBy: SortOption;
  fundedHoursOnly: boolean;
  filtersOpen: boolean;
  initialBounds: [number, number, number, number] | null;
  mapBounds: [number, number, number, number] | null;
  mapResetKey: number;
  /** Postcode bbox from the last search — needed to re-trigger sisSearch on restore. */
  postcodeBbox: [number, number, number, number] | null;
  /** Postcode centroid from the last search. */
  postcodeCentroid: [number, number] | null;
  /** Map center [lng, lat] for exact viewport restoration. */
  mapCenter: [number, number] | null;
  /** Map zoom level for exact viewport restoration. */
  mapZoom: number | null;
}

let snapshot: ProviderSearchSnapshot | null = null;

export function saveProviderSearchState(state: ProviderSearchSnapshot): void {
  snapshot = state;
}

export function getProviderSearchState(): ProviderSearchSnapshot | null {
  return snapshot;
}

export function clearProviderSearchState(): void {
  snapshot = null;
}

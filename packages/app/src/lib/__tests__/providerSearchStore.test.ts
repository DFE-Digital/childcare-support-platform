import { describe, it, expect, beforeEach } from "vitest";
import {
  getProviderSearchState,
  saveProviderSearchState,
  clearProviderSearchState,
  type ProviderSearchSnapshot,
} from "../providerSearchStore";

function makeSnapshot(
  overrides: Partial<ProviderSearchSnapshot> = {},
): ProviderSearchSnapshot {
  return {
    postcode: "OX1 1AA",
    searchedPostcode: "OX1 1AA",
    selectedTypes: ["private_nursery"],
    selectedChildren: ["Alice"],
    shortlistedOnly: false,
    costDisplayMode: "detailed",
    includeAdditionalCharges: true,
    sortBy: "distance",
    fundedHoursOnly: false,
    filtersOpen: true,
    initialBounds: [-1.3, 51.7, -1.2, 51.8],
    mapBounds: [-1.3, 51.7, -1.2, 51.8],
    mapResetKey: 1,
    postcodeBbox: [-1.3, 51.7, -1.2, 51.8],
    postcodeCentroid: [-1.25, 51.75],
    mapCenter: [-1.25, 51.75],
    mapZoom: 13,
    ...overrides,
  };
}

beforeEach(() => {
  clearProviderSearchState();
});

describe("providerSearchStore", () => {
  it("returns null when no state has been saved", () => {
    expect(getProviderSearchState()).toBeNull();
  });

  it("returns saved state after save", () => {
    const snap = makeSnapshot();
    saveProviderSearchState(snap);
    expect(getProviderSearchState()).toEqual(snap);
  });

  it("clears state", () => {
    saveProviderSearchState(makeSnapshot());
    clearProviderSearchState();
    expect(getProviderSearchState()).toBeNull();
  });

  it("overwrites previous state on subsequent save", () => {
    saveProviderSearchState(makeSnapshot({ postcode: "SW1A 1AA" }));
    saveProviderSearchState(makeSnapshot({ postcode: "EC1A 1BB" }));
    expect(getProviderSearchState()?.postcode).toBe("EC1A 1BB");
  });
});

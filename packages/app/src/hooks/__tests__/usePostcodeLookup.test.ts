import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { usePostcodeLookup } from "../usePostcodeLookup";

// --- Mock data ---
const MOCK_OUTWARD = ["AB1", "AB2", "S1", "SW1A", "SW1H"];
const MOCK_INWARD_SW1A = {
  _: ["E09000001", "E09000033"],
  "1AA": {
    b: [-0.1416, 51.4993, -0.1393, 51.5013] as [number, number, number, number],
    c: [-0.1405, 51.5003] as [number, number],
    a: [1],
  },
  "1AB": {
    b: [-0.142, 51.499, -0.139, 51.501] as [number, number, number, number],
    c: [-0.1405, 51.5] as [number, number],
    a: [0],
  },
  "2AA": {
    b: [-0.135, 51.502, -0.133, 51.504] as [number, number, number, number],
    c: [-0.134, 51.503] as [number, number],
    a: [1],
  },
};

vi.mock("@/data/loader", () => ({
  loadOutwardCodes: vi.fn(() => Promise.resolve(MOCK_OUTWARD)),
  loadInwardCodes: vi.fn((outward: string) => {
    if (outward === "SW1A") return Promise.resolve(MOCK_INWARD_SW1A);
    return Promise.resolve({});
  }),
}));

// Import after mock so we can spy on call counts
import { loadInwardCodes } from "@/data/loader";

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// 2a. filterOutward
// ---------------------------------------------------------------------------

describe("filterOutward", () => {
  it('filters by prefix "S"', async () => {
    const { result } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(result.current.outwardLoaded).toBe(true));
    expect(result.current.filterOutward("S")).toEqual(["S1", "SW1A", "SW1H"]);
  });

  it('filters by prefix "SW"', async () => {
    const { result } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(result.current.outwardLoaded).toBe(true));
    expect(result.current.filterOutward("SW")).toEqual(["SW1A", "SW1H"]);
  });

  it("returns exact match", async () => {
    const { result } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(result.current.outwardLoaded).toBe(true));
    expect(result.current.filterOutward("S1")).toEqual(["S1"]);
  });

  it("returns empty for no match", async () => {
    const { result } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(result.current.outwardLoaded).toBe(true));
    expect(result.current.filterOutward("ZZ")).toEqual([]);
  });

  it("returns empty for empty string", async () => {
    const { result } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(result.current.outwardLoaded).toBe(true));
    expect(result.current.filterOutward("")).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// 2b. filterInward
// ---------------------------------------------------------------------------

describe("filterInward", () => {
  async function setupWithInward() {
    const { result } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(result.current.outwardLoaded).toBe(true));
    act(() => result.current.prefetchInward("SW1A"));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    return result;
  }

  it('filters inward codes by prefix "1"', async () => {
    const result = await setupWithInward();
    expect(result.current.filterInward("SW1A", "1")).toEqual(["1AA", "1AB"]);
  });

  it("returns exact inward match", async () => {
    const result = await setupWithInward();
    expect(result.current.filterInward("SW1A", "1AA")).toEqual(["1AA"]);
  });

  it("returns empty for no inward match", async () => {
    const result = await setupWithInward();
    expect(result.current.filterInward("SW1A", "9")).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// 2c. getGeo
// ---------------------------------------------------------------------------

describe("getGeo", () => {
  async function setupWithInward() {
    const { result } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(result.current.outwardLoaded).toBe(true));
    act(() => result.current.prefetchInward("SW1A"));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    return result;
  }

  it("returns bbox and centroid for valid postcode", async () => {
    const result = await setupWithInward();
    const geo = result.current.getGeo("SW1A", "1AA");
    expect(geo).not.toBeNull();
    expect(geo!.bbox).toEqual([-0.1416, 51.4993, -0.1393, 51.5013]);
    expect(geo!.centroid).toEqual([-0.1405, 51.5003]);
  });

  it("returns null for unknown inward code", async () => {
    const result = await setupWithInward();
    expect(result.current.getGeo("SW1A", "9ZZ")).toBeNull();
  });

  it("returns null for unknown outward code", async () => {
    const result = await setupWithInward();
    expect(result.current.getGeo("ZZ1", "1AA")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 2d. isValid
// ---------------------------------------------------------------------------

describe("isValid", () => {
  async function setupWithInward() {
    const { result } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(result.current.outwardLoaded).toBe(true));
    act(() => result.current.prefetchInward("SW1A"));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    return result;
  }

  it("returns true for valid postcode with space", async () => {
    const result = await setupWithInward();
    expect(result.current.isValid("SW1A 1AA")).toBe(true);
  });

  it("returns false for unknown inward code", async () => {
    const result = await setupWithInward();
    expect(result.current.isValid("SW1A 9ZZ")).toBe(false);
  });

  it("returns false for unknown outward code", async () => {
    const result = await setupWithInward();
    expect(result.current.isValid("ZZ99 9ZZ")).toBe(false);
  });

  it("returns true for no space (normalised)", async () => {
    const result = await setupWithInward();
    expect(result.current.isValid("SW1A1AA")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 2e. prefetch dedup
// ---------------------------------------------------------------------------

describe("prefetch dedup", () => {
  it("calls loadInwardCodes only once for duplicate prefetch", async () => {
    const { result } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(result.current.outwardLoaded).toBe(true));

    act(() => {
      result.current.prefetchInward("SW1A");
      result.current.prefetchInward("SW1A");
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(loadInwardCodes).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// 2f. getLaCodes
// ---------------------------------------------------------------------------

describe("getLaCodes", () => {
  async function setupWithInward() {
    const { result } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(result.current.outwardLoaded).toBe(true));
    act(() => result.current.prefetchInward("SW1A"));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    return result;
  }

  it("returns LA codes for valid postcode", async () => {
    const result = await setupWithInward();
    expect(result.current.getLaCodes("SW1A", "1AA")).toEqual(["E09000033"]);
  });

  it("returns different LA codes for different inward", async () => {
    const result = await setupWithInward();
    expect(result.current.getLaCodes("SW1A", "1AB")).toEqual(["E09000001"]);
  });

  it("returns empty array for unknown inward code", async () => {
    const result = await setupWithInward();
    expect(result.current.getLaCodes("SW1A", "9ZZ")).toEqual([]);
  });

  it("returns empty array for uncached outward code", async () => {
    const result = await setupWithInward();
    expect(result.current.getLaCodes("ZZ1", "1AA")).toEqual([]);
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { usePostcodeLookup } from "@/hooks/usePostcodeLookup";
import { useFormAnalytics } from "@/hooks/useFormAnalytics";
import type { FormLocalStorageData } from "@/types/formData";

const MOCK_OUTWARD = ["SW1A"];
const MOCK_INWARD_SW1A = {
  _: ["E09000033"],
  "1AA": {
    b: [-0.1416, 51.4993, -0.1393, 51.5013] as [number, number, number, number],
    c: [-0.1405, 51.5003] as [number, number],
    a: [0],
    d: 7,
  },
};

vi.mock("@/data/loader", () => ({
  loadOutwardCodes: vi.fn(() => Promise.resolve(MOCK_OUTWARD)),
  loadInwardCodes: vi.fn((outward: string) => {
    if (outward === "SW1A") return Promise.resolve(MOCK_INWARD_SW1A);
    return Promise.resolve({});
  }),
}));

const mockCapture = vi.fn();
vi.mock("posthog-js/react", () => ({
  usePostHog: vi.fn(() => ({ capture: mockCapture })),
}));

function makeFormData(): FormLocalStorageData {
  return {
    schemaVersion: 7,
    location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] },
    household: { hasPartner: null },
    user: {
      isApprentice: null,
      firstYearApprentice: null,
      isSelfEmployed: null,
      selfEmployedLessThanTwelveMonths: null,
      ageBracket: null,
      workingStatus: null,
      receivesQualifyingAllowance: null,
      startingWorkNextMonth: null,
      hasLimitedCapacityForWork: null,
      hasNationalInsuranceNumber: null,
      residencyStatus: null,
      isStudying: null,
      studyLevel: null,
      isFullTimeStudent: null,
      courseIsPubliclyFunded: null,
      eligibleForStudentFinance: null,
    },
    partner: null,
    qualifyingBenefits: null,
    ucIncomeBelowThreshold: null,
    nrpfIncomeUnderThreshold: null,
    nrpfSavingsUnderLimit: null,
    children: [],
    shortlistedProviders: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("form page IoD analytics integration", () => {
  it("getGeo returns null when ensureInward has not been called on that instance", async () => {
    // Simulate the child (PostcodeStep) loading inward data
    const { result: child } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(child.current.outwardLoaded).toBe(true));
    await act(async () => {
      await child.current.ensureInward("SW1A");
    });
    expect(child.current.getGeo("SW1A", "1AA")).not.toBeNull();

    // Simulate the parent (SupportFormPage) — separate hook instance, empty cache
    const { result: parent } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(parent.current.outwardLoaded).toBe(true));

    // Without ensureInward, getGeo returns null — this was the bug
    expect(parent.current.getGeo("SW1A", "1AA")).toBeNull();
  });

  it("getGeo returns deprivationDecile after ensureInward is called", async () => {
    const { result: parent } = renderHook(() => usePostcodeLookup());
    await waitFor(() => expect(parent.current.outwardLoaded).toBe(true));

    await act(async () => {
      await parent.current.ensureInward("SW1A");
    });

    const geo = parent.current.getGeo("SW1A", "1AA");
    expect(geo).not.toBeNull();
    expect(geo!.deprivationDecile).toBe(7);
  });

  it("step_completed postcode event includes iod_decile after ensureInward", async () => {
    const { result: lookup } = renderHook(() => usePostcodeLookup());
    const { result: analytics } = renderHook(() => useFormAnalytics("support"));
    await waitFor(() => expect(lookup.current.outwardLoaded).toBe(true));

    // Replicate the fixed handleStepCompleted logic:
    // 1. ensureInward (populates this instance's cache)
    // 2. getGeo (reads from populated cache)
    // 3. setIodDecile + captureStep
    const formData = makeFormData();
    await act(async () => {
      await lookup.current.ensureInward("SW1A");
      const geo = lookup.current.getGeo("SW1A", "1AA");
      analytics.current.setIodDecile(geo?.deprivationDecile);
      analytics.current.captureStep("postcode", formData);
    });

    expect(mockCapture).toHaveBeenCalledWith("step_completed", {
      step: "postcode",
      form: "support",
      lad25cd: "E09000033",
      iod_decile: 7,
    });
  });

  it("step_completed postcode event has null iod_decile without ensureInward (pre-fix behavior)", async () => {
    const { result: lookup } = renderHook(() => usePostcodeLookup());
    const { result: analytics } = renderHook(() => useFormAnalytics("support"));
    await waitFor(() => expect(lookup.current.outwardLoaded).toBe(true));

    // Replicate the old buggy logic: getGeo without ensureInward
    const formData = makeFormData();
    act(() => {
      const geo = lookup.current.getGeo("SW1A", "1AA");
      analytics.current.setIodDecile(geo?.deprivationDecile);
      analytics.current.captureStep("postcode", formData);
    });

    expect(mockCapture).toHaveBeenCalledWith("step_completed", {
      step: "postcode",
      form: "support",
      lad25cd: "E09000033",
      iod_decile: null,
    });
  });
});

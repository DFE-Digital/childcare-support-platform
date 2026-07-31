import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useFormAnalytics } from "../useFormAnalytics";
import type { FormLocalStorageData } from "@/types/formData";

const mockCapture = vi.fn();

vi.mock("posthog-js/react", () => ({
  usePostHog: vi.fn(() => ({ capture: mockCapture })),
}));

function makeFormData(
  overrides: Partial<FormLocalStorageData> = {},
): FormLocalStorageData {
  return {
    schemaVersion: 7,
    location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] },
    household: { hasPartner: true },
    user: {
      isApprentice: null,
      firstYearApprentice: null,
      isSelfEmployed: null,
      selfEmployedLessThanTwelveMonths: null,
      ageBracket: null,
      workingStatus: "earning_above_nmw",
      receivesQualifyingAllowance: null,
      startingWorkNextMonth: null,
      hasLimitedCapacityForWork: null,
      hasNationalInsuranceNumber: null,
      residencyStatus: "british_irish_citizen",
      isStudying: false,
      studyLevel: null,
      isFullTimeStudent: null,
      courseIsPubliclyFunded: null,
      eligibleForStudentFinance: null,
    },
    partner: null,
    qualifyingBenefits: ["none"],
    ucIncomeBelowThreshold: null,
    nrpfIncomeUnderThreshold: null,
    nrpfSavingsUnderLimit: null,
    children: [
      {
        id: 1,
        firstName: "Alice",
        birthMonth: 3,
        birthYear: 2023,
        hasSEND: null,
        sendDetails: null,
        isFostered: null,
        hasEHCP: null,
        hasLeftCareForAdoptionOrSpecialGuardianship: null,
        childcareSelections: [
          { id: 1, careType: "private_nursery" as const, providerId: null },
        ],
      },
    ],
    shortlistedProviders: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useFormAnalytics", () => {
  it("captures step_completed with step name and form", () => {
    const { result } = renderHook(() => useFormAnalytics("support"));
    const formData = makeFormData();

    act(() => result.current.captureStep("partner", formData));

    expect(mockCapture).toHaveBeenCalledOnce();
    expect(mockCapture).toHaveBeenCalledWith("step_completed", {
      step: "partner",
      form: "support",
      has_partner: true,
    });
  });

  it("attaches location props for postcode step", () => {
    const { result } = renderHook(() => useFormAnalytics("costs"));
    const formData = makeFormData();

    act(() => result.current.setIodDecile(5));
    act(() => result.current.captureStep("postcode", formData));

    expect(mockCapture).toHaveBeenCalledWith("step_completed", {
      step: "postcode",
      form: "costs",
      lad25cd: "E09000033",
      iod_decile: 5,
    });
  });

  it("attaches immigration props for immigration step", () => {
    const { result } = renderHook(() => useFormAnalytics("support"));
    const formData = makeFormData();

    act(() => result.current.captureStep("immigration", formData));

    expect(mockCapture).toHaveBeenCalledWith("step_completed", {
      step: "immigration",
      form: "support",
      settled_in_uk: true,
    });
  });

  it("attaches working props for working step", () => {
    const { result } = renderHook(() => useFormAnalytics("support"));
    const formData = makeFormData();

    act(() => result.current.captureStep("working", formData));

    expect(mockCapture).toHaveBeenCalledWith("step_completed", {
      step: "working",
      form: "support",
      working: true,
      is_studying: false,
    });
  });

  it("attaches benefits props for benefits step", () => {
    const { result } = renderHook(() => useFormAnalytics("support"));
    const formData = makeFormData({ qualifyingBenefits: ["universal_credit"] });

    act(() => result.current.captureStep("benefits", formData));

    expect(mockCapture).toHaveBeenCalledWith("step_completed", {
      step: "benefits",
      form: "support",
      receives_benefits: true,
    });
  });

  it("attaches children props for children step", () => {
    const { result } = renderHook(() => useFormAnalytics("support"));
    const formData = makeFormData();

    act(() => result.current.captureStep("children", formData));

    expect(mockCapture).toHaveBeenCalledWith(
      "step_completed",
      expect.objectContaining({
        step: "children",
        form: "support",
        child_count: 1,
        youngest_band: expect.stringMatching(/^(0-4|5\+)$/),
      }),
    );
  });

  it("attaches childcare props for childcare step", () => {
    const { result } = renderHook(() => useFormAnalytics("costs"));
    const formData = makeFormData();

    act(() => result.current.captureStep("childcare", formData));

    expect(mockCapture).toHaveBeenCalledWith("step_completed", {
      step: "childcare",
      form: "costs",
      care_types_sought: ["private_nursery"],
    });
  });

  it("does not capture when posthog is null", async () => {
    const posthogModule = await import("posthog-js/react");
    vi.mocked(posthogModule.usePostHog).mockReturnValueOnce(
      // @ts-expect-error -- testing null posthog instance
      null,
    );

    const { result } = renderHook(() => useFormAnalytics("support"));
    const formData = makeFormData();

    act(() => result.current.captureStep("partner", formData));

    expect(mockCapture).not.toHaveBeenCalled();
  });

  it("setIodDecile persists value for subsequent postcode step capture", () => {
    const { result } = renderHook(() => useFormAnalytics("support"));
    const formData = makeFormData();

    act(() => result.current.setIodDecile(9));
    act(() => result.current.captureStep("postcode", formData));

    expect(mockCapture).toHaveBeenCalledWith(
      "step_completed",
      expect.objectContaining({ iod_decile: 9 }),
    );
  });

  it("never includes child names in any step event", () => {
    const { result } = renderHook(() => useFormAnalytics("support"));
    const formData = makeFormData();

    const steps = [
      "postcode",
      "partner",
      "immigration",
      "working",
      "benefits",
      "children",
      "childcare",
    ];
    for (const step of steps) {
      act(() => result.current.captureStep(step, formData));
    }

    for (const call of mockCapture.mock.calls) {
      const props = JSON.stringify(call[1]);
      expect(props).not.toContain("Alice");
    }
  });

  it("never includes birth dates in any step event", () => {
    const { result } = renderHook(() => useFormAnalytics("support"));
    const formData = makeFormData();

    act(() => result.current.captureStep("children", formData));

    const props = JSON.stringify(mockCapture.mock.calls[0][1]);
    expect(props).not.toContain("2023");
    expect(props).not.toContain("birthMonth");
    expect(props).not.toContain("birthYear");
  });
});

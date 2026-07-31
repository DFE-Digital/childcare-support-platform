import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, cleanup } from "@testing-library/react";
import { renderStep } from "@/test/renderStep";
import { ChildcareSelectionStep } from "../steps/ChildcareSelectionStep";
import type { FormChildData } from "@/types/formData";

// --- Mocks ---

vi.mock("@/hooks/usePostcodeLookup", () => ({
  usePostcodeLookup: () => ({
    filterOutward: () => [],
    filterInward: () => [],
    getGeo: () => null,
    getLaCodes: () => [],
    prefetchInward: vi.fn(),
    isValid: vi.fn(() => false),
    ensureInward: vi.fn(() => Promise.resolve({})),
    isLoading: false,
    outwardLoaded: true,
  }),
}));

vi.mock("@/hooks/useFamily", () => ({
  useFamily: () => ({
    completedSteps: {},
    markStepCompleted: vi.fn(),
    shortlistedProviders: [],
    getProviderById: () => undefined,
    schemes: [],
  }),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("@/hooks/useFeatureFlags", () => {
  const flags = {
    noBigKidEstimates: false,
    noProviderEstimates: false,
    showMetrics: false,
    showFees: false,
    showEligibility: false,
    showAvailability: false,
    showNotes: false,
    showSortDaily: false,
    showSortAnnual: false,
  };
  return { featureFlags: flags, useFeatureFlags: () => flags };
});

function makeChild(overrides: Partial<FormChildData> = {}): FormChildData {
  return {
    id: 1,
    firstName: "Alice",
    birthMonth: 3,
    birthYear: new Date().getFullYear() - 2,
    hasSEND: false,
    sendDetails: null,
    isFostered: false,
    hasEHCP: null,
    hasLeftCareForAdoptionOrSpecialGuardianship: null,
    childcareSelections: [],
    ...overrides,
  };
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// ChildcareSelectionStep — noBigKidEstimates OFF (non-production flag state)
// ---------------------------------------------------------------------------
describe("ChildcareSelectionStep (noBigKidEstimates off)", () => {
  it("5yo child sees care type cards, not info box", () => {
    const child = makeChild({
      firstName: "Older",
      birthYear: new Date().getFullYear() - 6,
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(
      screen.queryByText(/can't estimate childcare costs/),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /add childcare type/i }),
    ).toBeInTheDocument();
  });

  it("no secondary 'See your support options' button even with 5yo child", () => {
    const child = makeChild({
      firstName: "Older",
      birthYear: new Date().getFullYear() - 6,
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(
      screen.queryByRole("button", { name: /see your support options/i }),
    ).not.toBeInTheDocument();
  });

  it("continue button not disabled when all children are 5+", async () => {
    const child = makeChild({
      firstName: "Older",
      birthYear: new Date().getFullYear() - 6,
      childcareSelections: [
        {
          id: 1,
          careType: "childminder",
          providerId: null,
          hoursPerWeek: 10,
          weeksPerYear: 38,
        },
      ],
    });
    const { user, onContinue } = renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    await user.click(
      screen.getByRole("button", { name: /show your cost estimate/i }),
    );

    expect(onContinue).toHaveBeenCalled();
  });

  it("breakfast_club available in radio options for 4yo when flag off", () => {
    const fourYearOld = makeChild({
      firstName: "Four",
      birthYear: new Date().getFullYear() - 4,
      birthMonth: new Date().getMonth(), // just turned 4 (>= 48 months)
      childcareSelections: [
        { id: 1, careType: "private_nursery", providerId: null },
      ],
    });

    renderStep(ChildcareSelectionStep, {
      formData: { children: [fourYearOld] },
    });

    const radios = screen.getAllByRole("radio");
    const values = radios.map((r) => r.getAttribute("value"));

    expect(values).toContain("breakfast_club");
    expect(values).toContain("after_school_club");
    expect(values).toContain("holiday_club");
  });

  it("children shown in entry order (no small-first reordering)", () => {
    const big = makeChild({
      id: 1,
      firstName: "Older",
      birthYear: new Date().getFullYear() - 7,
    });
    const small = makeChild({
      id: 2,
      firstName: "Younger",
      birthYear: new Date().getFullYear() - 3,
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [big, small] },
    });

    const headings = screen.getAllByRole("heading", { level: 3 });
    // Entry order preserved: Older first, Younger second
    expect(headings[0]).toHaveTextContent("Older");
    expect(headings[1]).toHaveTextContent("Younger");
  });
});

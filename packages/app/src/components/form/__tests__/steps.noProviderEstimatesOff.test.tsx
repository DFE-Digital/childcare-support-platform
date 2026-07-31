import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

// jsdom doesn't implement HTMLDialogElement.showModal
HTMLDialogElement.prototype.showModal ??= vi.fn();

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// ChildcareSelectionStep — noProviderEstimates OFF (non-production flag state)
// ---------------------------------------------------------------------------
describe("ChildcareSelectionStep (noProviderEstimates off)", () => {
  it("shows provider dropdown when flag is off", () => {
    const child = makeChild({
      childcareSelections: [
        { id: 1, careType: "private_nursery", providerId: null },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(screen.getByText("Select shortlisted provider")).toBeInTheDocument();
  });

  it("modal shows Shortlisted provider section when flag is off", async () => {
    const user = userEvent.setup();
    renderStep(ChildcareSelectionStep, {
      formData: { children: [makeChild()] },
    });

    await user.click(
      screen.getByRole("button", { name: /how are cost estimates/i }),
    );

    expect(screen.getByText("Shortlisted provider")).toBeInTheDocument();
  });

  it("modal does not show Cost range or Older children when flag is off", async () => {
    const user = userEvent.setup();
    renderStep(ChildcareSelectionStep, {
      formData: { children: [makeChild()] },
    });

    await user.click(
      screen.getByRole("button", { name: /how are cost estimates/i }),
    );

    expect(screen.queryByText("Cost range")).not.toBeInTheDocument();
    expect(screen.queryByText("Older children")).not.toBeInTheDocument();
  });
});

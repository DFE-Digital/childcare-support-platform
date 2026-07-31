import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  screen,
  within,
  cleanup,
  waitFor,
  fireEvent,
} from "@testing-library/react";
import { renderStep, BLANK_DATA } from "@/test/renderStep";
import { PostcodeStep } from "../steps/PostcodeStep";
import { PartnerStep } from "../steps/PartnerStep";
import { ImmigrationStep } from "../steps/ImmigrationStep";
import { WorkingStep } from "../steps/WorkingStep";
import { UniversalCreditStep } from "../steps/UniversalCreditStep";
import { ChildrenStep } from "../steps/ChildrenStep";
import { ChildcareSelectionStep } from "../steps/ChildcareSelectionStep";
import type {
  FormPersonData,
  FormChildData,
  FormLocalStorageData,
} from "@/types/formData";
import type { EntitlementResult } from "@bsil/calculator";

// --- Mocks ---

const mockIsValid = vi.fn(() => false);
const mockEnsureInward = vi.fn(() => Promise.resolve({}));

vi.mock("@/hooks/usePostcodeLookup", () => ({
  usePostcodeLookup: () => ({
    filterOutward: () => [],
    filterInward: () => [],
    getGeo: () => null,
    getLaCodes: () => ["E09000033"],
    prefetchInward: vi.fn(),
    isValid: mockIsValid,
    ensureInward: mockEnsureInward,
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
    devolvedNationLinks: [],
    schemes: [
      {
        id: "tax_free_childcare",
        name: "Tax-Free Childcare",
        description: "Get up to £2,000 per year towards childcare costs.",
        ageRange: { minMonths: 0 },
      },
      {
        id: "universal_credit_childcare",
        name: "Universal Credit childcare",
        description: "Get up to 85% of your childcare costs paid back.",
        ageRange: { minMonths: 0 },
      },
      {
        id: "wraparound_childcare",
        name: "Wraparound childcare",
        description: "Before and after school childcare.",
        ageRange: { minYears: 4, maxYears: 14 },
      },
      {
        id: "free_breakfast_clubs",
        name: "Free breakfast clubs in primary schools",
        description: "Free 30-minute breakfast sessions.",
        ageRange: { minYears: 4, maxYears: 11 },
      },
    ],
  }),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

const mockFeatureFlags = vi.hoisted(() => ({
  noBigKidEstimates: true,
  noProviderEstimates: true,
  noAdditionalCharges: true,
  showMetrics: false,
  showFees: false,
  showEligibility: false,
  showAvailability: false,
  showNotes: false,
  showSortDaily: false,
  showSortAnnual: false,
}));

vi.mock("@/hooks/useFeatureFlags", () => ({
  featureFlags: mockFeatureFlags,
  useFeatureFlags: () => mockFeatureFlags,
}));

const mockCalculateEntitlements = vi.hoisted(() =>
  vi.fn((): EntitlementResult => ({ children: [] })),
);

vi.mock("@bsil/calculator", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@bsil/calculator")>();
  return {
    ...actual,
    calculateEntitlements: mockCalculateEntitlements,
  };
});

const ANSWERED_PERSON: FormPersonData = {
  isApprentice: false,
  firstYearApprentice: null,
  isSelfEmployed: false,
  selfEmployedLessThanTwelveMonths: null,
  ageBracket: "21+",
  workingStatus: "earning_above_nmw",
  receivesQualifyingAllowance: null,
  startingWorkNextMonth: null,
  hasLimitedCapacityForWork: null,
  hasNationalInsuranceNumber: true,
  residencyStatus: "british_irish_citizen",
  isStudying: false,
  studyLevel: null,
  isFullTimeStudent: null,
  courseIsPubliclyFunded: null,
  eligibleForStudentFinance: null,
};

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

const bigChild = (overrides: Partial<FormChildData> = {}): FormChildData => ({
  id: 1,
  firstName: "Older",
  birthMonth: 1,
  birthYear: new Date().getFullYear() - 7,
  hasSEND: false,
  sendDetails: null,
  isFostered: false,
  hasEHCP: null,
  hasLeftCareForAdoptionOrSpecialGuardianship: null,
  childcareSelections: [],
  ...overrides,
});

const smallChild = (overrides: Partial<FormChildData> = {}): FormChildData => ({
  id: 2,
  firstName: "Younger",
  birthMonth: 1,
  birthYear: new Date().getFullYear() - 3,
  hasSEND: false,
  sendDetails: null,
  isFostered: false,
  hasEHCP: null,
  hasLeftCareForAdoptionOrSpecialGuardianship: null,
  childcareSelections: [],
  ...overrides,
});

// Provide complete answered form data so resolveFormData doesn't throw
const answeredFormData: Partial<FormLocalStorageData> = {
  location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] },
  household: { hasPartner: false },
  user: ANSWERED_PERSON,
  partner: null,
  ucIncomeBelowThreshold: null,
  nrpfIncomeUnderThreshold: null,
  nrpfSavingsUnderLimit: null,
  qualifyingBenefits: [],
};

// jsdom doesn't implement HTMLDialogElement.showModal
HTMLDialogElement.prototype.showModal ??= vi.fn();

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// PostcodeStep
// ---------------------------------------------------------------------------
describe("PostcodeStep", () => {
  it("renders title and no back button", () => {
    renderStep(PostcodeStep);

    expect(screen.getByText("Where do you live?")).toBeInTheDocument();
    expect(screen.queryByText("Back")).not.toBeInTheDocument();
  });

  it("renders postcode input with current value", () => {
    renderStep(PostcodeStep, {
      formData: { location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] } },
    });

    expect(screen.getByRole("combobox")).toHaveValue("SW1A 1AA");
  });

  it("does not call onContinue when postcode is empty", async () => {
    mockIsValid.mockReturnValue(false);
    const { user, onContinue } = renderStep(PostcodeStep);

    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => {
      expect(onContinue).not.toHaveBeenCalled();
    });
  });

  it("does not call onContinue when postcode is invalid", async () => {
    mockIsValid.mockReturnValue(false);
    const { user, onContinue } = renderStep(PostcodeStep, {
      formData: { location: { postcode: "AAAA BBB", ladCodes: [] } },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => {
      expect(onContinue).not.toHaveBeenCalled();
    });
  });

  it("shows error message on invalid postcode", async () => {
    mockIsValid.mockReturnValue(false);
    const { user } = renderStep(PostcodeStep, {
      formData: { location: { postcode: "AAAA BBB", ladCodes: [] } },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => {
      expect(
        screen.getByText("Enter a valid UK postcode to continue"),
      ).toBeInTheDocument();
    });
  });

  it("calls onContinue when postcode is valid", async () => {
    mockIsValid.mockReturnValue(true);
    const { user, onContinue } = renderStep(PostcodeStep, {
      formData: { location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] } },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => {
      expect(onContinue).toHaveBeenCalled();
    });
  });

  it("clears error when user types", async () => {
    mockIsValid.mockReturnValue(false);
    const { user } = renderStep(PostcodeStep, {
      formData: { location: { postcode: "AAAA BBB", ladCodes: [] } },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => {
      expect(
        screen.getByText("Enter a valid UK postcode to continue"),
      ).toBeInTheDocument();
    });

    // Use fireEvent.change since the controlled input value won't update
    // (updateFormData is mocked), but this still triggers PostcodeStep's onChange
    // which calls setError(false)
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "SW1A" },
    });
    await waitFor(() => {
      expect(
        screen.queryByText("Enter a valid UK postcode to continue"),
      ).not.toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// PartnerStep
// ---------------------------------------------------------------------------
describe("PartnerStep", () => {
  it("renders partner question with back button", () => {
    renderStep(PartnerStep);

    expect(screen.getByText("Do you live with a partner?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back/i })).toBeInTheDocument();
  });

  it("blocks Continue when hasPartner is null", async () => {
    const { user, onContinue } = renderStep(PartnerStep);

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getByText("Please answer this question to continue"),
    ).toBeInTheDocument();
  });

  it("allows Continue when hasPartner is selected", async () => {
    const { user, onContinue } = renderStep(PartnerStep, {
      formData: { household: { hasPartner: false } },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).toHaveBeenCalled();
  });

  it("clicking Yes calls updateFormData with hasPartner true and partner defaults", async () => {
    const { user, updateFormData } = renderStep(PartnerStep);

    await user.click(screen.getByRole("radio", { name: "Yes" }));

    expect(updateFormData).toHaveBeenCalledWith(
      expect.objectContaining({
        household: { hasPartner: true },
        partner: expect.objectContaining({
          ageBracket: null,
          workingStatus: null,
        }),
      }),
    );
  });

  it("clicking No calls updateFormData with hasPartner false and partner null", async () => {
    const { user, updateFormData } = renderStep(PartnerStep, {
      formData: {
        household: { hasPartner: true },
        partner: ANSWERED_PERSON,
      },
    });

    await user.click(screen.getByRole("radio", { name: "No" }));

    expect(updateFormData).toHaveBeenCalledWith(
      expect.objectContaining({
        household: { hasPartner: false },
        partner: null,
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// ImmigrationStep
// ---------------------------------------------------------------------------
describe("ImmigrationStep", () => {
  it("renders About you section", () => {
    renderStep(ImmigrationStep);

    expect(screen.getByText("Immigration status")).toBeInTheDocument();
    expect(screen.getByText("About you")).toBeInTheDocument();
  });

  it("no radio selected when residencyStatus is null", () => {
    renderStep(ImmigrationStep);

    const britishRadios = screen.getAllByRole("radio", { name: "Yes" });
    expect(britishRadios[0]).not.toBeChecked();
  });

  it("hides residency sub-radio when residencyStatus is null", () => {
    renderStep(ImmigrationStep);

    expect(screen.queryByText(/with settled status/)).not.toBeInTheDocument();
  });

  it("shows residency sub-radio when not british_irish_citizen", () => {
    renderStep(ImmigrationStep, {
      formData: {
        user: { ...BLANK_DATA.user, residencyStatus: "settled_status" },
      },
    });

    expect(screen.getByText(/with settled status/)).toBeInTheDocument();
    expect(screen.getByText(/with pre-settled status/)).toBeInTheDocument();
  });

  it("blocks Continue when British/Irish is unanswered", async () => {
    const { user, onContinue } = renderStep(ImmigrationStep);

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getAllByText("Please answer this question to continue").length,
    ).toBeGreaterThan(0);
  });

  it("blocks Continue when NI number is unanswered", async () => {
    const { user, onContinue } = renderStep(ImmigrationStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          residencyStatus: "british_irish_citizen",
          hasNationalInsuranceNumber: null,
        },
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getByText("Please answer this question to continue"),
    ).toBeInTheDocument();
  });

  it("allows Continue when all questions answered", async () => {
    const { user, onContinue } = renderStep(ImmigrationStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          residencyStatus: "british_irish_citizen",
          hasNationalInsuranceNumber: true,
        },
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).toHaveBeenCalled();
  });

  it("clicking British/Irish No calls updateFormData with settled_status", async () => {
    const { user, updateFormData } = renderStep(ImmigrationStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          residencyStatus: "british_irish_citizen",
          hasNationalInsuranceNumber: true,
        },
      },
    });

    const noRadios = screen.getAllByRole("radio", { name: "No" });
    await user.click(noRadios[0]);

    expect(updateFormData).toHaveBeenCalledWith({
      user: expect.objectContaining({ residencyStatus: "settled_status" }),
    });
  });

  it("NI number toggle calls updateFormData", async () => {
    const { user, updateFormData } = renderStep(ImmigrationStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          residencyStatus: "british_irish_citizen",
          hasNationalInsuranceNumber: true,
        },
      },
    });

    // Click "No" on NI number question
    const noRadios = screen.getAllByRole("radio", { name: "No" });
    // The NI number "No" is the last "No" in the user section
    await user.click(noRadios[noRadios.length - 1]);

    expect(updateFormData).toHaveBeenCalledWith({
      user: expect.objectContaining({
        hasNationalInsuranceNumber: false,
      }),
    });
  });

  it("shows partner section when hasPartner is true", () => {
    renderStep(ImmigrationStep, {
      formData: {
        household: { hasPartner: true },
        partner: ANSWERED_PERSON,
      },
    });

    expect(screen.getByText("About your partner")).toBeInTheDocument();
  });

  it("hides partner section when hasPartner is false", () => {
    renderStep(ImmigrationStep);

    expect(screen.queryByText("About your partner")).not.toBeInTheDocument();
  });

  it("shows partner-specific labels in partner section", () => {
    renderStep(ImmigrationStep, {
      formData: {
        household: { hasPartner: true },
        user: {
          ...BLANK_DATA.user,
          residencyStatus: "settled_status",
          hasNationalInsuranceNumber: true,
        },
        partner: {
          ...ANSWERED_PERSON,
          residencyStatus: "settled_status",
        },
      },
    });

    expect(
      screen.getByText("Is your partner a British or Irish citizen?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "What is your partner's residency or immigration status?",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Does your partner have a National Insurance number?"),
    ).toBeInTheDocument();
    // User section still has "you" labels
    expect(
      screen.getByText("Are you a British or Irish citizen?"),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// WorkingStep
// ---------------------------------------------------------------------------
describe("WorkingStep", () => {
  it("renders working situation title", () => {
    renderStep(WorkingStep);

    expect(screen.getByText("Your working situation")).toBeInTheDocument();
  });

  it("blocks Continue when apprentice is unanswered", async () => {
    const { user, onContinue } = renderStep(WorkingStep);

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getAllByText("Please answer this question to continue").length,
    ).toBeGreaterThan(0);
  });

  it("blocks Continue when working status is unanswered", async () => {
    const { user, onContinue } = renderStep(WorkingStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          isApprentice: false,
          isSelfEmployed: false,
          isStudying: false,
          ageBracket: "21+",
          workingStatus: null,
        },
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getByText("Please answer this question to continue"),
    ).toBeInTheDocument();
  });

  it("blocks Continue when age bracket is unanswered", async () => {
    const { user, onContinue } = renderStep(WorkingStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          isApprentice: false,
          isSelfEmployed: false,
          isStudying: false,
          ageBracket: null,
          workingStatus: "earning_above_nmw",
        },
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getByText("Please answer this question to continue"),
    ).toBeInTheDocument();
  });

  it("shows standard working options for non-apprentice", () => {
    renderStep(WorkingStep, {
      formData: {
        user: { ...BLANK_DATA.user, isApprentice: false },
      },
    });

    expect(
      screen.getByText("Earning £203.36 or more per week"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Adjusted net income over £100,000"),
    ).toBeInTheDocument();
  });

  it("hides first year question when not apprentice", () => {
    renderStep(WorkingStep, {
      formData: { user: { ...BLANK_DATA.user, isApprentice: false } },
    });

    expect(
      screen.queryByText("Are you in your first year?"),
    ).not.toBeInTheDocument();
  });

  it("shows first year question when apprentice", () => {
    renderStep(WorkingStep, {
      formData: {
        user: { ...BLANK_DATA.user, isApprentice: true },
      },
    });

    expect(screen.getByText("Are you in your first year?")).toBeInTheDocument();
  });

  it("clicking apprentice Yes calls updateFormData with isApprentice true", async () => {
    const { user, updateFormData } = renderStep(WorkingStep);

    const yesRadios = screen.getAllByRole("radio", { name: "Yes" });
    await user.click(yesRadios[0]);

    expect(updateFormData).toHaveBeenCalledWith({
      user: expect.objectContaining({ isApprentice: true }),
    });
  });

  it("self-employed Yes with low earnings shows startup question", async () => {
    renderStep(WorkingStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          isApprentice: false,
          isSelfEmployed: true,
          workingStatus: "earning_below_nmw",
        },
      },
    });

    expect(
      screen.getByText(
        "Has your business been trading for less than 12 months?",
      ),
    ).toBeInTheDocument();
  });

  it("not working shows qualifying allowance question", () => {
    renderStep(WorkingStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          isApprentice: false,
          isSelfEmployed: false,
          ageBracket: "21+",
          workingStatus: "not_working",
          receivesQualifyingAllowance: false,
        },
      },
    });

    expect(
      screen.getByText(/Do you receive any of the following allowances/),
    ).toBeInTheDocument();
  });

  it("shows partner section when hasPartner", () => {
    renderStep(WorkingStep, {
      formData: {
        household: { hasPartner: true },
        partner: ANSWERED_PERSON,
      },
    });

    expect(screen.getByText("About your partner")).toBeInTheDocument();
  });

  it("shows partner-specific labels in partner section", () => {
    renderStep(WorkingStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          isApprentice: false,
          isSelfEmployed: false,
          ageBracket: "21+",
          workingStatus: "earning_above_nmw",
        },
        household: { hasPartner: true },
        partner: {
          ...ANSWERED_PERSON,
          isApprentice: false,
          isSelfEmployed: false,
        },
      },
    });

    expect(
      screen.getByText("Is your partner on an apprenticeship?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Is your partner self-employed?"),
    ).toBeInTheDocument();
    expect(screen.getByText("Your partner's age bracket")).toBeInTheDocument();
    expect(
      screen.getByText("Your partner's working and expected income situation"),
    ).toBeInTheDocument();
    // User section still has "you" labels
    expect(
      screen.getByText("Are you on an apprenticeship?"),
    ).toBeInTheDocument();
  });

  it("blocks Continue when Carer's Allowance is unanswered", async () => {
    const { user, onContinue } = renderStep(WorkingStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          isApprentice: false,
          isSelfEmployed: false,
          ageBracket: "21+",
          workingStatus: "not_working",
          receivesQualifyingAllowance: null,
        },
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getAllByText("Please answer this question to continue").length,
    ).toBeGreaterThan(0);
  });

  it("blocks Continue when startup question is unanswered", async () => {
    const { user, onContinue } = renderStep(WorkingStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          isApprentice: false,
          isSelfEmployed: true,
          ageBracket: "21+",
          workingStatus: "earning_below_nmw",
          selfEmployedLessThanTwelveMonths: null,
        },
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getAllByText("Please answer this question to continue").length,
    ).toBeGreaterThan(0);
  });

  it("allows Continue when all questions are answered", async () => {
    const { user, onContinue } = renderStep(WorkingStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          isApprentice: false,
          isSelfEmployed: false,
          isStudying: false,
          ageBracket: "21+",
          workingStatus: "not_working",
          receivesQualifyingAllowance: false,
        },
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).toHaveBeenCalled();
  });

  it("resets startingWorkNextMonth when working status changes", async () => {
    const { user, updateFormData } = renderStep(WorkingStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          isApprentice: false,
          isSelfEmployed: false,
          ageBracket: "21+",
          workingStatus: "not_working",
          receivesQualifyingAllowance: false,
          startingWorkNextMonth: true,
        },
      },
    });

    // Click "Earning £203.36 or more per week"
    await user.click(
      screen.getByRole("radio", { name: "Earning £203.36 or more per week" }),
    );

    expect(updateFormData).toHaveBeenCalledWith({
      user: expect.objectContaining({
        workingStatus: "earning_above_nmw",
        startingWorkNextMonth: null,
        hasLimitedCapacityForWork: null,
      }),
    });
  });

  it("resets startingWorkNextMonth when carer's allowance changes", async () => {
    const { user, updateFormData } = renderStep(WorkingStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          isApprentice: false,
          isSelfEmployed: false,
          ageBracket: "21+",
          workingStatus: "not_working",
          receivesQualifyingAllowance: false,
          startingWorkNextMonth: true,
        },
      },
    });

    // The carer's allowance question has Yes/No — click Yes
    const allowanceGroup = screen.getByRole("group", {
      name: /Do you receive any of the following allowances/i,
    });
    await user.click(
      within(allowanceGroup).getByRole("radio", { name: "Yes" }),
    );

    expect(updateFormData).toHaveBeenCalledWith({
      user: expect.objectContaining({
        receivesQualifyingAllowance: true,
        startingWorkNextMonth: null,
        hasLimitedCapacityForWork: null,
      }),
    });
  });

  it("blocks Continue for partner's unanswered sub-questions too", async () => {
    const { user, onContinue } = renderStep(WorkingStep, {
      formData: {
        user: {
          ...BLANK_DATA.user,
          isApprentice: false,
          isSelfEmployed: false,
          ageBracket: "21+",
          workingStatus: "earning_above_nmw",
        },
        household: { hasPartner: true },
        partner: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          receivesQualifyingAllowance: null,
        },
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getAllByText("Please answer this question to continue").length,
    ).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// UniversalCreditStep
// ---------------------------------------------------------------------------
describe("UniversalCreditStep", () => {
  it("renders single-parent question text", () => {
    renderStep(UniversalCreditStep);

    expect(
      screen.getByText("Do you get any of the following?"),
    ).toBeInTheDocument();
  });

  it("renders partner-aware question text", () => {
    renderStep(UniversalCreditStep, {
      formData: { household: { hasPartner: true } },
    });

    expect(
      screen.getByText("Do you or your partner get any of the following?"),
    ).toBeInTheDocument();
  });

  it("blocks Continue when benefits are unanswered", async () => {
    const { user, onContinue } = renderStep(UniversalCreditStep);

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getByText("Please answer this question to continue"),
    ).toBeInTheDocument();
  });

  it("allows Continue when benefits are selected", async () => {
    const { user, onContinue } = renderStep(UniversalCreditStep, {
      formData: { qualifyingBenefits: [] },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).toHaveBeenCalled();
  });

  it("clicking UC checkbox calls updateFormData with qualifyingBenefits", async () => {
    const { user, updateFormData } = renderStep(UniversalCreditStep, {
      formData: { qualifyingBenefits: [] },
    });

    await user.click(
      screen.getByRole("checkbox", { name: "Universal Credit" }),
    );
    expect(updateFormData).toHaveBeenCalledWith(
      expect.objectContaining({
        qualifyingBenefits: ["universal_credit"],
      }),
    );
  });

  it("clicking None clears other selections", async () => {
    const { user, updateFormData } = renderStep(UniversalCreditStep, {
      formData: { qualifyingBenefits: ["universal_credit"] },
    });

    await user.click(
      screen.getByRole("checkbox", { name: "None of the above" }),
    );
    expect(updateFormData).toHaveBeenCalledWith(
      expect.objectContaining({
        qualifyingBenefits: ["none"],
      }),
    );
  });

  it("does not show starting-work question when UC is false", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: [],
        user: { ...ANSWERED_PERSON, workingStatus: "not_working" },
      },
    });

    expect(
      screen.queryByText(/starting a job in the next month/),
    ).not.toBeInTheDocument();
  });

  it("does not show starting-work question when UC is true but user is working", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "earning_above_nmw",
        },
      },
    });

    expect(
      screen.queryByText(/starting a job in the next month/),
    ).not.toBeInTheDocument();
  });

  it("shows starting-work question when UC is true and user is not working", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        user: { ...ANSWERED_PERSON, workingStatus: "not_working" },
      },
    });

    expect(
      screen.getByText("Will you be starting a job in the next month?"),
    ).toBeInTheDocument();
  });

  it("shows partner starting-work question when UC is true and partner is not working", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: true },
        user: ANSWERED_PERSON,
        partner: { ...ANSWERED_PERSON, workingStatus: "not_working" },
      },
    });

    expect(
      screen.getByText(
        "Will your partner be starting a job in the next month?",
      ),
    ).toBeInTheDocument();
  });

  it("blocks continue when starting-work question is unanswered", async () => {
    const { user, onContinue } = renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: null,
        },
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(onContinue).not.toHaveBeenCalled();
  });

  it("clicking starting-work Yes calls updateFormData", async () => {
    const { user, updateFormData } = renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        user: { ...ANSWERED_PERSON, workingStatus: "not_working" },
      },
    });

    const group = screen.getByRole("group", {
      name: /starting a job in the next month/i,
    });
    await user.click(within(group).getByRole("radio", { name: "Yes" }));

    expect(updateFormData).toHaveBeenCalledWith(
      expect.objectContaining({
        user: expect.objectContaining({ startingWorkNextMonth: true }),
      }),
    );
  });

  it("hides starting-work question when user receives carer's allowance", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          receivesQualifyingAllowance: true,
        },
      },
    });

    expect(
      screen.queryByText(/starting a job in the next month/),
    ).not.toBeInTheDocument();
  });

  it("hides starting-work question when partner receives carer's allowance", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: true },
        user: ANSWERED_PERSON,
        partner: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          receivesQualifyingAllowance: true,
        },
      },
    });

    expect(
      screen.queryByText(/partner be starting a job in the next month/),
    ).not.toBeInTheDocument();
  });

  it("unchecking UC resets startingWorkNextMonth", async () => {
    const { user, updateFormData } = renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: true,
        },
        household: { hasPartner: true },
        partner: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: true,
        },
      },
    });

    // Uncheck UC checkbox — toggles it off
    await user.click(
      screen.getByRole("checkbox", { name: "Universal Credit" }),
    );

    expect(updateFormData).toHaveBeenCalledWith(
      expect.objectContaining({
        qualifyingBenefits: [],
        user: expect.objectContaining({ startingWorkNextMonth: null }),
        partner: expect.objectContaining({ startingWorkNextMonth: null }),
      }),
    );
  });

  it("shows LCW question when user not working, not starting, partner working", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: true },
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: false,
        },
        partner: ANSWERED_PERSON,
      },
    });

    expect(
      screen.getByText(/Do you have a disability which results in/i),
    ).toBeInTheDocument();
  });

  it("hides LCW question when user answered yes to starting work", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: true },
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: true,
        },
        partner: ANSWERED_PERSON,
      },
    });

    expect(
      screen.queryByText(/Do you have a disability which results in/i),
    ).not.toBeInTheDocument();
  });

  it("hides LCW question when user receives carer's allowance", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: true },
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          receivesQualifyingAllowance: true,
        },
        partner: ANSWERED_PERSON,
      },
    });

    expect(
      screen.queryByText(/Do you have a disability which results in/i),
    ).not.toBeInTheDocument();
  });

  it("hides LCW question for single parent", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: false },
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: false,
        },
      },
    });

    expect(
      screen.queryByText(/Do you have a disability which results in/i),
    ).not.toBeInTheDocument();
  });

  it("hides LCW question when neither parent is working", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: true },
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: false,
        },
        partner: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: false,
        },
      },
    });

    expect(
      screen.queryByText(/Do you have a disability which results in/i),
    ).not.toBeInTheDocument();
  });

  it("shows partner LCW question when partner not working, user working", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: true },
        user: ANSWERED_PERSON,
        partner: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: false,
        },
      },
    });

    expect(screen.getByText(/partner have a disability/i)).toBeInTheDocument();
  });

  it("unchecking UC resets hasLimitedCapacityForWork", async () => {
    const { user, updateFormData } = renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: true },
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: false,
          hasLimitedCapacityForWork: true,
        },
        partner: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: false,
          hasLimitedCapacityForWork: true,
        },
      },
    });

    // Uncheck UC checkbox
    await user.click(
      screen.getByRole("checkbox", { name: "Universal Credit" }),
    );

    expect(updateFormData).toHaveBeenCalledWith(
      expect.objectContaining({
        user: expect.objectContaining({ hasLimitedCapacityForWork: null }),
        partner: expect.objectContaining({ hasLimitedCapacityForWork: null }),
      }),
    );
  });

  it("changing starting-work answer resets hasLimitedCapacityForWork", async () => {
    const { user, updateFormData } = renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: true },
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: false,
          hasLimitedCapacityForWork: true,
        },
        partner: ANSWERED_PERSON,
      },
    });

    const startingGroup = screen.getByRole("group", {
      name: /starting a job in the next month/i,
    });
    await user.click(within(startingGroup).getByRole("radio", { name: "Yes" }));

    expect(updateFormData).toHaveBeenCalledWith(
      expect.objectContaining({
        user: expect.objectContaining({ hasLimitedCapacityForWork: null }),
      }),
    );
  });

  // --- NRPF + benefits incompatibility ---

  it("shows NRPF error when all parents NRPF and benefit selected", async () => {
    const { user } = renderStep(UniversalCreditStep, {
      formData: {
        ...answeredFormData,
        user: {
          ...ANSWERED_PERSON,
          residencyStatus: "no_recourse_to_public_funds",
        },
        qualifyingBenefits: ["universal_credit"],
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(
      screen.getByText(/no parent has access to public funds/),
    ).toBeInTheDocument();
  });

  it("allows Continue when all parents NRPF and 'none' selected", async () => {
    const { user, onContinue } = renderStep(UniversalCreditStep, {
      formData: {
        ...answeredFormData,
        user: {
          ...ANSWERED_PERSON,
          residencyStatus: "no_recourse_to_public_funds",
        },
        qualifyingBenefits: ["none"],
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).toHaveBeenCalled();
  });

  it("no NRPF error when only one parent is NRPF", async () => {
    const { user, onContinue } = renderStep(UniversalCreditStep, {
      formData: {
        ...answeredFormData,
        household: { hasPartner: true },
        user: {
          ...ANSWERED_PERSON,
          residencyStatus: "no_recourse_to_public_funds",
        },
        partner: {
          ...ANSWERED_PERSON,
          residencyStatus: "british_irish_citizen",
        },
        qualifyingBenefits: ["universal_credit"],
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).toHaveBeenCalled();
    expect(
      screen.queryByText(/no parent has access to public funds/),
    ).not.toBeInTheDocument();
  });

  it("clears NRPF error on checkbox change", async () => {
    const { user } = renderStep(UniversalCreditStep, {
      formData: {
        ...answeredFormData,
        user: {
          ...ANSWERED_PERSON,
          residencyStatus: "no_recourse_to_public_funds",
        },
        qualifyingBenefits: ["universal_credit"],
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(
      screen.getByText(/no parent has access to public funds/),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("checkbox", { name: /None of the above/ }),
    );
    expect(
      screen.queryByText(/no parent has access to public funds/),
    ).not.toBeInTheDocument();
  });

  it("shows 'Why does starting work matter?' footer when UC + not working", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: false },
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
        },
      },
    });

    expect(
      screen.getByText(/Why does starting work matter/),
    ).toBeInTheDocument();
  });

  it("shows 'What is limited capacity for work?' footer when LCW visible", () => {
    renderStep(UniversalCreditStep, {
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: true },
        user: {
          ...ANSWERED_PERSON,
          workingStatus: "not_working",
          startingWorkNextMonth: false,
        },
        partner: ANSWERED_PERSON,
      },
    });

    expect(
      screen.getByText(/What is limited capacity for work/),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ChildrenStep
// ---------------------------------------------------------------------------
describe("ChildrenStep", () => {
  it("renders child cards", () => {
    renderStep(ChildrenStep, {
      formData: { children: [makeChild()] },
    });

    expect(screen.getByText("Child 1")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Alice")).toBeInTheDocument();
  });

  it("Add a child button adds a new child", async () => {
    const child = makeChild();
    const { user, updateFormData } = renderStep(ChildrenStep, {
      formData: { children: [child] },
    });

    await user.click(screen.getByRole("button", { name: /add a child/i }));

    expect(updateFormData).toHaveBeenCalledWith({
      children: expect.arrayContaining([
        child,
        expect.objectContaining({
          id: 2,
          firstName: "",
          birthMonth: null,
          birthYear: null,
          hasSEND: null,
        }),
      ]),
    });
  });

  it("Remove button removes a child", async () => {
    const children = [
      makeChild({ id: 1 }),
      makeChild({ id: 2, firstName: "Bob" }),
    ];
    const { user, updateFormData } = renderStep(ChildrenStep, {
      formData: { children },
    });

    const removeButtons = screen.getAllByText("Remove");
    await user.click(removeButtons[0]); // remove first child

    expect(updateFormData).toHaveBeenCalledWith({
      children: [children[1]],
    });
  });

  it("Remove button is hidden when only one child", () => {
    renderStep(ChildrenStep, {
      formData: { children: [makeChild()] },
    });

    expect(screen.queryByText("Remove")).not.toBeInTheDocument();
  });

  it("disability radio calls updateFormData", async () => {
    const { user, updateFormData } = renderStep(ChildrenStep, {
      formData: { children: [makeChild({ hasSEND: false })] },
    });

    const disabilityGroup = screen.getByRole("group", {
      name: /disability/i,
    });
    await user.click(
      within(disabilityGroup).getByRole("radio", { name: "Yes" }),
    );

    expect(updateFormData).toHaveBeenCalledWith({
      children: [expect.objectContaining({ hasSEND: true })],
    });
  });

  it("foster carer radio calls updateFormData", async () => {
    const { user, updateFormData } = renderStep(ChildrenStep, {
      formData: { children: [makeChild({ isFostered: false })] },
    });

    const fosterGroup = screen.getByRole("group", {
      name: /foster carer/i,
    });
    await user.click(within(fosterGroup).getByRole("radio", { name: "Yes" }));

    expect(updateFormData).toHaveBeenCalledWith({
      children: [expect.objectContaining({ isFostered: true })],
    });
  });

  it("backfills blank child name with 'Child N' on continue", async () => {
    const { user, onContinue, updateFormData } = renderStep(ChildrenStep, {
      formData: { children: [makeChild({ firstName: "" })] },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(updateFormData).toHaveBeenCalledWith(
      expect.objectContaining({
        children: [expect.objectContaining({ firstName: "Child 1" })],
      }),
    );
    expect(onContinue).toHaveBeenCalled();
  });

  it("backfills multiple blank names with correct indices", async () => {
    const { user, onContinue, updateFormData } = renderStep(ChildrenStep, {
      formData: {
        children: [
          makeChild({ id: 1, firstName: "" }),
          makeChild({ id: 2, firstName: "" }),
        ],
      },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(updateFormData).toHaveBeenCalledWith(
      expect.objectContaining({
        children: [
          expect.objectContaining({ firstName: "Child 1" }),
          expect.objectContaining({ firstName: "Child 2" }),
        ],
      }),
    );
    expect(onContinue).toHaveBeenCalled();
  });

  it("blocks Continue when disability is unanswered", async () => {
    const { user, onContinue } = renderStep(ChildrenStep, {
      formData: { children: [makeChild({ hasSEND: null })] },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getByText("Please answer this question to continue"),
    ).toBeInTheDocument();
  });

  it("blocks Continue when birth month is not selected", async () => {
    const { user, onContinue } = renderStep(ChildrenStep, {
      formData: { children: [makeChild({ birthMonth: null })] },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getByText("Please select the child's date of birth"),
    ).toBeInTheDocument();
  });

  it("blocks Continue when birth year is not selected", async () => {
    const { user, onContinue } = renderStep(ChildrenStep, {
      formData: { children: [makeChild({ birthYear: null })] },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getByText("Please select the child's date of birth"),
    ).toBeInTheDocument();
  });

  it("allows Continue when all children have names and fields filled", async () => {
    const { user, onContinue } = renderStep(ChildrenStep, {
      formData: { children: [makeChild({ firstName: "Alice" })] },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).toHaveBeenCalled();
  });

  it("keeps user-provided name and does not auto-fill", async () => {
    const { user, onContinue, updateFormData } = renderStep(ChildrenStep, {
      formData: { children: [makeChild({ firstName: "Alice" })] },
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));

    // Should not update children since name is already provided
    expect(updateFormData).not.toHaveBeenCalledWith(
      expect.objectContaining({
        children: [expect.objectContaining({ firstName: "Child 1" })],
      }),
    );
    expect(onContinue).toHaveBeenCalled();
  });

  describe("NRPF questions", () => {
    const nrpfPerson = {
      ...BLANK_DATA.user,
      residencyStatus: "no_recourse_to_public_funds" as const,
      hasNationalInsuranceNumber: true as const,
    };

    const eligible2yo: FormChildData = {
      id: 1,
      firstName: "Child",
      birthMonth: 3,
      birthYear: new Date().getFullYear() - 2,
      hasSEND: false,
      sendDetails: null,
      isFostered: false,
      hasEHCP: false,
      hasLeftCareForAdoptionOrSpecialGuardianship: false,
      childcareSelections: [],
    };

    it("shows NRPF income question when all parents NRPF with eligible 2yo", () => {
      renderStep(ChildrenStep, {
        formData: {
          location: { postcode: "OX2 0AA", ladCodes: ["E07000178"] },
          user: nrpfPerson,
          partner: null,
          household: { hasPartner: false },
          children: [eligible2yo],
        },
      });

      expect(
        screen.getByText(/Is your household income less than £26,500/),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Do you have less than £16,000 in savings/),
      ).toBeInTheDocument();
    });

    it("shows London threshold for E09 LAD codes", () => {
      renderStep(ChildrenStep, {
        formData: {
          location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] },
          user: nrpfPerson,
          partner: null,
          household: { hasPartner: false },
          children: [eligible2yo],
        },
      });

      expect(
        screen.getByText(/Is your household income less than £34,500/),
      ).toBeInTheDocument();
    });

    it("shows 2+ children threshold", () => {
      renderStep(ChildrenStep, {
        formData: {
          location: { postcode: "OX2 0AA", ladCodes: ["E07000178"] },
          user: nrpfPerson,
          partner: null,
          household: { hasPartner: false },
          children: [eligible2yo, { ...eligible2yo, id: 2 }],
        },
      });

      expect(
        screen.getByText(/Is your household income less than £30,600/),
      ).toBeInTheDocument();
    });

    it("hides NRPF questions when only one parent is NRPF", () => {
      renderStep(ChildrenStep, {
        formData: {
          location: { postcode: "OX2 0AA", ladCodes: ["E07000178"] },
          household: { hasPartner: true },
          user: nrpfPerson,
          partner: {
            ...BLANK_DATA.user,
            residencyStatus: "british_irish_citizen",
          },
          children: [eligible2yo],
        },
      });

      expect(
        screen.queryByText(/Is your household income less than/),
      ).not.toBeInTheDocument();
    });

    it("hides NRPF questions when not in England", () => {
      renderStep(ChildrenStep, {
        formData: {
          location: { postcode: "CF10 1AA", ladCodes: ["W06000015"] },
          user: nrpfPerson,
          partner: null,
          household: { hasPartner: false },
          children: [eligible2yo],
        },
      });

      expect(
        screen.queryByText(/Is your household income less than/),
      ).not.toBeInTheDocument();
    });

    it("blocks Continue when NRPF income question is unanswered", async () => {
      const { user, onContinue } = renderStep(ChildrenStep, {
        formData: {
          location: { postcode: "OX2 0AA", ladCodes: ["E07000178"] },
          user: nrpfPerson,
          partner: null,
          household: { hasPartner: false },
          children: [eligible2yo],
          nrpfIncomeUnderThreshold: null,
          nrpfSavingsUnderLimit: null,
        },
      });

      await user.click(screen.getByRole("button", { name: /continue/i }));
      expect(onContinue).not.toHaveBeenCalled();
    });
  });

  it("shows 'What is an EHCP?' footer when EHCP questions are visible", () => {
    renderStep(ChildrenStep, {
      formData: {
        location: { postcode: "OX2 0AA", ladCodes: ["E07000178"] },
        household: { hasPartner: false },
        user: ANSWERED_PERSON,
        partner: null,
        children: [makeChild({ isFostered: false, hasSEND: false })],
      },
    });

    expect(screen.getByText(/What is an EHCP/)).toBeInTheDocument();
  });

  it("shows 'What does left care mean' footer when EHCP questions are visible", () => {
    renderStep(ChildrenStep, {
      formData: {
        location: { postcode: "OX2 0AA", ladCodes: ["E07000178"] },
        household: { hasPartner: false },
        user: ANSWERED_PERSON,
        partner: null,
        children: [makeChild({ isFostered: false, hasSEND: false })],
      },
    });

    expect(screen.getByText(/left care.*mean/i)).toBeInTheDocument();
  });

  it("shows 'What counts as household income?' footer when NRPF questions visible", () => {
    renderStep(ChildrenStep, {
      formData: {
        location: { postcode: "OX2 0AA", ladCodes: ["E07000178"] },
        user: {
          ...BLANK_DATA.user,
          residencyStatus: "no_recourse_to_public_funds" as const,
          hasNationalInsuranceNumber: true as const,
        },
        partner: null,
        household: { hasPartner: false },
        children: [
          makeChild({
            isFostered: false,
            hasSEND: false,
            hasEHCP: false,
            hasLeftCareForAdoptionOrSpecialGuardianship: false,
          }),
        ],
      },
    });

    expect(
      screen.getByText(/What counts as household income/),
    ).toBeInTheDocument();
  });

  it("shows 'What counts as savings?' footer when NRPF questions visible", () => {
    renderStep(ChildrenStep, {
      formData: {
        location: { postcode: "OX2 0AA", ladCodes: ["E07000178"] },
        user: {
          ...BLANK_DATA.user,
          residencyStatus: "no_recourse_to_public_funds" as const,
          hasNationalInsuranceNumber: true as const,
        },
        partner: null,
        household: { hasPartner: false },
        children: [
          makeChild({
            isFostered: false,
            hasSEND: false,
            hasEHCP: false,
            hasLeftCareForAdoptionOrSpecialGuardianship: false,
          }),
        ],
      },
    });

    expect(
      screen.getByText(/What counts as savings and investments/),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ChildcareSelectionStep
// ---------------------------------------------------------------------------
describe("ChildcareSelectionStep", () => {
  it("renders per-child sections", () => {
    renderStep(ChildcareSelectionStep, {
      formData: { children: [makeChild()] },
    });

    expect(screen.getByText("Childcare arrangements")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent(
      "Alice",
    );
  });

  it("Add childcare type button adds a selection", async () => {
    const child = makeChild();
    const { user, updateFormData } = renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    await user.click(
      screen.getByRole("button", { name: /add childcare type/i }),
    );

    expect(updateFormData).toHaveBeenCalledWith({
      children: [
        expect.objectContaining({
          childcareSelections: [
            expect.objectContaining({ careType: "private_nursery" }),
          ],
        }),
      ],
    });
  });

  it("shows age-appropriate care types for young child", () => {
    const child = makeChild({
      childcareSelections: [
        { id: 1, careType: "private_nursery", providerId: null },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    // For a 2-year-old: private_nursery, childminder (no school-based yet for <24mo check...)
    // Actually 2yo = 24 months, so school_based_nursery IS available
    const radios = screen.getAllByRole("radio");
    const values = radios.map((r) => r.getAttribute("value"));

    expect(values).toContain("private_nursery");
    expect(values).toContain("childminder");
    // Should NOT have after_school_club for <4 year old
    expect(values).not.toContain("after_school_club");
  });

  it("shows SBN info message for children aged 9-23 months", () => {
    const now = new Date();
    // Create a child that is 15 months old
    let birthMonth = now.getMonth() + 1 - 15;
    let birthYear = now.getFullYear();
    while (birthMonth <= 0) {
      birthMonth += 12;
      birthYear -= 1;
    }
    const child = makeChild({
      birthMonth,
      birthYear,
      childcareSelections: [
        { id: 1, careType: "private_nursery", providerId: null },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(
      screen.getByText(/school-based nursery might also accept your child/i),
    ).toBeInTheDocument();
  });

  it("does not show SBN info message for children aged 24+ months", () => {
    const child = makeChild({
      childcareSelections: [
        { id: 1, careType: "private_nursery", providerId: null },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(
      screen.queryByText(/school-based nursery might also accept your child/i),
    ).not.toBeInTheDocument();
  });

  it("shows Continue with custom label", () => {
    renderStep(ChildcareSelectionStep, {
      formData: { children: [makeChild()] },
    });

    expect(
      screen.getByRole("button", { name: /show your cost estimate/i }),
    ).toBeInTheDocument();
  });

  it("blocks Continue when no child has any selections", async () => {
    const { user, onContinue } = renderStep(ChildcareSelectionStep, {
      formData: { children: [makeChild()] },
    });

    await user.click(
      screen.getByRole("button", { name: /show your cost estimate/i }),
    );

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getByText(
        "Add at least one childcare type to get a cost estimate",
      ),
    ).toBeInTheDocument();
  });

  it("allows Continue when at least one child has a selection with valid values", async () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: {
            morning: { daysPerWeek: 3 },
            afternoon: { daysPerWeek: 2 },
          },
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

  it("blocks Continue when fields are empty (undefined)", async () => {
    const child = makeChild({
      childcareSelections: [
        { id: 1, careType: "private_nursery", providerId: null },
      ],
    });
    const { user, onContinue } = renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    await user.click(
      screen.getByRole("button", { name: /show your cost estimate/i }),
    );

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getAllByText("Enter a number between 0 and 7").length,
    ).toBeGreaterThan(0);
  });

  it("shows zero-usage warning for selections with all-zero values", () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: {
            morning: { daysPerWeek: 0 },
            afternoon: { daysPerWeek: 0 },
          },
        },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(
      screen.getByText(/zero usage.*affect your estimate/),
    ).toBeInTheDocument();
  });

  it("does not show zero-usage warning for newly-added selection with no numeric fields", () => {
    const child = makeChild({
      childcareSelections: [
        { id: 1, careType: "private_nursery", providerId: null },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(
      screen.queryByText(/zero usage.*affect your estimate/),
    ).not.toBeInTheDocument();
  });

  it("stores raw value without clamping for out-of-range input", () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: { morning: { daysPerWeek: 0 } },
        },
      ],
    });
    const { updateFormData } = renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    const input = screen.getByLabelText("Morning sessions per week");
    fireEvent.change(input, { target: { value: "99" } });

    expect(updateFormData).toHaveBeenCalledWith({
      children: [
        expect.objectContaining({
          childcareSelections: [
            expect.objectContaining({
              sessions: expect.objectContaining({
                morning: { daysPerWeek: 99 },
              }),
            }),
          ],
        }),
      ],
    });
  });

  it("shows validation error on Continue when field is out of range", async () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: {
            morning: { daysPerWeek: 99 },
            afternoon: { daysPerWeek: 2 },
          },
        },
      ],
    });
    const { user, onContinue } = renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    await user.click(
      screen.getByRole("button", { name: /show your cost estimate/i }),
    );

    expect(onContinue).not.toHaveBeenCalled();
    expect(
      screen.getByText("Enter a number between 0 and 7"),
    ).toBeInTheDocument();
  });

  it("allows Continue when fields are in valid range", async () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: {
            morning: { daysPerWeek: 3 },
            afternoon: { daysPerWeek: 2 },
          },
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

  it("shows red ring immediately for out-of-range value", () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: { morning: { daysPerWeek: 99 } },
        },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    // Red border applied directly on the input (no ValidationWrapper)
    const input = screen.getByLabelText("Morning sessions per week");
    expect(input.className).toContain("border-red-600");
  });

  it("reverts to red ring (no message) after editing a field post-submit", async () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: {
            morning: { daysPerWeek: 99 },
            afternoon: { daysPerWeek: 2 },
          },
        },
      ],
    });
    const { user } = renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    // Submit → validation message appears (only morning is invalid)
    await user.click(
      screen.getByRole("button", { name: /show your cost estimate/i }),
    );
    expect(
      screen.getByText("Enter a number between 0 and 7"),
    ).toBeInTheDocument();

    // Edit the field → usageErrors resets, validation message disappears
    const input = screen.getByLabelText("Morning sessions per week");
    fireEvent.change(input, { target: { value: "88" } });

    // Re-query: ValidationWrapper now keeps a stable DOM so the node is preserved
    const updatedInput = screen.getByLabelText("Morning sessions per week");
    // The full validation message text is gone (usageErrors reset)
    expect(
      screen.queryByText("Enter a number between 0 and 7"),
    ).not.toBeInTheDocument();
    // Red ring still present because the prop value (99) is still invalid
    expect(updatedInput.className).toContain("border-red-600");
  });

  // --- noBigKidEstimates behavior (flag is on by default, matching production) ---

  it("shows info box for big kid instead of care type cards", () => {
    mockCalculateEntitlements.mockReturnValue({
      children: [
        {
          childId: 1,
          childName: "Older",
          schemes: [
            {
              schemeId: "tax_free_childcare",
              eligible: true,
              reasons: [],
              caveats: [],
            },
          ],
        },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [bigChild()] },
    });

    expect(
      screen.getByText(
        (_content, el) =>
          el?.tagName === "P" &&
          el?.textContent?.includes("estimate childcare costs for") === true &&
          el?.textContent?.includes("Older") === true,
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /add childcare type/i }),
    ).not.toBeInTheDocument();
  });

  it("shows eligible schemes for big kid", () => {
    mockCalculateEntitlements.mockReturnValue({
      children: [
        {
          childId: 1,
          childName: "Older",
          schemes: [
            {
              schemeId: "tax_free_childcare",
              eligible: true,
              reasons: [],
              caveats: [],
            },
            {
              schemeId: "wraparound_childcare",
              eligible: true,
              reasons: [],
              caveats: [],
            },
            {
              schemeId: "free_breakfast_clubs",
              eligible: true,
              reasons: [],
              caveats: [],
            },
            {
              schemeId: "universal_credit_childcare",
              eligible: false,
              reasons: ["Not on UC"],
              caveats: [],
            },
          ],
        },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [bigChild()] },
    });

    expect(screen.getByText("Tax-Free Childcare")).toBeInTheDocument();
    expect(screen.getByText("Wraparound childcare")).toBeInTheDocument();
    expect(
      screen.getByText("Free breakfast clubs in primary schools"),
    ).toBeInTheDocument();
    // UC childcare was marked ineligible in mock, should not appear
    expect(
      screen.queryByText("Universal Credit childcare"),
    ).not.toBeInTheDocument();
  });

  it("renders mixed family: info box for big kid, cards for small kid", () => {
    mockCalculateEntitlements.mockReturnValue({
      children: [
        {
          childId: 1,
          childName: "Older",
          schemes: [
            {
              schemeId: "tax_free_childcare",
              eligible: true,
              reasons: [],
              caveats: [],
            },
          ],
        },
        { childId: 2, childName: "Younger", schemes: [] },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [bigChild(), smallChild()] },
    });

    // Big kid info box
    expect(
      screen.getByText(
        (_content, el) =>
          el?.tagName === "P" &&
          el?.textContent?.includes("estimate childcare costs for") === true &&
          el?.textContent?.includes("Older") === true,
      ),
    ).toBeInTheDocument();
    // Small kid gets care type button
    expect(
      screen.getByRole("button", { name: /add childcare type/i }),
    ).toBeInTheDocument();
  });

  it("shows small kids before big kids", () => {
    mockCalculateEntitlements.mockReturnValue({
      children: [
        {
          childId: 1,
          childName: "Older",
          schemes: [
            {
              schemeId: "tax_free_childcare",
              eligible: true,
              reasons: [],
              caveats: [],
            },
          ],
        },
        { childId: 2, childName: "Younger", schemes: [] },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [bigChild(), smallChild()] },
    });

    const headings = screen.getAllByRole("heading", { level: 3 });
    // Younger should appear first despite being second in data
    expect(headings[0]).toHaveTextContent("Younger");
    expect(headings[1]).toHaveTextContent("Older");
  });

  it("disables continue button when all children are big kids", () => {
    mockCalculateEntitlements.mockReturnValue({
      children: [
        {
          childId: 1,
          childName: "Older",
          schemes: [],
        },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [bigChild()] },
    });

    const button = screen.getByRole("button", {
      name: /show your cost estimate/i,
    });
    expect(button).toBeDisabled();
  });

  it("shows secondary 'See your support options' button when any big kid", () => {
    mockCalculateEntitlements.mockReturnValue({
      children: [
        {
          childId: 1,
          childName: "Older",
          schemes: [
            {
              schemeId: "tax_free_childcare",
              eligible: true,
              reasons: [],
              caveats: [],
            },
          ],
        },
        { childId: 2, childName: "Younger", schemes: [] },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [bigChild(), smallChild()] },
    });

    expect(
      screen.getByRole("button", { name: /see your support options/i }),
    ).toBeInTheDocument();
  });

  it("filters out inestimable care types from radio options for 4yo", () => {
    const fourYearOld = smallChild({
      id: 3,
      firstName: "Four",
      birthYear: new Date().getFullYear() - 4,
      birthMonth: new Date().getMonth(), // just turned 4 (>= 48 months)
      childcareSelections: [
        { id: 1, careType: "private_nursery", providerId: null },
      ],
    });
    mockCalculateEntitlements.mockReturnValue({ children: [] });

    renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [fourYearOld] },
    });

    const radios = screen.getAllByRole("radio");
    const values = radios.map((r) => r.getAttribute("value"));

    expect(values).toContain("private_nursery");
    expect(values).toContain("childminder");
    expect(values).not.toContain("breakfast_club");
    expect(values).not.toContain("after_school_club");
    expect(values).not.toContain("holiday_club");
  });

  it("validates only small kids when continuing with mixed family", async () => {
    mockCalculateEntitlements.mockReturnValue({
      children: [
        {
          childId: 1,
          childName: "Older",
          schemes: [
            {
              schemeId: "tax_free_childcare",
              eligible: true,
              reasons: [],
              caveats: [],
            },
          ],
        },
        { childId: 2, childName: "Younger", schemes: [] },
      ],
    });
    const young = smallChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: {
            morning: { daysPerWeek: 3 },
            afternoon: { daysPerWeek: 2 },
          },
        },
      ],
    });

    const { user, onContinue } = renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [bigChild(), young] },
    });

    await user.click(
      screen.getByRole("button", { name: /show your cost estimate/i }),
    );

    // Should succeed — big kid has no selections but is excluded from validation
    expect(onContinue).toHaveBeenCalled();
  });

  it("shows alternate subtitle when all children are 5+", () => {
    mockCalculateEntitlements.mockReturnValue({
      children: [{ childId: 1, childName: "Older", schemes: [] }],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [bigChild()] },
    });

    expect(
      screen.getByText(/can\u2019t create a cost estimate/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/select the types of childcare/),
    ).not.toBeInTheDocument();
  });

  it("shows normal subtitle when mix of big and small kids", () => {
    mockCalculateEntitlements.mockReturnValue({
      children: [
        {
          childId: 1,
          childName: "Older",
          schemes: [
            {
              schemeId: "tax_free_childcare",
              eligible: true,
              reasons: [],
              caveats: [],
            },
          ],
        },
        { childId: 2, childName: "Younger", schemes: [] },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [bigChild(), smallChild()] },
    });

    expect(
      screen.getByText(/select the types of childcare/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/can\u2019t create a cost estimate/),
    ).not.toBeInTheDocument();
  });

  it("shows 'Search for childcare providers' button when all children are 5+", () => {
    mockCalculateEntitlements.mockReturnValue({
      children: [{ childId: 1, childName: "Older", schemes: [] }],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [bigChild()] },
    });

    expect(
      screen.getByRole("button", { name: /search for childcare providers/i }),
    ).toBeInTheDocument();
  });

  it("does not show 'Search for childcare providers' button when mix of ages", () => {
    mockCalculateEntitlements.mockReturnValue({
      children: [
        {
          childId: 1,
          childName: "Older",
          schemes: [
            {
              schemeId: "tax_free_childcare",
              eligible: true,
              reasons: [],
              caveats: [],
            },
          ],
        },
        { childId: 2, childName: "Younger", schemes: [] },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { ...answeredFormData, children: [bigChild(), smallChild()] },
    });

    expect(
      screen.queryByRole("button", { name: /search for childcare providers/i }),
    ).not.toBeInTheDocument();
  });

  // --- noProviderEstimates behavior (flag is on by default, matching production) ---

  it("hides provider dropdown when noProviderEstimates is true", () => {
    const child = makeChild({
      childcareSelections: [
        { id: 1, careType: "private_nursery", providerId: null },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(
      screen.queryByText("Select shortlisted provider"),
    ).not.toBeInTheDocument();
  });

  it("modal shows DfE survey text when noProviderEstimates is true", async () => {
    const { user } = renderStep(ChildcareSelectionStep, {
      formData: { children: [makeChild()] },
    });

    await user.click(
      screen.getByRole("button", { name: /how are cost estimates/i }),
    );

    expect(
      screen.getByText(/DfE Early Years Childcare Provider Survey/),
    ).toBeInTheDocument();
  });

  it("modal shows Cost range section when noProviderEstimates is true", async () => {
    const { user } = renderStep(ChildcareSelectionStep, {
      formData: { children: [makeChild()] },
    });

    await user.click(
      screen.getByRole("button", { name: /how are cost estimates/i }),
    );

    expect(screen.getByText("Cost range")).toBeInTheDocument();
  });

  it("modal shows Older children section when noProviderEstimates is true", async () => {
    const { user } = renderStep(ChildcareSelectionStep, {
      formData: { children: [makeChild()] },
    });

    await user.click(
      screen.getByRole("button", { name: /how are cost estimates/i }),
    );

    expect(screen.getByText("Older children")).toBeInTheDocument();
    expect(
      screen.getByText(/average costs for early years childcare/),
    ).toBeInTheDocument();
  });

  it("modal hides Shortlisted provider section when noProviderEstimates is true", async () => {
    const { user } = renderStep(ChildcareSelectionStep, {
      formData: { children: [makeChild()] },
    });

    await user.click(
      screen.getByRole("button", { name: /how are cost estimates/i }),
    );

    expect(screen.queryByText("Shortlisted provider")).not.toBeInTheDocument();
  });

  // --- Nursery weeks-per-year radio + conditional input ---

  it("shows default weeks radio for PVI nursery (50 weeks year-round)", () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: { morning: { daysPerWeek: 3 } },
        },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(
      screen.getByRole("radio", {
        name: /50 weeks per year \(year-round\)/i,
      }),
    ).toBeChecked();
    expect(screen.getByRole("radio", { name: /custom/i })).not.toBeChecked();
  });

  it("shows default weeks radio for school-based nursery (38 weeks term-time)", () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "school_based_nursery",
          providerId: null,
          sessions: { morning: { daysPerWeek: 3 } },
        },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(
      screen.getByRole("radio", {
        name: /38 weeks per year \(term-time only\)/i,
      }),
    ).toBeChecked();
  });

  it("reveals custom weeks input when Custom radio is selected", async () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: { morning: { daysPerWeek: 3 } },
        },
      ],
    });
    const { user } = renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(screen.queryByLabelText("Weeks per year")).not.toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: /custom/i }));

    expect(screen.getByLabelText("Weeks per year")).toBeInTheDocument();
  });

  it("pre-fills custom weeks with default value (50 for PVI)", async () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: { morning: { daysPerWeek: 3 } },
        },
      ],
    });
    const { user, updateFormData } = renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    await user.click(screen.getByRole("radio", { name: /custom/i }));

    expect(updateFormData).toHaveBeenCalledWith({
      children: [
        expect.objectContaining({
          childcareSelections: [expect.objectContaining({ weeksPerYear: 50 })],
        }),
      ],
    });
  });

  it("keeps custom weeks input visible when value is cleared", async () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: { morning: { daysPerWeek: 3 } },
          weeksPerYear: 50,
        },
      ],
    });
    renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    const input = screen.getByLabelText("Weeks per year");
    fireEvent.change(input, { target: { value: "" } });

    expect(screen.getByLabelText("Weeks per year")).toBeInTheDocument();
  });

  it("hides custom weeks input when switching back to default", async () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: { morning: { daysPerWeek: 3 } },
          weeksPerYear: 42,
        },
      ],
    });
    const { user } = renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    expect(screen.getByLabelText("Weeks per year")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: /50 weeks per year/i }));

    expect(screen.queryByLabelText("Weeks per year")).not.toBeInTheDocument();
  });

  it("blocks Continue when custom weeks is empty", async () => {
    const child = makeChild({
      childcareSelections: [
        {
          id: 1,
          careType: "private_nursery",
          providerId: null,
          sessions: { morning: { daysPerWeek: 3 } },
          weeksPerYear: undefined,
        },
      ],
    });
    const { user } = renderStep(ChildcareSelectionStep, {
      formData: { children: [child] },
    });

    await user.click(screen.getByRole("radio", { name: /custom/i }));

    // Clear the pre-filled value
    const input = screen.getByLabelText("Weeks per year");
    fireEvent.change(input, { target: { value: "" } });

    await user.click(
      screen.getByRole("button", { name: /show your cost estimate/i }),
    );

    expect(
      screen.getByText("Enter a number between 1 and 52"),
    ).toBeInTheDocument();
  });
});

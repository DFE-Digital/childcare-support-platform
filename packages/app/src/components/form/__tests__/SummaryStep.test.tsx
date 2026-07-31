import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SummaryStep } from "../SummaryStep";
import type { FormLocalStorageData } from "@/types/formData";
import { BLANK_DATA } from "@/test/renderStep";

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("@/hooks/useFeatureFlags", () => {
  const flags = {
    noBigKidEstimates: true,
    noProviderEstimates: true,
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

function bigChild(id = 1, name = "Older") {
  return {
    id,
    firstName: name,
    birthMonth: 1,
    birthYear: new Date().getFullYear() - 7,
    hasSEND: false as const,
    sendDetails: null,
    isFostered: false as const,
    hasEHCP: null,
    hasLeftCareForAdoptionOrSpecialGuardianship: null,
    childcareSelections:
      [] as FormLocalStorageData["children"][0]["childcareSelections"],
  };
}

const ALL_LABELS = [
  "Where you live",
  "Living situation",
  "Working situation",
  "Benefits",
  "Your children",
  "Childcare arrangements",
];

function renderSummary(
  overrides: {
    formData?: Partial<FormLocalStorageData>;
    completedLabels?: string[];
    invalidLabels?: string[];
    allLabels?: string[];
  } = {},
) {
  const formData: FormLocalStorageData = {
    ...BLANK_DATA,
    ...overrides.formData,
    location: { ...BLANK_DATA.location, ...overrides.formData?.location },
    household: { ...BLANK_DATA.household, ...overrides.formData?.household },
    user: { ...BLANK_DATA.user, ...overrides.formData?.user },
  };
  const onEdit = vi.fn();
  const onContinue = vi.fn();
  const user = userEvent.setup();

  const result = render(
    <SummaryStep
      formData={formData}
      completedLabels={overrides.completedLabels ?? ALL_LABELS.slice(0, 2)}
      invalidLabels={overrides.invalidLabels ?? []}
      allLabels={overrides.allLabels ?? ALL_LABELS}
      onEdit={onEdit}
      onContinue={onContinue}
    />,
  );

  return { ...result, user, onEdit, onContinue };
}

beforeEach(() => {
  cleanup();
});

describe("SummaryStep", () => {
  it("shows completed step answers", () => {
    renderSummary({
      formData: {
        location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] },
        household: { hasPartner: false },
      },
      completedLabels: ["Where you live", "Living situation"],
    });

    expect(screen.getByText("SW1A 1AA")).toBeInTheDocument();
    expect(screen.getByText("Single parent")).toBeInTheDocument();
  });

  it("shows partner label when hasPartner is true", () => {
    renderSummary({
      formData: {
        household: { hasPartner: true },
      },
      completedLabels: ["Living situation"],
    });

    expect(screen.getByText("Lives with a partner")).toBeInTheDocument();
  });

  it("hides uncompleted steps", () => {
    renderSummary({
      completedLabels: ["Where you live"],
    });

    // "Where you live" is completed
    expect(screen.getByText("Where you live")).toBeInTheDocument();
    // "Living situation" is NOT completed — should not appear
    expect(screen.queryByText("Living situation")).not.toBeInTheDocument();
  });

  it("Edit button calls onEdit with step number", async () => {
    const { user, onEdit } = renderSummary({
      completedLabels: ["Where you live", "Living situation"],
    });

    const editButtons = screen.getAllByText("Edit");
    await user.click(editButtons[0]); // Edit "Where you live" (step 1)
    expect(onEdit).toHaveBeenCalledWith(1);

    await user.click(editButtons[1]); // Edit "Living situation" (step 2)
    expect(onEdit).toHaveBeenCalledWith(2);
  });

  it("shows Continue button when uncompleted steps remain", () => {
    renderSummary({
      completedLabels: ["Where you live"],
    });

    expect(
      screen.getByRole("button", { name: /continue/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /show results/i }),
    ).not.toBeInTheDocument();
  });

  it("shows Show results button when all steps complete", () => {
    renderSummary({
      completedLabels: ALL_LABELS,
    });

    expect(
      screen.getByRole("button", { name: /show results/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^continue$/i }),
    ).not.toBeInTheDocument();
  });

  it("onContinue callback fires on button click", async () => {
    const { user, onContinue } = renderSummary({
      completedLabels: ["Where you live"],
    });

    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(onContinue).toHaveBeenCalled();
  });

  it("renders Benefits answer", () => {
    renderSummary({
      formData: { qualifyingBenefits: ["universal_credit"] },
      completedLabels: ["Benefits"],
    });

    expect(screen.getByText("Benefits")).toBeInTheDocument();
  });

  it("renders children summary with disability and fostered tags", () => {
    renderSummary({
      formData: {
        children: [
          {
            id: 1,
            firstName: "Alice",
            birthMonth: 3,
            birthYear: 2023,
            hasSEND: true,
            sendDetails: null,
            isFostered: true as const,
            hasEHCP: null,
            hasLeftCareForAdoptionOrSpecialGuardianship: null,
            childcareSelections: [],
          },
        ],
      },
      completedLabels: ["Your children"],
    });

    expect(screen.getByText(/Alice/)).toBeInTheDocument();
    expect(screen.getByText(/March/)).toBeInTheDocument();
    expect(screen.getByText(/2023/)).toBeInTheDocument();
    expect(
      screen.getByText("(disability or SEN, fostered)"),
    ).toBeInTheDocument();
  });

  it("renders fostered-only tag", () => {
    renderSummary({
      formData: {
        children: [
          {
            id: 1,
            firstName: "Bob",
            birthMonth: 6,
            birthYear: 2022,
            hasSEND: false as const,
            sendDetails: null,
            isFostered: true as const,
            hasEHCP: null,
            hasLeftCareForAdoptionOrSpecialGuardianship: null,
            childcareSelections: [],
          },
        ],
      },
      completedLabels: ["Your children"],
    });

    expect(screen.getByText("(fostered)")).toBeInTheDocument();
  });

  it("renders no tags when child is not disabled or fostered", () => {
    renderSummary({
      formData: {
        children: [
          {
            id: 1,
            firstName: "Charlie",
            birthMonth: 9,
            birthYear: 2023,
            hasSEND: false as const,
            sendDetails: null,
            isFostered: false as const,
            hasEHCP: null,
            hasLeftCareForAdoptionOrSpecialGuardianship: null,
            childcareSelections: [],
          },
        ],
      },
      completedLabels: ["Your children"],
    });

    expect(screen.queryByText(/disability/)).not.toBeInTheDocument();
    expect(screen.queryByText(/fostered/)).not.toBeInTheDocument();
  });

  it("renders childcare arrangements summary", () => {
    renderSummary({
      formData: {
        children: [
          {
            id: 1,
            firstName: "Bob",
            birthMonth: 6,
            birthYear: 2022,
            hasSEND: false,
            sendDetails: null,
            isFostered: false as const,
            hasEHCP: null,
            hasLeftCareForAdoptionOrSpecialGuardianship: null,
            childcareSelections: [
              { id: 1, careType: "private_nursery", providerId: null },
              { id: 2, careType: "childminder", providerId: null },
            ],
          },
        ],
      },
      completedLabels: ["Childcare arrangements"],
    });

    expect(
      screen.getByText(/Nursery \(Private, Voluntary or Independent\)/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Childminder/)).toBeInTheDocument();
  });

  it("renders working situation summary", () => {
    renderSummary({
      formData: {
        user: {
          ...BLANK_DATA.user,
          ageBracket: "21+",
          workingStatus: "earning_above_nmw",
        },
        household: { hasPartner: true },
        partner: {
          ...BLANK_DATA.user,
          ageBracket: "18-20",
          workingStatus: "not_working",
          receivesQualifyingAllowance: true,
        },
      },
      completedLabels: ["Working situation"],
    });

    expect(screen.getByText(/You:/)).toBeInTheDocument();
    expect(screen.getByText(/Partner:/)).toBeInTheDocument();
    expect(screen.getByText(/Carer's Allowance/)).toBeInTheDocument();
  });

  it("Benefits row shows starting work for user", () => {
    renderSummary({
      formData: {
        qualifyingBenefits: ["universal_credit"],
        user: {
          ...BLANK_DATA.user,
          workingStatus: "not_working",
          startingWorkNextMonth: true,
        },
      },
      completedLabels: ["Benefits"],
    });

    expect(screen.getByText(/Universal Credit/)).toBeInTheDocument();
    expect(
      screen.getByText(/Starting work within a month/),
    ).toBeInTheDocument();
  });

  it("Benefits row shows starting work for partner", () => {
    renderSummary({
      formData: {
        qualifyingBenefits: ["universal_credit"],
        household: { hasPartner: true },
        user: {
          ...BLANK_DATA.user,
          workingStatus: "earning_above_nmw",
        },
        partner: {
          ...BLANK_DATA.user,
          workingStatus: "not_working",
          startingWorkNextMonth: true,
        },
      },
      completedLabels: ["Benefits"],
    });

    expect(screen.getByText(/Your partner:/)).toBeInTheDocument();
    expect(
      screen.getByText(/Starting work within a month/),
    ).toBeInTheDocument();
  });

  it("Benefits row shows LCW label when hasLimitedCapacityForWork is true", () => {
    renderSummary({
      formData: {
        household: { hasPartner: true },
        user: {
          ...BLANK_DATA.user,
          workingStatus: "not_working",
          hasLimitedCapacityForWork: true,
        },
        qualifyingBenefits: ["universal_credit"],
      },
      completedLabels: ["Benefits"],
    });

    expect(screen.getByText(/Limited capacity for work/)).toBeInTheDocument();
  });

  it("Benefits row does not show LCW label when hasLimitedCapacityForWork is false", () => {
    renderSummary({
      formData: {
        household: { hasPartner: true },
        user: {
          ...BLANK_DATA.user,
          workingStatus: "not_working",
          hasLimitedCapacityForWork: false,
        },
        qualifyingBenefits: ["universal_credit"],
      },
      completedLabels: ["Benefits"],
    });

    expect(
      screen.queryByText(/Limited capacity for work/),
    ).not.toBeInTheDocument();
  });

  it("Benefits row does not show starting work when not starting soon", () => {
    renderSummary({
      formData: {
        qualifyingBenefits: ["universal_credit"],
        user: {
          ...BLANK_DATA.user,
          workingStatus: "not_working",
          startingWorkNextMonth: false,
        },
      },
      completedLabels: ["Benefits"],
    });

    expect(screen.getByText(/Universal Credit/)).toBeInTheDocument();
    expect(
      screen.queryByText(/Starting work within a month/),
    ).not.toBeInTheDocument();
  });

  it("renders invalidated steps with Update button and warning message", () => {
    renderSummary({
      completedLabels: ["Where you live"],
      invalidLabels: ["Working situation"],
    });

    expect(screen.getByText("Where you live")).toBeInTheDocument();
    expect(screen.getByText("Working situation")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Needs updating — your earlier changes affected this step",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Update")).toBeInTheDocument();
    expect(screen.getByText("Edit")).toBeInTheDocument();
  });

  it("Update button on invalid step calls onEdit with correct step number", async () => {
    const { user, onEdit } = renderSummary({
      completedLabels: ["Where you live"],
      invalidLabels: ["Working situation"],
    });

    await user.click(screen.getByText("Update"));
    expect(onEdit).toHaveBeenCalledWith(3); // "Working situation" is step 3
  });

  it("shows Continue button (not Show results) when invalid steps exist", () => {
    renderSummary({
      completedLabels: ALL_LABELS,
      invalidLabels: ["Working situation"],
    });

    expect(
      screen.getByRole("button", { name: /continue/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /show results/i }),
    ).not.toBeInTheDocument();
  });

  it("shows updating subtitle when invalid steps exist", () => {
    renderSummary({
      completedLabels: ["Where you live"],
      invalidLabels: ["Working situation"],
    });

    expect(screen.getByText(/some answers need updating/i)).toBeInTheDocument();
  });

  it("renders mix of valid and invalid steps correctly", () => {
    renderSummary({
      formData: {
        location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] },
        household: { hasPartner: false },
      },
      completedLabels: ["Where you live", "Living situation"],
      invalidLabels: ["Working situation", "Benefits"],
    });

    // Valid steps show their data
    expect(screen.getByText("SW1A 1AA")).toBeInTheDocument();
    expect(screen.getByText("Single parent")).toBeInTheDocument();

    // Invalid steps show warning
    expect(screen.getByText("Working situation")).toBeInTheDocument();
    expect(screen.getByText("Benefits")).toBeInTheDocument();
    const warnings = screen.getAllByText(
      "Needs updating — your earlier changes affected this step",
    );
    expect(warnings).toHaveLength(2);

    // 2 Edit buttons + 2 Update buttons
    expect(screen.getAllByText("Edit")).toHaveLength(2);
    expect(screen.getAllByText("Update")).toHaveLength(2);
  });

  it("shows unmarked-but-invalid steps with Update styling", () => {
    // Simulates steps that were unmarked (not in completedLabels) but still
    // fail validation — they should still appear with "Update" styling
    renderSummary({
      formData: {
        location: { postcode: "SW1A 1AA", ladCodes: ["E09000033"] },
        household: { hasPartner: true },
      },
      completedLabels: ["Where you live", "Living situation"],
      invalidLabels: ["Working situation", "Benefits"],
    });

    // Completed steps show their data
    expect(screen.getByText("SW1A 1AA")).toBeInTheDocument();
    expect(screen.getByText("Lives with a partner")).toBeInTheDocument();

    // Invalid steps (not in completedLabels) still show with Update button
    expect(screen.getByText("Working situation")).toBeInTheDocument();
    expect(screen.getByText("Benefits")).toBeInTheDocument();
    expect(screen.getAllByText("Update")).toHaveLength(2);
    expect(screen.getAllByText(/needs updating/i)).toHaveLength(2);

    // Steps that are neither completed nor invalid are hidden
    expect(screen.queryByText("Your children")).not.toBeInTheDocument();
  });

  it("empty invalidLabels behaves identically to previous behaviour", () => {
    renderSummary({
      completedLabels: ["Where you live", "Living situation"],
      invalidLabels: [],
    });

    expect(screen.getByText("Where you live")).toBeInTheDocument();
    expect(screen.getByText("Living situation")).toBeInTheDocument();
    expect(screen.queryByText("Update")).not.toBeInTheDocument();
    expect(screen.queryByText(/needs updating/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("Edit")).toHaveLength(2);
  });

  // --- noBigKidEstimates: allBigKids on cost form ---

  it("disables button and shows warning when all children are 5+ on cost form", () => {
    renderSummary({
      formData: { children: [bigChild()] },
      completedLabels: ALL_LABELS.slice(0, 5),
      allLabels: ALL_LABELS,
    });

    expect(
      screen.getByText(/can\u2019t provide a cost estimate/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();
  });

  it("shows secondary buttons when all children are 5+ on cost form", () => {
    renderSummary({
      formData: { children: [bigChild()] },
      completedLabels: ALL_LABELS.slice(0, 5),
      allLabels: ALL_LABELS,
    });

    expect(
      screen.getByRole("button", { name: /see your support options/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /search for childcare providers/i }),
    ).toBeInTheDocument();
  });

  it("does not disable button when children are young", () => {
    renderSummary({
      formData: {
        children: [
          {
            ...bigChild(),
            birthYear: new Date().getFullYear() - 2,
          },
        ],
      },
      completedLabels: ALL_LABELS.slice(0, 5),
      allLabels: ALL_LABELS,
    });

    expect(
      screen.getByRole("button", { name: /continue/i }),
    ).not.toBeDisabled();
    expect(
      screen.queryByText(/can\u2019t provide a cost estimate/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /see your support options/i }),
    ).not.toBeInTheDocument();
  });

  it("does not disable button on support form even with all big kids", () => {
    const supportLabels = ALL_LABELS.filter(
      (l) => l !== "Childcare arrangements",
    );
    renderSummary({
      formData: { children: [bigChild()] },
      completedLabels: supportLabels,
      allLabels: supportLabels,
    });

    expect(
      screen.getByRole("button", { name: /show results/i }),
    ).not.toBeDisabled();
    expect(
      screen.queryByText(/can\u2019t provide a cost estimate/),
    ).not.toBeInTheDocument();
  });

  it("renders NRPF income and savings answers when all parents NRPF", () => {
    renderSummary({
      formData: {
        user: {
          ...BLANK_DATA.user,
          residencyStatus: "no_recourse_to_public_funds",
        },
        children: [
          {
            id: 1,
            firstName: "Test",
            birthMonth: 3,
            birthYear: 2023,
            hasSEND: false,
            sendDetails: null,
            isFostered: false as const,
            hasEHCP: false,
            hasLeftCareForAdoptionOrSpecialGuardianship: false,
            childcareSelections: [],
          },
        ],
        nrpfIncomeUnderThreshold: 26500,
        nrpfSavingsUnderLimit: 16000,
      },
      completedLabels: ["Your children"],
    });

    expect(
      screen.getByText("Household income below £26,500: Yes"),
    ).toBeInTheDocument();
    expect(screen.getByText("Savings below £16,000: Yes")).toBeInTheDocument();
  });

  it("does not render NRPF answers when not all parents NRPF", () => {
    renderSummary({
      formData: {
        user: {
          ...BLANK_DATA.user,
          residencyStatus: "british_irish_citizen",
        },
        children: [
          {
            id: 1,
            firstName: "Test",
            birthMonth: 3,
            birthYear: 2023,
            hasSEND: false,
            sendDetails: null,
            isFostered: false as const,
            hasEHCP: false,
            hasLeftCareForAdoptionOrSpecialGuardianship: false,
            childcareSelections: [],
          },
        ],
        nrpfIncomeUnderThreshold: 26500,
        nrpfSavingsUnderLimit: 16000,
      },
      completedLabels: ["Your children"],
    });

    expect(
      screen.queryByText(/Household income below £/),
    ).not.toBeInTheDocument();
  });
});

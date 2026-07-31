import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MultiStepForm } from "../MultiStepForm";
import type { FormLocalStorageData } from "@/types/formData";
import { BLANK_DATA } from "@/test/renderStep";

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

// --- Mock useFamily ---
const mockCompletedSteps: Record<string, boolean> = {};
const mockMarkStepCompleted = vi.fn();
const mockUpdateFamilyData = vi.fn();

let mockValidateFormData: (
  form: FormLocalStorageData,
  labels: string[],
) => string[] = () => [];

vi.mock("@/types/formData", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/types/formData")>();
  return {
    ...actual,
    validateFormData: (...args: Parameters<typeof actual.validateFormData>) =>
      mockValidateFormData(...args),
  };
});

vi.mock("@/hooks/useFamily", () => ({
  useFamily: () => ({
    completedSteps: mockCompletedSteps,
    markStepCompleted: mockMarkStepCompleted,
    unmarkSteps: vi.fn(),
    updateFamilyData: mockUpdateFamilyData,
    shortlistedProviders: [],
    getProviderById: () => undefined,
  }),
}));

// --- Helpers ---

function makeSteps(count = 3) {
  return Array.from({ length: count }, (_, i) => ({
    number: i + 1,
    label: `Step ${i + 1}`,
    render: vi.fn(({ onContinue, onBack }) => (
      <div>
        <span data-testid={`step-content-${i + 1}`}>Step {i + 1} content</span>
        <button onClick={onContinue}>Continue</button>
        <button onClick={onBack}>Back</button>
      </div>
    )),
  }));
}

const initialData: FormLocalStorageData = { ...BLANK_DATA };

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  Element.prototype.scrollIntoView = vi.fn();
  mockValidateFormData = () => [];
  // Reset completed steps
  for (const key of Object.keys(mockCompletedSteps)) {
    delete mockCompletedSteps[key];
  }
});

describe("MultiStepForm", () => {
  it("renders step 1 when no steps completed", () => {
    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    expect(screen.getByTestId("step-content-1")).toBeInTheDocument();
    expect(screen.queryByTestId("step-content-2")).not.toBeInTheDocument();
  });

  it("calls step render function with correct props", () => {
    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    expect(steps[0].render).toHaveBeenCalledWith(
      expect.objectContaining({
        formData: expect.objectContaining({ schemaVersion: 1 }),
        updateFormData: expect.any(Function),
        onContinue: expect.any(Function),
        onBack: expect.any(Function),
      }),
    );
  });

  it("advances to next step on Continue", async () => {
    const user = userEvent.setup();
    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    await user.click(screen.getByText("Continue"));

    expect(mockMarkStepCompleted).toHaveBeenCalledWith("Step 1");
    expect(screen.getByTestId("step-content-2")).toBeInTheDocument();
  });

  it("calls onComplete after last step Continue", async () => {
    // Pre-complete steps 1 and 2 so we start on step 3
    mockCompletedSteps["Step 1"] = true;
    mockCompletedSteps["Step 2"] = true;

    const user = userEvent.setup();
    const onComplete = vi.fn();
    const steps = makeSteps();

    // Start by editing step 3 from summary
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={onComplete}
        familyId="test"
      />,
    );

    // We're on summary since there are completed steps. Click continue to go to step 3.
    await user.click(screen.getByRole("button", { name: /continue/i }));

    // Now on step 3 — click Continue
    await user.click(screen.getByText("Continue"));
    expect(onComplete).toHaveBeenCalled();
  });

  it("handleBack from step 1 goes to summary if completed steps exist", async () => {
    mockCompletedSteps["Step 1"] = true;

    const user = userEvent.setup();
    const steps = makeSteps();

    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    // We're on summary. Click "Edit" on step 1 to go to step 1.
    await user.click(screen.getByText("Edit"));

    // Now on step 1. Click Back → should go back to summary.
    await user.click(screen.getByText("Back"));

    expect(screen.getByText("Your answers so far")).toBeInTheDocument();
  });

  it("handleBack from step 2+ goes to previous step", async () => {
    const user = userEvent.setup();
    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    // Advance to step 2
    await user.click(screen.getByText("Continue"));
    expect(screen.getByTestId("step-content-2")).toBeInTheDocument();

    // Go back to step 1
    await user.click(screen.getByText("Back"));
    expect(screen.getByTestId("step-content-1")).toBeInTheDocument();
  });

  it("shows summary when returning with completed steps", () => {
    mockCompletedSteps["Step 1"] = true;
    mockCompletedSteps["Step 2"] = true;

    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    expect(screen.getByText("Your answers so far")).toBeInTheDocument();
  });

  it("summary Edit navigates to correct step", async () => {
    mockCompletedSteps["Step 1"] = true;
    mockCompletedSteps["Step 2"] = true;

    const user = userEvent.setup();
    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    // Both completed — should see two Edit buttons
    const editButtons = screen.getAllByText("Edit");
    // Click edit for step 2 (second edit button)
    await user.click(editButtons[1]);

    expect(screen.getByTestId("step-content-2")).toBeInTheDocument();
  });

  it("summary Continue goes to first uncompleted step", async () => {
    mockCompletedSteps["Step 1"] = true;
    // Step 2 not completed

    const user = userEvent.setup();
    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    // On summary — click Continue (should go to step 2 which is uncompleted)
    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(screen.getByTestId("step-content-2")).toBeInTheDocument();
  });

  it("summary Show results calls onComplete when all done", async () => {
    mockCompletedSteps["Step 1"] = true;
    mockCompletedSteps["Step 2"] = true;
    mockCompletedSteps["Step 3"] = true;

    const user = userEvent.setup();
    const onComplete = vi.fn();
    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={onComplete}
        familyId="test"
      />,
    );

    await user.click(screen.getByRole("button", { name: /show results/i }));
    expect(onComplete).toHaveBeenCalled();
  });

  it("skips completed steps when continuing", async () => {
    mockCompletedSteps["Step 2"] = true;

    const user = userEvent.setup();
    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    // Summary → go to first uncompleted (step 1)
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(screen.getByTestId("step-content-1")).toBeInTheDocument();

    // Continue from step 1 → should skip step 2 (already completed) → go to step 3
    await user.click(screen.getByText("Continue"));
    expect(screen.getByTestId("step-content-3")).toBeInTheDocument();
  });

  it("summary hides never-started steps (absent from completedSteps)", () => {
    // Step 1: completed, Steps 2-3: never started (keys absent)
    mockCompletedSteps["Step 1"] = true;
    mockValidateFormData = () => ["Step 2", "Step 3"];

    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    // Should be on summary view since Step 1 is completed
    expect(screen.getByText("Your answers so far")).toBeInTheDocument();

    // Step 1 (completed) should appear
    expect(screen.getByText("Step 1")).toBeInTheDocument();

    // Steps 2-3 (never started, keys absent) should NOT appear
    expect(screen.queryByText("Step 2")).not.toBeInTheDocument();
    expect(screen.queryByText("Step 3")).not.toBeInTheDocument();
  });

  it("summary shows invalidated completed steps with 'Needs updating'", () => {
    // All three steps previously completed, but Step 3 data is now invalid
    mockCompletedSteps["Step 1"] = true;
    mockCompletedSteps["Step 2"] = true;
    mockCompletedSteps["Step 3"] = false;
    mockValidateFormData = () => ["Step 3"];

    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    expect(screen.getByText("Your answers so far")).toBeInTheDocument();

    // Steps 1-2 should appear as completed
    expect(screen.getByText("Step 1")).toBeInTheDocument();
    expect(screen.getByText("Step 2")).toBeInTheDocument();

    // Step 3 should appear with "Needs updating" treatment
    expect(screen.getByText("Step 3")).toBeInTheDocument();
    expect(screen.getByText(/needs updating/i)).toBeInTheDocument();
  });

  it("syncs form data to context on step Continue", async () => {
    const user = userEvent.setup();
    const steps = makeSteps();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
      />,
    );

    await user.click(screen.getByText("Continue"));
    expect(mockUpdateFamilyData).toHaveBeenCalledWith(
      expect.objectContaining({ schemaVersion: 1 }),
    );
  });

  it("calls onStepCompleted with label and formData on step Continue", async () => {
    const user = userEvent.setup();
    const steps = makeSteps();
    const onStepCompleted = vi.fn();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
        onStepCompleted={onStepCompleted}
      />,
    );

    await user.click(screen.getByText("Continue"));

    expect(onStepCompleted).toHaveBeenCalledOnce();
    expect(onStepCompleted).toHaveBeenCalledWith(
      "Step 1",
      expect.objectContaining({ schemaVersion: 1 }),
    );
  });

  it("does not call onStepCompleted from summary Continue", async () => {
    mockCompletedSteps["Step 1"] = true;

    const user = userEvent.setup();
    const steps = makeSteps();
    const onStepCompleted = vi.fn();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
        onStepCompleted={onStepCompleted}
      />,
    );

    // On summary — click Continue (navigates to step 2, does not complete a step)
    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onStepCompleted).not.toHaveBeenCalled();
  });

  it("does not call onStepCompleted from summary Show Results", async () => {
    mockCompletedSteps["Step 1"] = true;
    mockCompletedSteps["Step 2"] = true;
    mockCompletedSteps["Step 3"] = true;

    const user = userEvent.setup();
    const steps = makeSteps();
    const onStepCompleted = vi.fn();
    render(
      <MultiStepForm
        steps={steps}
        initialData={initialData}
        onComplete={vi.fn()}
        familyId="test"
        onStepCompleted={onStepCompleted}
      />,
    );

    await user.click(screen.getByRole("button", { name: /show results/i }));

    expect(onStepCompleted).not.toHaveBeenCalled();
  });
});

import { useState, useEffect, useMemo, useRef, type ReactNode } from "react";
import { validateFormData, type FormLocalStorageData } from "@/types/formData";
import { useFamily } from "@/hooks/useFamily";
import { FormLayout } from "./FormLayout";
import { SummaryStep } from "./SummaryStep";

export interface StepRenderProps {
  formData: FormLocalStorageData;
  updateFormData: (patch: Partial<FormLocalStorageData>) => void;
  onContinue: () => void;
  onBack: () => void;
}

interface StepDef {
  number: number;
  label: string;
  render: (props: StepRenderProps) => ReactNode;
}

interface MultiStepFormProps {
  steps: StepDef[];
  initialData: FormLocalStorageData;
  onComplete: (formData: FormLocalStorageData) => void;
  familyId: string;
  onReset?: () => void;
  onStepCompleted?: (stepLabel: string, formData: FormLocalStorageData) => void;
}

// Sentinel value: 0 = showing the summary screen
const SUMMARY_VIEW = 0;

export function MultiStepForm({
  steps,
  initialData,
  onComplete,
  familyId,
  onReset,
  onStepCompleted,
}: MultiStepFormProps) {
  const { completedSteps, markStepCompleted, unmarkSteps, updateFamilyData } =
    useFamily();
  const [formData, setFormData] = useState<FormLocalStorageData>(initialData);
  const formDataRef = useRef(formData);
  const formRef = useRef<HTMLDivElement>(null);
  const selfUpdateRef = useRef(false);

  const scrollToForm = () => {
    const hero = document.getElementById("page-hero");
    if (hero) {
      const heroBottom = hero.getBoundingClientRect().bottom + window.scrollY;
      const stickyHeader = document.getElementById("sticky-header");
      const offset = stickyHeader?.offsetHeight ?? 0;
      window.scrollTo({ top: heroBottom - offset, behavior: "smooth" });
    } else {
      formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const allLabels = useMemo(() => steps.map((s) => s.label), [steps]);
  const completedLabels = useMemo(
    () => allLabels.filter((l) => completedSteps[l]),
    [allLabels, completedSteps],
  );
  const hasAnyCompleted = completedLabels.length > 0;

  // Start on summary if there are completed steps, otherwise step 1
  const [currentStep, setCurrentStep] = useState(() =>
    hasAnyCompleted ? SUMMARY_VIEW : 1,
  );

  // Reset when family changes (external source), but skip when we triggered the change ourselves
  useEffect(() => {
    if (selfUpdateRef.current) {
      selfUpdateRef.current = false;
      return;
    }
    setFormData(initialData);
    // completedSteps is already reset by the context — recalculate starting view
    setCurrentStep(SUMMARY_VIEW); // will immediately flip to 1 below if nothing completed
  }, [familyId, initialData]);

  // If we're on the summary but nothing is completed, go straight to step 1
  useEffect(() => {
    if (currentStep === SUMMARY_VIEW && completedLabels.length === 0) {
      setCurrentStep(1);
    }
  }, [currentStep, completedLabels.length]);

  const updateFormData = (patch: Partial<FormLocalStorageData>) => {
    const next = { ...formDataRef.current, ...patch };
    formDataRef.current = next;
    setFormData(next);
  };

  /** Find the first step whose label is not yet in completedSteps, or null if all done. */
  const firstUncompletedStep = useMemo(() => {
    for (const s of steps) {
      if (!completedSteps[s.label]) return s.number;
    }
    return null;
  }, [steps, completedSteps]);

  const handleContinue = () => {
    const step = steps.find((s) => s.number === currentStep);
    if (step) {
      markStepCompleted(step.label);
      onStepCompleted?.(step.label, formDataRef.current);
    }

    // Sync form data to context so other pages see the latest answers
    selfUpdateRef.current = true;
    updateFamilyData(formDataRef.current);

    // Validate all steps and unmark any that are now invalid
    const invalid = validateFormData(formDataRef.current, allLabels);
    if (invalid.length > 0) {
      unmarkSteps(invalid);
    }

    // Build a fresh "effective completed" set (current step + already completed − invalid)
    const completedSet = new Set(
      allLabels.filter((l) => completedSteps[l] || l === step?.label),
    );
    for (const l of invalid) completedSet.delete(l);

    // Find next uncompleted step after the current one
    const remaining = steps.filter(
      (s) => s.number > currentStep && !completedSet.has(s.label),
    );

    if (remaining.length > 0) {
      setCurrentStep(remaining[0].number);
    } else {
      // No uncompleted steps after current — check if any invalid steps exist at all
      const anyIncomplete = steps.some((s) => !completedSet.has(s.label));
      if (anyIncomplete) {
        setCurrentStep(SUMMARY_VIEW);
      } else {
        onComplete(formDataRef.current);
        return;
      }
    }

    scrollToForm();
  };

  const handleBack = () => {
    if (currentStep <= 1) {
      // Go back to summary if there were previously completed steps
      if (hasAnyCompleted) {
        setCurrentStep(SUMMARY_VIEW);
        scrollToForm();
      }
      return;
    }
    setCurrentStep((s) => s - 1);
    scrollToForm();
  };

  const handleSummaryContinue = () => {
    if (firstUncompletedStep !== null) {
      setCurrentStep(firstUncompletedStep);
    } else {
      // All steps marked completed — validate data before submitting
      const invalidLabels = validateFormData(formDataRef.current, allLabels);
      if (invalidLabels.length > 0) {
        unmarkSteps(invalidLabels);
        const firstInvalid = steps.find((s) => invalidLabels.includes(s.label));
        if (firstInvalid) {
          setCurrentStep(firstInvalid.number);
        }
        scrollToForm();
        return;
      }
      onComplete(formDataRef.current);
      return;
    }
    scrollToForm();
  };

  const handleSummaryEdit = (stepNumber: number) => {
    setCurrentStep(stepNumber);
    scrollToForm();
  };

  const invalidLabels = useMemo(
    () =>
      validateFormData(formData, allLabels).filter(
        (l) => completedSteps[l] === false,
      ),
    [formData, allLabels, completedSteps],
  );

  // --- Render ---

  if (currentStep === SUMMARY_VIEW) {
    return (
      <div
        ref={formRef}
        className="space-y-6 scroll-mt-16 max-w-[576px] mx-auto"
      >
        <SummaryStep
          formData={formData}
          completedLabels={completedLabels}
          invalidLabels={invalidLabels}
          allLabels={allLabels}
          onEdit={handleSummaryEdit}
          onContinue={handleSummaryContinue}
          onReset={onReset}
        />
      </div>
    );
  }

  const step = steps.find((s) => s.number === currentStep);
  if (!step) return null;

  // eslint-disable-next-line react-hooks/refs -- step.render() returns JSX; event handlers are not called during render
  const stepContent = step.render({
    formData,
    updateFormData,
    onContinue: handleContinue,
    onBack: handleBack,
  });

  return (
    <div ref={formRef} className="space-y-6 scroll-mt-16">
      <FormLayout
        steps={steps.map((s) => ({ number: s.number, label: s.label }))}
        currentStep={currentStep}
      >
        {stepContent}
      </FormLayout>
    </div>
  );
}

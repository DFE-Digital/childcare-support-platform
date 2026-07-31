import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useFamily } from "@/hooks/useFamily";
import { useFormAnalytics } from "@/hooks/useFormAnalytics";
import { usePostcodeLookup } from "@/hooks/usePostcodeLookup";
import { PageHero } from "@/components/layout/PageHero";
import { Container } from "@/components/layout/Container";
import { BetaBanner } from "@/components/ui/BetaBanner";
import {
  MultiStepForm,
  type StepRenderProps,
} from "@/components/form/MultiStepForm";
import { PostcodeStep } from "@/components/form/steps/PostcodeStep";
import { PartnerStep } from "@/components/form/steps/PartnerStep";
import { ImmigrationStep } from "@/components/form/steps/ImmigrationStep";
import { WorkingStep } from "@/components/form/steps/WorkingStep";
import { UniversalCreditStep } from "@/components/form/steps/UniversalCreditStep";
import { ChildrenStep } from "@/components/form/steps/ChildrenStep";
import type { FormLocalStorageData } from "@/types/formData";

const steps = [
  {
    number: 1,
    label: "Where you live",
    render: (props: StepRenderProps) => (
      <PostcodeStep {...props} showSchemesLink />
    ),
  },
  {
    number: 2,
    label: "Living situation",
    render: (props: StepRenderProps) => <PartnerStep {...props} />,
  },
  {
    number: 3,
    label: "Immigration status",
    render: (props: StepRenderProps) => <ImmigrationStep {...props} />,
  },
  {
    number: 4,
    label: "Working situation",
    render: (props: StepRenderProps) => <WorkingStep {...props} />,
  },
  {
    number: 5,
    label: "Benefits",
    render: (props: StepRenderProps) => <UniversalCreditStep {...props} />,
  },
  {
    number: 6,
    label: "Your children",
    render: (props: StepRenderProps) => <ChildrenStep {...props} />,
  },
];

const STEP_MAP: Record<string, string> = {
  "Where you live": "postcode",
  "Living situation": "partner",
  "Immigration status": "immigration",
  "Working situation": "working",
  Benefits: "benefits",
  "Your children": "children",
};

export default function SupportFormPage() {
  const { selectedFamily, loading, updateFamilyData, resetSteps } = useFamily();
  const navigate = useNavigate();
  const { captureStep, setIodDecile } = useFormAnalytics("support");
  const { getGeo, ensureInward } = usePostcodeLookup();

  const handleStepCompleted = useCallback(
    async (label: string, formData: FormLocalStorageData) => {
      if (
        label === "Where you live" &&
        formData.location.postcode.includes(" ")
      ) {
        const [outward, inward] = formData.location.postcode.split(" ");
        await ensureInward(outward);
        const geo = getGeo(outward, inward);
        setIodDecile(geo?.deprivationDecile);
      }
      const step = STEP_MAP[label];
      if (step) captureStep(step, formData);
    },
    [ensureInward, getGeo, setIodDecile, captureStep],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" role="status">
        <div
          className="animate-spin w-8 h-8 border-4 border-neutral-700 border-t-transparent rounded-full"
          aria-hidden="true"
        />
        <span className="sr-only">Loading</span>
      </div>
    );
  }

  return (
    <>
      <div className="flex flex-col">
        <div className="order-2 py-4 px-5 md:px-7">
          <div className="mx-auto" style={{ maxWidth: 960 }}>
            <BetaBanner />
          </div>
        </div>
        <PageHero
          title="What support am I entitled to?"
          subtitle="Answer a few questions and we'll show you which government schemes your family may be eligible for."
          breadcrumbs={[{ label: "Get Support" }]}
          date="Last updated: May 2026"
        />
      </div>
      <Container className="py-10">
        <MultiStepForm
          steps={steps}
          initialData={selectedFamily.localStorage}
          familyId="default"
          onStepCompleted={handleStepCompleted}
          onComplete={(formData) => {
            updateFamilyData(formData);
            navigate("/support/results#main-content");
          }}
          onReset={resetSteps}
        />
      </Container>
    </>
  );
}

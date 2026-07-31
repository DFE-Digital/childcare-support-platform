import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import type { FormLocalStorageData } from "@/types/formData";

const BLANK_PERSON = {
  isApprentice: null as boolean | null,
  firstYearApprentice: null as boolean | null,
  isSelfEmployed: null as boolean | null,
  selfEmployedLessThanTwelveMonths: null as boolean | null,
  ageBracket: null as FormLocalStorageData["user"]["ageBracket"],
  workingStatus: null as FormLocalStorageData["user"]["workingStatus"],
  receivesQualifyingAllowance: null as boolean | null,
  startingWorkNextMonth: null as boolean | null,
  hasLimitedCapacityForWork: null as boolean | null,
  hasNationalInsuranceNumber: null as boolean | null,
  residencyStatus: null as FormLocalStorageData["user"]["residencyStatus"],
  isStudying: null as boolean | null,
  studyLevel: null as FormLocalStorageData["user"]["studyLevel"],
  isFullTimeStudent: null as boolean | null,
  courseIsPubliclyFunded: null as boolean | null,
  eligibleForStudentFinance: null as boolean | null,
};

export const BLANK_DATA: FormLocalStorageData = {
  schemaVersion: 1,
  location: { postcode: "", ladCodes: [] },
  household: { hasPartner: null },
  user: { ...BLANK_PERSON },
  partner: null,
  ucIncomeBelowThreshold: null,
  nrpfIncomeUnderThreshold: null,
  nrpfSavingsUnderLimit: null,
  qualifyingBenefits: null,
  children: [],
  shortlistedProviders: [],
};

interface StepRenderProps {
  formData: FormLocalStorageData;
  updateFormData: (patch: Partial<FormLocalStorageData>) => void;
  onContinue: () => void;
  onBack: () => void;
}

export function renderStep(
  Component: React.ComponentType<StepRenderProps>,
  overrides?: { formData?: Partial<FormLocalStorageData> },
) {
  const formData: FormLocalStorageData = {
    ...BLANK_DATA,
    ...overrides?.formData,
    // deep-merge nested objects that callers commonly override
    location: { ...BLANK_DATA.location, ...overrides?.formData?.location },
    household: { ...BLANK_DATA.household, ...overrides?.formData?.household },
    user: { ...BLANK_DATA.user, ...overrides?.formData?.user },
  };
  const updateFormData = vi.fn();
  const onContinue = vi.fn();
  const onBack = vi.fn();
  const user = userEvent.setup();

  const result = render(
    <Component
      formData={formData}
      updateFormData={updateFormData}
      onContinue={onContinue}
      onBack={onBack}
    />,
  );

  return { ...result, user, formData, updateFormData, onContinue, onBack };
}

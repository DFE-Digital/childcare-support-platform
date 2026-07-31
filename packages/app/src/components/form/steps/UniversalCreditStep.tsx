import { useState } from "react";
import type { FormLocalStorageData } from "@/types/formData";
import { FormStep } from "@/components/ui/FormStep";
import { CheckboxGroup } from "@/components/ui/CheckboxGroup";
import { RadioGroup } from "@/components/ui/RadioGroup";
import { ValidationWrapper } from "@/components/ui/ValidationWrapper";
import { Explainer } from "@/components/ui/Explainer";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { scrollToFirstError } from "@/lib/scrollToFirstError";

const QUALIFYING_BENEFITS = [
  { value: "universal_credit", label: "Universal Credit" },
  {
    value: "pension_credit",
    label: "The guaranteed element of Pension Credit",
  },
  {
    value: "esa",
    label: "Income-related Employment and Support Allowance (ESA)",
  },
  { value: "none", label: "None of the above" },
];

interface Props {
  formData: FormLocalStorageData;
  updateFormData: (patch: Partial<FormLocalStorageData>) => void;
  onContinue: () => void;
  onBack: () => void;
}

function isNotWorking(
  workingStatus: FormLocalStorageData["user"]["workingStatus"],
): boolean {
  return workingStatus === "not_working";
}

function isWorking(
  workingStatus: FormLocalStorageData["user"]["workingStatus"],
): boolean {
  return workingStatus !== null && !isNotWorking(workingStatus);
}

export function UniversalCreditStep({
  formData,
  updateFormData,
  onContinue,
  onBack,
}: Props) {
  const hasPartner = formData.household.hasPartner;
  const hasUC =
    formData.qualifyingBenefits?.includes("universal_credit") ?? false;
  const [error, setError] = useState(false);
  const [nrpfBenefitsError, setNrpfBenefitsError] = useState(false);
  const [userStartingError, setUserStartingError] = useState(false);
  const [partnerStartingError, setPartnerStartingError] = useState(false);
  const [userLcwError, setUserLcwError] = useState(false);
  const [partnerLcwError, setPartnerLcwError] = useState(false);

  const allNRPF =
    formData.user.residencyStatus === "no_recourse_to_public_funds" &&
    (!formData.partner ||
      formData.partner.residencyStatus === "no_recourse_to_public_funds");

  const userNotWorking =
    isNotWorking(formData.user.workingStatus) &&
    formData.user.receivesQualifyingAllowance !== true;
  const partnerNotWorking =
    hasPartner &&
    formData.partner !== null &&
    isNotWorking(formData.partner.workingStatus) &&
    formData.partner.receivesQualifyingAllowance !== true;

  // LCW question: couples only, when one parent is not working (answered "No"
  // to starting work) and the other parent IS working or starting soon.
  const showUserLcw =
    hasUC &&
    userNotWorking &&
    formData.user.startingWorkNextMonth === false &&
    hasPartner &&
    formData.partner !== null &&
    (isWorking(formData.partner.workingStatus) ||
      formData.partner.startingWorkNextMonth === true);

  const showPartnerLcw =
    hasUC &&
    partnerNotWorking &&
    formData.partner?.startingWorkNextMonth === false &&
    (isWorking(formData.user.workingStatus) ||
      formData.user.startingWorkNextMonth === true);

  const handleContinue = () => {
    let hasError = false;

    if (formData.qualifyingBenefits === null) {
      setError(true);
      hasError = true;
    }

    if (
      allNRPF &&
      formData.qualifyingBenefits !== null &&
      formData.qualifyingBenefits.length > 0 &&
      !formData.qualifyingBenefits.every((b) => b === "none")
    ) {
      setNrpfBenefitsError(true);
      hasError = true;
    }

    if (
      hasUC &&
      userNotWorking &&
      formData.user.startingWorkNextMonth === null
    ) {
      setUserStartingError(true);
      hasError = true;
    }

    if (
      hasUC &&
      partnerNotWorking &&
      formData.partner?.startingWorkNextMonth === null
    ) {
      setPartnerStartingError(true);
      hasError = true;
    }

    if (showUserLcw && formData.user.hasLimitedCapacityForWork === null) {
      setUserLcwError(true);
      hasError = true;
    }

    if (
      showPartnerLcw &&
      formData.partner?.hasLimitedCapacityForWork === null
    ) {
      setPartnerLcwError(true);
      hasError = true;
    }

    if (hasError) {
      scrollToFirstError();
      return;
    }
    onContinue();
  };

  return (
    <>
      <FormStep
        title="Benefits"
        onContinue={handleContinue}
        onBack={onBack}
        footer={
          <div className="space-y-3">
            <Explainer label="How do benefits affect my childcare support?">
              <p>
                The benefits you receive affect which childcare support schemes
                are available to you.
              </p>
              <p className="font-bold">Early Learning for 2-year-olds</p>
              <p>
                If you receive income-related ESA, or Pension Credit, your
                2-year-old may qualify for{" "}
                <strong>
                  15 funded hours per week over 38 weeks of the year.
                </strong>{" "}
                Families on Universal Credit may also qualify if household
                income is £15,400 or less after tax.
              </p>
              <p className="font-bold">Universal Credit childcare</p>
              <p>
                If you are on Universal Credit and in paid work, you can claim
                back up to <strong>85% of your childcare costs</strong>, up to:
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>£1,071.09 per month for one child </li>
                <li>£1,836.16 per month for two or more children</li>
              </ul>
              <p className="font-bold">
                Tax-Free Childcare is not available with Universal Credit
              </p>
              <p>
                Universal Credit and Tax-Free Childcare{" "}
                <strong>cannot be used together</strong>. If you receive
                Universal Credit, Tax-Free Childcare will not be included in
                your results.
              </p>
              <div className="pt-2 space-y-1">
                <p>
                  <ExternalLink
                    href="https://beststartinlife.gov.uk/childcare-early-years-education/universal-credit-childcare/eligibility-for-universal-credit-childcare/"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    Universal Credit childcare eligibility on Best Start in Life
                  </ExternalLink>
                </p>
                <p>
                  <ExternalLink
                    href="https://beststartinlife.gov.uk/childcare-early-years-education/combining-schemes/"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    Which schemes can be combined
                  </ExternalLink>
                </p>
              </div>
            </Explainer>
            {hasUC && (userNotWorking || partnerNotWorking) && (
              <Explainer label="Why does starting work matter?">
                <p>
                  Universal Credit childcare normally requires you to be in paid
                  work. However, there is an exception: if you have a{" "}
                  <strong>confirmed job starting within the next month</strong>,
                  you can still qualify.
                </p>
                <p>
                  This means you can arrange childcare before your start date,
                  rather than waiting until you&apos;ve started.
                </p>
                <p className="font-bold">
                  What counts as &ldquo;starting work&rdquo;?
                </p>
                <p>
                  You should have a confirmed offer with a start date in the
                  next month. Simply looking for work or applying for jobs does
                  not count.
                </p>
                <p>
                  If you answer &ldquo;Yes&rdquo;, we&apos;ll include Universal
                  Credit Childcare in your results so you can see what support
                  would be available once you start.
                </p>
                {hasPartner && (
                  <p>
                    If your partner is working and you are not, answering
                    &ldquo;No&rdquo; does not necessarily rule out Universal
                    Credit Childcare &mdash; we&apos;ll also check whether you
                    have limited capacity for work, which can waive the work
                    requirement.
                  </p>
                )}
              </Explainer>
            )}
            {(showUserLcw || showPartnerLcw) && (
              <Explainer label="What is limited capacity for work?">
                <p>
                  <strong>Limited capability for work (LCW)</strong> and{" "}
                  <strong>
                    limited capability for work-related activity (LCWRA)
                  </strong>{" "}
                  are official assessments by the Department for Work and
                  Pensions.
                </p>
                <p>
                  If you have a health condition or disability that limits what
                  work you can do, you may have been assessed as having LCW or
                  LCWRA as part of your Universal Credit claim.
                </p>
                <p className="font-bold">How would I know?</p>
                <p>
                  You would know if this applies to you &mdash; it is recorded
                  in your Universal Credit journal and affects the amount of
                  Universal Credit you receive. LCWRA adds an extra amount to
                  your payment. If you&apos;re unsure, check your Universal
                  Credit journal or speak to your work coach.
                </p>
                <p className="font-bold">Why it matters for childcare</p>
                <p>
                  Normally, Universal Credit childcare requires the parent (and
                  partner if you live with one) to be working. But if you or
                  your partner has LCW or LCWRA, the{" "}
                  <strong>work requirement is waived</strong> for that person.
                  This means a couple where one parent works and the other has
                  LCW or LCWRA can still claim Universal Credit childcare.
                </p>
              </Explainer>
            )}
          </div>
        }
      >
        <ValidationWrapper
          error={error || nrpfBenefitsError}
          message={
            nrpfBenefitsError
              ? "Families where no parent has access to public funds, aren\u2019t eligible for these benefits. Please select \u2018None of the above\u2019, or go back and update your immigration status."
              : "Please answer this question to continue"
          }
        >
          {({ errorId, invalid }) => (
            <CheckboxGroup
              name="qualifying-benefits"
              label={
                hasPartner
                  ? "Do you or your partner get any of the following?"
                  : "Do you get any of the following?"
              }
              options={QUALIFYING_BENEFITS}
              value={formData.qualifyingBenefits ?? []}
              aria-describedby={errorId}
              aria-invalid={invalid}
              onChange={(selected) => {
                setError(false);
                setNrpfBenefitsError(false);
                setUserStartingError(false);
                setPartnerStartingError(false);
                setUserLcwError(false);
                setPartnerLcwError(false);
                // Mutual exclusivity: "none" vs everything else
                const hadNone = (formData.qualifyingBenefits ?? []).includes(
                  "none",
                );
                let next: string[];
                if (!hadNone && selected.includes("none")) {
                  next = ["none"];
                } else {
                  next = selected.filter((v) => v !== "none");
                }
                const nextHasUC = next.includes("universal_credit");
                updateFormData({
                  qualifyingBenefits: next,
                  // Reset UC follow-ups when UC is toggled off
                  ...(!nextHasUC && hasUC
                    ? {
                        ucIncomeBelowThreshold: null,
                        user: {
                          ...formData.user,
                          startingWorkNextMonth: null,
                          hasLimitedCapacityForWork: null,
                        },
                        ...(formData.partner
                          ? {
                              partner: {
                                ...formData.partner,
                                startingWorkNextMonth: null,
                                hasLimitedCapacityForWork: null,
                              },
                            }
                          : {}),
                      }
                    : {}),
                });
              }}
            />
          )}
        </ValidationWrapper>

        {hasUC && userNotWorking && (
          <div className="ml-6 border-l-2 border-zinc-200 pl-5">
            <ValidationWrapper
              error={userStartingError}
              message="Please answer this question to continue"
            >
              {({ errorId, invalid }) => (
                <RadioGroup
                  name="user-starting-work"
                  label="Will you be starting a job in the next month?"
                  options={[
                    { value: "yes", label: "Yes" },
                    { value: "no", label: "No" },
                  ]}
                  value={
                    formData.user.startingWorkNextMonth === null
                      ? ""
                      : formData.user.startingWorkNextMonth
                        ? "yes"
                        : "no"
                  }
                  aria-describedby={errorId}
                  aria-invalid={invalid}
                  onChange={(v) => {
                    setUserStartingError(false);
                    setUserLcwError(false);
                    updateFormData({
                      user: {
                        ...formData.user,
                        startingWorkNextMonth: v === "yes",
                        hasLimitedCapacityForWork: null,
                      },
                    });
                  }}
                />
              )}
            </ValidationWrapper>
          </div>
        )}

        {hasUC && partnerNotWorking && (
          <div className="ml-6 border-l-2 border-zinc-200 pl-5">
            <ValidationWrapper
              error={partnerStartingError}
              message="Please answer this question to continue"
            >
              {({ errorId, invalid }) => (
                <RadioGroup
                  name="partner-starting-work"
                  label="Will your partner be starting a job in the next month?"
                  options={[
                    { value: "yes", label: "Yes" },
                    { value: "no", label: "No" },
                  ]}
                  value={
                    formData.partner?.startingWorkNextMonth === null
                      ? ""
                      : formData.partner?.startingWorkNextMonth
                        ? "yes"
                        : "no"
                  }
                  aria-describedby={errorId}
                  aria-invalid={invalid}
                  onChange={(v) => {
                    setPartnerStartingError(false);
                    setPartnerLcwError(false);
                    if (formData.partner) {
                      updateFormData({
                        partner: {
                          ...formData.partner,
                          startingWorkNextMonth: v === "yes",
                          hasLimitedCapacityForWork: null,
                        },
                      });
                    }
                  }}
                />
              )}
            </ValidationWrapper>
          </div>
        )}

        {showUserLcw && (
          <div className="ml-6 border-l-2 border-zinc-200 pl-5">
            <ValidationWrapper
              error={userLcwError}
              message="Please answer this question to continue"
            >
              {({ errorId, invalid }) => (
                <RadioGroup
                  name="user-lcw"
                  label="Do you have a disability which results in a limited capacity for work (LCW / LCWRA)?"
                  options={[
                    { value: "yes", label: "Yes" },
                    { value: "no", label: "No" },
                  ]}
                  value={
                    formData.user.hasLimitedCapacityForWork === null
                      ? ""
                      : formData.user.hasLimitedCapacityForWork
                        ? "yes"
                        : "no"
                  }
                  aria-describedby={errorId}
                  aria-invalid={invalid}
                  onChange={(v) => {
                    setUserLcwError(false);
                    updateFormData({
                      user: {
                        ...formData.user,
                        hasLimitedCapacityForWork: v === "yes",
                      },
                    });
                  }}
                />
              )}
            </ValidationWrapper>
          </div>
        )}

        {showPartnerLcw && (
          <div className="ml-6 border-l-2 border-zinc-200 pl-5">
            <ValidationWrapper
              error={partnerLcwError}
              message="Please answer this question to continue"
            >
              {({ errorId, invalid }) => (
                <RadioGroup
                  name="partner-lcw"
                  label="Does your partner have a disability which results in a limited capacity for work (LCW / LCWRA)?"
                  options={[
                    { value: "yes", label: "Yes" },
                    { value: "no", label: "No" },
                  ]}
                  value={
                    formData.partner?.hasLimitedCapacityForWork === null
                      ? ""
                      : formData.partner?.hasLimitedCapacityForWork
                        ? "yes"
                        : "no"
                  }
                  aria-describedby={errorId}
                  aria-invalid={invalid}
                  onChange={(v) => {
                    setPartnerLcwError(false);
                    if (formData.partner) {
                      updateFormData({
                        partner: {
                          ...formData.partner,
                          hasLimitedCapacityForWork: v === "yes",
                        },
                      });
                    }
                  }}
                />
              )}
            </ValidationWrapper>
          </div>
        )}
      </FormStep>
    </>
  );
}

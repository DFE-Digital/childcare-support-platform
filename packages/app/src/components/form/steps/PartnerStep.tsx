import { useState } from "react";
import type { FormLocalStorageData } from "@/types/formData";
import { FormStep } from "@/components/ui/FormStep";
import { RadioGroup } from "@/components/ui/RadioGroup";
import { ValidationWrapper } from "@/components/ui/ValidationWrapper";
import { Explainer } from "@/components/ui/Explainer";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { scrollToFirstError } from "@/lib/scrollToFirstError";

interface Props {
  formData: FormLocalStorageData;
  updateFormData: (patch: Partial<FormLocalStorageData>) => void;
  onContinue: () => void;
  onBack: () => void;
}

export function PartnerStep({
  formData,
  updateFormData,
  onContinue,
  onBack,
}: Props) {
  const [error, setError] = useState(false);

  const handleContinue = () => {
    if (formData.household.hasPartner === null) {
      setError(true);
      scrollToFirstError();
      return;
    }
    onContinue();
  };

  return (
    <>
      <FormStep
        title="Do you live with a partner?"
        onContinue={handleContinue}
        onBack={onBack}
        footer={
          <>
            <Explainer
              label="Why does my living situation matter?"
              modalTitle="Why your living situation matters"
            >
              <p>
                Some childcare schemes require you and your partner (if you live
                with one) to meet work and income criteria. For example:
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>
                  <strong>30 Hours Childcare</strong> and{" "}
                  <strong>Tax-Free Childcare</strong> both require you and your
                  partner (if you live with one) to be working and earning above
                  a minimum threshold.
                </li>
                <li>
                  <strong>Universal Credit childcare</strong> requires you and
                  your partner (if you live with one) to be in paid work, unless
                  your partner has a particular health condition or caring
                  responsibilities.
                </li>
              </ul>
              <p className="pt-2">
                <ExternalLink
                  href="https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/"
                  className="text-purple-700 underline hover:text-purple-900"
                >
                  30 Hours eligibility on Best Start in Life
                </ExternalLink>
              </p>
            </Explainer>
            <Explainer label="What if my partner is away or overseas?">
              <p>
                If your partner normally lives with you but is temporarily away,
                they still count as living with you for childcare scheme
                purposes. This includes partners who work away, such as Crown
                servants, members of the armed forces, mariners, and workers on
                offshore installations.
              </p>
              <p>
                In these cases, you should answer{" "}
                <strong>&ldquo;Yes&rdquo;</strong> to the question &ldquo;Do you
                live with a partner?&rdquo;. Your partner&apos;s work and income
                will still be assessed as part of your household when
                determining eligibility for schemes like 30 Hours Childcare and
                Tax-Free Childcare.
              </p>
              <div className="pt-2 space-y-1">
                <p>
                  <ExternalLink
                    href="https://www.gov.uk/30-hours-free-childcare"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    30 Hours Childcare on GOV.UK
                  </ExternalLink>
                </p>
                <p>
                  <ExternalLink
                    href="https://www.gov.uk/tax-free-childcare"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    Tax-Free Childcare on GOV.UK
                  </ExternalLink>
                </p>
              </div>
            </Explainer>
          </>
        }
      >
        <ValidationWrapper
          error={error}
          message="Please answer this question to continue"
        >
          {({ errorId, invalid }) => (
            <RadioGroup
              name="hasPartner"
              options={[
                { value: "yes", label: "Yes" },
                { value: "no", label: "No" },
              ]}
              value={
                formData.household.hasPartner === true
                  ? "yes"
                  : formData.household.hasPartner === false
                    ? "no"
                    : ""
              }
              onChange={(v) => {
                setError(false);
                updateFormData({
                  household: { hasPartner: v === "yes" },
                  partner:
                    v === "yes"
                      ? formData.partner || {
                          isApprentice: null,
                          firstYearApprentice: null,
                          isSelfEmployed: null,
                          selfEmployedLessThanTwelveMonths: null,
                          ageBracket: null,
                          workingStatus: null,
                          receivesQualifyingAllowance: null,
                          startingWorkNextMonth: null,
                          hasLimitedCapacityForWork: null,
                          hasNationalInsuranceNumber: null,
                          residencyStatus: null,
                          isStudying: null,
                          studyLevel: null,
                          isFullTimeStudent: null,
                          courseIsPubliclyFunded: null,
                          eligibleForStudentFinance: null,
                        }
                      : null,
                });
              }}
              aria-describedby={errorId}
              aria-invalid={invalid}
            />
          )}
        </ValidationWrapper>
      </FormStep>
    </>
  );
}

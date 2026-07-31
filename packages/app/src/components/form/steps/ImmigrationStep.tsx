import { useState } from "react";
import type { FormLocalStorageData, FormPersonData } from "@/types/formData";
import type { ResidencyStatus } from "@/types/family";
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

interface PersonErrors {
  residency?: boolean;
  niNumber?: boolean;
}

function validatePerson(person: FormPersonData): PersonErrors {
  const errors: PersonErrors = {};
  if (person.residencyStatus === null) errors.residency = true;
  if (person.hasNationalInsuranceNumber === null) errors.niNumber = true;
  return errors;
}

function PersonImmigrationSection({
  label,
  person,
  onChange,
  errors,
  isPartner,
}: {
  label: string;
  person: FormPersonData;
  onChange: (updated: FormPersonData) => void;
  errors?: PersonErrors;
  isPartner: boolean;
}) {
  return (
    <div className="space-y-5 bg-white rounded-xl p-6 border border-zinc-200">
      <h3 className="font-bold text-xl">{label}</h3>

      <ValidationWrapper
        error={errors?.residency && person.residencyStatus === null}
        message="Please answer this question to continue"
      >
        {({ errorId, invalid }) => (
          <RadioGroup
            name={`${label}-british-irish`}
            label={
              isPartner
                ? "Is your partner a British or Irish citizen?"
                : "Are you a British or Irish citizen?"
            }
            options={[
              { value: "yes", label: "Yes" },
              { value: "no", label: "No" },
            ]}
            value={
              person.residencyStatus === null
                ? ""
                : person.residencyStatus === "british_irish_citizen"
                  ? "yes"
                  : "no"
            }
            onChange={(v) =>
              onChange({
                ...person,
                residencyStatus:
                  v === "yes" ? "british_irish_citizen" : "settled_status",
              })
            }
            aria-describedby={errorId}
            aria-invalid={invalid}
          />
        )}
      </ValidationWrapper>

      {person.residencyStatus !== null &&
        person.residencyStatus !== "british_irish_citizen" && (
          <div className="ml-6 border-l-2 border-zinc-200 pl-5">
            <RadioGroup
              name={`${label}-residency`}
              label={
                isPartner
                  ? "What is your partner's residency or immigration status?"
                  : "What is your residency or immigration status?"
              }
              options={[
                {
                  value: "settled_status",
                  label: isPartner
                    ? "They are a citizen of an EU or EEA country, or Switzerland, with settled status"
                    : "I am a citizen of an EU or EEA country, or Switzerland, with settled status",
                },
                {
                  value: "pre_settled_status",
                  label: isPartner
                    ? "They are a citizen of an EU or EEA country, or Switzerland, with pre-settled status"
                    : "I am a citizen of an EU or EEA country, or Switzerland, with pre-settled status",
                },
                {
                  value: "permission_to_access_public_funds",
                  label: "Permission to access public funds",
                },
                {
                  value: "no_recourse_to_public_funds",
                  label: "No recourse to public funds",
                },
                { value: "other", label: "Other or unsure" },
              ]}
              value={person.residencyStatus}
              onChange={(v) =>
                onChange({
                  ...person,
                  residencyStatus: v as ResidencyStatus,
                })
              }
            />
          </div>
        )}

      <ValidationWrapper
        error={errors?.niNumber}
        message="Please answer this question to continue"
      >
        {({ errorId, invalid }) => (
          <RadioGroup
            name={`${label}-ni-number`}
            label={
              isPartner
                ? "Does your partner have a National Insurance number?"
                : "Do you have a National Insurance number?"
            }
            options={[
              { value: "yes", label: "Yes" },
              { value: "no", label: "No" },
            ]}
            value={
              person.hasNationalInsuranceNumber === null
                ? ""
                : person.hasNationalInsuranceNumber
                  ? "yes"
                  : "no"
            }
            onChange={(v) =>
              onChange({ ...person, hasNationalInsuranceNumber: v === "yes" })
            }
            aria-describedby={errorId}
            aria-invalid={invalid}
          />
        )}
      </ValidationWrapper>
    </div>
  );
}

export function ImmigrationStep({
  formData,
  updateFormData,
  onContinue,
  onBack,
}: Props) {
  const [userErrors, setUserErrors] = useState<PersonErrors>({});
  const [partnerErrors, setPartnerErrors] = useState<PersonErrors>({});
  const handleContinue = () => {
    const ue = validatePerson(formData.user);
    const pe =
      formData.household.hasPartner && formData.partner
        ? validatePerson(formData.partner)
        : {};

    setUserErrors(ue);
    setPartnerErrors(pe);

    if (Object.keys(ue).length > 0 || Object.keys(pe).length > 0) {
      scrollToFirstError();
      return;
    }
    onContinue();
  };

  return (
    <>
      <FormStep
        title="Immigration status"
        onContinue={handleContinue}
        onBack={onBack}
        footer={
          <>
            <Explainer
              label="Why do you need to know my immigration status?"
              modalTitle="Why we ask about immigration status"
            >
              <p>
                For schemes like <strong>30 Hours Childcare</strong> and{" "}
                <strong>Tax-Free Childcare</strong>, you (and your partner) must
                have a National Insurance number and have at least one of the
                following:
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>British or Irish citizenship</li>
                <li>
                  Settled or pre-settled status (or have applied and are
                  awaiting a decision)
                </li>
                <li>Permission to access public funds</li>
              </ul>
              <p>
                If your immigration status says{" "}
                <strong>"no recourse to public funds"</strong>, you may still
                qualify for the <strong>Early Learning for 2-year-olds</strong>{" "}
                scheme if your household income is below a certain threshold.
              </p>
              <p>
                All 3 to 4 year olds can access up to 15 hours childcare (over
                38 weeks of the year), regardless of family circumstances.
              </p>
              <p className="font-bold">Your privacy</p>
              <p>
                Your answers stay in your browser. They are never sent to a
                server, stored, or linked to you in any way.
              </p>
              <div className="pt-2 space-y-1">
                <p>
                  <ExternalLink
                    href="https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    30 Hours eligibility on Best Start in Life
                  </ExternalLink>
                </p>
                <p>
                  <ExternalLink
                    href="https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/additional-support/eligibility/"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    Early Learning for 2-year-olds eligibility
                  </ExternalLink>
                </p>
                <p>
                  <ExternalLink
                    href="https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/universal-offer/how-it-works/"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    How 15 hours for all 3 to 4 year olds works
                  </ExternalLink>
                </p>
              </div>
            </Explainer>
            <Explainer label="What is a National Insurance number?">
              <p>
                A National Insurance (NI) number is a unique personal number
                used for tax and benefits in the UK. It looks like this:{" "}
                <strong className="font-mono">AB 12 34 56 C</strong> (two
                letters, six digits, one letter).
              </p>
              <p>You can find it on:</p>
              <ul className="list-disc pl-5 space-y-1">
                <li>Your payslip</li>
                <li>Your P60 or tax letters from HMRC</li>
                <li>The HMRC app or personal tax account</li>
              </ul>
              <p>
                If you were born in the UK and a parent claimed Child Benefit
                for you, you should have received your NI number automatically
                before your 16th birthday. If not, you can apply for one.
              </p>
              <p>
                A National Insurance number is required for most childcare
                support schemes, including 30 Hours Childcare and Tax-Free
                Childcare.
              </p>
              <p className="pt-2">
                <ExternalLink
                  href="https://www.gov.uk/apply-national-insurance-number"
                  className="text-purple-700 underline hover:text-purple-900"
                >
                  Apply for a National Insurance number on GOV.UK
                </ExternalLink>
              </p>
            </Explainer>
          </>
        }
      >
        <PersonImmigrationSection
          label="About you"
          person={formData.user}
          errors={userErrors}
          isPartner={false}
          onChange={(user) => {
            setUserErrors({});
            updateFormData({ user });
          }}
        />

        {formData.household.hasPartner && formData.partner && (
          <PersonImmigrationSection
            label="About your partner"
            person={formData.partner}
            errors={partnerErrors}
            isPartner={true}
            onChange={(partner) => {
              setPartnerErrors({});
              updateFormData({ partner });
            }}
          />
        )}
      </FormStep>
    </>
  );
}

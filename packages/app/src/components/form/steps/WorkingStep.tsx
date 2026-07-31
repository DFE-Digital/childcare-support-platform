import { useState } from "react";
import type { FormLocalStorageData, FormPersonData } from "@/types/formData";
import type { AgeBracket, WorkingStatus, StudyLevel } from "@/types/family";
import { NMW_WEEKLY, APPRENTICE_BRACKET, nmwForPeriod } from "@bsil/calculator";
import { FormStep } from "@/components/ui/FormStep";
import { RadioGroup } from "@/components/ui/RadioGroup";
import { ValidationWrapper } from "@/components/ui/ValidationWrapper";
import { Explainer } from "@/components/ui/Explainer";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { scrollToFirstError } from "@/lib/scrollToFirstError";

interface PersonErrors {
  apprentice?: boolean;
  firstYear?: boolean;
  selfEmployed?: boolean;
  ageBracket?: boolean;
  workingStatus?: boolean;
  carersAllowance?: boolean;
  startup?: boolean;
  isStudying?: boolean;
  studyLevel?: boolean;
  isFullTimeStudent?: boolean;
  courseIsPubliclyFunded?: boolean;
  eligibleForStudentFinance?: boolean;
}

interface Props {
  formData: FormLocalStorageData;
  updateFormData: (patch: Partial<FormLocalStorageData>) => void;
  onContinue: () => void;
  onBack: () => void;
}

function isLowEarning(status: WorkingStatus | null): boolean {
  return status === "earning_below_nmw";
}

function validatePerson(person: FormPersonData): PersonErrors {
  const errors: PersonErrors = {};
  if (person.isApprentice === null) errors.apprentice = true;
  if (person.isApprentice && person.firstYearApprentice === null)
    errors.firstYear = true;
  if (person.isApprentice === false && person.isSelfEmployed === null)
    errors.selfEmployed = true;
  if (
    !(person.isApprentice && person.firstYearApprentice) &&
    person.ageBracket === null
  )
    errors.ageBracket = true;
  if (person.workingStatus === null) errors.workingStatus = true;
  if (
    person.workingStatus === "not_working" &&
    person.receivesQualifyingAllowance === null
  )
    errors.carersAllowance = true;
  if (
    person.isSelfEmployed &&
    isLowEarning(person.workingStatus) &&
    person.selfEmployedLessThanTwelveMonths === null
  )
    errors.startup = true;
  if (person.isStudying === null) errors.isStudying = true;
  if (person.isStudying && person.studyLevel === null) errors.studyLevel = true;
  if (
    person.isStudying &&
    person.studyLevel === "higher_education" &&
    person.isFullTimeStudent === null
  )
    errors.isFullTimeStudent = true;
  if (
    person.isStudying &&
    person.studyLevel === "higher_education" &&
    person.eligibleForStudentFinance === null
  )
    errors.eligibleForStudentFinance = true;
  if (
    person.isStudying &&
    (person.studyLevel === "school_sixth_form" ||
      person.studyLevel === "further_education") &&
    person.courseIsPubliclyFunded === null
  )
    errors.courseIsPubliclyFunded = true;
  return errors;
}

function PersonWorkSection({
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
  const bracket = person.ageBracket ?? "21+";
  const threshold = NMW_WEEKLY[bracket].toFixed(2);
  const apprenticeThreshold = NMW_WEEKLY[APPRENTICE_BRACKET].toFixed(2);

  const apprenticeEffectiveThreshold = person.firstYearApprentice
    ? apprenticeThreshold
    : threshold;

  const workingOptions = person.isApprentice
    ? [
        {
          value: "earning_below_nmw",
          label: `Earning less than £${apprenticeEffectiveThreshold} per week`,
        },
        {
          value: "earning_above_nmw",
          label: `Earning £${apprenticeEffectiveThreshold} or more per week`,
        },
        { value: "not_working", label: "Not working" },
      ]
    : [
        {
          value: "earning_below_nmw",
          label: `Earning less than £${threshold} per week`,
        },
        {
          value: "earning_above_nmw",
          label: `Earning £${threshold} or more per week`,
        },
        {
          value: "income_over_100k",
          label: "Adjusted net income over £100,000",
        },
        { value: "not_working", label: "Not working" },
      ];

  return (
    <div className="space-y-5 bg-white rounded-xl p-6 border border-zinc-200">
      <h3 className="font-bold text-xl">{label}</h3>

      <ValidationWrapper
        error={errors?.apprentice}
        message="Please answer this question to continue"
      >
        {({ errorId, invalid }) => (
          <RadioGroup
            name={`${label}-apprentice`}
            label={
              isPartner
                ? "Is your partner on an apprenticeship?"
                : "Are you on an apprenticeship?"
            }
            options={[
              { value: "yes", label: "Yes" },
              { value: "no", label: "No" },
            ]}
            value={
              person.isApprentice === null
                ? ""
                : person.isApprentice
                  ? "yes"
                  : "no"
            }
            onChange={(v) =>
              onChange({
                ...person,
                isApprentice: v === "yes",
                firstYearApprentice:
                  v === "yes" ? person.firstYearApprentice : null,
                isSelfEmployed: v === "yes" ? false : person.isSelfEmployed,
                selfEmployedLessThanTwelveMonths:
                  v === "yes" ? null : person.selfEmployedLessThanTwelveMonths,
                workingStatus: null,
                receivesQualifyingAllowance: null,
                startingWorkNextMonth: null,
                hasLimitedCapacityForWork: null,
              })
            }
            aria-describedby={errorId}
            aria-invalid={invalid}
          />
        )}
      </ValidationWrapper>

      {person.isApprentice && (
        <div className="ml-6 border-l-2 border-zinc-200 pl-5">
          <ValidationWrapper
            error={errors?.firstYear}
            message="Please answer this question to continue"
          >
            {({ errorId, invalid }) => (
              <RadioGroup
                name={`${label}-firstyear`}
                label={
                  isPartner
                    ? "Is your partner in their first year?"
                    : "Are you in your first year?"
                }
                options={[
                  { value: "yes", label: "Yes" },
                  { value: "no", label: "No" },
                ]}
                value={
                  person.firstYearApprentice === null
                    ? ""
                    : person.firstYearApprentice
                      ? "yes"
                      : "no"
                }
                onChange={(v) =>
                  onChange({
                    ...person,
                    firstYearApprentice: v === "yes",
                    workingStatus: null,
                    receivesQualifyingAllowance: null,
                    startingWorkNextMonth: null,
                    hasLimitedCapacityForWork: null,
                  })
                }
                aria-describedby={errorId}
                aria-invalid={invalid}
              />
            )}
          </ValidationWrapper>
        </div>
      )}

      {person.isApprentice === false && (
        <ValidationWrapper
          error={errors?.selfEmployed}
          message="Please answer this question to continue"
        >
          {({ errorId, invalid }) => (
            <RadioGroup
              name={`${label}-self-employed`}
              label={
                isPartner
                  ? "Is your partner self-employed?"
                  : "Are you self-employed?"
              }
              options={[
                { value: "yes", label: "Yes" },
                { value: "no", label: "No" },
              ]}
              value={
                person.isSelfEmployed === null
                  ? ""
                  : person.isSelfEmployed
                    ? "yes"
                    : "no"
              }
              onChange={(v) =>
                onChange({
                  ...person,
                  isSelfEmployed: v === "yes",
                  selfEmployedLessThanTwelveMonths:
                    v === "yes"
                      ? person.selfEmployedLessThanTwelveMonths
                      : null,
                })
              }
              aria-describedby={errorId}
              aria-invalid={invalid}
            />
          )}
        </ValidationWrapper>
      )}

      {!(person.isApprentice && person.firstYearApprentice) && (
        <ValidationWrapper
          error={errors?.ageBracket}
          message="Please answer this question to continue"
        >
          {({ errorId, invalid }) => (
            <RadioGroup
              name={`${label}-age-bracket`}
              label={
                isPartner ? "Your partner's age bracket" : "Your age bracket"
              }
              options={[
                { value: "16-17", label: "16 to 17" },
                { value: "18-20", label: "18 to 20" },
                { value: "21+", label: "21 or over" },
              ]}
              value={person.ageBracket ?? ""}
              onChange={(v) =>
                onChange({
                  ...person,
                  ageBracket: v as AgeBracket,
                  workingStatus: null,
                  receivesQualifyingAllowance: null,
                  startingWorkNextMonth: null,
                  hasLimitedCapacityForWork: null,
                })
              }
              aria-describedby={errorId}
              aria-invalid={invalid}
            />
          )}
        </ValidationWrapper>
      )}

      <ValidationWrapper
        error={errors?.workingStatus}
        message="Please answer this question to continue"
      >
        {({ errorId, invalid }) => (
          <RadioGroup
            name={`${label}-working`}
            label={
              isPartner
                ? "Your partner's working and expected income situation"
                : "Your working and expected income situation"
            }
            options={workingOptions}
            value={person.workingStatus ?? ""}
            onChange={(v) =>
              onChange({
                ...person,
                workingStatus: v as WorkingStatus,
                receivesQualifyingAllowance:
                  v === "not_working"
                    ? (person.receivesQualifyingAllowance ?? null)
                    : null,
                startingWorkNextMonth: null,
                hasLimitedCapacityForWork: null,
              })
            }
            aria-describedby={errorId}
            aria-invalid={invalid}
          />
        )}
      </ValidationWrapper>

      {person.workingStatus === "not_working" && (
        <div className="ml-6 border-l-2 border-zinc-200 pl-5">
          <ValidationWrapper
            error={errors?.carersAllowance}
            message="Please answer this question to continue"
          >
            {({ errorId, invalid }) => (
              <RadioGroup
                name={`${label}-carers-allowance`}
                label={
                  <>
                    {isPartner
                      ? "Does your partner receive any of the following allowances:"
                      : "Do you receive any of the following allowances:"}
                    <ul className="list-disc pl-5 mt-2 text-base font-normal">
                      <li>Carer's Allowance?</li>
                      <li>Carer Support Payment (Scotland)?</li>
                      <li>Incapacity Benefit?</li>
                      <li>Severe Disablement Allowance?</li>
                      <li>
                        Contribution-based Employment and Support Allowance?
                      </li>
                    </ul>
                  </>
                }
                options={[
                  { value: "yes", label: "Yes" },
                  { value: "no", label: "No" },
                ]}
                value={
                  person.receivesQualifyingAllowance === true
                    ? "yes"
                    : person.receivesQualifyingAllowance === false
                      ? "no"
                      : ""
                }
                onChange={(v) =>
                  onChange({
                    ...person,
                    receivesQualifyingAllowance: v === "yes",
                    startingWorkNextMonth: null,
                    hasLimitedCapacityForWork: null,
                  })
                }
                aria-describedby={errorId}
                aria-invalid={invalid}
              />
            )}
          </ValidationWrapper>
        </div>
      )}

      {person.isSelfEmployed && isLowEarning(person.workingStatus) && (
        <div className="ml-6 border-l-2 border-zinc-200 pl-5">
          <ValidationWrapper
            error={errors?.startup}
            message="Please answer this question to continue"
          >
            {({ errorId, invalid }) => (
              <RadioGroup
                name={`${label}-startup`}
                label={
                  isPartner
                    ? "Has your partner's business been trading for less than 12 months?"
                    : "Has your business been trading for less than 12 months?"
                }
                options={[
                  { value: "yes", label: "Yes" },
                  { value: "no", label: "No" },
                ]}
                value={
                  person.selfEmployedLessThanTwelveMonths === true
                    ? "yes"
                    : person.selfEmployedLessThanTwelveMonths === false
                      ? "no"
                      : ""
                }
                onChange={(v) =>
                  onChange({
                    ...person,
                    selfEmployedLessThanTwelveMonths: v === "yes",
                  })
                }
                aria-describedby={errorId}
                aria-invalid={invalid}
              />
            )}
          </ValidationWrapper>
        </div>
      )}

      <ValidationWrapper
        error={errors?.isStudying}
        message="Please answer this question to continue"
      >
        {({ errorId, invalid }) => (
          <RadioGroup
            name={`${label}-studying`}
            label={
              isPartner
                ? person.isApprentice
                  ? "Excluding their apprenticeship, is your partner studying for anything else?"
                  : "Is your partner currently studying?"
                : person.isApprentice
                  ? "Excluding your apprenticeship, are you studying for anything else?"
                  : "Are you currently studying?"
            }
            options={[
              { value: "yes", label: "Yes" },
              { value: "no", label: "No" },
            ]}
            value={
              person.isStudying === null ? "" : person.isStudying ? "yes" : "no"
            }
            onChange={(v) =>
              onChange({
                ...person,
                isStudying: v === "yes",
                studyLevel: v === "yes" ? person.studyLevel : null,
                isFullTimeStudent:
                  v === "yes" ? person.isFullTimeStudent : null,
                courseIsPubliclyFunded:
                  v === "yes" ? person.courseIsPubliclyFunded : null,
                eligibleForStudentFinance:
                  v === "yes" ? person.eligibleForStudentFinance : null,
              })
            }
            aria-describedby={errorId}
            aria-invalid={invalid}
          />
        )}
      </ValidationWrapper>

      {person.isStudying && (
        <div className="ml-6 border-l-2 border-zinc-200 pl-5 space-y-5">
          <ValidationWrapper
            error={errors?.studyLevel}
            message="Please answer this question to continue"
          >
            {({ errorId, invalid }) => (
              <RadioGroup
                name={`${label}-study-level`}
                label={
                  isPartner
                    ? "What level is your partner studying at?"
                    : "What level are you studying at?"
                }
                options={[
                  { value: "school_sixth_form", label: "School or sixth form" },
                  {
                    value: "further_education",
                    label: "Further education (e.g. NVQ, BTEC, PGCE)",
                  },
                  {
                    value: "higher_education",
                    label: "Higher education (university)",
                  },
                ]}
                value={person.studyLevel ?? ""}
                onChange={(v) =>
                  onChange({
                    ...person,
                    studyLevel: v as StudyLevel,
                    isFullTimeStudent:
                      v === "higher_education"
                        ? person.isFullTimeStudent
                        : null,
                    courseIsPubliclyFunded:
                      v === "school_sixth_form" || v === "further_education"
                        ? person.courseIsPubliclyFunded
                        : null,
                    eligibleForStudentFinance:
                      v === "higher_education"
                        ? person.eligibleForStudentFinance
                        : null,
                  })
                }
                aria-describedby={errorId}
                aria-invalid={invalid}
              />
            )}
          </ValidationWrapper>

          {(person.studyLevel === "school_sixth_form" ||
            person.studyLevel === "further_education") && (
            <ValidationWrapper
              error={errors?.courseIsPubliclyFunded}
              message="Please answer this question to continue"
            >
              {({ errorId, invalid }) => (
                <RadioGroup
                  name={`${label}-publicly-funded`}
                  label={
                    isPartner
                      ? "Is your partner's course publicly funded?"
                      : "Is your course publicly funded?"
                  }
                  options={[
                    { value: "yes", label: "Yes" },
                    { value: "no", label: "No" },
                  ]}
                  value={
                    person.courseIsPubliclyFunded === true
                      ? "yes"
                      : person.courseIsPubliclyFunded === false
                        ? "no"
                        : ""
                  }
                  onChange={(v) =>
                    onChange({
                      ...person,
                      courseIsPubliclyFunded: v === "yes",
                    })
                  }
                  aria-describedby={errorId}
                  aria-invalid={invalid}
                />
              )}
            </ValidationWrapper>
          )}

          {person.studyLevel === "higher_education" && (
            <>
              <ValidationWrapper
                error={errors?.isFullTimeStudent}
                message="Please answer this question to continue"
              >
                {({ errorId, invalid }) => (
                  <RadioGroup
                    name={`${label}-full-time`}
                    label={
                      isPartner
                        ? "Is your partner studying full-time (120 or more credits per year)?"
                        : "Are you studying full-time (120 or more credits per year)?"
                    }
                    options={[
                      { value: "yes", label: "Yes" },
                      { value: "no", label: "No" },
                    ]}
                    value={
                      person.isFullTimeStudent === true
                        ? "yes"
                        : person.isFullTimeStudent === false
                          ? "no"
                          : ""
                    }
                    onChange={(v) =>
                      onChange({
                        ...person,
                        isFullTimeStudent: v === "yes",
                      })
                    }
                    aria-describedby={errorId}
                    aria-invalid={invalid}
                  />
                )}
              </ValidationWrapper>

              <ValidationWrapper
                error={errors?.eligibleForStudentFinance}
                message="Please answer this question to continue"
              >
                {({ errorId, invalid }) => (
                  <RadioGroup
                    name={`${label}-student-finance`}
                    label={
                      isPartner
                        ? "Is your partner eligible for student finance?"
                        : "Are you eligible for student finance?"
                    }
                    options={[
                      { value: "yes", label: "Yes" },
                      { value: "no", label: "No" },
                    ]}
                    value={
                      person.eligibleForStudentFinance === true
                        ? "yes"
                        : person.eligibleForStudentFinance === false
                          ? "no"
                          : ""
                    }
                    onChange={(v) =>
                      onChange({
                        ...person,
                        eligibleForStudentFinance: v === "yes",
                      })
                    }
                    aria-describedby={errorId}
                    aria-invalid={invalid}
                  />
                )}
              </ValidationWrapper>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function WorkingStep({
  formData,
  updateFormData,
  onContinue,
  onBack,
}: Props) {
  const [userErrors, setUserErrors] = useState<PersonErrors>({});
  const [partnerErrors, setPartnerErrors] = useState<PersonErrors>({});

  const people = [
    formData.user,
    ...(formData.household.hasPartner && formData.partner
      ? [formData.partner]
      : []),
  ];
  const anyStudyingSchoolFE = people.some(
    (p) =>
      p.isStudying &&
      (p.studyLevel === "school_sixth_form" ||
        p.studyLevel === "further_education"),
  );
  const anyStudyingHE = people.some(
    (p) => p.isStudying && p.studyLevel === "higher_education",
  );

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
        title="Your working situation"
        onContinue={handleContinue}
        onBack={onBack}
        footer={
          <>
            <Explainer label="Why do you need to know about my work and income?">
              <p>
                Key childcare schemes like <strong>30 Hours Childcare</strong>{" "}
                and <strong>Tax-Free Childcare</strong> have minimum earnings
                requirements. You (and your partner, if you have one) must each
                expect to earn at least the equivalent of 16 hours per week at
                the National Minimum Wage.
              </p>
              <p>
                The exact threshold depends on your age, which is why we ask for
                your age bracket. There is also a maximum: your expected
                adjusted net income must not exceed{" "}
                <strong>£100,000 per year</strong>.
              </p>
              <p>
                <strong>Universal Credit childcare</strong> has different rules
                — there is no minimum earnings requirement, but you must be in
                paid work.
              </p>
              <p>
                If you are not working, you may still qualify if you receive
                certain benefits such as Carer&apos;s Allowance or Incapacity
                Benefit, and your partner is working.
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
                    href="https://beststartinlife.gov.uk/childcare-early-years-education/tax-free-childcare/eligibility/"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    Tax-Free Childcare eligibility on Best Start in Life
                  </ExternalLink>
                </p>
              </div>
            </Explainer>
            <Explainer label="What if I'm on leave from work?">
              <p>
                For childcare schemes like <strong>30 Hours Childcare</strong>{" "}
                and <strong>Tax-Free Childcare</strong>, you are usually treated
                as being in paid work even if you are currently on certain types
                of leave. This includes:
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>Maternity leave</li>
                <li>Paternity leave</li>
                <li>Shared parental leave</li>
                <li>Adoption leave</li>
                <li>Neonatal care leave</li>
                <li>Bereaved partner paternity leave</li>
                <li>Sick leave</li>
                <li>Annual leave</li>
              </ul>
              <p>
                If you are on one of these types of leave and are applying on
                behalf of a different child than the one you are on leave for,
                you still count as working and can apply for or continue
                receiving funded childcare. You do not need to have returned to
                work first.
              </p>
              <p>
                However, if you are starting or returning to work after parental
                leave, there are specific rules about when you can first access
                your entitlement, based on which term your return date falls in.
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
                    href="https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    Full eligibility details on Best Start in Life
                  </ExternalLink>
                </p>
              </div>
            </Explainer>
            <Explainer label="What's the income threshold as a monthly, quarterly, or annual figure?">
              <p>
                The government sets the minimum earnings threshold as a 3-month
                figure, based on working 16 hours per week at the National
                Minimum Wage. Here are the thresholds shown weekly, monthly,
                over 3 months, and annually:
              </p>
              <div className="space-y-3">
                {(
                  [
                    { bracket: "21+" as const, label: "21+" },
                    { bracket: "18-20" as const, label: "18 to 20" },
                    {
                      bracket: "16-17" as const,
                      label: "Under 18 or first year apprentice",
                    },
                  ] as const
                ).map(({ bracket: b, label: l }) => {
                  const periods = nmwForPeriod(b);
                  return (
                    <div
                      key={b}
                      className="border border-zinc-200 rounded-lg p-3"
                    >
                      <p className="font-bold mb-2">{l}</p>
                      <table className="w-full text-sm">
                        <tbody>
                          <tr className="bg-zinc-50">
                            <td className="text-zinc-600 py-1 px-2 rounded-l">
                              Weekly
                            </td>
                            <td className="text-right py-1 px-2 rounded-r">
                              £{periods.weekly.toFixed(2)}
                            </td>
                          </tr>
                          <tr>
                            <td className="text-zinc-600 py-1 px-2">Monthly</td>
                            <td className="text-right py-1 px-2">
                              £
                              {periods.monthly.toLocaleString("en-GB", {
                                minimumFractionDigits: 2,
                              })}
                            </td>
                          </tr>
                          <tr className="bg-zinc-50">
                            <td className="text-zinc-600 py-1 px-2 rounded-l">
                              Over 3 months
                            </td>
                            <td className="text-right py-1 px-2 rounded-r">
                              £
                              {periods.quarterly.toLocaleString("en-GB", {
                                minimumFractionDigits: 2,
                              })}
                            </td>
                          </tr>
                          <tr>
                            <td className="text-zinc-600 py-1 px-2">
                              Annually
                            </td>
                            <td className="text-right py-1 px-2">
                              £
                              {periods.annual.toLocaleString("en-GB", {
                                minimumFractionDigits: 2,
                              })}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  );
                })}
              </div>
              <p>
                These are <strong>before tax</strong> figures. You must expect
                to earn at least this much over the next 3 months to qualify for
                30 Hours Childcare and Tax-Free Childcare.
              </p>
              <p>
                There is also a maximum: your adjusted net income must not
                exceed <strong>£100,000 per year</strong>.
              </p>
              <p>
                If you are <strong>self-employed</strong> and your business has
                been trading for less than 12 months, you can earn less than
                these thresholds and still be eligible.
              </p>
              <p className="pt-2">
                <ExternalLink
                  href="https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/"
                  className="text-purple-700 underline hover:text-purple-900"
                >
                  Full eligibility details on Best Start in Life
                </ExternalLink>
              </p>
            </Explainer>
            <Explainer label="What do these income thresholds mean?">
              <p>
                To qualify for 30 Hours Childcare and Tax-Free Childcare, you
                must earn at least the National Minimum Wage for 16 hours per
                week. The thresholds are:
              </p>
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-zinc-200">
                    <th className="text-left py-2 pr-4 font-bold">Age</th>
                    <th className="text-right py-2 font-bold">
                      Weekly minimum
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-zinc-100">
                    <td className="py-2 pr-4">21 and over</td>
                    <td className="text-right py-2">
                      £{NMW_WEEKLY["21+"].toFixed(2)}
                    </td>
                  </tr>
                  <tr className="border-b border-zinc-100">
                    <td className="py-2 pr-4">18 to 20</td>
                    <td className="text-right py-2">
                      £{NMW_WEEKLY["18-20"].toFixed(2)}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4">Under 18 or apprentice</td>
                    <td className="text-right py-2">
                      £{NMW_WEEKLY["16-17"].toFixed(2)}
                    </td>
                  </tr>
                </tbody>
              </table>
              <p>
                If you are <strong>self-employed</strong> and your business has
                been trading for less than 12 months, you can earn less than
                these thresholds and still be eligible. You can use an average
                of your expected earnings over the current tax year.
              </p>
              <p>
                <strong>Income that does not count</strong> toward the minimum:
                dividends, interest, property income, and pension payments.
              </p>
              <p>
                If you have <strong>multiple jobs</strong>, your total earnings
                from all employment and self-employment count together.
              </p>
              <p className="pt-2">
                <ExternalLink
                  href="https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/"
                  className="text-purple-700 underline hover:text-purple-900"
                >
                  Full eligibility details on Best Start in Life
                </ExternalLink>
              </p>
            </Explainer>
            <Explainer label="What does &ldquo;adjusted net income&rdquo; mean?">
              <p>
                Adjusted net income (ANI) is the figure HMRC uses to decide
                whether you exceed the <strong>£100,000 per year</strong> cap
                for 30 Hours Childcare and Tax-Free Childcare.
              </p>
              <p className="font-bold">How it is calculated</p>
              <p>
                Start with your expected total taxable income (salary,
                self-employment profits, pensions, rental income, savings
                interest, dividends, etc.), then subtract:
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>
                  Pension contributions paid gross (e.g. to a personal pension)
                </li>
                <li>
                  Gift Aid donations (grossed up by the basic rate of tax)
                </li>
                <li>Trading losses and certain other tax reliefs</li>
              </ul>
              <p>
                The result is your adjusted net income. If it is over £100,000
                in a tax year, you are not eligible for 30 Hours Childcare or
                Tax-Free Childcare for that period.
              </p>
              <p>
                Foreign and worldwide income is included in the calculation,
                regardless of where you are tax-resident.
              </p>
              <p className="font-bold">Why it matters</p>
              <p>
                If your gross salary is over £100,000, you may still be under
                the cap once pension contributions and Gift Aid are deducted. It
                is worth checking your adjusted figure before assuming you are
                ineligible.
              </p>
              <div className="pt-2 space-y-1">
                <p>
                  <ExternalLink
                    href="https://www.gov.uk/guidance/adjusted-net-income"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    Adjusted net income on GOV.UK
                  </ExternalLink>
                </p>
                <p>
                  <ExternalLink
                    href="https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    30 Hours eligibility on Best Start in Life
                  </ExternalLink>
                </p>
              </div>
            </Explainer>
            <Explainer label="What is Carer's Allowance?">
              <p>
                Carer&apos;s Allowance is a benefit for people who spend at
                least 35 hours a week caring for someone with substantial caring
                needs. It is currently £86.45 per week.
              </p>
              <p className="font-bold">Why it matters for childcare support</p>
              <p>
                If you are not working but receive Carer&apos;s Allowance (or
                certain other benefits like Incapacity Benefit or Severe
                Disablement Allowance), your working partner (if they live with
                you) can still qualify the household for:
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>30 Hours Childcare</li>
                <li>Tax-Free Childcare</li>
              </ul>
              <p>
                This means a household where one person cares full-time and the
                other works can still access these schemes. However, if you are
                a single parent receiving Carer&apos;s Allowance (or other
                certain benefits) you will also need to be working and meet the
                income requirements to be eligible for 30 Hours Childcare.
              </p>
              <p className="pt-2">
                <ExternalLink
                  href="https://www.gov.uk/carers-allowance"
                  className="text-purple-700 underline hover:text-purple-900"
                >
                  Carer&apos;s Allowance on GOV.UK
                </ExternalLink>
              </p>
            </Explainer>
            <Explainer
              label="Why are you asking about studying?"
              modalTitle="Why we ask about studying"
            >
              <p>
                Some childcare support schemes are specifically for parents who
                are studying. We ask about your study situation so we can check
                whether you might qualify for any of these.
              </p>
              <p className="font-bold">Care to Learn</p>
              <p>
                Helps young parents (under 20 at the start of their course) who
                are on a publicly funded course at school or further education
                level. It can pay up to £180 per child per week (or £195 in
                London) toward childcare costs while you study.
              </p>
              <p className="font-bold">Learner Support</p>
              <p>
                Discretionary funding from further education learning providers
                for students aged 19 or over. The amount and availability depend
                on your provider — they decide how to allocate their hardship
                funds, which can include help with childcare.
              </p>
              <p className="font-bold">Childcare Grant</p>
              <p>
                For full-time higher education students who are eligible for
                student finance. It provides up to £199.62 per week for one
                child, or £342.24 per week for two or more children. You do not
                have to pay it back.
              </p>
              <div className="pt-2 space-y-1">
                <p>
                  <ExternalLink
                    href="https://www.gov.uk/care-to-learn"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    Care to Learn on GOV.UK
                  </ExternalLink>
                </p>
                <p>
                  <ExternalLink
                    href="https://www.gov.uk/learner-support"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    Learner Support on GOV.UK
                  </ExternalLink>
                </p>
                <p>
                  <ExternalLink
                    href="https://www.gov.uk/childcare-grant"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    Childcare Grant on GOV.UK
                  </ExternalLink>
                </p>
              </div>
            </Explainer>
            {anyStudyingSchoolFE && (
              <Explainer label="What counts as a publicly funded course?">
                <p>
                  A publicly funded course is one where the tuition fees are
                  paid by the government rather than by you. This matters for{" "}
                  <strong>Care to Learn</strong> eligibility.
                </p>
                <p className="font-bold">Usually publicly funded</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>Courses at state schools and sixth form colleges</li>
                  <li>
                    Most courses at further education colleges (GCSEs, A-levels,
                    T-levels, BTECs, NVQs, and other qualifications funded by
                    the Education and Skills Funding Agency)
                  </li>
                  <li>
                    Apprenticeships (though Care to Learn does not apply to
                    apprenticeships)
                  </li>
                </ul>
                <p className="font-bold">Usually not publicly funded</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>Courses at private or independent schools</li>
                  <li>Courses where you pay the fees yourself</li>
                  <li>
                    Some short commercial or leisure courses at FE colleges
                  </li>
                </ul>
                <p>
                  If you are unsure, ask your school or college — they can tell
                  you whether your course is publicly funded.
                </p>
                <p className="pt-2">
                  <ExternalLink
                    href="https://www.gov.uk/care-to-learn"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    Care to Learn on GOV.UK
                  </ExternalLink>
                </p>
              </Explainer>
            )}
            {anyStudyingHE && (
              <Explainer label="What does &ldquo;eligible for student finance&rdquo; mean?">
                <p>
                  Student finance from Student Finance England provides tuition
                  fee loans, maintenance loans, and grants to help with the cost
                  of higher education. The <strong>Childcare Grant</strong> is
                  only available to students who are eligible for student
                  finance — even if you choose not to take out a loan.
                </p>
                <p className="font-bold">You are usually eligible if</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>
                    You are studying your first higher education qualification
                    (undergraduate degree, HND, foundation degree, etc.)
                  </li>
                  <li>Your course is at a university or college in England</li>
                  <li>
                    You meet the residency requirements (usually you must have
                    been living in the UK for at least 3 years)
                  </li>
                </ul>
                <p className="font-bold">You may not be eligible if</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>
                    You already hold an equivalent or higher qualification (for
                    example, studying a second degree)
                  </li>
                  <li>Your course is not designated for student support</li>
                  <li>You do not meet the residency criteria</li>
                </ul>
                <p>
                  If you are unsure, you can check with your university or apply
                  to Student Finance England to find out — there is no
                  obligation to accept funding if you are approved.
                </p>
                <div className="pt-2 space-y-1">
                  <p>
                    <ExternalLink
                      href="https://www.gov.uk/student-finance"
                      className="text-purple-700 underline hover:text-purple-900"
                    >
                      Student finance on GOV.UK
                    </ExternalLink>
                  </p>
                  <p>
                    <ExternalLink
                      href="https://www.gov.uk/childcare-grant"
                      className="text-purple-700 underline hover:text-purple-900"
                    >
                      Childcare Grant on GOV.UK
                    </ExternalLink>
                  </p>
                </div>
              </Explainer>
            )}
          </>
        }
      >
        <PersonWorkSection
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
          <PersonWorkSection
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

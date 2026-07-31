import { useNavigate } from "react-router-dom";
import type { FormLocalStorageData, FormPersonData } from "@/types/formData";
import { normalisePostcode } from "@/lib/postcode";
import { featureFlags } from "@/hooks/useFeatureFlags";
import { areAllChildrenBigKids } from "@/lib/childAge";
import { NMW_WEEKLY, APPRENTICE_BRACKET } from "@bsil/calculator";

interface SummaryStepProps {
  formData: FormLocalStorageData;
  completedLabels: string[];
  invalidLabels: string[];
  allLabels: string[];
  onEdit: (stepNumber: number) => void;
  onContinue: () => void;
  onReset?: () => void;
}

const monthNames = [
  "",
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function workingLabel(person: FormPersonData): string {
  const threshold = NMW_WEEKLY[person.ageBracket ?? "21+"].toFixed(2);
  const apprenticeThreshold = NMW_WEEKLY[APPRENTICE_BRACKET].toFixed(2);
  const status: Record<string, string> = {
    earning_above_nmw: `Earning £${threshold}+ per week`,
    earning_above_apprentice_nmw: `Earning £${apprenticeThreshold}+ per week (apprentice rate)`,
    earning_below_nmw: `Earning below £${threshold} per week`,
    not_working: "Not working",
    income_over_100k: "Income over £100,000",
  };
  const parts: string[] = [];
  if (person.isApprentice) {
    if (person.firstYearApprentice) {
      parts.push("First year apprentice");
    } else if (person.ageBracket) {
      parts.push(`Apprentice (age ${person.ageBracket})`);
    } else {
      parts.push("Apprentice");
    }
  } else if (person.isSelfEmployed) {
    if (person.selfEmployedLessThanTwelveMonths) {
      parts.push("Self-employed (< 12 months)");
    } else {
      parts.push("Self-employed");
    }
  }
  parts.push(
    person.workingStatus
      ? status[person.workingStatus] || person.workingStatus
      : "Not answered",
  );
  if (person.receivesQualifyingAllowance) parts.push("Carer's Allowance");
  if (person.isStudying) {
    const levelLabels: Record<string, string> = {
      school_sixth_form: "School/sixth form",
      further_education: "Further education",
      higher_education: "Higher education",
    };
    const level = person.studyLevel
      ? levelLabels[person.studyLevel] || person.studyLevel
      : "Studying";
    parts.push(`Studying (${level})`);
  }
  return parts.join(", ");
}

const residencyLabels: Record<string, string> = {
  british_irish_citizen: "British or Irish citizen",
  settled_status:
    "I am a citizen of an EU or EEA country, or Switzerland, with settled status",
  pre_settled_status:
    "I am a citizen of an EU or EEA country, or Switzerland, with pre-settled status",
  permission_to_access_public_funds: "Permission to access public funds",
  no_recourse_to_public_funds: "No recourse to public funds",
  other: "Other or unsure",
};

function immigrationLabel(person: FormPersonData): string {
  const parts: string[] = [];
  parts.push(
    person.residencyStatus
      ? residencyLabels[person.residencyStatus] || person.residencyStatus
      : "Not answered",
  );
  if (person.hasNationalInsuranceNumber !== null) {
    parts.push(
      person.hasNationalInsuranceNumber ? "Has NI number" : "No NI number",
    );
  }
  return parts.join(", ");
}

function careTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    private_nursery: "Nursery (Private, Voluntary or Independent)",
    school_based_nursery: "School-based nursery",
    childminder: "Childminder",
    breakfast_club: "Breakfast club",
    free_breakfast_club: "Free breakfast club",
    after_school_club: "After school club",
    holiday_club: "Holiday club",
  };
  return labels[type] || type;
}

function StepSummaryRow({
  label,
  stepNumber,
  onEdit,
  isInvalid,
  children,
}: {
  label: string;
  stepNumber: number;
  onEdit: (n: number) => void;
  isInvalid?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`py-4 border-b border-zinc-200 last:border-b-0${isInvalid ? " bg-amber-50 -mx-4 px-4 rounded" : ""}`}
    >
      <div className="flex items-center justify-between gap-4 mb-1">
        <h3 className="font-bold text-sm text-zinc-500">{label}</h3>
        <button
          onClick={() => onEdit(stepNumber)}
          aria-label={`${isInvalid ? "Update" : "Edit"} ${label}`}
          className={`shrink-0 text-sm font-bold underline transition-colors ${isInvalid ? "text-amber-700 hover:text-amber-500 hover:no-underline" : "text-purple-800 hover:text-purple-500 hover:no-underline"}`}
        >
          {isInvalid ? "Update" : "Edit"}
        </button>
      </div>
      <div className="text-base">{children}</div>
    </div>
  );
}

export function SummaryStep({
  formData,
  completedLabels,
  invalidLabels,
  allLabels,
  onEdit,
  onContinue,
  onReset,
}: SummaryStepProps) {
  const navigate = useNavigate();
  const hasUncompleted = allLabels.some((l) => !completedLabels.includes(l));
  const hasInvalid = invalidLabels.length > 0;

  const isCostForm = allLabels.includes("Childcare arrangements");
  const allBigKids =
    isCostForm &&
    featureFlags.noBigKidEstimates &&
    areAllChildrenBigKids(formData.children);

  let subtitle: string;
  if (hasInvalid) {
    subtitle =
      "Some answers need updating after your changes. Update them below, then continue.";
  } else if (hasUncompleted) {
    subtitle =
      "We've kept your previous answers. Review them below, then continue to the remaining questions.";
  } else {
    subtitle =
      "You've answered all the questions. Review your answers below, or continue to see your results.";
  }

  return (
    <div>
      {onReset && (
        <button
          onClick={onReset}
          className="flex items-center gap-1 text-base font-bold text-neutral-700 hover:text-neutral-600 mb-6 transition-colors"
        >
          <span aria-hidden="true">&larr;</span> Start again from the beginning
        </button>
      )}
      <h2 className="text-[27px] md:text-[31px] xl:text-[36px] font-bold mb-2">
        Your answers so far
      </h2>
      <p className="text-base text-zinc-600 mb-6">{subtitle}</p>

      <div className="bg-white rounded-xl border border-zinc-200 p-6">
        {allLabels.map((label, i) => {
          const stepNumber = i + 1;
          const isInvalid = invalidLabels.includes(label);
          const isCompleted = completedLabels.includes(label);

          if (!isCompleted && !isInvalid) return null;

          return (
            <StepSummaryRow
              key={label}
              label={label}
              stepNumber={stepNumber}
              onEdit={onEdit}
              isInvalid={isInvalid}
            >
              {isInvalid ? (
                <p className="text-amber-700">
                  Needs updating — your earlier changes affected this step
                </p>
              ) : (
                <StepAnswerSummary label={label} formData={formData} />
              )}
            </StepSummaryRow>
          );
        })}
      </div>

      {allBigKids && (
        <p className="mt-6 text-base text-zinc-600">
          Unfortunately, we can&rsquo;t provide a cost estimate for older
          children at the moment. We don't currently have reliable average cost
          data for children aged 5 and over. You should contact childcare
          providers directly to see how much they charge.
        </p>
      )}

      <div className="mt-8 flex flex-col items-start gap-3">
        <button
          onClick={onContinue}
          className={`btn-dark${allBigKids ? " opacity-50 cursor-not-allowed" : ""}`}
          disabled={allBigKids}
        >
          {hasUncompleted || hasInvalid ? "Continue" : "Show results"}{" "}
          <span aria-hidden="true">&rarr;</span>
        </button>
        {allBigKids && (
          <>
            <button
              onClick={() => navigate("/support/results#main-content")}
              className="btn"
            >
              See your support options <span aria-hidden="true">&rarr;</span>
            </button>
            <button
              onClick={() => navigate("/providers#main-content")}
              className="btn"
            >
              Search for childcare providers{" "}
              <span aria-hidden="true">&rarr;</span>
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function StepAnswerSummary({
  label,
  formData,
}: {
  label: string;
  formData: FormLocalStorageData;
}) {
  switch (label) {
    case "Where you live":
      return <p>{normalisePostcode(formData.location.postcode)}</p>;

    case "Living situation":
      return (
        <p>
          {formData.household.hasPartner === null
            ? "Not answered"
            : formData.household.hasPartner
              ? "Lives with a partner"
              : "Single parent"}
        </p>
      );

    case "Immigration status":
      return (
        <div className="space-y-1 text-base">
          <p>
            <span className="font-bold">You:</span>{" "}
            {immigrationLabel(formData.user)}
          </p>
          {formData.partner && (
            <p>
              <span className="font-bold">Partner:</span>{" "}
              {immigrationLabel(formData.partner)}
            </p>
          )}
        </div>
      );

    case "Working situation":
      return (
        <div className="space-y-1 text-base">
          <p>
            <span className="font-bold">You:</span>{" "}
            {workingLabel(formData.user)}
          </p>
          {formData.partner && (
            <p>
              <span className="font-bold">Partner:</span>{" "}
              {workingLabel(formData.partner)}
            </p>
          )}
        </div>
      );

    case "Benefits": {
      const benefits = formData.qualifyingBenefits ?? [];
      const benefitLabels: Record<string, string> = {
        universal_credit: "Universal Credit",
        pension_credit: "Pension Credit (guaranteed element)",
        esa: "Income-related ESA",
        none: "None",
      };
      const hasUC = benefits.includes("universal_credit");
      const startingWork: string[] = [];
      if (hasUC && formData.user.startingWorkNextMonth) {
        startingWork.push(formData.partner ? "You" : "You");
      }
      if (hasUC && formData.partner?.startingWorkNextMonth) {
        startingWork.push("Your partner");
      }
      const lcw: string[] = [];
      if (hasUC && formData.user.hasLimitedCapacityForWork) {
        lcw.push(formData.partner ? "You" : "You");
      }
      if (hasUC && formData.partner?.hasLimitedCapacityForWork) {
        lcw.push("Your partner");
      }
      return (
        <div className="space-y-1 text-base">
          {benefits.length === 0 ? (
            <p>Not answered</p>
          ) : (
            <p>{benefits.map((b) => benefitLabels[b] || b).join(", ")}</p>
          )}
          {startingWork.map((label) => (
            <p key={label}>
              <span className="font-bold">{label}:</span> Starting work within a
              month
            </p>
          ))}
          {lcw.map((label) => (
            <p key={`lcw-${label}`}>
              <span className="font-bold">{label}:</span> Limited capacity for
              work (LCW/LCWRA)
            </p>
          ))}
        </div>
      );
    }

    case "Your children":
      if (formData.children.length === 0)
        return <p className="text-zinc-600">No children added</p>;
      return (
        <div className="space-y-1 text-base">
          {formData.children.map((c) => (
            <p key={c.id}>
              <span className="font-bold">{c.firstName}:</span>{" "}
              {c.birthMonth !== null ? monthNames[c.birthMonth] : "?"}{" "}
              {c.birthYear ?? "?"}
              {(() => {
                const sendTag = c.hasSEND
                  ? c.sendDetails
                    ? [
                        c.sendDetails.receivesDLA && "DLA",
                        c.sendDetails.receivesPIP && "PIP",
                        c.sendDetails.isRegisteredBlind && "registered blind",
                      ]
                        .filter(Boolean)
                        .join(", ") || "disability or SEN"
                    : "disability or SEN"
                  : null;
                const tags = [
                  sendTag,
                  c.isFostered && "fostered",
                  c.hasEHCP && "EHCP",
                  c.hasLeftCareForAdoptionOrSpecialGuardianship &&
                    "care leaver",
                ].filter(Boolean);
                return tags.length > 0 ? (
                  <span className="ml-2">({tags.join(", ")})</span>
                ) : null;
              })()}
            </p>
          ))}
          {(formData.qualifyingBenefits ?? []).includes("universal_credit") &&
            formData.ucIncomeBelowThreshold !== null && (
              <p className="mt-1">
                UC household income below £15,400:{" "}
                {formData.ucIncomeBelowThreshold ? "Yes" : "No"}
              </p>
            )}
          {formData.user.residencyStatus === "no_recourse_to_public_funds" &&
            (!formData.partner ||
              formData.partner.residencyStatus ===
                "no_recourse_to_public_funds") &&
            formData.nrpfIncomeUnderThreshold !== null && (
              <>
                <p className="mt-1">
                  Household income below £
                  {formData.nrpfIncomeUnderThreshold > 0
                    ? `${formData.nrpfIncomeUnderThreshold.toLocaleString()}: Yes`
                    : "threshold: No"}
                </p>
                <p className="mt-1">
                  Savings below £16,000:{" "}
                  {formData.nrpfSavingsUnderLimit != null &&
                  formData.nrpfSavingsUnderLimit > 0
                    ? "Yes"
                    : "No"}
                </p>
              </>
            )}
        </div>
      );

    case "Childcare arrangements":
      return (
        <div className="space-y-2 text-base">
          {formData.children.map((c) => {
            if (c.childcareSelections.length === 0) return null;
            return (
              <div key={c.id}>
                <span className="font-bold">{c.firstName}:</span>{" "}
                {c.childcareSelections.map((s, i) => {
                  const label = careTypeLabel(s.careType);
                  const parts: string[] = [];
                  const morningDays = s.sessions?.morning?.daysPerWeek;
                  const afternoonDays = s.sessions?.afternoon?.daysPerWeek;
                  if (morningDays != null && morningDays > 0) {
                    parts.push(
                      `${morningDays} morning${morningDays !== 1 ? "s" : ""}`,
                    );
                  }
                  if (afternoonDays != null && afternoonDays > 0) {
                    parts.push(
                      `${afternoonDays} afternoon${afternoonDays !== 1 ? "s" : ""}`,
                    );
                  }
                  if (s.weeksPerYear != null) {
                    parts.push(`${s.weeksPerYear} weeks per year`);
                  }
                  if (s.sessionHours) {
                    const fmt = (v: number) => {
                      const h = Math.floor(v);
                      const m = Math.round((v - h) * 60);
                      if (m === 0) return `${h}h`;
                      if (h === 0) return `${m}min`;
                      return `${h}h ${m}min`;
                    };
                    if (s.sessionHours.morning != null)
                      parts.push(
                        `${fmt(s.sessionHours.morning)} morning sessions`,
                      );
                    if (s.sessionHours.afternoon != null)
                      parts.push(
                        `${fmt(s.sessionHours.afternoon)} afternoon sessions`,
                      );
                  }
                  const text =
                    parts.length > 0 ? `${label}, ${parts.join(", ")}` : label;
                  return (
                    <span key={i}>
                      {i > 0 ? "; " : ""}
                      {text}
                    </span>
                  );
                })}
              </div>
            );
          })}
        </div>
      );

    default:
      return <p className="text-zinc-600">Completed</p>;
  }
}

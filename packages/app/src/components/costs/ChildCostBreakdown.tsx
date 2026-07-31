import type {
  CostSelection,
  ChildCostData,
  ChildData,
  ChildcareSelection,
  FeeSource,
} from "@bsil/calculator";
import { formatAge } from "@/lib/childAge";
import { formatHoursMinutes } from "@/lib/formatHours";

const careTypeLabels: Record<string, string> = {
  private_nursery: "Nursery",
  school_based_nursery: "School-based nursery",
  childminder: "Childminder",
  breakfast_club: "Breakfast club",
  free_breakfast_club: "Free breakfast club",
  after_school_club: "After school club",
  holiday_club: "Holiday club",
};

export function careTypeLabel(type: string): string {
  return careTypeLabels[type] ?? type.replace(/_/g, " ");
}

interface ChildCostBreakdownProps {
  childData: ChildCostData;
  inputChild: ChildData;
  isUC: boolean;
  period: "yearly" | "monthly";
}

function formatMoney(value: number | undefined | null): string {
  if (typeof value === "number") {
    return (
      "£" +
      value.toLocaleString("en-GB", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      })
    );
  }
  return "-";
}

function pluralise(n: number, singular: string, plural?: string): string {
  return n === 1 ? singular : (plural ?? singular + "s");
}

function buildAttendanceSummary(
  input: ChildcareSelection | undefined,
  weeksPerYear?: number,
  sessionHours?: { morning: number; afternoon: number; fullDay?: number },
): string | null {
  if (!input) return null;
  const parts: string[] = [];

  if (input.sessions) {
    const { morning, afternoon, fullDay } = input.sessions;
    const sessionParts: string[] = [];
    if (fullDay?.daysPerWeek) {
      sessionParts.push(
        `${fullDay.daysPerWeek} full ${pluralise(fullDay.daysPerWeek, "day")}`,
      );
    }
    if (morning?.daysPerWeek) {
      sessionParts.push(
        `${morning.daysPerWeek} ${pluralise(morning.daysPerWeek, "morning")}`,
      );
    }
    if (afternoon?.daysPerWeek) {
      sessionParts.push(
        `${afternoon.daysPerWeek} ${pluralise(afternoon.daysPerWeek, "afternoon")}`,
      );
    }
    if (sessionParts.length > 0) {
      let weeklyHoursStr = "";
      if (sessionHours) {
        const hours =
          (fullDay?.daysPerWeek ?? 0) * (sessionHours.fullDay ?? 0) +
          (morning?.daysPerWeek ?? 0) * sessionHours.morning +
          (afternoon?.daysPerWeek ?? 0) * sessionHours.afternoon;
        if (hours > 0) weeklyHoursStr = ` (${formatHoursMinutes(hours)})`;
      }
      parts.push(sessionParts.join(" and ") + " per week" + weeklyHoursStr);
    }
  }

  if (input.hoursPerWeek) {
    parts.push(`${input.hoursPerWeek} hours per week`);
  }

  if (input.daysPerWeek && !input.sessions) {
    parts.push(
      `${input.daysPerWeek} ${pluralise(input.daysPerWeek, "day")} per week`,
    );
  }

  const weeks = input.weeksPerYear ?? weeksPerYear;
  if (weeks) {
    parts.push(`${weeks} weeks per year`);
  }

  if (input.daysPerYear) {
    parts.push(
      `${input.daysPerYear} ${pluralise(input.daysPerYear, "day")} per year`,
    );
  }

  if (parts.length === 0) return null;

  // Join with commas and "for" before the duration
  if (parts.length === 1) return parts[0];
  const attendance = parts.slice(0, -1).join(", ");
  return `${attendance}, for ${parts[parts.length - 1]}`;
}

function areaAverageLabel(feeSource: FeeSource): string {
  switch (feeSource.costArea) {
    case "region":
      return `Regional average for ${feeSource.regionName ?? "your region"}`;
    case "national":
      return `National average for ${feeSource.nationName ?? "England"}`;
    case "insufficient":
      return "Estimated average (limited local data)";
    default:
      return `Local average for ${feeSource.laName ?? "your area"}`;
  }
}

export function areaExplanation(feeSource: FeeSource): string {
  switch (feeSource.costArea) {
    case "region":
      return `There was insufficient local data, so we have used regional averages for ${feeSource.regionName ?? "your region"}.`;
    case "national":
      return `There was insufficient local or regional data, so we have used national averages for ${feeSource.nationName ?? "England"}.`;
    case "insufficient":
      return "There was limited data available, so these figures should be treated as rough estimates.";
    default:
      return `We have sufficient data to calculate averages for ${feeSource.laName ?? "your area"}.`;
  }
}

function SelectionCard({
  sel,
  inputChild,
  period,
}: {
  sel: CostSelection;
  inputChild: ChildData;
  period: "yearly" | "monthly";
}) {
  const d = period === "monthly" ? 12 : 1;
  const calc = sel.calculation;
  const { feeSource } = sel;
  const id = sel.selectionId;
  const inputSel = inputChild.childcareSelections.find(
    (s) => s.id === sel.selectionId,
  );
  const attendanceSummary = buildAttendanceSummary(
    inputSel,
    sel.weeksPerYear,
    feeSource.sessionHours,
  );
  const selTotal =
    (calc.step1_childcareFees.total -
      (calc.step3_fundedHoursReduction?.savingToParent ?? 0) +
      calc.step4_additionalCharges.total) /
    d;
  const hasBreakdown =
    !!calc.step3_fundedHoursReduction || calc.step4_additionalCharges.total > 0;

  return (
    <div
      className="bg-zinc-50 rounded-lg p-4 border border-zinc-200"
      data-testid={`selection-card-${id}`}
    >
      <span className="text-xs font-bold uppercase text-purple-800 bg-purple-50 px-2 py-0.5 rounded">
        {careTypeLabel(sel.careType ?? "")}
      </span>
      <p className="text-sm font-bold text-zinc-700 mt-1">
        {feeSource.type === "provider"
          ? feeSource.providerName
          : areaAverageLabel(feeSource)}
      </p>
      {(attendanceSummary || feeSource.rates) && (
        <p className="text-xs text-zinc-500 mt-0.5 max-w-prose">
          {[attendanceSummary, feeSource.rates ? `at ${feeSource.rates}` : null]
            .filter(Boolean)
            .join(", ")}
        </p>
      )}

      {hasBreakdown ? (
        <div className="mt-3 text-sm text-zinc-600 space-y-1 border-t border-zinc-200 pt-2">
          <div className="flex justify-between gap-2">
            <span>Childcare fees</span>
            <span data-testid={`sel-${id}-childcare-fees`}>
              {formatMoney(calc.step1_childcareFees.total / d)}
            </span>
          </div>
          {calc.step3_fundedHoursReduction && (
            <div className="flex justify-between gap-2 text-green-700">
              <span>
                Funded hours
                <span className="block text-xs text-zinc-600">
                  {calc.step3_fundedHoursReduction.scheme} (
                  {Math.min(38, sel.weeksPerYear)} weeks per year)
                </span>
              </span>
              <span
                className="shrink-0 whitespace-nowrap"
                data-testid={`sel-${id}-funded-hours`}
              >
                -
                {formatMoney(
                  calc.step3_fundedHoursReduction.savingToParent / d,
                )}
              </span>
            </div>
          )}
          {calc.step4_additionalCharges.total > 0 && (
            <div className="flex justify-between gap-2">
              <span>
                Additional charges
                {calc.step4_additionalCharges.estimated && (
                  <span className="block text-xs text-zinc-600 max-w-prose">
                    Additional charges such as meals are typically charged per
                    day, and we have estimated attendance days from the hours
                    you entered. Actual costs may vary.
                  </span>
                )}
              </span>
              <span className="shrink-0" data-testid={`sel-${id}-additional`}>
                {formatMoney(calc.step4_additionalCharges.total / d)}
              </span>
            </div>
          )}
          <div className="flex justify-between gap-2 font-semibold border-t border-zinc-200 pt-1 mt-1">
            <span>Provider cost</span>
            <span data-testid={`sel-${id}-total`}>{formatMoney(selTotal)}</span>
          </div>
        </div>
      ) : (
        <div className="mt-3 border-t border-zinc-200 pt-2">
          <div
            className={`flex justify-between gap-2 text-sm font-semibold ${selTotal === 0 ? "text-green-700" : "text-zinc-600"}`}
          >
            <span>Provider cost</span>
            <span data-testid={`sel-${id}-total`}>{formatMoney(selTotal)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function getAllSelections(childData: ChildCostData): CostSelection[] {
  return [
    ...(childData.selections ?? []),
    ...(childData.termTimeCare?.selections ?? []),
    ...(childData.yearRoundCare?.selections ?? []),
  ];
}

export function ChildCostBreakdown({
  childData,
  inputChild,
  isUC,
  period,
}: ChildCostBreakdownProps) {
  if (!childData) return null;

  const d = period === "monthly" ? 12 : 1;
  const { total } = childData;
  const allSelections = getAllSelections(childData);

  const name = childData.child;

  return (
    <div
      className="bg-white rounded-xl border border-zinc-200 p-6 mb-6"
      data-testid={`child-breakdown-${name}`}
    >
      <h2 className="font-bold text-xl mb-4 capitalize">
        For {name} ({formatAge(inputChild.birthMonth, inputChild.birthYear)})
      </h2>

      {/* Selection cards */}
      <div className="space-y-3">
        {allSelections.map((sel, i) => (
          <SelectionCard
            key={i}
            sel={sel}
            inputChild={inputChild}
            period={period}
          />
        ))}
      </div>

      {/* Child cost summary */}
      <div className="mt-4 pt-3 text-zinc-600 space-y-1 px-4">
        <div className="flex justify-between gap-2 text-sm">
          <span>{name}&apos;s subtotal</span>
          <span data-testid={`child-${name}-subtotal`}>
            {formatMoney((total.grossCost - total.support.fundedHours) / d)}
          </span>
        </div>
        {allSelections.some((s) => s.careType === "free_breakfast_club") && (
          <div className="flex justify-between gap-2 text-sm text-green-700">
            <span>Free breakfast club</span>
            <span>{formatMoney(0)}</span>
          </div>
        )}
        {total.support.taxFreeChildcare > 0 && (
          <div className="flex justify-between gap-2 text-sm text-green-700">
            <span>Tax-Free Childcare</span>
            <span
              className="whitespace-nowrap"
              data-testid={`child-${name}-tfc`}
              aria-label={`minus ${formatMoney(total.support.taxFreeChildcare / d)}`}
            >
              −{formatMoney(total.support.taxFreeChildcare / d)}
            </span>
          </div>
        )}
        {total.support.ucChildcare > 0 && (
          <div className="flex justify-between gap-2 text-sm text-green-700">
            <span>Universal Credit childcare</span>
            <span
              className="whitespace-nowrap"
              data-testid={`child-${name}-uc`}
              aria-label={`minus ${formatMoney(total.support.ucChildcare / d)}`}
            >
              −{formatMoney(total.support.ucChildcare / d)}
            </span>
          </div>
        )}
        <div className="flex justify-between gap-2 text-base font-semibold border-t border-zinc-200 pt-1 mt-1">
          <span>Estimated cost to family</span>
          <span data-testid={`child-${name}-cost-to-family`}>
            {formatMoney(total.costToFamily / d)}
          </span>
        </div>
        {isUC && total.support.ucChildcare > 0 && (
          <p className="text-xs text-zinc-600 mt-1 max-w-prose">
            UC support is a family-level benefit — amounts shown per child are
            indicative
          </p>
        )}
      </div>
    </div>
  );
}

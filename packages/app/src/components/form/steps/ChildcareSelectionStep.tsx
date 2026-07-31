import { useState, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import type { FormLocalStorageData, FormChildData } from "@/types/formData";
import { resolveFormData } from "@/types/formData";
import type { ChildcareSelection, CareTypeId } from "@/types/family";
import type { Provider, ProviderCareType } from "@/types/provider";
import type { Scheme } from "@/types/scheme";
import { calculateEntitlements } from "@bsil/calculator";
import { resolveTemplate } from "@/lib/resolveTemplate";
import { useFamily } from "@/hooks/useFamily";
import { featureFlags } from "@/hooks/useFeatureFlags";
import { FormStep } from "@/components/ui/FormStep";
import { RadioGroup } from "@/components/ui/RadioGroup";
import { TextInput } from "@/components/ui/TextInput";
import { ValidationWrapper } from "@/components/ui/ValidationWrapper";
import { Explainer } from "@/components/ui/Explainer";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { scrollToFirstError } from "@/lib/scrollToFirstError";
import { normalisePostcode } from "@/lib/postcode";
import { formatHoursMinutes } from "@/lib/formatHours";
import { BIG_KID_MONTHS } from "@/lib/childAge";

interface Props {
  formData: FormLocalStorageData;
  updateFormData: (patch: Partial<FormLocalStorageData>) => void;
  onContinue: () => void;
  onBack: () => void;
}

const careTypeLabels: Record<CareTypeId, string> = {
  private_nursery: "Nursery (Private, Voluntary or Independent)",
  school_based_nursery: "School-based nursery",
  childminder: "Childminder",
  breakfast_club: "Breakfast club",
  free_breakfast_club: "Free breakfast club",
  after_school_club: "After school club",
  holiday_club: "Holiday club",
};

function getAgeMonths(child: FormChildData): number {
  const now = new Date();
  return (
    (now.getFullYear() - (child.birthYear ?? now.getFullYear())) * 12 +
    (now.getMonth() + 1 - (child.birthMonth ?? 1))
  );
}

function getAvailableCareTypes(child: FormChildData): CareTypeId[] {
  const ageMonths = getAgeMonths(child);
  const types: CareTypeId[] = [];

  if (ageMonths < 60) {
    types.push("private_nursery");
    if (ageMonths >= 24) types.push("school_based_nursery");
    types.push("childminder");
  }
  if (ageMonths >= 48) {
    types.push(
      "breakfast_club",
      "free_breakfast_club",
      "after_school_club",
      "holiday_club",
    );
    types.push("childminder");
  }

  return [...new Set(types)];
}

const INESTIMABLE_CARE_TYPES: CareTypeId[] = [
  "breakfast_club",
  "free_breakfast_club",
  "after_school_club",
  "holiday_club",
];

function getFilteredCareTypes(
  child: FormChildData,
  noBigKidEstimates: boolean,
): CareTypeId[] {
  const types = getAvailableCareTypes(child);
  if (!noBigKidEstimates) return types;
  return types.filter((t) => !INESTIMABLE_CARE_TYPES.includes(t));
}

/** Find the ProviderCareType entry on a provider that matches a given care type ID */
function findCareTypeEntry(
  provider: Provider,
  careType: CareTypeId,
): ProviderCareType | undefined {
  return provider.careTypes.find((ct) => ct.type === careType);
}

/** Check whether a child's age falls within the provider's age range for a care type */
function childMeetsAgeRange(
  child: FormChildData,
  ct: ProviderCareType,
): boolean {
  const ar = ct.eligibleAgeRange;
  if (!ar) return true;
  const ageMonths = getAgeMonths(child);
  const minMonths = ar.minMonths ?? (ar.minYears ?? 0) * 12;
  const maxMonths = ar.maxYears ? (ar.maxYears + 1) * 12 - 1 : 999;
  return ageMonths >= minMonths && ageMonths <= maxMonths;
}

/**
 * Return a warning reason string if a provider+child+careType combo has issues,
 * or null if everything looks fine.
 */
function getWarningReason(
  child: FormChildData,
  provider: Provider,
  careType: CareTypeId,
): string | null {
  const ct = findCareTypeEntry(provider, careType);
  if (!ct) return "This provider does not list this care type";
  if (
    !ct.eligibleAgeRange &&
    !ct.eligibleAttendeesOnly &&
    (!ct.eligibleOther || ct.eligibleOther.length === 0)
  )
    return "No eligibility requirements specified — check with provider";
  if (!childMeetsAgeRange(child, ct)) {
    const ar = ct.eligibleAgeRange;
    if (ar) {
      const minMonths = ar.minMonths ?? (ar.minYears ?? 0) * 12;
      const minLabel =
        minMonths >= 12
          ? `${Math.floor(minMonths / 12)} years`
          : `${minMonths} months`;
      const maxLabel = ar.maxYears != null ? `${ar.maxYears} years` : "";
      const rangeStr = maxLabel ? `${minLabel} to ${maxLabel}` : `${minLabel}+`;
      return `Child's age is outside this provider's range (${rangeStr})`;
    }
  }
  return null;
}

function parseNum(value: string): number | undefined {
  if (value === "") return undefined;
  const n = Number(value);
  if (isNaN(n)) return undefined;
  return n;
}

function getFieldError(
  value: number | undefined,
  min: number,
  max: number,
): string | null {
  if (value === undefined) return null;
  if (value < min || value > max)
    return `Enter a number between ${min} and ${max}`;
  return null;
}

function getSubmitFieldError(
  value: number | undefined,
  min: number,
  max: number,
): string | null {
  if (value === undefined) return `Enter a number between ${min} and ${max}`;
  return getFieldError(value, min, max);
}

function hasInvalidFields(children: FormChildData[]): boolean {
  for (const child of children) {
    for (const sel of child.childcareSelections) {
      const ct = sel.careType;
      if (ct === "private_nursery" || ct === "school_based_nursery") {
        const m = sel.sessions?.morning?.daysPerWeek;
        const a = sel.sessions?.afternoon?.daysPerWeek;
        if (getSubmitFieldError(m, 0, 7) || getSubmitFieldError(a, 0, 7))
          return true;
        if (
          sel.weeksPerYear !== undefined &&
          getSubmitFieldError(sel.weeksPerYear, 1, 52)
        )
          return true;
        if (sel.sessionHours) {
          const mHours = sel.sessionHours.morning;
          const aHours = sel.sessionHours.afternoon;
          if (mHours !== undefined && (mHours <= 0 || mHours > 12)) return true;
          if (aHours !== undefined && (aHours <= 0 || aHours > 12)) return true;
        }
      } else if (ct === "childminder") {
        if (
          getSubmitFieldError(sel.hoursPerWeek, 0, 168) ||
          getSubmitFieldError(sel.weeksPerYear, 0, 52)
        )
          return true;
      } else if (ct === "holiday_club") {
        if (getSubmitFieldError(sel.daysPerYear, 0, 365)) return true;
      } else {
        if (getSubmitFieldError(sel.daysPerWeek, 0, 7)) return true;
      }
    }
  }
  return false;
}

function isZeroUsage(selection: ChildcareSelection): boolean {
  const ct = selection.careType;
  if (ct === "private_nursery" || ct === "school_based_nursery") {
    const m = selection.sessions?.morning?.daysPerWeek;
    const a = selection.sessions?.afternoon?.daysPerWeek;
    if (m === undefined && a === undefined) return false;
    return (m ?? 0) === 0 && (a ?? 0) === 0;
  }
  if (ct === "childminder") {
    return selection.hoursPerWeek !== undefined && selection.hoursPerWeek === 0;
  }
  if (ct === "holiday_club") {
    return selection.daysPerYear !== undefined && selection.daysPerYear === 0;
  }
  return selection.daysPerWeek !== undefined && selection.daysPerWeek === 0;
}

function SessionDurationInputs({
  idPrefix,
  selection,
  sessionHours,
  showErrors,
  hasMorningSessions,
  hasAfternoonSessions,
  onChange,
}: {
  idPrefix: string;
  selection: ChildcareSelection;
  sessionHours?: { morning?: number; afternoon?: number };
  showErrors: boolean;
  hasMorningSessions: boolean;
  hasAfternoonSessions: boolean;
  onChange: (s: ChildcareSelection) => void;
}) {
  const morningDecimal =
    selection.sessionHours?.morning ?? sessionHours?.morning;
  const afternoonDecimal =
    selection.sessionHours?.afternoon ?? sessionHours?.afternoon;

  const mSplit =
    morningDecimal != null
      ? splitHoursMinutes(morningDecimal)
      : { hours: undefined, minutes: undefined };
  const aSplit =
    afternoonDecimal != null
      ? splitHoursMinutes(afternoonDecimal)
      : { hours: undefined, minutes: undefined };

  const morningError = getSessionHoursError(
    mSplit.hours,
    mSplit.minutes,
    hasMorningSessions,
  );
  const morningSubmitError = getSessionHoursSubmitError(
    mSplit.hours,
    mSplit.minutes,
    hasMorningSessions,
  );
  const afternoonError = getSessionHoursError(
    aSplit.hours,
    aSplit.minutes,
    hasAfternoonSessions,
  );
  const afternoonSubmitError = getSessionHoursSubmitError(
    aSplit.hours,
    aSplit.minutes,
    hasAfternoonSessions,
  );

  function updateMorning(
    hours: number | undefined,
    minutes: number | undefined,
  ) {
    const val = combineHoursMinutes(hours, minutes);
    onChange({
      ...selection,
      sessionHours: { ...selection.sessionHours, morning: val },
    });
  }

  function updateAfternoon(
    hours: number | undefined,
    minutes: number | undefined,
  ) {
    const val = combineHoursMinutes(hours, minutes);
    onChange({
      ...selection,
      sessionHours: { ...selection.sessionHours, afternoon: val },
    });
  }

  return (
    <div className="space-y-3">
      <ValidationWrapper
        error={showErrors && !!morningSubmitError}
        message={morningSubmitError ?? undefined}
      >
        <label className="block text-sm font-bold">
          Morning session duration
        </label>
        <div className="flex items-center gap-2 mt-1.5">
          <TextInput
            id={`${idPrefix}-morning-hours`}
            type="number"
            min="0"
            max="12"
            placeholder="0"
            className={`w-16 ${morningError && !showErrors ? "!border-red-600 !border-2 !outline-none ring-2 ring-red-600" : ""}`}
            value={mSplit.hours ?? ""}
            onFocus={(e) => e.currentTarget.select()}
            onChange={(e) =>
              updateMorning(parseNum(e.currentTarget.value), mSplit.minutes)
            }
          />
          <span className="text-sm text-zinc-600">hours</span>
          <TextInput
            id={`${idPrefix}-morning-minutes`}
            type="number"
            min="0"
            max="59"
            placeholder="0"
            className={`w-16 ${morningError && !showErrors ? "!border-red-600 !border-2 !outline-none ring-2 ring-red-600" : ""}`}
            value={mSplit.minutes || ""}
            onFocus={(e) => e.currentTarget.select()}
            onChange={(e) =>
              updateMorning(mSplit.hours, parseNum(e.currentTarget.value))
            }
          />
          <span className="text-sm text-zinc-600">minutes</span>
        </div>
      </ValidationWrapper>
      <ValidationWrapper
        error={showErrors && !!afternoonSubmitError}
        message={afternoonSubmitError ?? undefined}
      >
        <label className="block text-sm font-bold">
          Afternoon session duration
        </label>
        <div className="flex items-center gap-2 mt-1.5">
          <TextInput
            id={`${idPrefix}-afternoon-hours`}
            type="number"
            min="0"
            max="12"
            placeholder="0"
            className={`w-16 ${afternoonError && !showErrors ? "!border-red-600 !border-2 !outline-none ring-2 ring-red-600" : ""}`}
            value={aSplit.hours ?? ""}
            onFocus={(e) => e.currentTarget.select()}
            onChange={(e) =>
              updateAfternoon(parseNum(e.currentTarget.value), aSplit.minutes)
            }
          />
          <span className="text-sm text-zinc-600">hours</span>
          <TextInput
            id={`${idPrefix}-afternoon-minutes`}
            type="number"
            min="0"
            max="59"
            placeholder="0"
            className={`w-16 ${afternoonError && !showErrors ? "!border-red-600 !border-2 !outline-none ring-2 ring-red-600" : ""}`}
            value={aSplit.minutes || ""}
            onFocus={(e) => e.currentTarget.select()}
            onChange={(e) =>
              updateAfternoon(aSplit.hours, parseNum(e.currentTarget.value))
            }
          />
          <span className="text-sm text-zinc-600">minutes</span>
        </div>
      </ValidationWrapper>
    </div>
  );
}

function splitHoursMinutes(decimal: number): {
  hours: number;
  minutes: number;
} {
  const hours = Math.floor(decimal);
  const minutes = Math.round((decimal - hours) * 60);
  return { hours, minutes };
}

function combineHoursMinutes(
  hours: number | undefined,
  minutes: number | undefined,
): number | undefined {
  if (hours === undefined && minutes === undefined) return undefined;
  return (hours ?? 0) + (minutes ?? 0) / 60;
}

function getSessionHoursError(
  hours: number | undefined,
  minutes: number | undefined,
  hasDays: boolean,
): string | null {
  if (!hasDays) return null;
  if (hours !== undefined && (hours < 0 || hours > 12))
    return "Hours must be between 0 and 12";
  if (minutes !== undefined && (minutes < 0 || minutes > 59))
    return "Minutes must be between 0 and 59";
  const total = combineHoursMinutes(hours, minutes);
  if (total !== undefined && total <= 0)
    return "Duration must be greater than 0";
  if (total !== undefined && total > 12)
    return "Duration must be 12 hours or less";
  return null;
}

function getSessionHoursSubmitError(
  hours: number | undefined,
  minutes: number | undefined,
  hasDays: boolean,
): string | null {
  if (!hasDays) return null;
  if (hours === undefined && minutes === undefined)
    return "Enter a session duration";
  return getSessionHoursError(hours, minutes, hasDays);
}

function SelectionConfig({
  selection,
  onChange,
  showErrors,
  idPrefix,
  sessionHours,
}: {
  selection: ChildcareSelection;
  onChange: (s: ChildcareSelection) => void;
  showErrors: boolean;
  idPrefix: string;
  sessionHours?: { morning?: number; afternoon?: number; fullDay?: number };
}) {
  const [customWeeks, setCustomWeeks] = useState(
    selection.weeksPerYear !== undefined ||
      selection.sessionHours !== undefined,
  );
  const ct = selection.careType;
  const zeroUsage = isZeroUsage(selection);

  if (ct === "private_nursery" || ct === "school_based_nursery") {
    const morningError = getFieldError(
      selection.sessions?.morning?.daysPerWeek,
      0,
      7,
    );
    const morningSubmitError = getSubmitFieldError(
      selection.sessions?.morning?.daysPerWeek,
      0,
      7,
    );
    const afternoonError = getFieldError(
      selection.sessions?.afternoon?.daysPerWeek,
      0,
      7,
    );
    const afternoonSubmitError = getSubmitFieldError(
      selection.sessions?.afternoon?.daysPerWeek,
      0,
      7,
    );
    const weeksError = customWeeks
      ? getFieldError(selection.weeksPerYear, 1, 52)
      : null;
    const weeksSubmitError = customWeeks
      ? getSubmitFieldError(selection.weeksPerYear, 1, 52)
      : null;

    const morningInput = (
      <TextInput
        id={`${idPrefix}-morning`}
        type="number"
        min="0"
        max="7"
        placeholder="Enter a number"
        className={
          morningError && !showErrors
            ? "!border-red-600 !border-2 !outline-none ring-2 ring-red-600"
            : ""
        }
        value={selection.sessions?.morning?.daysPerWeek ?? ""}
        onChange={(e) => {
          const v = parseNum(e.currentTarget.value);
          onChange({
            ...selection,
            sessions: {
              ...selection.sessions,
              morning: v !== undefined ? { daysPerWeek: v } : undefined,
            },
          });
        }}
      />
    );

    const afternoonInput = (
      <TextInput
        id={`${idPrefix}-afternoon`}
        type="number"
        min="0"
        max="7"
        placeholder="Enter a number"
        className={
          afternoonError && !showErrors
            ? "!border-red-600 !border-2 !outline-none ring-2 ring-red-600"
            : ""
        }
        value={selection.sessions?.afternoon?.daysPerWeek ?? ""}
        onChange={(e) => {
          const v = parseNum(e.currentTarget.value);
          onChange({
            ...selection,
            sessions: {
              ...selection.sessions,
              afternoon: v !== undefined ? { daysPerWeek: v } : undefined,
            },
          });
        }}
      />
    );

    const defaultWeeks = ct === "school_based_nursery" ? 38 : 50;

    return (
      <div className="space-y-4">
        <div className="space-y-4">
          <ValidationWrapper
            error={showErrors && !!morningSubmitError}
            message={morningSubmitError ?? undefined}
          >
            <label
              htmlFor={`${idPrefix}-morning`}
              className="block text-sm font-bold"
            >
              Morning sessions per week
            </label>
            <div className="grid grid-cols-2 items-center gap-3 mt-1.5">
              <div>{morningInput}</div>
              {(selection.sessionHours?.morning ?? sessionHours?.morning) !=
                null && (
                <p className="text-sm text-zinc-500">
                  Morning sessions are{" "}
                  {formatHoursMinutes(
                    selection.sessionHours?.morning ?? sessionHours!.morning!,
                  )}{" "}
                  long
                </p>
              )}
            </div>
          </ValidationWrapper>
          <ValidationWrapper
            error={showErrors && !!afternoonSubmitError}
            message={afternoonSubmitError ?? undefined}
          >
            <label
              htmlFor={`${idPrefix}-afternoon`}
              className="block text-sm font-bold"
            >
              Afternoon sessions per week
            </label>
            <div className="grid grid-cols-2 items-center gap-3 mt-1.5">
              <div>{afternoonInput}</div>
              {(selection.sessionHours?.afternoon ?? sessionHours?.afternoon) !=
                null && (
                <p className="text-sm text-zinc-500">
                  Afternoon sessions are{" "}
                  {formatHoursMinutes(
                    selection.sessionHours?.afternoon ??
                      sessionHours!.afternoon!,
                  )}{" "}
                  long
                </p>
              )}
            </div>
          </ValidationWrapper>
        </div>
        <RadioGroup
          name={`weeks-${idPrefix}`}
          options={[
            {
              value: "default",
              label:
                ct === "school_based_nursery"
                  ? "For 38 weeks per year (term-time only)"
                  : "For 50 weeks per year (year-round)",
            },
            { value: "custom", label: "Custom" },
          ]}
          value={customWeeks ? "custom" : "default"}
          onChange={(v) => {
            const isCustom = v === "custom";
            setCustomWeeks(isCustom);
            if (isCustom) {
              onChange({
                ...selection,
                weeksPerYear: defaultWeeks,
                sessionHours: {
                  morning: sessionHours?.morning,
                  afternoon: sessionHours?.afternoon,
                },
              });
            } else {
              onChange({
                ...selection,
                weeksPerYear: undefined,
                sessionHours: undefined,
              });
            }
          }}
        />
        {customWeeks && (
          <div className="ml-6 border-l-2 border-zinc-200 pl-5 space-y-4">
            <ValidationWrapper
              error={showErrors && !!weeksSubmitError}
              message={weeksSubmitError ?? undefined}
            >
              <TextInput
                id={`${idPrefix}-weeks`}
                label="Weeks per year"
                type="number"
                min="1"
                max="52"
                placeholder="Enter a number"
                className={
                  weeksError && !showErrors
                    ? "!border-red-600 !border-2 !outline-none ring-2 ring-red-600"
                    : ""
                }
                value={selection.weeksPerYear ?? ""}
                onChange={(e) =>
                  onChange({
                    ...selection,
                    weeksPerYear: parseNum(e.currentTarget.value),
                  })
                }
              />
            </ValidationWrapper>
            <SessionDurationInputs
              idPrefix={idPrefix}
              selection={selection}
              sessionHours={sessionHours}
              showErrors={showErrors}
              hasMorningSessions={
                (selection.sessions?.morning?.daysPerWeek ?? 0) > 0
              }
              hasAfternoonSessions={
                (selection.sessions?.afternoon?.daysPerWeek ?? 0) > 0
              }
              onChange={onChange}
            />
          </div>
        )}
        {zeroUsage && (
          <p className="text-sm text-amber-700 mt-1">
            This has zero usage — it won&apos;t affect your estimate
          </p>
        )}
      </div>
    );
  }

  if (ct === "childminder") {
    const hoursError = getFieldError(selection.hoursPerWeek, 0, 168);
    const hoursSubmitError = getSubmitFieldError(
      selection.hoursPerWeek,
      0,
      168,
    );
    const weeksError = getFieldError(selection.weeksPerYear, 0, 52);
    const weeksSubmitError = getSubmitFieldError(selection.weeksPerYear, 0, 52);

    const hoursInput = (
      <TextInput
        id={`${idPrefix}-hours`}
        label="Hours per week"
        type="number"
        min="0"
        max="168"
        placeholder="Enter a number"
        className={
          hoursError && !showErrors
            ? "!border-red-600 !border-2 !outline-none ring-2 ring-red-600"
            : ""
        }
        value={selection.hoursPerWeek ?? ""}
        onChange={(e) =>
          onChange({
            ...selection,
            hoursPerWeek: parseNum(e.currentTarget.value),
          })
        }
      />
    );

    const weeksInput = (
      <TextInput
        id={`${idPrefix}-weeks`}
        label="Weeks per year"
        type="number"
        min="0"
        max="52"
        placeholder="For example: 38"
        className={
          weeksError && !showErrors
            ? "!border-red-600 !border-2 !outline-none ring-2 ring-red-600"
            : ""
        }
        value={selection.weeksPerYear ?? ""}
        onChange={(e) =>
          onChange({
            ...selection,
            weeksPerYear: parseNum(e.currentTarget.value),
          })
        }
      />
    );

    return (
      <div>
        <div className="grid grid-cols-2 gap-3 mt-2">
          <ValidationWrapper
            error={showErrors && !!hoursSubmitError}
            message={hoursSubmitError ?? undefined}
          >
            {hoursInput}
          </ValidationWrapper>
          <ValidationWrapper
            error={showErrors && !!weeksSubmitError}
            message={weeksSubmitError ?? undefined}
          >
            {weeksInput}
          </ValidationWrapper>
        </div>
        {zeroUsage && (
          <p className="text-sm text-amber-700 mt-1">
            This has zero usage — it won&apos;t affect your estimate
          </p>
        )}
      </div>
    );
  }

  if (ct === "holiday_club") {
    const daysError = getFieldError(selection.daysPerYear, 0, 365);
    const daysSubmitError = getSubmitFieldError(selection.daysPerYear, 0, 365);

    const daysInput = (
      <TextInput
        id={`${idPrefix}-days`}
        label="Days per year"
        type="number"
        min="0"
        max="365"
        placeholder="Enter a number"
        className={
          daysError && !showErrors
            ? "!border-red-600 !border-2 !outline-none ring-2 ring-red-600"
            : ""
        }
        value={selection.daysPerYear ?? ""}
        onChange={(e) =>
          onChange({
            ...selection,
            daysPerYear: parseNum(e.currentTarget.value),
          })
        }
      />
    );

    return (
      <div className="mt-2">
        <ValidationWrapper
          error={showErrors && !!daysSubmitError}
          message={daysSubmitError ?? undefined}
        >
          {daysInput}
        </ValidationWrapper>
        {zeroUsage && (
          <p className="text-sm text-amber-700 mt-1">
            This has zero usage — it won&apos;t affect your estimate
          </p>
        )}
      </div>
    );
  }

  // breakfast_club, after_school_club, free_breakfast_club
  const daysError = getFieldError(selection.daysPerWeek, 0, 7);
  const daysSubmitError = getSubmitFieldError(selection.daysPerWeek, 0, 7);

  const daysInput = (
    <TextInput
      id={`${idPrefix}-days`}
      label="Days per week"
      type="number"
      min="0"
      max="7"
      placeholder="Enter a number"
      className={
        daysError && !showErrors
          ? "!border-red-600 !border-2 !outline-none ring-2 ring-red-600"
          : ""
      }
      value={selection.daysPerWeek ?? ""}
      onChange={(e) =>
        onChange({
          ...selection,
          daysPerWeek: parseNum(e.currentTarget.value),
        })
      }
    />
  );

  return (
    <div className="mt-2">
      <ValidationWrapper
        error={showErrors && !!daysSubmitError}
        message={daysSubmitError ?? undefined}
      >
        {daysInput}
      </ValidationWrapper>
      {zeroUsage && (
        <p className="text-sm text-amber-700 mt-1">
          This has zero usage — it won&apos;t affect your estimate
        </p>
      )}
    </div>
  );
}

export function ChildcareSelectionStep({
  formData,
  updateFormData,
  onContinue,
  onBack,
}: Props) {
  const navigate = useNavigate();
  const { shortlistedProviders, getProviderById, schemes, areaCosts } =
    useFamily();
  const { noBigKidEstimates, noProviderEstimates } = featureFlags;
  const shortlistedProviderObjects = shortlistedProviders
    .map((id) => getProviderById(id))
    .filter((p): p is Provider => p !== undefined);
  const children = formData.children;
  const [noSelectionsError, setNoSelectionsError] = useState(false);
  const [usageErrors, setUsageErrors] = useState(false);
  const pendingFocusSelection = useRef<number | null>(null);
  const childCardRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  const isBigKid = (child: FormChildData) =>
    noBigKidEstimates && getAgeMonths(child) >= BIG_KID_MONTHS;
  const hasBigKids = children.some(isBigKid);
  const allBigKids = children.length > 0 && children.every(isBigKid);

  // When flag is on, show small kids first (in entry order), then big kids
  const sortedChildren = useMemo(() => {
    if (!noBigKidEstimates) return children;
    const isOlder = (c: FormChildData) => getAgeMonths(c) >= BIG_KID_MONTHS;
    const small = children.filter((c) => !isOlder(c));
    const big = children.filter((c) => isOlder(c));
    return [...small, ...big];
  }, [children, noBigKidEstimates]);

  // Compute scheme entitlements for big kids using the same pipeline as SupportResults
  const entitlementResult = useMemo(() => {
    if (!noBigKidEstimates || !hasBigKids || schemes.length === 0) return null;
    try {
      const resolved = resolveFormData(formData);
      return calculateEntitlements(resolved, schemes, new Date());
    } catch {
      return null;
    }
  }, [formData, schemes, noBigKidEstimates, hasBigKids]);

  function getEligibleSchemesForChild(childId: number): Scheme[] {
    if (!entitlementResult) return [];
    const childResult = entitlementResult.children.find(
      (c) => c.childId === childId,
    );
    if (!childResult) return [];
    return childResult.schemes
      .filter((s) => s.eligible)
      .map((s) => schemes.find((sc) => sc.id === s.schemeId))
      .filter((s): s is Scheme => s !== undefined);
  }

  const handleContinue = () => {
    const estimatableChildren = noBigKidEstimates
      ? children.filter((c) => getAgeMonths(c) < BIG_KID_MONTHS)
      : children;

    const hasAny = estimatableChildren.some(
      (c) => c.childcareSelections.length > 0,
    );
    if (!hasAny) {
      setNoSelectionsError(true);
      scrollToFirstError();
      return;
    }
    if (hasInvalidFields(estimatableChildren)) {
      setUsageErrors(true);
      scrollToFirstError();
      return;
    }
    setUsageErrors(false);
    onContinue();
  };

  const updateChildSelections = (
    childIndex: number,
    selections: ChildcareSelection[],
  ) => {
    const updated = children.map((c, i) =>
      i === childIndex ? { ...c, childcareSelections: selections } : c,
    );
    updateFormData({ children: updated });
  };

  const addSelection = (childIndex: number) => {
    setNoSelectionsError(false);
    const child = children[childIndex];
    const available = getFilteredCareTypes(child, noBigKidEstimates);
    const existingTypes = child.childcareSelections.map((s) => s.careType);
    const nextType =
      available.find((t) => !existingTypes.includes(t)) || available[0];
    const newId =
      child.childcareSelections.length > 0
        ? Math.max(...child.childcareSelections.map((s) => s.id)) + 1
        : 1;

    pendingFocusSelection.current = childIndex;
    requestAnimationFrame(() => {
      if (pendingFocusSelection.current != null) {
        const card = childCardRefs.current.get(pendingFocusSelection.current);
        if (card) {
          const selections = card.querySelectorAll<HTMLElement>(
            "[data-selection-card]",
          );
          const last = selections[selections.length - 1];
          last?.querySelector<HTMLInputElement>("input")?.focus();
        }
        pendingFocusSelection.current = null;
      }
    });
    updateChildSelections(childIndex, [
      ...child.childcareSelections,
      { id: newId, careType: nextType, providerId: null },
    ]);
  };

  const removeSelection = (childIndex: number, selIndex: number) => {
    const updated = children[childIndex].childcareSelections.filter(
      (_, i) => i !== selIndex,
    );
    updateChildSelections(childIndex, updated);
  };

  return (
    <>
      <FormStep
        title="Childcare arrangements"
        onContinue={handleContinue}
        onBack={onBack}
        continueLabel="Show your cost estimate"
        continueDisabled={allBigKids}
        secondaryAction={
          hasBigKids ? (
            <>
              <button
                onClick={() => {
                  updateFormData(formData);
                  navigate("/support/results#main-content");
                }}
                className="btn"
              >
                See your support options <span aria-hidden="true">&rarr;</span>
              </button>
              {allBigKids && (
                <button
                  onClick={() => {
                    updateFormData(formData);
                    navigate("/providers#main-content");
                  }}
                  className="btn"
                >
                  Search for childcare providers{" "}
                  <span aria-hidden="true">&rarr;</span>
                </button>
              )}
            </>
          ) : undefined
        }
        footer={
          <>
            <Explainer label="Can I choose the number of weeks per year?">
              <p>
                Not all childcare providers operate for the same number of weeks
                per year. The default we show depends on the average for that
                type of provider:
              </p>
              <ul className="list-disc pl-5 space-y-2">
                <li>
                  <strong>
                    Private, voluntary or independent (PVI) nurseries
                  </strong>{" "}
                  &mdash; typically open year-round, around 50 weeks per year.
                  Check with your provider what arrangements are available.
                </li>
                <li>
                  <strong>School-based nurseries</strong> &mdash; usually
                  operate during term time only (38 weeks per year). Check with
                  your provider to see if they offer provision in school
                  holidays.
                </li>
                <li>
                  <strong>Childminders</strong> &mdash; vary widely. Many work
                  around 44&ndash;50 weeks per year, but this depends on your
                  individual arrangement with them.
                </li>
              </ul>
              <p>
                If your provider offers a different number of weeks (for example
                44 or 48), select &ldquo;Custom&rdquo; and enter the number of
                weeks they require you to pay for.
              </p>
              <p>
                If you&rsquo;re unsure how many weeks your provider operates,
                check with them directly. The weeks a provider offers may vary
                for accessing the funded childcare hours.
              </p>
            </Explainer>
            <Explainer label="Can I choose the number of hours per week?">
              <p>
                Different types of childcare charge in different ways, so the
                form asks for the length of childcare in a way that matches how
                providers of that type would usually bill you.
              </p>
              <p className="font-bold">
                Session durations used in your estimate
              </p>
              <p>
                Not all childcare providers operate for the same session
                duration. The default we show depends on the average for that
                type of provider. These durations affect how we convert
                session-based fees into comparable hourly or monthly cost
                estimates.
              </p>
              {areaCosts && (
                <ul className="list-disc pl-5 space-y-2">
                  {(() => {
                    const sh =
                      areaCosts.averageCosts.private_nursery?.sessionHours;
                    if (!sh) return null;
                    return (
                      <li>
                        <strong>Nursery</strong>
                        <ul className="list-disc pl-5 space-y-1 mt-1">
                          {sh.morning != null && (
                            <li>Morning: {formatHoursMinutes(sh.morning)}</li>
                          )}
                          {sh.afternoon != null && (
                            <li>
                              Afternoon: {formatHoursMinutes(sh.afternoon)}
                            </li>
                          )}
                        </ul>
                      </li>
                    );
                  })()}
                  {(() => {
                    const sh =
                      areaCosts.averageCosts.school_based_nursery?.sessionHours;
                    if (!sh || (!sh.morning && !sh.afternoon)) return null;
                    return (
                      <li>
                        <strong>School nursery</strong>
                        <ul className="list-disc pl-5 space-y-1 mt-1">
                          {sh.morning != null && (
                            <li>Morning: {formatHoursMinutes(sh.morning)}</li>
                          )}
                          {sh.afternoon != null && (
                            <li>
                              Afternoon: {formatHoursMinutes(sh.afternoon)}
                            </li>
                          )}
                        </ul>
                      </li>
                    );
                  })()}
                  {(() => {
                    const sh =
                      areaCosts.averageCosts.breakfast_club?.sessionHours;
                    if (!sh?.session) return null;
                    return (
                      <li>
                        <strong>Breakfast club</strong>
                        <ul className="list-disc pl-5 space-y-1 mt-1">
                          <li>Session: {formatHoursMinutes(sh.session)}</li>
                        </ul>
                      </li>
                    );
                  })()}
                  {(() => {
                    const sh =
                      areaCosts.averageCosts.after_school_club?.sessionHours;
                    if (!sh?.session) return null;
                    return (
                      <li>
                        <strong>After school club</strong>
                        <ul className="list-disc pl-5 space-y-1 mt-1">
                          <li>Session: {formatHoursMinutes(sh.session)}</li>
                        </ul>
                      </li>
                    );
                  })()}
                  {(() => {
                    const sh =
                      areaCosts.averageCosts.holiday_club?.sessionHours;
                    if (!sh?.day) return null;
                    return (
                      <li>
                        <strong>Holiday club</strong>
                        <ul className="list-disc pl-5 space-y-1 mt-1">
                          <li>Day: {formatHoursMinutes(sh.day)}</li>
                        </ul>
                      </li>
                    );
                  })()}
                </ul>
              )}
              <p>
                If your provider offers a different number of hours per session
                (for example 5 hours 30 minutes or 3 hours), select "Custom" and
                enter the number of hours and minutes they require you to pay
                for.
              </p>
              <p>
                Always confirm the hours offered and the way sessions are
                arranged directly with your provider. These may vary for funded
                childcare hours and a provider's paid-for offer.
              </p>
            </Explainer>
            <Explainer label="How are cost estimates calculated?">
              <p>
                We estimate what you would pay for childcare after government
                support has been applied. Here is how it works:
              </p>
              <ul className="list-disc pl-5 space-y-2">
                {!noProviderEstimates && (
                  <li>
                    <strong>Shortlisted provider</strong> — if you have selected
                    a specific provider from your shortlist, we use their actual
                    published fees.
                  </li>
                )}
                <li>
                  <strong>Average costs</strong> —{" "}
                  {noProviderEstimates
                    ? "we use average childcare costs from the DfE Early Years Childcare Provider Survey (2025) to estimate what you might pay in your area."
                    : "if no provider is selected, we use the average childcare costs for your postcode area, based on data from local providers."}
                </li>
                {noProviderEstimates && (
                  <>
                    <li>
                      <strong>Cost range</strong> — we show you a range of
                      estimates to give you an idea of how much your actual
                      childcare costs might vary from our estimate.
                    </li>
                    <li>
                      <strong>Older children</strong> — at the moment we only
                      have average costs for early years childcare.
                    </li>
                  </>
                )}
                <li>
                  <strong>Funded hours</strong> — any government-funded hours
                  your child is eligible for (15 or 30 hours per week for 38
                  weeks of the year) are deducted automatically, reducing the
                  total cost. You will need to speak to your provider to
                  understand their availability of funded hours.
                </li>
                <li>
                  <strong>Tax-Free Childcare</strong> — if eligible, the
                  government&apos;s 20% top-up is applied (for every £8 you pay,
                  the government adds £2, up to £2,000 per child per year).
                </li>
                <li>
                  <strong>Universal Credit childcare</strong> — if eligible, we
                  show the maximum 85% reimbursement that could be included in
                  your Universal Credit payment.
                </li>
              </ul>
              <p>
                The estimate is a guide based on the information you have
                provided. Actual costs may vary depending on your provider and
                exact circumstances.
              </p>
              <div className="pt-2 space-y-1">
                <p>
                  <ExternalLink
                    href="https://beststartinlife.gov.uk/childcare-early-years-education/tax-free-childcare/how-it-works/"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    How Tax-Free Childcare works
                  </ExternalLink>
                </p>
                <p>
                  <ExternalLink
                    href="https://beststartinlife.gov.uk/childcare-early-years-education/universal-credit-childcare/how-universal-credit-childcare-works/"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    How Universal Credit childcare works
                  </ExternalLink>
                </p>
              </div>
            </Explainer>
          </>
        }
      >
        <p className="text-base text-zinc-600">
          {allBigKids
            ? "Although we can\u2019t create a cost estimate for your children, you may still be eligible for government benefits and you can still check our database of childcare providers."
            : "For each child, select the types of childcare they use and configure the hours or sessions."}
        </p>

        {noSelectionsError && (
          <p
            role="alert"
            data-error-field
            className="text-base text-white bg-red-600 rounded-md px-4 py-2"
          >
            Add at least one childcare type to get a cost estimate
          </p>
        )}

        {sortedChildren.map((child) => {
          // Use original index in children array for mutations
          const childIdx = children.indexOf(child);
          const available = getFilteredCareTypes(child, noBigKidEstimates);
          const childName = child.firstName;
          const ageMonths = getAgeMonths(child);
          const years = Math.floor(ageMonths / 12);
          const months = ageMonths % 12;
          const ageParts = [];
          if (years > 0)
            ageParts.push(`${years} year${years !== 1 ? "s" : ""}`);
          if (months > 0)
            ageParts.push(`${months} month${months !== 1 ? "s" : ""}`);

          return (
            <div
              key={child.id}
              ref={(el) => {
                if (el) childCardRefs.current.set(childIdx, el);
              }}
              className="bg-white rounded-xl p-6 border border-zinc-200 space-y-4"
            >
              <h3 className="font-bold text-lg">
                {childName} ({ageParts.join(", ")} old)
              </h3>

              {isBigKid(child) ? (
                <div className="space-y-3">
                  <p className="text-sm text-zinc-700">
                    We can&apos;t estimate childcare costs for{" "}
                    <strong>{childName}</strong> yet. We don&apos;t currently
                    have reliable average cost data for children aged 5 and
                    over. You&apos;ll need to get costs directly from your
                    childcare providers.
                  </p>
                  {(() => {
                    const eligibleSchemes = getEligibleSchemesForChild(
                      child.id,
                    );
                    if (eligibleSchemes.length > 0) {
                      return (
                        <>
                          <p className="text-sm text-zinc-700">
                            However, <strong>{childName}</strong> may still be
                            eligible for a range of government support:
                          </p>
                          <ul className="list-disc pl-5 space-y-1">
                            {eligibleSchemes.map((scheme) => (
                              <li
                                key={scheme.id}
                                className="text-sm text-zinc-700"
                              >
                                <strong>{scheme.name}</strong> &mdash;{" "}
                                {resolveTemplate(
                                  scheme.description,
                                  scheme.defaultDescriptionParams,
                                )}
                              </li>
                            ))}
                          </ul>
                        </>
                      );
                    }
                    return null;
                  })()}
                </div>
              ) : (
                <>
                  {child.childcareSelections.map((sel, selIdx) => {
                    const matchingProviders = shortlistedProviderObjects.filter(
                      (p) => p.careTypes.some((ct) => ct.type === sel.careType),
                    );
                    const selectedProvider = matchingProviders.find(
                      (p) => p.id === sel.providerId,
                    );
                    const warningReason = selectedProvider
                      ? getWarningReason(child, selectedProvider, sel.careType)
                      : null;

                    return (
                      <div
                        key={sel.id}
                        data-selection-card
                        className="border border-zinc-200 rounded-lg p-4 space-y-4"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-lg">
                            Type of care
                          </span>
                          <button
                            onClick={() => removeSelection(childIdx, selIdx)}
                            className="text-sm text-red-600 hover:text-red-800 font-medium underline hover:no-underline"
                            aria-label={`Remove ${careTypeLabels[sel.careType]} for ${childName}`}
                          >
                            Remove
                          </button>
                        </div>
                        <RadioGroup
                          name={`care-type-${child.id}-${sel.id}`}
                          options={available.map((t) => ({
                            value: t,
                            label: careTypeLabels[t],
                          }))}
                          value={sel.careType}
                          onChange={(value) => {
                            const updated = [...child.childcareSelections];
                            updated[selIdx] = {
                              id: sel.id,
                              careType: value as CareTypeId,
                              providerId: null,
                            };
                            updateChildSelections(childIdx, updated);
                          }}
                        />
                        {ageMonths >= 9 && ageMonths < 24 && (
                          <p className="text-sm text-zinc-600 bg-zinc-50 border border-zinc-200 rounded-lg px-3 py-2">
                            A school-based nursery might also accept your child,
                            but we don&apos;t yet have enough data to give you a
                            cost estimate.
                          </p>
                        )}

                        {!noProviderEstimates && (
                          <div>
                            <label
                              htmlFor={`provider-select-${child.id}-${sel.id}`}
                              className="block text-sm font-bold mb-1.5"
                            >
                              Select shortlisted provider
                            </label>
                            <select
                              id={`provider-select-${child.id}-${sel.id}`}
                              value={sel.providerId ?? ""}
                              onChange={(e) => {
                                if (e.target.value === "__shortlist__") {
                                  navigate("/providers#main-content");
                                  return;
                                }
                                const updated = [...child.childcareSelections];
                                updated[selIdx] = {
                                  ...sel,
                                  providerId: e.target.value || null,
                                };
                                updateChildSelections(childIdx, updated);
                              }}
                              className="w-full border-2 border-neutral-700 bg-white text-neutral-700 rounded-lg px-4 py-3 text-base"
                            >
                              <option value="">
                                Use average costs for{" "}
                                {normalisePostcode(formData.location.postcode)}
                              </option>
                              {matchingProviders.map((p) => {
                                const reason = getWarningReason(
                                  child,
                                  p,
                                  sel.careType,
                                );
                                return (
                                  <option key={p.id} value={p.id}>
                                    {reason ? "\u26A0 " : ""}
                                    {p.name}
                                  </option>
                                );
                              })}
                              <option value="__shortlist__">
                                Shortlist childcare providers →
                              </option>
                            </select>
                            {warningReason && (
                              <p className="mt-1 text-sm text-yellow-700 flex items-start gap-1.5">
                                <i className="bi bi-exclamation-triangle-fill shrink-0" />
                                <span>{warningReason}</span>
                              </p>
                            )}
                          </div>
                        )}

                        <div className="font-bold text-lg">Length of care</div>
                        <SelectionConfig
                          key={sel.careType}
                          selection={sel}
                          showErrors={usageErrors}
                          idPrefix={`child-${child.id}-sel-${sel.id}`}
                          sessionHours={
                            sel.careType === "private_nursery" ||
                            sel.careType === "school_based_nursery"
                              ? areaCosts?.averageCosts[sel.careType]
                                  ?.sessionHours
                              : undefined
                          }
                          onChange={(updated) => {
                            setUsageErrors(false);
                            const selections = [...child.childcareSelections];
                            selections[selIdx] = updated;
                            updateChildSelections(childIdx, selections);
                          }}
                        />
                      </div>
                    );
                  })}

                  {child.childcareSelections.length === 0 && (
                    <p className="text-sm text-zinc-600">
                      Use the button below to choose the kind of childcare
                      you&apos;d like to use for <strong>{childName}</strong>.
                      You can add more than one type.
                    </p>
                  )}

                  {available.length > 0 && (
                    <button
                      onClick={() => addSelection(childIdx)}
                      className="btn text-sm py-2 px-4"
                    >
                      Add childcare type <span aria-hidden="true">+</span>
                    </button>
                  )}
                </>
              )}
            </div>
          );
        })}
      </FormStep>
    </>
  );
}

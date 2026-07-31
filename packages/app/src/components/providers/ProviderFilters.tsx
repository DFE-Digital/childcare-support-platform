import { useState, useRef, useMemo, useEffect } from "react";
import { Link } from "react-router-dom";
import type { FormChildData } from "@/types/formData";
import { useLastInputWasKeyboard } from "@/hooks/useLastInputWasKeyboard";
import type {
  AverageCostsCareType,
  CostTriad,
  CostArea,
  PostcodeAreaCosts,
} from "@/types/costs";
import { Modal } from "@/components/ui/Modal";
import { featureFlags } from "@/hooks/useFeatureFlags";

const { showFees, showFundedHoursFilter } = featureFlags;

const providerTypeDescriptions: Record<string, string> = {
  private_nursery:
    "These nurseries are delivered by a wide range of providers, including private companies, charities, social enterprises, community groups and sole traders. They typically offer places for children from around 3 months old up to school age (4 to 5). They typically open from around 7:00am to 6:00pm, year-round (usually 50 to 51 weeks), making them a popular choice for working parents who need longer hours and holiday cover. Opening times do not necessarily represent when entitlements hours can be accessed so you will need to speak to individual providers to understand what availability they have.",
  school_based_nursery:
    "These include school-based nurseries (nurseries attached to primary schools) and maintained nursery schools (local authority-maintained schools that specialise in places particularly for those from disadvantaged backgrounds and often delivering specialist SEND and family support) usually take children from aged 2 to 4, but some also cater for children under 2. Opening hours are normally aligned with the school day, although wraparound care may also be offered as well as holiday provision. They can either be run directly by the school or operated by private or voluntary providers on the school site.",
  childminder:
    "Childminders are self-employed early years professionals who provide places, from birth to 8 years old (and sometimes older school-age children), traditionally in their own home. Childminders play an important role in the early education system, with a flexible, personalised offer that many families value. They tend to have smaller groups of children, which some parents prefer. Their availability may differ for when entitlements hours can be accessed so you will need to speak to individual childminders to understand their offer.",
  breakfast_club:
    "Breakfast clubs run at, or in the vicinity of, primary schools before the school day starts, typically from around 7:30am or 8:00am until school begins. Your child gets breakfast (usually cereal, toast, fruit) and may have access to supervised activities, free play and 'quiet' time or reading time. They're usually only available to children who attend that school. Some schools offer free breakfast clubs as part of a government initiative. These clubs operate for a minimum of 30minutes, directly before the school day starts, to offer children a 'soft start' to their day   — check with your school. Breakfast clubs are a practical option, if you need to start work before the school day begins.",
  after_school_club:
    "After school clubs provide childcare from the end of the school day (around 3:15pm) until early evening, usually 5:30pm or 6:00pm. Children are given a snack and can usually take part in supervised activities, free play, or have homework or reading time.  Like breakfast clubs, they are usually only available to pupils of the host school and run during the 38 term-time weeks only. After school clubs are one of the most common forms of wraparound care for working parents with school-age children, and can be a useful way to help children access enriching activity and play, and to socialise with friends and peers.",
  holiday_club:
    "Holiday clubs (sometimes called holiday camps or playschemes) provide childcare during school holidays. They're available for school-age children, typically from age 4 up to around 14. Hours vary — some run a full day (8am to 6pm), others just mornings or afternoons. Activities range from sports and arts to trips and themed weeks, whilst some can be focused on free play. Availability can be mixed: not every area has holiday clubs for every week of the holidays, and popular ones fill up quickly. You'll typically need to book and pay in advance, often week by week or for individual days.",
};

const ageBandLabels: Record<string, string> = {
  under2: "Under 2",
  age2: "Age 2",
  age2plus: "Age 2+",
  age3to4: "Age 3 to 4",
  all: "",
};

function formatCurrency(value: number): string {
  return `\u00A3${value.toFixed(2)}`;
}

function extractCost(cost: number | CostTriad): number {
  return typeof cost === "number" ? cost : cost.mean;
}

function buildCostLines(
  _careType: string,
  data: AverageCostsCareType,
): { label: string; value: string }[] {
  const lines: { label: string; value: string }[] = [];
  const fees = data.fees;

  if (fees) {
    for (const [band, rates] of Object.entries(fees)) {
      const triad = rates?.perHour;
      if (!triad) continue;
      const bandLabel = ageBandLabels[band] || band;
      if (triad.lower > 0 && triad.upper > 0 && triad.lower !== triad.upper) {
        lines.push({
          label: bandLabel || "Per hour",
          value: `${formatCurrency(triad.lower)} to ${formatCurrency(triad.upper)} per\u00A0hour`,
        });
      } else {
        lines.push({
          label: bandLabel || "Per hour",
          value:
            triad.mean > 0
              ? `${formatCurrency(triad.mean)} per\u00A0hour`
              : "Free",
        });
      }
    }
  }

  return lines;
}

function buildExtras(data: AverageCostsCareType): string[] {
  const extras: string[] = [];
  if (data.operatingWeeksPerYear) {
    extras.push(
      data.operatingWeeksPerYear === 38
        ? "Term time only — 38 weeks per year"
        : `Typically open ${data.operatingWeeksPerYear} weeks per year`,
    );
  }
  if (data.additionalCharges) {
    for (const charge of data.additionalCharges) {
      const costValue = extractCost(charge.cost);
      if (costValue > 0) {
        extras.push(
          `${charge.item}: around ${formatCurrency(costValue)} ${charge.unit} (${charge.description})`,
        );
      }
    }
  }
  return extras;
}

export type CostDisplayMode = "hourly" | "monthly" | "detailed";

import { sortOptions, sortDescriptions, type SortOption } from "./sortOptions";
export type { SortOption } from "./sortOptions";

interface ProviderFiltersProps {
  selectedTypes: string[];
  onTypesChange: (types: string[]) => void;
  selectedChildren: string[];
  onChildrenChange: (children: string[]) => void;
  children: FormChildData[];
  shortlistedOnly: boolean;
  onShortlistedOnlyChange: (value: boolean) => void;
  shortlistedCount: number;
  isOpen: boolean;
  onToggle: () => void;
  costDisplayMode: CostDisplayMode;
  onCostDisplayModeChange: (mode: CostDisplayMode) => void;
  includeAdditionalCharges: boolean;
  onIncludeAdditionalChargesChange: (value: boolean) => void;
  sortBy: SortOption;
  onSortByChange: (sort: SortOption) => void;
  fundedHoursOnly: boolean;
  onFundedHoursOnlyChange: (value: boolean) => void;
  postcode: string;
  areaCosts?: PostcodeAreaCosts | null;
  toolbarMode?: boolean;
}

const providerTypes = [
  {
    value: "private_nursery",
    label: "Nursery (Private, Voluntary or Independent)",
  },
  { value: "school_based_nursery", label: "School-based nursery" },
  { value: "childminder", label: "Childminder" },
  { value: "breakfast_club", label: "Breakfast club" },
  { value: "after_school_club", label: "After school club" },
  { value: "holiday_club", label: "Holiday club" },
];

export function ProviderFilters({
  selectedTypes,
  onTypesChange,
  selectedChildren,
  onChildrenChange,
  children: childrenData,
  shortlistedOnly,
  onShortlistedOnlyChange,
  shortlistedCount,
  isOpen,
  onToggle,
  costDisplayMode,
  onCostDisplayModeChange,
  includeAdditionalCharges,
  onIncludeAdditionalChargesChange,
  sortBy,
  onSortByChange,
  fundedHoursOnly,
  onFundedHoursOnlyChange,
  postcode,
  areaCosts,
  toolbarMode = false,
}: ProviderFiltersProps) {
  const [infoType, setInfoType] = useState<string | null>(null);
  const [caveatModal, setCaveatModal] = useState<string | null>(null);
  const infoButtonRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [activeInfoIdx, setActiveInfoIdx] = useState(0);
  const [toolbarFocused, setToolbarFocused] = useState(false);
  const [infoButtonCount, setInfoButtonCount] = useState(1);
  const lastInputWasKeyboard = useLastInputWasKeyboard();

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const count = infoButtonRefs.current.filter(Boolean).length;
    if (count > 0 && count !== infoButtonCount) setInfoButtonCount(count);
  });

  const safeActiveIdx = Math.min(activeInfoIdx, infoButtonCount - 1);
  let renderCounter = 0;

  const nextInfoButton = (baseClassName: string) => {
    const idx = renderCounter++;
    const isActive = toolbarMode && toolbarFocused && idx === safeActiveIdx;
    return {
      ref: (el: HTMLButtonElement | null) => {
        infoButtonRefs.current[idx] = el;
      },
      tabIndex: toolbarMode ? (idx === safeActiveIdx ? 0 : -1) : undefined,
      className: isActive
        ? `${baseClassName} ring-2 ring-blue-500 ring-offset-1 rounded-full`
        : baseClassName,
    };
  };

  const handleToolbarKeyDown = (e: React.KeyboardEvent) => {
    const buttons = infoButtonRefs.current.filter(
      (b): b is HTMLButtonElement => b != null,
    );
    if (!buttons.length) return;
    const clamped = Math.min(activeInfoIdx, buttons.length - 1);
    let next = clamped;
    switch (e.key) {
      case "ArrowDown":
      case "ArrowRight":
        e.preventDefault();
        next = (clamped + 1) % buttons.length;
        break;
      case "ArrowUp":
      case "ArrowLeft":
        e.preventDefault();
        next = (clamped - 1 + buttons.length) % buttons.length;
        break;
      case "Home":
        e.preventDefault();
        next = 0;
        break;
      case "End":
        e.preventDefault();
        next = buttons.length - 1;
        break;
      default:
        return;
    }
    setActiveInfoIdx(next);
    setToolbarFocused(true);
    buttons[next]?.focus();
  };

  const inputTabIndex = toolbarMode ? -1 : undefined;

  const infoData = useMemo(() => {
    if (!infoType) return null;
    const careData = areaCosts?.averageCosts[infoType] as
      | AverageCostsCareType
      | undefined;
    const areas: CostArea[] = [];
    if (careData?.fees) {
      for (const band of Object.values(careData.fees)) {
        const a = band?.perHour?.area;
        if (a && !areas.includes(a)) areas.push(a);
      }
    }
    return {
      description: providerTypeDescriptions[infoType] || "",
      costLines: careData ? buildCostLines(infoType, careData) : [],
      extras: careData ? buildExtras(careData) : [],
      laName: areaCosts?.laName,
      lastUpdated: areaCosts?.lastUpdated,
      costAreas: areas,
    };
  }, [infoType, areaCosts]);

  const toggleType = (type: string) => {
    if (selectedTypes.includes(type)) {
      onTypesChange(selectedTypes.filter((t) => t !== type));
    } else {
      onTypesChange([...selectedTypes, type]);
    }
  };

  const toggleChild = (name: string) => {
    if (selectedChildren.includes(name)) {
      onChildrenChange(selectedChildren.filter((c) => c !== name));
    } else {
      onChildrenChange([...selectedChildren, name]);
    }
  };

  return (
    <div>
      <button
        onClick={onToggle}
        tabIndex={inputTabIndex}
        className="lg:hidden btn text-sm py-2 px-4 mb-4 w-full"
      >
        {isOpen ? "Hide filters" : "Show filters"}
      </button>

      <div
        className={`${isOpen ? "block" : "hidden"} lg:block`}
        {...(toolbarMode
          ? {
              role: "toolbar",
              "aria-label": "Filter information",
              onKeyDown: handleToolbarKeyDown,
              onFocus: () => {
                if (!lastInputWasKeyboard.current) return;
                setToolbarFocused(true);
              },
              onBlur: (e: React.FocusEvent) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                  setToolbarFocused(false);
                }
              },
            }
          : {})}
      >
        <div className="bg-white rounded-xl border border-zinc-200 p-5">
          <h3
            className="font-bold text-base mb-4"
            aria-hidden={toolbarMode || undefined}
          >
            Filter results
          </h3>

          <div className="mb-5">
            <div className="flex items-center justify-between">
              <label
                className="flex items-center gap-2 cursor-pointer text-sm"
                aria-hidden={toolbarMode || undefined}
              >
                <input
                  type="checkbox"
                  checked={shortlistedOnly}
                  onChange={() => onShortlistedOnlyChange(!shortlistedOnly)}
                  tabIndex={inputTabIndex}
                  className="w-4 h-4 rounded border-neutral-700 accent-purple-800"
                />
                <span className="font-bold text-purple-800">
                  Shortlisted only
                  {shortlistedCount > 0 && ` (${shortlistedCount})`}
                </span>
              </label>
              <button
                {...nextInfoButton(
                  "shrink-0 w-5 h-5 flex items-center justify-center text-zinc-600 hover:text-zinc-700 transition-colors outline-none",
                )}
                onClick={() => setCaveatModal("shortlisted_only")}
                aria-label="More information about shortlisted only"
              >
                <i className="bi bi-info-circle" />
              </button>
            </div>
          </div>

          <div className="mb-5">
            <h4
              className="font-bold text-sm mb-2"
              aria-hidden={toolbarMode || undefined}
            >
              Providers
            </h4>
            <div className="space-y-2">
              {providerTypes.map((pt) => (
                <div
                  key={pt.value}
                  className="flex items-start justify-between"
                >
                  <label
                    className="flex items-start gap-2 cursor-pointer text-sm"
                    aria-hidden={toolbarMode || undefined}
                  >
                    <input
                      type="checkbox"
                      checked={selectedTypes.includes(pt.value)}
                      onChange={() => toggleType(pt.value)}
                      tabIndex={inputTabIndex}
                      className="w-4 h-4 mt-0.5 shrink-0 rounded border-neutral-700 accent-neutral-700"
                    />
                    {pt.value === "private_nursery" ? (
                      <span>
                        Nursery
                        <span className="block text-xs text-zinc-500">
                          Private, Voluntary or Independent
                        </span>
                      </span>
                    ) : (
                      pt.label
                    )}
                  </label>
                  <button
                    {...nextInfoButton(
                      "shrink-0 w-5 h-5 flex items-center justify-center text-zinc-600 hover:text-zinc-700 transition-colors outline-none",
                    )}
                    onClick={() => setInfoType(pt.value)}
                    aria-label={`More information about ${pt.label}`}
                  >
                    <i className="bi bi-info-circle" />
                  </button>
                </div>
              ))}
              {showFundedHoursFilter && (
                <div className="flex items-center justify-between">
                  <label
                    className="flex items-center gap-2 cursor-pointer text-sm"
                    aria-hidden={toolbarMode || undefined}
                  >
                    <input
                      type="checkbox"
                      checked={fundedHoursOnly}
                      onChange={() => onFundedHoursOnlyChange(!fundedHoursOnly)}
                      tabIndex={inputTabIndex}
                      className="w-4 h-4 rounded border-neutral-700 accent-neutral-700"
                    />
                    Accepts funded hours
                  </label>
                  <button
                    {...nextInfoButton(
                      "shrink-0 w-5 h-5 flex items-center justify-center text-zinc-600 hover:text-zinc-700 transition-colors outline-none",
                    )}
                    onClick={() => setCaveatModal("funded_hours")}
                    aria-label="More information about funded hours"
                  >
                    <i className="bi bi-info-circle" />
                  </button>
                </div>
              )}
            </div>
          </div>

          {childrenData.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4
                  className="font-bold text-sm"
                  aria-hidden={toolbarMode || undefined}
                >
                  Match age range
                </h4>
                <button
                  {...nextInfoButton(
                    "shrink-0 w-5 h-5 flex items-center justify-center text-zinc-600 hover:text-zinc-700 transition-colors outline-none",
                  )}
                  onClick={() => setCaveatModal("match_age_range")}
                  aria-label="More information about match age range"
                >
                  <i className="bi bi-info-circle" />
                </button>
              </div>
              <div className="space-y-2" aria-hidden={toolbarMode || undefined}>
                {childrenData.map((child) => (
                  <label
                    key={child.id}
                    className="flex items-center gap-2 cursor-pointer text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={selectedChildren.includes(child.firstName)}
                      onChange={() => toggleChild(child.firstName)}
                      tabIndex={inputTabIndex}
                      className="w-4 h-4 rounded border-neutral-700 accent-neutral-700"
                    />
                    {(() => {
                      const now = new Date();
                      const ageMonths =
                        (now.getFullYear() - (child.birthYear ?? 0)) * 12 +
                        (now.getMonth() + 1 - (child.birthMonth ?? 0));
                      const years = Math.floor(ageMonths / 12);
                      if (years === 0)
                        return `${child.firstName} (${ageMonths} month${ageMonths !== 1 ? "s" : ""} old)`;
                      return `${child.firstName} (${years} year${years !== 1 ? "s" : ""} old)`;
                    })()}
                  </label>
                ))}
              </div>
            </div>
          )}

          {showFees && (
            <div
              className={childrenData.length > 0 ? "mt-5" : ""}
              aria-hidden={toolbarMode || undefined}
            >
              <h4 className="font-bold text-sm mb-2">Compare costs</h4>
              <div className="space-y-3">
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 cursor-pointer text-sm">
                      <input
                        type="radio"
                        name="costDisplay"
                        checked={costDisplayMode === "hourly"}
                        onChange={() => onCostDisplayModeChange("hourly")}
                        tabIndex={inputTabIndex}
                        className="w-4 h-4 accent-neutral-700"
                      />
                      Show hourly costs
                    </label>
                    {costDisplayMode === "hourly" && (
                      <button
                        {...nextInfoButton(
                          "shrink-0 w-5 h-5 flex items-center justify-center text-zinc-600 hover:text-zinc-700 transition-colors outline-none",
                        )}
                        onClick={() => setCaveatModal("hourly")}
                        aria-label="Caveats about hourly cost comparison"
                      >
                        <i className="bi bi-exclamation-triangle-fill" />
                      </button>
                    )}
                  </div>
                  {costDisplayMode === "hourly" && (
                    <div className="flex items-center justify-between pl-6">
                      <label className="flex items-center gap-2 cursor-pointer text-sm">
                        <input
                          type="checkbox"
                          checked={includeAdditionalCharges}
                          onChange={() =>
                            onIncludeAdditionalChargesChange(
                              !includeAdditionalCharges,
                            )
                          }
                          tabIndex={inputTabIndex}
                          className="w-4 h-4 rounded border-neutral-700 accent-neutral-700"
                        />
                        Additional charges
                      </label>
                      <button
                        {...nextInfoButton(
                          "shrink-0 w-5 h-5 flex items-center justify-center text-zinc-600 hover:text-zinc-700 transition-colors outline-none",
                        )}
                        onClick={() => setCaveatModal("additional")}
                        aria-label="More information about additional charges"
                      >
                        <i className="bi bi-info-circle" />
                      </button>
                    </div>
                  )}
                </div>
                {/* Monthly cost option — temporarily hidden
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 cursor-pointer text-sm">
                      <input
                        type="radio"
                        name="costDisplay"
                        checked={costDisplayMode === "monthly"}
                        onChange={() => onCostDisplayModeChange("monthly")}
                        className="w-4 h-4 accent-neutral-700"
                      />
                      Monthly cost
                    </label>
                    {costDisplayMode === "monthly" && (
                      <button
                        onClick={() => setCaveatModal("monthly")}
                        className="text-zinc-600 hover:text-zinc-700 transition-colors outline-none"
                        aria-label="Caveats about monthly cost comparison"
                      >
                        <i className="bi bi-exclamation-triangle-fill" />
                      </button>
                    )}
                  </div>
                  {costDisplayMode === "monthly" && (
                    <div className="flex items-center justify-between pl-6">
                      <label className="flex items-center gap-2 cursor-pointer text-sm">
                        <input
                          type="checkbox"
                          checked={includeAdditionalCharges}
                          onChange={() =>
                            onIncludeAdditionalChargesChange(
                              !includeAdditionalCharges,
                            )
                          }
                          className="w-4 h-4 rounded border-neutral-700 accent-neutral-700"
                        />
                        Additional charges
                      </label>
                      <button
                        onClick={() => setCaveatModal("additional")}
                        className="text-zinc-600 hover:text-zinc-700 transition-colors outline-none"
                        aria-label="More information about additional charges"
                      >
                        <i className="bi bi-info-circle" />
                      </button>
                    </div>
                  )}
                </div>
                */}
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 cursor-pointer text-sm">
                    <input
                      type="radio"
                      name="costDisplay"
                      checked={costDisplayMode === "detailed"}
                      onChange={() => onCostDisplayModeChange("detailed")}
                      tabIndex={inputTabIndex}
                      className="w-4 h-4 accent-neutral-700"
                    />
                    Show detailed costs
                  </label>
                </div>
              </div>
            </div>
          )}

          <div className="mt-5">
            <div className="flex items-center justify-between mb-2">
              <h4
                className="font-bold text-base"
                aria-hidden={toolbarMode || undefined}
              >
                Sort by
              </h4>
              <button
                {...nextInfoButton(
                  "shrink-0 w-5 h-5 flex items-center justify-center text-zinc-600 hover:text-zinc-700 transition-colors outline-none",
                )}
                onClick={() => setCaveatModal("sort")}
                aria-label="More information about sort options"
              >
                <i className="bi bi-info-circle" />
              </button>
            </div>
            <select
              value={sortBy}
              onChange={(e) => onSortByChange(e.target.value as SortOption)}
              tabIndex={inputTabIndex}
              aria-hidden={toolbarMode || undefined}
              className="w-full border-2 border-neutral-700 bg-white text-neutral-700 rounded-lg px-3 py-2 text-sm"
            >
              {sortOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label.replace("{postcode}", postcode)}
                </option>
              ))}
            </select>
          </div>

          {(selectedTypes.length > 0 ||
            selectedChildren.length > 0 ||
            shortlistedOnly ||
            fundedHoursOnly) && (
            <button
              onClick={() => {
                onTypesChange([]);
                onChildrenChange([]);
                onShortlistedOnlyChange(false);
                onFundedHoursOnlyChange(false);
              }}
              tabIndex={inputTabIndex}
              aria-hidden={toolbarMode || undefined}
              className="mt-4 text-sm text-purple-800 hover:text-purple-700 font-medium"
            >
              Clear all filters
            </button>
          )}
        </div>

        {showFees && (
          <>
            <p className="mt-8 text-sm text-neutral-600">
              If you shortlist some childcare providers, we can give you a more
              accurate estimate of your childcare costs.
            </p>
            <Link
              to="/costs#main-content"
              tabIndex={inputTabIndex}
              className="btn text-sm py-2.5 px-5 mt-4 mx-auto block w-fit"
            >
              Estimate your costs <span aria-hidden="true">&rarr;</span>
            </Link>
          </>
        )}
      </div>

      {caveatModal && (
        <Modal
          onClose={() => setCaveatModal(null)}
          title={
            caveatModal === "additional" ||
            caveatModal === "sort" ||
            caveatModal === "funded_hours" ||
            caveatModal === "match_age_range" ||
            caveatModal === "shortlisted_only" ? (
              <span className="flex items-baseline gap-2">
                <i className="bi bi-info-circle text-zinc-600" />{" "}
                {caveatModal === "shortlisted_only"
                  ? "Shortlisted only"
                  : caveatModal === "match_age_range"
                    ? "Match age range"
                    : caveatModal === "sort"
                      ? "Sort options"
                      : caveatModal === "funded_hours"
                        ? "Government-funded childcare hours"
                        : "Additional charges"}
              </span>
            ) : (
              <span className="flex items-baseline gap-2">
                <i className="bi bi-exclamation-triangle-fill text-yellow-600" />{" "}
                {caveatModal === "hourly"
                  ? "Hourly cost comparison"
                  : "Monthly cost comparison"}
              </span>
            )
          }
        >
          {caveatModal === "hourly" && (
            <div className="text-sm text-zinc-700 leading-relaxed space-y-3">
              <p>
                To help you compare providers, we calculate a standardised
                hourly cost based on a full-time equivalent day. Where a
                provider offers different rates, for example by age of child, we
                show the minimum and maximum hourly cost as a range. If you
                select a &lsquo;Match age range&rsquo; filter for one of your
                children, we&rsquo;ll re-calculate using a fee band which
                matches the age you gave us for that child.
              </p>
              <p>
                However, many providers do not actually charge by the hour.
                Nurseries typically charge per session or per day, as do
                breakfast and after-school clubs, and while childminders
                sometimes do charge by the hour, they may also have minimum
                booking periods. The standardised hourly figure we show may not
                match the rate a provider would quote you directly.
              </p>
              <p>
                Moreover, not all providers offer full-time care, and even those
                that do may have different opening hours. A provider open
                7:30am-6:00pm has a different effective hourly rate from one
                open 8:00am-5:00pm, even if their daily fee is the same.
              </p>
              <p>
                Use the hourly cost to get a rough comparison between providers,
                but check each provider's actual fee structure before making a
                decision.
              </p>
            </div>
          )}

          {caveatModal === "monthly" && (
            <div className="text-sm text-zinc-700 leading-relaxed space-y-3">
              <p>
                To help you compare providers, we calculate a standardised
                monthly cost based on full-time attendance spread evenly across
                12 calendar months. Where a provider offers different rates —
                for example by the age of your child — we show the minimum and
                maximum monthly cost as a range.
              </p>
              <p>
                However, many providers do not actually bill monthly. Nurseries
                typically charge per session or per term, and childminders may
                invoice weekly. The standardised monthly figure we show may not
                match what a provider would actually bill you in any given
                month.
              </p>
              <p>
                Not all providers operate year-round. Some only open during the
                38 school term weeks, while others run for 50 to 51 weeks. Our
                standardised monthly cost is calculated based on a typical month
                of full-time care. However, your real payments throughout the
                year might vary.
              </p>
              <p>
                Use the monthly cost to get a rough comparison between
                providers, but check each provider's actual fee structure before
                making a decision.
              </p>
            </div>
          )}

          {caveatModal === "sort" && (
            <div className="text-sm text-zinc-700 leading-relaxed space-y-4">
              {sortOptions.map((opt) => (
                <div key={opt.value}>
                  <p className="font-medium text-neutral-700 mb-1">
                    {opt.label.replace("{postcode}", "your postcode")}
                  </p>
                  <p>{sortDescriptions[opt.value]}</p>
                </div>
              ))}
            </div>
          )}

          {caveatModal === "additional" && (
            <div className="text-sm text-zinc-700 leading-relaxed space-y-3">
              <p>
                Many childcare providers charge for extras on top of their core
                fees. Common additional charges include:
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>
                  <strong>Meals and snacks</strong> — lunch, breakfast, or
                  afternoon snacks, typically £2.50 to £3.50 per day
                </li>
                <li>
                  <strong>Consumables</strong> — nappies, wipes, sun cream, and
                  art supplies, typically £1 to £3 per week
                </li>
                <li>
                  <strong>Extended hours</strong> — early drop-off or late
                  collection, typically £3 to £5 per session
                </li>
              </ul>
              <p>
                When "Include additional charges" is ticked, we add typical
                additional charges to the cost shown on each provider card. This
                gives a more realistic picture of what you'll actually pay, but
                the exact charges will depend on your child's age, attendance
                pattern, and the provider's specific pricing.
              </p>
              <p>When unticked, you see only the core childcare fee.</p>
            </div>
          )}

          {caveatModal === "match_age_range" && (
            <div className="text-sm text-zinc-700 leading-relaxed space-y-3">
              <p>
                Each checkbox shows a child you have added to your family
                profile, along with their current age. When you tick a child's
                name, the results are filtered to show only providers whose
                stated age range covers that child — so you won't see nurseries
                that only take children from age 3 if your child is still a
                baby.
              </p>
              <p>
                If you tick more than one child, a provider is shown if it can
                accept <em>any</em> of the selected children — not necessarily
                all of them at the same time.
              </p>
              <p>
                Ticking a child also adjusts how costs are shown. Instead of
                displaying the full range of a provider's fees, we narrow it
                down to the age band that matches your child. This makes the
                cost comparison more relevant to your situation.
              </p>
              <p>
                Provider age ranges come from Ofsted registration data and may
                not always reflect current availability. We recommend confirming
                directly with the provider that they have a place for your
                child's age group.
              </p>
            </div>
          )}

          {caveatModal === "shortlisted_only" && (
            <div className="text-sm text-zinc-700 leading-relaxed space-y-3">
              <p>
                If you find a provider you're interested in, you can add it to
                your shortlist using the "Shortlist" toggle button on its card.
                Shortlisting helps you keep track of any providers you might be
                interested in, while you continue to explore your options.
              </p>
              <p>
                Ticking "Shortlisted only" hides all providers that aren't on
                your shortlist, so you can focus on the ones you've already
                identified as possibilities.
              </p>
              <p>
                Your shortlist is saved in your browser and will still be there
                if you return to this page later. It is not shared with
                providers or anyone else.
              </p>
            </div>
          )}

          {caveatModal === "funded_hours" && (
            <div className="text-sm text-zinc-700 leading-relaxed space-y-3">
              <p>
                Depending on your circumstances, you may be entitled to 15 or 30
                hours of free childcare per week during term time over 38 weeks
                of the year for children aged 9 months to 4 years old. You will
                need to speak to the provider to understand when they offer
                funded childcare, and any optional, chargeable extras they
                offer.
              </p>
              <p>
                When this filter is enabled, only providers that accept funded
                hours (or offer free provision such as free breakfast clubs) are
                shown. When a provider offers several care types, any that do
                not accept funded hours are shown with a strikethrough so you
                can see at a glance which of their services are covered.
              </p>
            </div>
          )}
        </Modal>
      )}

      {infoType && infoData && (
        <Modal
          onClose={() => setInfoType(null)}
          title={
            <span className="flex items-baseline gap-2">
              <i className="bi bi-info-circle text-zinc-600" />
              {providerTypes.find((pt) => pt.value === infoType)?.label}
            </span>
          }
        >
          <p className="text-sm text-zinc-700 leading-relaxed">
            {infoData.description}
          </p>

          {infoData.costLines.length > 0 && (
            <div className="mt-5">
              <h4 className="font-bold text-sm mb-2">
                Average costs in your area
              </h4>
              <table className="w-full text-sm">
                <tbody>
                  {infoData.costLines.map((line, i) => (
                    <tr key={i} className={i % 2 === 0 ? "bg-zinc-50" : ""}>
                      <td className="py-1.5 px-2 text-neutral-600">
                        {line.label}
                      </td>
                      <td className="py-1.5 px-2 text-right font-medium">
                        {line.value}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {infoData.extras.length > 0 && (
            <ul className="mt-4 space-y-1">
              {infoData.extras.map((extra, i) => (
                <li
                  key={i}
                  className="text-sm text-neutral-500 flex items-start gap-1.5"
                >
                  <span className="shrink-0 mt-1 text-xs">&#8226;</span>
                  <span>{extra}</span>
                </li>
              ))}
            </ul>
          )}

          {infoData.laName && (
            <p className="mt-4 text-xs text-neutral-600">
              Based on local averages for {infoData.laName}, last updated{" "}
              {infoData.lastUpdated}.
              {infoData.costAreas.some(
                (a) => a === "region" || a === "national",
              ) &&
                " Some costs use regional or national averages where local data is limited."}
              {infoData.costAreas.includes("insufficient") &&
                " Some costs are estimated due to limited local data."}
            </p>
          )}
        </Modal>
      )}
    </div>
  );
}

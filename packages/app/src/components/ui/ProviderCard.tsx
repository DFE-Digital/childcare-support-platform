import { useState, useEffect, forwardRef } from "react";
import type { Provider, WaitingListEntry } from "@/types/provider";
import {
  getOfstedRatingLabel,
  getOfstedBadgeClasses,
  getReportCardJudgements,
  getReportCardBooleans,
} from "@/types/provider";
import type {
  CostDisplayMode,
  SortOption,
} from "@/components/providers/ProviderFilters";
import { getProviderCostDisplay } from "@/utils/providerCosts";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { featureFlags } from "@/hooks/useFeatureFlags";
import {
  getDailyOpeningSpan,
  getDailyOpeningHours,
  getLongestAnnualWeeks,
} from "./providerCardHelpers";
import { Modal } from "./Modal";
import { loadLaCosts } from "@/data/loader";

const { showMetrics, showFees } = featureFlags;

function formatDistance(miles: number): string {
  return miles >= 1 ? Math.round(miles).toString() : miles.toFixed(1);
}

interface ProviderCardProps {
  id?: string;
  provider: Provider;
  isShortlisted?: boolean;
  onSelect?: () => void;
  onToggleShortlist?: () => void;
  costDisplayMode: CostDisplayMode;
  includeAdditionalCharges: boolean;
  sortBy?: SortOption;
  postcode?: string;
  fundedHoursOnly?: boolean;
  selectedTypes?: string[];
  childAgesMonths?: number[];
  active?: boolean;
}

function careTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    private_nursery: "Nursery",
    school_based_nursery: "School-based nursery",
    childminder: "Childminder",
    breakfast_club: "Breakfast club",
    free_breakfast_club: "Free breakfast club",
    after_school_club: "After school club",
    holiday_club: "Holiday club",
  };
  return labels[type] || type;
}

type WaitingListSummary =
  | { known: false }
  | { known: true; placesAvailable: true }
  | { known: true; placesAvailable: false; label: string };

function entryToWeeks(e: WaitingListEntry): number {
  if (e.months != null) return e.months * 4.3;
  return e.weeks ?? 0;
}

function formatWaitValue(e: WaitingListEntry): string {
  if (e.months != null) return `${e.months} months`;
  return `${e.weeks ?? 0} weeks`;
}

function getWaitingListSummary(provider: Provider): WaitingListSummary {
  const allEntries: { entry: WaitingListEntry }[] = [];
  for (const ct of provider.careTypes) {
    if (ct.waitingList) {
      for (const band of Object.keys(ct.waitingList)) {
        allEntries.push({ entry: ct.waitingList[band] });
      }
    }
  }
  if (allEntries.length === 0) return { known: false };

  const weeks = allEntries.map((e) => entryToWeeks(e.entry));
  const minWeeks = Math.min(...weeks);
  const maxWeeks = Math.max(...weeks);

  if (maxWeeks === 0) return { known: true, placesAvailable: true };

  // Find the original entries for min and max to display in their native unit
  const minEntry = allEntries[weeks.indexOf(minWeeks)].entry;
  const maxEntry = allEntries[weeks.indexOf(maxWeeks)].entry;

  if (minWeeks === maxWeeks) {
    return {
      known: true,
      placesAvailable: false,
      label: formatWaitValue(maxEntry),
    };
  }

  const sameUnit =
    minEntry.months != null && maxEntry.months != null
      ? true
      : minEntry.weeks != null && maxEntry.weeks != null;
  const minLabel =
    minWeeks === 0
      ? "0"
      : sameUnit
        ? `${minEntry.months ?? minEntry.weeks}`
        : formatWaitValue(minEntry);
  const maxLabel = formatWaitValue(maxEntry);
  return {
    known: true,
    placesAvailable: false,
    label: `${minLabel} to ${maxLabel}`,
  };
}

function isFundedCareType(ct: {
  type: string;
  fundedHoursAccepted?: boolean;
}): boolean {
  return ct.fundedHoursAccepted === true || ct.type === "free_breakfast_club";
}

export const ProviderCard = forwardRef<HTMLDivElement, ProviderCardProps>(
  function ProviderCard(
    {
      id,
      provider,
      isShortlisted,
      onSelect,
      onToggleShortlist,
      costDisplayMode,
      includeAdditionalCharges,
      sortBy,
      postcode = "",
      fundedHoursOnly,
      selectedTypes = [],
      childAgesMonths = [],
      active,
    },
    ref,
  ) {
    const [showNoPinModal, setShowNoPinModal] = useState(false);
    const [laName, setLaName] = useState<string | null>(null);
    const hasPin = provider.latitude != null;

    useEffect(() => {
      if (!showNoPinModal) return;
      if (provider.boundingBox?.geoType !== "local_authority") return;
      let cancelled = false;
      loadLaCosts(provider.boundingBox.geoCode).then(
        (costs) => {
          if (!cancelled) setLaName(costs.laName);
        },
        () => {},
      );
      return () => {
        cancelled = true;
      };
    }, [showNoPinModal, provider.boundingBox]);

    const displayName =
      provider.name ||
      `Unnamed ${(provider.institutionType ?? "provider").replace(/^./, (c) => c.toUpperCase())}`;
    const types = [...new Set(provider.careTypes.map((ct) => ct.type))];
    const costDisplay = getProviderCostDisplay(
      provider,
      costDisplayMode,
      includeAdditionalCharges,
      selectedTypes,
      childAgesMonths,
    );

    const cardUrl: string | undefined =
      provider.website ??
      provider.fisUrl ??
      (() => {
        const activeCts =
          selectedTypes.length > 0
            ? provider.careTypes.filter((ct) => selectedTypes.includes(ct.type))
            : provider.careTypes;
        if (activeCts.length === 1) {
          return activeCts[0].website ?? activeCts[0].fisUrl;
        }
        return undefined;
      })();

    const optionLabel = [
      displayName,
      types.map((t) => careTypeLabel(t)).join(", "),
      `${formatDistance(provider.distanceMiles)} miles`,
      getOfstedRatingLabel(provider.ofsted)
        ? `Ofsted: ${getOfstedRatingLabel(provider.ofsted)}`
        : provider.cma
          ? ""
          : "Not inspected",
    ]
      .filter(Boolean)
      .join(". ");

    return (
      <>
        <div
          ref={ref}
          id={id}
          role="option"
          aria-selected={active}
          aria-label={optionLabel}
          tabIndex={-1}
          className={`@container bg-white rounded-xl border p-5 overflow-visible outline-none ${
            active
              ? "ring-2 ring-blue-500 ring-offset-2 border-blue-300"
              : isShortlisted
                ? "border-purple-400 ring-2 ring-purple-200"
                : "border-zinc-200"
          }`}
        >
          <div>
            <div className="hidden @sm:flex float-right ml-3 mb-2 flex-col items-stretch gap-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleShortlist?.();
                }}
                tabIndex={-1}
                className={`text-xs font-bold px-3 py-1.5 rounded-full border-2 transition-colors cursor-pointer ${
                  isShortlisted
                    ? "bg-purple-50 border-purple-400 text-purple-800 hover:bg-purple-800 hover:text-white hover:border-purple-800"
                    : "border-zinc-400 text-zinc-500 hover:bg-neutral-700 hover:text-white hover:border-neutral-700"
                }`}
                aria-label={
                  isShortlisted
                    ? `Remove ${displayName} from shortlist`
                    : `Add ${displayName} to shortlist`
                }
              >
                {isShortlisted ? "Shortlisted" : "Shortlist"}
              </button>
              <button
                onClick={onSelect}
                tabIndex={-1}
                className="btn-tertiary !px-3 !py-1.5 !text-xs"
              >
                Show details
              </button>
            </div>
            <h3
              onClick={onSelect}
              className="font-bold text-base mb-1 hover:underline cursor-pointer"
            >
              {displayName}
            </h3>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {types.map((t) => {
                const funded =
                  !fundedHoursOnly ||
                  provider.careTypes.some(
                    (ct) => ct.type === t && isFundedCareType(ct),
                  );
                return funded ? (
                  <span
                    key={t}
                    className="text-xs bg-purple-50 text-purple-800 px-2 py-0.5 rounded-full font-medium text-center"
                  >
                    {careTypeLabel(t)}
                  </span>
                ) : (
                  <span
                    key={t}
                    className="relative text-xs bg-zinc-100 text-zinc-600 px-2 py-0.5 rounded-full font-medium text-center"
                  >
                    {careTypeLabel(t)}
                    <span className="absolute inset-0 flex items-center pointer-events-none">
                      <span className="w-full border-t border-current" />
                    </span>
                  </span>
                );
              })}
              {sortBy === "most_graduate" && (
                <span className="text-xs bg-zinc-200 text-zinc-600 px-2 py-0.5 rounded-full font-medium text-center">
                  {provider.staff?.graduatePercentage != null
                    ? `${provider.staff.graduatePercentage}% graduate staff`
                    : "Not reported"}
                </span>
              )}
              {sortBy === "lowest_turnover" && (
                <span className="text-xs bg-zinc-200 text-zinc-600 px-2 py-0.5 rounded-full font-medium text-center">
                  {provider.staff?.turnoverPercentage != null
                    ? `${provider.staff.turnoverPercentage}% staff turnover`
                    : "Not reported"}
                </span>
              )}
              {sortBy === "longest_daily" && (
                <span className="text-xs bg-zinc-200 text-zinc-600 px-2 py-0.5 rounded-full font-medium text-center">
                  {(() => {
                    const hours = getDailyOpeningHours(provider, selectedTypes);
                    return hours != null
                      ? `${Math.round(hours * 10) / 10} hours per\u00A0day`
                      : "? hours per\u00A0day";
                  })()}
                </span>
              )}
              {sortBy === "longest_annual" && (
                <span className="text-xs bg-zinc-200 text-zinc-600 px-2 py-0.5 rounded-full font-medium text-center">
                  {getLongestAnnualWeeks(provider, selectedTypes) > 0
                    ? `${getLongestAnnualWeeks(provider, selectedTypes)} weeks per\u00A0year`
                    : "? weeks per\u00A0year"}
                </span>
              )}
              {sortBy === "lowest_cost" && costDisplayMode === "detailed" && (
                <span className="text-xs bg-zinc-200 text-zinc-600 px-2 py-0.5 rounded-full font-medium text-center">
                  {
                    getProviderCostDisplay(
                      provider,
                      "hourly",
                      includeAdditionalCharges,
                      selectedTypes,
                      childAgesMonths,
                    ).summary
                  }
                </span>
              )}
              {sortBy === "distance" && (
                <span className="text-xs bg-zinc-200 text-zinc-600 px-2 py-0.5 rounded-full font-medium text-center">
                  {hasPin ? "" : "within "}
                  {formatDistance(provider.distanceMiles)} miles
                  {hasPin ? " from " : " of "}
                  {postcode}
                </span>
              )}
              {!hasPin && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowNoPinModal(true);
                  }}
                  tabIndex={-1}
                  className="inline-flex items-center justify-center w-5 h-5 text-zinc-500 hover:text-zinc-600 transition-colors"
                  aria-label="No map pin available"
                >
                  <i
                    className="bi bi-patch-question text-lg"
                    aria-hidden="true"
                  />
                </button>
              )}
            </div>
            {(() => {
              const parts = [
                provider.address.line1,
                provider.address.city,
              ].filter(Boolean);
              const line =
                parts.length > 0 && provider.address.postcode
                  ? `${parts.join(", ")} ${provider.address.postcode}`
                  : parts.length > 0
                    ? parts.join(", ")
                    : provider.address.postcode || null;
              return line ? (
                <p className="text-sm text-zinc-500">{line}</p>
              ) : null;
            })()}
            {cardUrl && (
              <p>
                <ExternalLink
                  href={cardUrl}
                  showIcon={false}
                  tabIndex={-1}
                  className="text-sm text-zinc-500 hover:underline break-all"
                >
                  {cardUrl}
                </ExternalLink>
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm mt-2">
            {costDisplayMode !== "detailed" && (
              <span className="font-medium">{costDisplay.summary}</span>
            )}
            {(() => {
              const ofsted = provider.ofsted;
              if (ofsted?.framework === "report_card") {
                const judgements = getReportCardJudgements(ofsted);
                const booleans = getReportCardBooleans(ofsted);
                const sortedJudgements = [...judgements].sort(
                  (a, b) => a.rank - b.rank,
                );
                return (
                  <span className="inline-flex items-center gap-1">
                    <span className="text-xs font-bold text-zinc-500">
                      Ofsted:
                    </span>
                    {sortedJudgements.map((j) => (
                      <span
                        key={j.field}
                        role="img"
                        aria-label={`${j.label}: ${j.grade}`}
                        className="inline-block w-3 h-3 rounded-full border border-black shrink-0"
                        style={{ backgroundColor: j.colour }}
                      />
                    ))}
                    {booleans.map((b) => (
                      <i
                        key={b.field}
                        aria-label={`${b.label}: ${b.met ? "Met" : "Not met"}`}
                        className={`bi ${b.met ? "bi-check-circle" : "bi-x-circle-fill"} shrink-0`}
                        style={{
                          color: b.met ? "#33903C" : "#CE1E02",
                          fontSize: "0.75rem",
                        }}
                      />
                    ))}
                  </span>
                );
              }
              if (ofsted?.framework === "legacy_transition") {
                return (
                  <span className="px-2 py-0.5 rounded text-xs font-bold text-center bg-zinc-100 text-zinc-600">
                    Ofsted: no summary
                  </span>
                );
              }
              const ratingLabel = getOfstedRatingLabel(ofsted);
              if (!ratingLabel && provider.cma) return null;
              return (
                <span
                  className={`px-2 py-0.5 rounded text-xs font-bold text-center ${getOfstedBadgeClasses(ratingLabel)}`}
                >
                  {ratingLabel ? `Ofsted: ${ratingLabel}` : "Not inspected"}
                </span>
              );
            })()}
            {provider.cma && (
              <span
                className={`px-2 py-0.5 rounded text-xs font-bold text-center ${
                  provider.cma.qaGrading
                    ? provider.cma.qaGrading === "outstanding" ||
                      provider.cma.qaGrading === "good"
                      ? "bg-green-50 text-green-800"
                      : provider.cma.qaGrading === "good-with-actions" ||
                          provider.cma.qaGrading === "support-required"
                        ? "bg-amber-50 text-amber-800"
                        : "bg-red-50 text-red-800"
                    : "bg-zinc-100 text-zinc-600"
                }`}
              >
                {provider.cma.qaGrading
                  ? `${provider.cma.agency}: ${provider.cma.qaGrading.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}`
                  : `${provider.cma.agency}: Awaiting first visit`}
              </span>
            )}
            {sortBy !== "distance" && (
              <span className="inline-flex items-center gap-1 text-sm text-zinc-500">
                <i className="bi bi-geo" aria-hidden="true" />
                {hasPin ? "" : "under "}
                {formatDistance(provider.distanceMiles)} miles
              </span>
            )}
            {getDailyOpeningSpan(provider, selectedTypes) !== "–" && (
              <span className="inline-flex items-center gap-1 text-sm text-zinc-500">
                <i className="bi bi-clock" aria-hidden="true" />
                {getDailyOpeningSpan(provider, selectedTypes)}
              </span>
            )}
            {getLongestAnnualWeeks(provider, selectedTypes) > 0 && (
              <span className="inline-flex items-center gap-1 text-sm text-zinc-500">
                <i className="bi bi-calendar3" aria-hidden="true" />
                {getLongestAnnualWeeks(provider, selectedTypes)} weeks a year
              </span>
            )}
            {showMetrics &&
              (() => {
                const summary = getWaitingListSummary(provider);
                return (
                  <span className="inline-flex items-center gap-1 text-sm text-zinc-500">
                    <i
                      className={`bi ${summary.known ? "bi-hourglass-split" : "bi-question-circle-fill"}`}
                      aria-hidden="true"
                    />
                    {summary.known
                      ? summary.placesAvailable
                        ? "Places available"
                        : summary.label
                      : "Waiting list"}
                  </span>
                );
              })()}
            {sortBy !== "most_graduate" && showMetrics && (
              <span className="inline-flex items-center gap-1 text-sm text-zinc-500">
                <i
                  className={`bi ${provider.staff?.graduatePercentage != null ? "bi-mortarboard" : "bi-question-circle-fill"}`}
                  aria-hidden="true"
                />
                {provider.staff?.graduatePercentage != null
                  ? `${provider.staff.graduatePercentage}% graduate`
                  : "Graduate staff"}
              </span>
            )}
            {sortBy !== "lowest_turnover" && showMetrics && (
              <span className="inline-flex items-center gap-1 text-sm text-zinc-500">
                <i
                  className={`bi ${provider.staff?.turnoverPercentage != null ? "bi-person-walking" : "bi-question-circle-fill"}`}
                  aria-hidden="true"
                />
                {provider.staff?.turnoverPercentage != null
                  ? `${provider.staff.turnoverPercentage}% turnover`
                  : "Staff turnover"}
              </span>
            )}
            {showMetrics && (
              <span className="relative text-sm text-zinc-500">
                <i
                  className={`bi ${provider.facilities ? "bi-leaf" : "bi-question-circle-fill"}`}
                  aria-hidden="true"
                />{" "}
                Garden
                {provider.facilities && !provider.facilities.hasGarden && (
                  <span className="absolute inset-0 flex items-center pointer-events-none">
                    <span className="w-full border-t border-current" />
                  </span>
                )}
              </span>
            )}
            {showMetrics && (
              <span className="relative text-sm text-zinc-500">
                <i
                  className={`bi ${provider.facilities ? "bi-fork-knife" : "bi-question-circle-fill"}`}
                  aria-hidden="true"
                />{" "}
                Kitchen
                {provider.facilities && !provider.facilities.hasKitchen && (
                  <span className="absolute inset-0 flex items-center pointer-events-none">
                    <span className="w-full border-t border-current" />
                  </span>
                )}
              </span>
            )}
          </div>
          {showFees &&
            costDisplayMode === "detailed" &&
            !costDisplay.table &&
            !costDisplay.detailed &&
            !costDisplay.feeRows &&
            !costDisplay.extras && (
              <p className="mt-3 border-t border-zinc-100 pt-3 text-sm text-zinc-500">
                Contact for fees
              </p>
            )}
          {showFees &&
            (costDisplay.table ||
              costDisplay.detailed ||
              costDisplay.feeRows ||
              costDisplay.extras) && (
              <div className="mt-3 border-t border-zinc-100 pt-3 space-y-2">
                {costDisplay.feeRows &&
                  (() => {
                    const rows = costDisplay.feeRows!;
                    const hasAge = rows.some((r) => r.age !== "");
                    const needsNarrowFallback = hasAge;

                    return (
                      <div className="overflow-x-auto">
                        <table
                          className={`w-full text-sm ${needsNarrowFallback ? "hidden sm:table" : ""}`}
                        >
                          <caption className="sr-only">Session fees</caption>
                          <tbody>
                            {rows.map((row, i) => {
                              const prev = i > 0 ? rows[i - 1] : null;
                              const showCareType =
                                !prev || prev.careType !== row.careType;
                              const showAge =
                                hasAge &&
                                (!prev ||
                                  prev.careType !== row.careType ||
                                  prev.age !== row.age);

                              return (
                                <tr
                                  key={i}
                                  className={i % 2 === 0 ? "bg-zinc-50" : ""}
                                >
                                  <td
                                    className={`py-1 px-2 text-zinc-500${showCareType ? "" : " text-transparent select-none"}`}
                                  >
                                    {showCareType ? row.careType : ""}
                                  </td>
                                  {hasAge && (
                                    <td
                                      className={`py-1 px-2 text-zinc-500${showAge ? "" : " text-transparent select-none"}`}
                                    >
                                      {showAge ? row.age : ""}
                                    </td>
                                  )}
                                  <td className="py-1 px-2 text-zinc-500">
                                    {row.period}
                                  </td>
                                  <td className="py-1 px-2 text-right font-medium">
                                    {row.cost}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                        {needsNarrowFallback && (
                          <table className="w-full text-sm sm:hidden">
                            <caption className="sr-only">Session fees</caption>
                            <tbody>
                              {rows.map((row, i) => {
                                const merged = row.age
                                  ? `${row.careType} · ${row.age}`
                                  : row.careType;
                                const prev = i > 0 ? rows[i - 1] : null;
                                const prevMerged = prev
                                  ? prev.age
                                    ? `${prev.careType} · ${prev.age}`
                                    : prev.careType
                                  : null;
                                const showMerged = merged !== prevMerged;

                                return (
                                  <tr
                                    key={i}
                                    className={i % 2 === 0 ? "bg-zinc-50" : ""}
                                  >
                                    <td
                                      className={`py-1 px-2 text-zinc-500${showMerged ? "" : " text-transparent select-none"}`}
                                    >
                                      {showMerged ? merged : ""}
                                    </td>
                                    <td className="py-1 px-2 text-zinc-500">
                                      {row.period}
                                    </td>
                                    <td className="py-1 px-2 text-right font-medium">
                                      {row.cost}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        )}
                      </div>
                    );
                  })()}
                {costDisplay.table &&
                  (() => {
                    const { columns, rows } = costDisplay.table;
                    const needsNarrowFallback = columns.length >= 3;

                    return (
                      <div className="overflow-x-auto">
                        <table
                          className={`w-full text-sm ${needsNarrowFallback ? "hidden sm:table" : ""}`}
                        >
                          <caption className="sr-only">Session fees</caption>
                          <thead>
                            <tr>
                              <th
                                scope="col"
                                className="py-1 px-2 text-left text-xs text-zinc-500 font-medium"
                              ></th>
                              {columns.map((col) => (
                                <th
                                  scope="col"
                                  key={col}
                                  className="py-1 px-2 text-right text-xs text-zinc-500 font-medium"
                                >
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {rows.map((row, i) => (
                              <tr
                                key={i}
                                className={i % 2 === 0 ? "bg-zinc-50" : ""}
                              >
                                <td className="py-1 px-2 text-zinc-500">
                                  {row.label}
                                </td>
                                {row.values.map((val, j) => (
                                  <td
                                    key={j}
                                    className="py-1 px-2 text-right font-medium"
                                  >
                                    {val ?? "–"}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {needsNarrowFallback && (
                          <table className="w-full text-sm sm:hidden">
                            <caption className="sr-only">Session fees</caption>
                            <tbody>
                              {rows.flatMap((row, i) => {
                                let labelShown = false;
                                return row.values.map((val, j) => {
                                  if (!val) return null;
                                  const showLabel = !labelShown;
                                  labelShown = true;
                                  return (
                                    <tr
                                      key={`${i}-${j}`}
                                      className={
                                        i % 2 === 0 ? "bg-zinc-50" : ""
                                      }
                                    >
                                      <td
                                        className={`py-1 px-2 text-zinc-500${showLabel ? "" : " text-transparent select-none"}`}
                                      >
                                        {showLabel ? row.label : ""}
                                      </td>
                                      <td className="py-1 px-2 text-zinc-500">
                                        {columns[j]}
                                      </td>
                                      <td className="py-1 px-2 text-right font-medium">
                                        {val}
                                      </td>
                                    </tr>
                                  );
                                });
                              })}
                            </tbody>
                          </table>
                        )}
                      </div>
                    );
                  })()}
                {costDisplay.detailed && costDisplay.detailed.length > 0 && (
                  <table className="w-full text-sm">
                    <caption className="sr-only">Session fees</caption>
                    <tbody>
                      {costDisplay.detailed.map((line, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-zinc-50" : ""}>
                          <td className="py-1 px-2 text-zinc-500">
                            {line.label}
                          </td>
                          <td className="py-1 px-2 text-right font-medium">
                            {line.value}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                {costDisplay.extras && costDisplay.extras.length > 0 && (
                  <div className="pt-1">
                    <p className="text-xs font-bold text-zinc-500 px-2 pb-1">
                      Additional charges
                    </p>
                    <table className="w-full text-sm">
                      <caption className="sr-only">Additional charges</caption>
                      <tbody>
                        {costDisplay.extras.map((extra, i) => (
                          <tr
                            key={i}
                            className={i % 2 === 0 ? "bg-zinc-50" : ""}
                          >
                            <td className="py-1 px-2 text-zinc-500">
                              {extra.label}
                            </td>
                            <td className="py-1 px-2 text-right font-medium">
                              {extra.value}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          <div className="flex @sm:hidden gap-2 mt-3">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleShortlist?.();
              }}
              tabIndex={-1}
              className={`flex-1 text-xs font-bold px-3 py-1.5 rounded-full border-2 transition-colors cursor-pointer ${
                isShortlisted
                  ? "bg-purple-50 border-purple-400 text-purple-800 hover:bg-purple-800 hover:text-white hover:border-purple-800"
                  : "border-zinc-400 text-zinc-500 hover:bg-neutral-700 hover:text-white hover:border-neutral-700"
              }`}
              aria-label={
                isShortlisted
                  ? `Remove ${displayName} from shortlist`
                  : `Add ${displayName} to shortlist`
              }
            >
              {isShortlisted ? "Shortlisted" : "Shortlist"}
            </button>
            <button
              onClick={onSelect}
              tabIndex={-1}
              className="btn-tertiary flex-1 !px-3 !py-1.5 !text-xs"
            >
              Show details
            </button>
          </div>
        </div>
        {showNoPinModal && (
          <Modal
            onClose={() => setShowNoPinModal(false)}
            title="Approximate location"
          >
            <div className="space-y-3 text-sm text-zinc-600">
              <p>
                We don&apos;t have an exact address for this provider, so it
                can&apos;t be shown as a pin on the map.
              </p>
              {provider.boundingBox ? (
                <p>
                  {provider.boundingBox.geoType === "postcode" &&
                    `We know they're in the ${provider.boundingBox.geoCode} postcode area.`}
                  {provider.boundingBox.geoType === "postcode_district" &&
                    `We know they're in the ${provider.boundingBox.geoCode} postcode district.`}
                  {provider.boundingBox.geoType === "local_authority" && (
                    <>
                      We know they&apos;re somewhere in the{" "}
                      <strong>{laName ?? provider.boundingBox.geoCode}</strong>{" "}
                      local authority area.
                    </>
                  )}
                  {provider.boundingBox.geoType !== "postcode" &&
                    provider.boundingBox.geoType !== "postcode_district" &&
                    provider.boundingBox.geoType !== "local_authority" &&
                    `We know they're in the ${provider.boundingBox.geoCode} area.`}
                </p>
              ) : (
                <p>We don&apos;t have any location data for this provider.</p>
              )}
            </div>
          </Modal>
        )}
      </>
    );
  },
);

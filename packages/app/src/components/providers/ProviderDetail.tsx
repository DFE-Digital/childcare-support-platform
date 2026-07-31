import type {
  Provider,
  MinimumCommitment,
  WaitingListEntry,
} from "@/types/provider";
import {
  getOfstedRatingLabel,
  getOfstedBadgeClasses,
  getReportCardJudgements,
  getReportCardBooleans,
} from "@/types/provider";
import { formatUKPhone } from "@/utils/formatPhone";
import { getProviderCostDisplay } from "@/utils/providerCosts";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { Modal } from "@/components/ui/Modal";
import { featureFlags } from "@/hooks/useFeatureFlags";

const {
  showFees,
  showMetrics,
  showEligibility,
  showAvailability,
  showNotes,
  showFundedHoursFilter,
} = featureFlags;

function formatDistance(miles: number): string {
  return miles >= 1 ? Math.round(miles).toString() : miles.toFixed(1);
}

interface ProviderDetailProps {
  provider: Provider;
  onClose: () => void;
  isShortlisted: boolean;
  onToggleShortlist: () => void;
  postcode: string;
  childAgesMonths?: number[];
  coLocatedProviders?: Provider[];
  onNavigate?: (provider: Provider) => void;
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

function formatMinimumCommitment(mc: MinimumCommitment): string {
  const unitLabels: Record<string, string> = {
    full_days: "full day",
    sessions: "session",
    hours: "hour",
  };
  const durationLabels: Record<string, string> = {
    half_term: "half-termly",
    term: "termly",
    year: "yearly",
  };

  if (mc.amount != null && mc.unitPerWeek) {
    const label = unitLabels[mc.unitPerWeek] || mc.unitPerWeek;
    const plural = mc.amount === 1 ? label : label + "s";
    const base = `Minimum ${mc.amount} ${plural} per week`;
    if (mc.duration) {
      return `${base}, for at least 1 ${mc.duration === "half_term" ? "half term" : mc.duration}`;
    }
    return base;
  }

  if (mc.duration) {
    return `Booked on a ${durationLabels[mc.duration] || mc.duration} basis`;
  }

  return "Minimum commitment applies";
}

function formatDays(days: string): string {
  const labels: Record<string, string> = {
    "1": "Mon",
    "2": "Tue",
    "3": "Wed",
    "4": "Thu",
    "5": "Fri",
    "6": "Sat",
    "7": "Sun",
  };
  const nums = days.split("");
  if (nums.length === 0) return "";
  const allConsecutive = nums.every(
    (n, i) => i === 0 || Number(n) === Number(nums[i - 1]) + 1,
  );
  if (allConsecutive && nums.length > 2) {
    return `${labels[nums[0]]} to ${labels[nums[nums.length - 1]]}`;
  }
  return nums.map((n) => labels[n] || n).join(", ");
}

const AGE_BAND_LABELS: Record<string, string> = {
  under2: "Under 2",
  age2: "Age 2",
  age3to4: "Age 3 to 4",
  age2plus: "Age 2+",
  all: "All ages",
};

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

export function ProviderDetail({
  provider,
  onClose,
  isShortlisted,
  onToggleShortlist,
  postcode,
  childAgesMonths = [],
  coLocatedProviders,
  onNavigate,
}: ProviderDetailProps) {
  const currentIndex =
    coLocatedProviders?.findIndex((p) => p.id === provider.id) ?? -1;
  const showNav =
    coLocatedProviders && coLocatedProviders.length > 1 && currentIndex >= 0;

  const total = coLocatedProviders!.length;
  const headerExtra = showNav ? (
    <div className="inline-flex items-center gap-1">
      <button
        onClick={() => {
          const prevIndex = (currentIndex - 1 + total) % total;
          onNavigate?.(coLocatedProviders![prevIndex]);
        }}
        className="w-7 h-7 flex items-center justify-center rounded hover:bg-zinc-100 text-zinc-500"
        aria-label="Previous provider"
      >
        <i className="bi bi-chevron-left text-xs" />
      </button>
      <span className="text-xs text-zinc-600 text-center relative">
        <span className="invisible">
          {total} of {total} at this location
        </span>
        <span className="absolute inset-0">
          {currentIndex + 1} of {total} at this location
        </span>
      </span>
      <button
        onClick={() => {
          const nextIndex = (currentIndex + 1) % total;
          onNavigate?.(coLocatedProviders![nextIndex]);
        }}
        className="w-7 h-7 flex items-center justify-center rounded hover:bg-zinc-100 text-zinc-500"
        aria-label="Next provider"
      >
        <i className="bi bi-chevron-right text-xs" />
      </button>
    </div>
  ) : undefined;

  const costDisplay = getProviderCostDisplay(
    provider,
    "detailed",
    true,
    [],
    childAgesMonths,
  );

  return (
    <Modal
      onClose={onClose}
      title={provider.name}
      maxWidth="max-w-2xl"
      headerExtra={headerExtra}
    >
      <button
        onClick={onToggleShortlist}
        className={`text-sm font-bold px-4 py-1.5 rounded-full border-2 transition-colors cursor-pointer mb-4 ${
          isShortlisted
            ? "bg-purple-50 border-purple-400 text-purple-800 hover:bg-purple-800 hover:text-white hover:border-purple-800"
            : "border-zinc-400 text-zinc-500 hover:bg-neutral-700 hover:text-white hover:border-neutral-700"
        }`}
      >
        {isShortlisted ? "Remove from shortlist" : "Add to shortlist"}
      </button>

      {/* Metrics */}
      {(() => {
        const metrics: {
          icon: string;
          label: string;
          value: React.ReactNode;
          strikethrough?: boolean;
          missing?: boolean;
          mobileValue?: React.ReactNode;
          mobileInline?: boolean;
          twoRowUntilMd?: boolean;
        }[] = [];

        // Contact rows
        const addressParts = [
          provider.address.line1,
          provider.address.line2,
          provider.address.city,
          provider.address.postcode,
        ].filter(Boolean);
        metrics.push({
          icon: "bi-house",
          label: "Address",
          value: (
            <>
              {addressParts.map((part, i) => (
                <span key={i}>
                  {part}
                  {i < addressParts.length - 1 ? ", " : ""}
                </span>
              ))}
            </>
          ),
          twoRowUntilMd: true,
          mobileValue: (
            <>
              {addressParts.map((part, i) => (
                <div key={i}>{part}</div>
              ))}
            </>
          ),
        });
        if (provider.phone) {
          metrics.push({
            icon: "bi-telephone",
            label: "Phone",
            value: (
              <a href={`tel:${provider.phone}`} className="hover:underline">
                {formatUKPhone(provider.phone)}
              </a>
            ),
            mobileInline: true,
          });
        }
        if (provider.email) {
          metrics.push({
            icon: "bi-envelope",
            label: "Email",
            value: (
              <a
                href={`mailto:${provider.email}`}
                className="hover:underline break-words"
              >
                {provider.email}
              </a>
            ),
            twoRowUntilMd: true,
          });
        }
        if (provider.website) {
          metrics.push({
            icon: "bi-globe2",
            label: "Website",
            value: (
              <ExternalLink
                href={provider.website}
                showIcon={false}
                className="hover:underline block truncate max-w-[260px] sm:max-w-[380px] md:max-w-[480px]"
              >
                {provider.website.replace(/^https?:\/\//, "")}
              </ExternalLink>
            ),
            twoRowUntilMd: true,
          });
        }
        if (provider.fisUrl) {
          metrics.push({
            icon: "bi-globe2",
            label: "Family info",
            value: (
              <ExternalLink
                href={provider.fisUrl}
                showIcon={false}
                className="hover:underline block truncate max-w-[220px] sm:max-w-[340px] md:max-w-[440px]"
              >
                {provider.fisUrl.replace(/^https?:\/\//, "")}
              </ExternalLink>
            ),
            twoRowUntilMd: true,
          });
        }

        if (postcode) {
          metrics.push({
            icon: "bi-geo",
            label: `Distance from ${postcode}`,
            value: `${formatDistance(provider.distanceMiles)} miles`,
            mobileInline: true,
          });
        }
        if (provider.registeredPlaces != null) {
          metrics.push({
            icon: "bi-people",
            label: "Registered places",
            value: `${provider.registeredPlaces}`,
            mobileInline: true,
          });
        } else {
          metrics.push({
            icon: "bi-people",
            label: "Registered places",
            value: "Registered places",
            missing: true,
            mobileInline: true,
          });
        }
        if (showMetrics) {
          const wlSummary = getWaitingListSummary(provider);
          if (!wlSummary.known) {
            metrics.push({
              icon: "bi-hourglass-split",
              label: "Waiting list",
              value: "Waiting list",
              missing: true,
              mobileInline: true,
            });
          } else if (wlSummary.placesAvailable) {
            metrics.push({
              icon: "bi-hourglass-split",
              label: "Waiting list",
              value: "Places available",
              mobileInline: true,
            });
          } else {
            metrics.push({
              icon: "bi-hourglass-split",
              label: "Waiting list",
              value: wlSummary.label,
              mobileInline: true,
            });
          }
          metrics.push(
            provider.staff?.graduatePercentage != null
              ? {
                  icon: "bi-mortarboard",
                  label: "Staff with degrees",
                  value: `${provider.staff.graduatePercentage}%`,
                  mobileInline: true,
                }
              : {
                  icon: "bi-mortarboard",
                  label: "Staff with degrees",
                  value: "Graduate staff",
                  missing: true,
                  mobileInline: true,
                },
          );
          metrics.push(
            provider.staff?.turnoverPercentage != null
              ? {
                  icon: "bi-person-walking",
                  label: "Staff turnover",
                  value: `${provider.staff.turnoverPercentage}%`,
                  mobileInline: true,
                }
              : {
                  icon: "bi-person-walking",
                  label: "Staff turnover",
                  value: "Staff turnover",
                  missing: true,
                  mobileInline: true,
                },
          );
          if (provider.facilities) {
            metrics.push({
              icon: "bi-leaf",
              label: "Garden",
              value: provider.facilities.hasGarden ? "Yes" : "No",
              strikethrough: !provider.facilities.hasGarden,
              mobileInline: true,
            });
            metrics.push({
              icon: "bi-fork-knife",
              label: "Kitchen",
              value: provider.facilities.hasKitchen ? "Yes" : "No",
              strikethrough: !provider.facilities.hasKitchen,
              mobileInline: true,
            });
          } else {
            metrics.push({
              icon: "bi-leaf",
              label: "Garden",
              value: "Garden",
              missing: true,
              mobileInline: true,
            });
            metrics.push({
              icon: "bi-fork-knife",
              label: "Kitchen",
              value: "Kitchen",
              missing: true,
              mobileInline: true,
            });
          }
        }
        return (
          <div className="mb-6 text-sm">
            {metrics.map((m, i) => {
              const bg = i % 2 === 0 ? "bg-zinc-50" : "";
              const displayValue = m.missing ? (
                <i className="bi bi-question-circle text-black" />
              ) : (
                m.value
              );
              // Use fully static Tailwind class names so they survive
              // production CSS purging (dynamic `${bp}:flex` gets stripped).
              const hiddenBp = m.twoRowUntilMd
                ? "hidden md:flex"
                : "hidden sm:flex";
              const visibleBp = m.twoRowUntilMd ? "md:hidden" : "sm:hidden";
              return (
                <div key={i}>
                  <div
                    className={`py-1 px-2 ${bg} ${hiddenBp} justify-between`}
                  >
                    <span className="text-zinc-600 shrink-0 whitespace-nowrap">
                      <i className={`bi ${m.icon} mr-2`} />
                      {m.label}
                    </span>
                    <span className="font-medium text-right">
                      {displayValue}
                    </span>
                  </div>
                  {m.mobileInline ? (
                    <div
                      className={`${visibleBp} flex justify-between py-1 px-2 ${bg}`}
                    >
                      <span className="text-zinc-600">
                        <i className={`bi ${m.icon} mr-2`} />
                        {m.label}
                      </span>
                      <span className="font-medium text-right">
                        {displayValue}
                      </span>
                    </div>
                  ) : (
                    <>
                      <div
                        className={`${visibleBp} py-1 px-2 text-zinc-600 ${bg}`}
                      >
                        <i className={`bi ${m.icon} mr-2`} />
                        {m.label}
                      </div>
                      <div
                        className={`${visibleBp} py-1 px-2 text-right font-medium ${bg}`}
                      >
                        {m.mobileValue ?? displayValue}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        );
      })()}

      {/* Ofsted */}
      {(() => {
        const ofsted = provider.ofsted;
        const ratingLabel = getOfstedRatingLabel(ofsted);

        if (!ofsted && !provider.cma) {
          return (
            <div className="mb-6 space-y-2">
              <span className="px-3 py-1 rounded-full text-sm font-bold text-center bg-zinc-100 text-zinc-600">
                No Ofsted inspection
              </span>
            </div>
          );
        }
        if (!ofsted) {
          return null;
        }

        const subGrades =
          (ofsted.framework === "legacy" ||
            ofsted.framework === "legacy_transition") &&
          ofsted.legacySubGrades
            ? ofsted.legacySubGrades
            : null;

        const SUB_GRADE_LABELS: Record<string, string> = {
          qualityOfEducation: "Quality of education",
          behaviourAndAttitudes: "Behaviour and attitudes",
          personalDevelopment: "Personal development",
          leadershipAndManagement: "Leadership and management",
          earlyYears: "Early years",
        };

        return (
          <div className="mb-6 space-y-2">
            {ofsted.framework === "legacy" && subGrades && (
              <table className="w-full text-sm">
                <caption className="sr-only">Ofsted inspection grades</caption>
                <tbody>
                  <tr>
                    <td className="py-2 pl-0 pr-2">
                      <span
                        className={`whitespace-nowrap px-3 py-1 rounded-lg text-sm font-bold ${getOfstedBadgeClasses(ratingLabel)}`}
                      >
                        {ratingLabel ? `Ofsted: ${ratingLabel}` : "Not rated"}
                      </span>
                    </td>
                    <td className="py-1 px-2 text-right text-xs text-zinc-600">
                      Inspected{" "}
                      <span className="whitespace-nowrap">
                        {ofsted.inspectionDate}
                      </span>
                    </td>
                  </tr>
                  {Object.entries(subGrades).map(([key, grade], i) => (
                    <tr key={key} className={i % 2 === 0 ? "bg-zinc-50" : ""}>
                      <td className="py-1 px-2 text-zinc-500">
                        {SUB_GRADE_LABELS[key] ?? key}
                      </td>
                      <td className="py-1 px-2 text-right font-medium">
                        {grade}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {ofsted.framework === "legacy_transition" && (
              <table className="w-full text-sm">
                <caption className="sr-only">Ofsted inspection grades</caption>
                <tbody>
                  <tr>
                    <td className="py-1.5 px-2">
                      <h3 className="font-bold text-xs uppercase tracking-wide">
                        Ofsted
                      </h3>
                    </td>
                    <td className="py-1.5 px-2 text-right text-xs text-zinc-600">
                      Inspected{" "}
                      <span className="whitespace-nowrap">
                        {ofsted.inspectionDate}
                      </span>
                    </td>
                  </tr>
                  {Object.entries(ofsted.legacySubGrades).map(
                    ([key, grade], i) => (
                      <tr key={key} className={i % 2 === 0 ? "bg-zinc-50" : ""}>
                        <td className="py-1 px-2 text-zinc-500">
                          {SUB_GRADE_LABELS[key] ?? key}
                        </td>
                        <td className="py-1 px-2 text-right font-medium">
                          {grade}
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            )}
            {(ofsted.framework === "legacy" ||
              ofsted.framework === "ungraded_confirmed") &&
              !subGrades && (
                <div className="flex items-center gap-x-3">
                  <span
                    className={`min-w-0 px-3 py-1 rounded-lg text-sm font-bold text-center ${getOfstedBadgeClasses(ratingLabel)}`}
                  >
                    {ratingLabel ? `Ofsted: ${ratingLabel}` : "Not rated"}
                  </span>
                  {ofsted.inspectionDate && (
                    <span className="text-xs text-zinc-600 ml-auto flex-shrink-0">
                      Inspected{" "}
                      <span className="whitespace-nowrap">
                        {ofsted.inspectionDate}
                      </span>
                    </span>
                  )}
                </div>
              )}
            {ofsted.framework === "report_card" &&
              (() => {
                const judgements = getReportCardJudgements(ofsted);
                const booleans = getReportCardBooleans(ofsted);
                return (
                  (judgements.length > 0 || booleans.length > 0) && (
                    <table className="w-full text-sm">
                      <caption className="sr-only">Ofsted report card</caption>
                      <tbody>
                        <tr>
                          <td className="py-1.5 px-2">
                            <h3 className="font-bold text-xs uppercase tracking-wide">
                              Ofsted
                            </h3>
                          </td>
                          <td className="py-1.5 px-2 text-center text-xs text-zinc-600">
                            Inspected{" "}
                            <span className="whitespace-nowrap">
                              {ofsted.inspectionDate}
                            </span>
                          </td>
                        </tr>
                        {judgements.map((j, i) => (
                          <tr
                            key={j.field}
                            className={i % 2 === 0 ? "bg-zinc-50" : ""}
                          >
                            <td className="py-1.5 px-2 text-zinc-500 align-middle">
                              {j.label}
                            </td>
                            <td className="py-1.5 px-2 text-center align-middle">
                              <span
                                className="inline-block px-2.5 py-0.5 rounded-full text-xs font-bold text-white"
                                style={{ backgroundColor: j.colour }}
                              >
                                {j.grade}
                              </span>
                            </td>
                          </tr>
                        ))}
                        {booleans.map((b, i) => (
                          <tr
                            key={b.field}
                            className={
                              (judgements.length + i) % 2 === 0
                                ? "bg-zinc-50"
                                : ""
                            }
                          >
                            <td className="py-1.5 px-2 text-zinc-500 align-middle">
                              {b.label}
                            </td>
                            <td className="py-1.5 px-2 text-center align-middle">
                              <i
                                aria-label={b.met ? "Met" : "Not met"}
                                className={`bi text-lg ${b.met ? "bi-check-circle text-green-600" : "bi-x-circle-fill text-red-600"}`}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )
                );
              })()}
          </div>
        );
      })()}

      {/* CMA Quality Assurance */}
      {provider.cma && (
        <div className="mb-6 space-y-2">
          <h3 className="text-sm font-semibold text-zinc-700">
            Quality Assurance ({provider.cma.agency})
          </h3>
          {provider.cma.qaGrading ? (
            <div className="flex items-center gap-3">
              <span
                className={`px-3 py-1 rounded-full text-sm font-bold ${
                  provider.cma.qaGrading === "outstanding" ||
                  provider.cma.qaGrading === "good"
                    ? "bg-green-50 text-green-800"
                    : provider.cma.qaGrading === "good-with-actions" ||
                        provider.cma.qaGrading === "support-required"
                      ? "bg-amber-50 text-amber-800"
                      : "bg-red-50 text-red-800"
                }`}
              >
                {provider.cma.qaGrading
                  .replace(/-/g, " ")
                  .replace(/\b\w/g, (c) => c.toUpperCase())}
              </span>
              {provider.cma.inspectionDate && (
                <span className="text-sm text-zinc-500">
                  {new Date(provider.cma.inspectionDate).toLocaleDateString(
                    "en-GB",
                    {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    },
                  )}
                </span>
              )}
            </div>
          ) : (
            <span className="px-3 py-1 rounded-full text-sm font-bold bg-zinc-100 text-zinc-600">
              Awaiting first visit
            </span>
          )}
        </div>
      )}

      {/* Fees */}

      {showFees && (
        <>
          {costDisplay.table ||
          costDisplay.detailed ||
          costDisplay.feeRows ||
          costDisplay.extras ? (
            <div className="mb-6 space-y-2">
              <h3
                className={`font-bold text-xs uppercase tracking-wide mb-2 px-2 ${costDisplay.table ? "sm:hidden" : ""}`}
              >
                Session fees
              </h3>
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
              {costDisplay.table && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm hidden sm:table">
                    <caption className="sr-only">Session fees</caption>
                    <thead>
                      <tr>
                        <th className="py-1 px-2 text-left font-bold text-xs uppercase tracking-wide">
                          Session fees
                        </th>
                        {costDisplay.table.columns.map((col) => (
                          <th
                            key={col}
                            className="py-1 px-2 text-right text-xs text-zinc-600 font-medium"
                          >
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {costDisplay.table.rows.map((row, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-zinc-50" : ""}>
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
                  <table className="w-full text-sm sm:hidden">
                    <caption className="sr-only">Session fees</caption>
                    <tbody>
                      {costDisplay.table.rows.flatMap((row, i) => {
                        let labelShown = false;
                        return row.values.map((val, j) => {
                          if (!val) return null;
                          const showLabel = !labelShown;
                          labelShown = true;
                          return (
                            <tr
                              key={`${i}-${j}`}
                              className={i % 2 === 0 ? "bg-zinc-50" : ""}
                            >
                              <td
                                className={`py-1 px-2 text-zinc-500${showLabel ? "" : " text-transparent select-none"}`}
                              >
                                {showLabel ? row.label : ""}
                              </td>
                              <td className="py-1 px-2 text-zinc-500">
                                {costDisplay.table!.columns[j]}
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
                </div>
              )}
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
                <div className="mt-6">
                  <h4 className="font-bold text-xs uppercase tracking-wide mb-2 px-2">
                    Additional charges
                  </h4>
                  <table className="w-full text-sm">
                    <caption className="sr-only">Additional charges</caption>
                    <tbody>
                      {costDisplay.extras.map((extra, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-zinc-50" : ""}>
                          <td className="py-1 px-2 text-zinc-500">
                            {extra.label}
                            {extra.description && (
                              <p className="text-xs text-zinc-600 mt-0.5">
                                {extra.description}
                              </p>
                            )}
                          </td>
                          <td className="py-1 px-2 text-right font-medium align-top">
                            {extra.value}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div className="mb-6 space-y-2">
              <h3 className="font-bold text-xs uppercase tracking-wide mb-2 px-2">
                Session fees
              </h3>
              <table className="w-full text-sm">
                <tbody>
                  <tr className="bg-zinc-50">
                    <td className="py-1 px-2 text-zinc-600" colSpan={2}>
                      No fee information available
                    </td>
                  </tr>
                </tbody>
              </table>
              <p className="text-sm text-zinc-600 pt-1">
                Contact provider directly for fees
              </p>
            </div>
          )}
        </>
      )}

      {/* Care types */}
      {provider.careTypes.map((ct, i) => (
        <div key={i} className="border border-zinc-200 rounded-lg p-4 mb-4">
          <h3 className="font-bold text-base mb-2">{careTypeLabel(ct.type)}</h3>
          {(() => {
            type Row = {
              icon: string;
              label: string;
              value: React.ReactNode;
              /** Extra value rows (opening hours with different day schedules) */
              extras?: React.ReactNode[];
              mobileInline?: boolean;
            };
            const rows: Row[] = [];

            if (ct.openingHours?.length) {
              rows.push({
                icon: "bi-clock",
                label: "Opening hours",
                value: (
                  <>
                    {formatDays(ct.openingHours[0].days)}:{" "}
                    {ct.openingHours[0].open} to {ct.openingHours[0].close}
                  </>
                ),
                extras: ct.openingHours.slice(1).map((oh) => (
                  <>
                    {formatDays(oh.days)}: {oh.open} to {oh.close}
                  </>
                )),
              });
            } else {
              rows.push({
                icon: "bi-clock",
                label: "Opening hours",
                value: <i className="bi bi-question-circle text-black" />,
                mobileInline: true,
              });
            }

            if (ct.operatingWeeksPerYear != null) {
              rows.push({
                icon: "bi-calendar3",
                label: "Annual opening",
                value: `${ct.operatingWeeksPerYear} weeks per\u00A0year`,
              });
            } else {
              rows.push({
                icon: "bi-calendar3",
                label: "Annual opening",
                value: <i className="bi bi-question-circle text-black" />,
                mobileInline: true,
              });
            }

            if (ct.eligibleAgeRange) {
              const lo =
                ct.eligibleAgeRange.minMonths != null
                  ? `${ct.eligibleAgeRange.minMonths} months`
                  : `${ct.eligibleAgeRange.minYears} years`;
              rows.push({
                icon: "bi-cake2",
                label: "Age range",
                value: `${lo} to ${ct.eligibleAgeRange.maxYears} years`,
                mobileInline: true,
              });
            }

            if (showFundedHoursFilter && ct.type !== "free_breakfast_club") {
              rows.push({
                icon: "bi-piggy-bank",
                label: "Funded hours",
                value:
                  ct.fundedHoursAccepted === true ? (
                    "Yes"
                  ) : ct.fundedHoursAccepted === false ? (
                    "No"
                  ) : (
                    <i className="bi bi-question-circle text-black" />
                  ),
                mobileInline: true,
              });
            }

            if (ct.website) {
              rows.push({
                icon: "bi-globe2",
                label: "Website",
                value: (
                  <ExternalLink
                    href={ct.website}
                    showIcon={false}
                    className="hover:underline block truncate max-w-[230px] sm:max-w-[340px] md:max-w-[440px]"
                  >
                    {ct.website.replace(/^https?:\/\//, "")}
                  </ExternalLink>
                ),
              });
            }
            if (ct.fisUrl) {
              rows.push({
                icon: "bi-globe2",
                label: "Family info",
                value: (
                  <ExternalLink
                    href={ct.fisUrl}
                    showIcon={false}
                    className="hover:underline block truncate max-w-[230px] sm:max-w-[340px] md:max-w-[440px]"
                  >
                    {ct.fisUrl.replace(/^https?:\/\//, "")}
                  </ExternalLink>
                ),
              });
            }

            return (
              <div className="text-sm mb-3">
                {rows.map((r, ri) => {
                  const bg = ri % 2 === 0 ? "bg-zinc-50" : "";
                  const extraRows = r.extras ?? [];
                  return (
                    <div key={ri}>
                      {/* Desktop: always label + value side by side */}
                      <div
                        className={`py-1 px-2 ${bg} hidden sm:flex justify-between`}
                      >
                        <span className="text-zinc-600">
                          <i className={`bi ${r.icon} mr-2`} />
                          {r.label}
                        </span>
                        <span className="font-medium text-right">
                          {r.value}
                        </span>
                      </div>
                      {r.mobileInline ? (
                        <div
                          className={`sm:hidden flex justify-between py-1 px-2 ${bg}`}
                        >
                          <span className="text-zinc-600">
                            <i className={`bi ${r.icon} mr-2`} />
                            {r.label}
                          </span>
                          <span className="font-medium text-right">
                            {r.value}
                          </span>
                        </div>
                      ) : (
                        <>
                          <div
                            className={`sm:hidden py-1 px-2 text-zinc-600 ${bg}`}
                          >
                            <i className={`bi ${r.icon} mr-2`} />
                            {r.label}
                          </div>
                          <div
                            className={`sm:hidden py-1 px-2 text-right font-medium ${bg}`}
                          >
                            {r.value}
                          </div>
                        </>
                      )}
                      {/* Extra rows (e.g. additional opening hour schedules) */}
                      {extraRows.map((extra, ei) => (
                        <div
                          key={ei}
                          className={`py-1 px-2 text-right font-medium ${bg}`}
                        >
                          {extra}
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            );
          })()}
          {showEligibility &&
            (ct.eligibleAttendeesOnly ||
              (ct.eligibleInstitutions && ct.eligibleInstitutions.length > 0) ||
              (ct.eligibleOther && ct.eligibleOther.length > 0)) && (
              <div className="text-sm mb-3">
                <span className="text-zinc-600">Eligibility:</span>
                <ul className="mt-1 space-y-1 pl-4">
                  {ct.eligibleAttendeesOnly && (
                    <li className="flex items-baseline gap-1.5">
                      <i className="bi bi-exclamation-triangle-fill text-yellow-700 shrink-0" />
                      <span>Attendees of {provider.name} only</span>
                    </li>
                  )}
                  {ct.eligibleInstitutions &&
                    ct.eligibleInstitutions.length > 0 && (
                      <li className="flex items-baseline gap-1.5">
                        <i className="bi bi-exclamation-triangle-fill text-yellow-700 shrink-0" />
                        <span>
                          Pupils of{" "}
                          {ct.eligibleInstitutions.length === 1
                            ? ct.eligibleInstitutions[0]
                            : `${ct.eligibleInstitutions.slice(0, -1).join(", ")}${ct.eligibleInstitutions.length > 2 ? "," : ""} and ${ct.eligibleInstitutions[ct.eligibleInstitutions.length - 1]}`}{" "}
                          only
                        </span>
                      </li>
                    )}
                  {(ct.eligibleOther ?? []).map((note, noteIdx) => (
                    <li key={noteIdx} className="flex items-baseline gap-1.5">
                      <i className="bi bi-exclamation-triangle-fill text-yellow-700 shrink-0" />
                      <span>{note}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

          {showAvailability && (
            <div className="text-sm mb-3">
              <span className="text-zinc-600">Availability:</span>
              {ct.waitingList ? (
                <ul className="mt-1 space-y-1 pl-4">
                  {Object.entries(ct.waitingList).map(([band, entry]) => {
                    const wait = entryToWeeks(entry);
                    const available = wait === 0;
                    return (
                      <li key={band} className="flex items-baseline gap-1.5">
                        <i
                          className={`bi ${available ? "bi-check-circle-fill text-green-600" : "bi-exclamation-triangle-fill text-yellow-700"} shrink-0`}
                        />
                        <span>
                          {AGE_BAND_LABELS[band] ?? band}:{" "}
                          {available
                            ? "Places available"
                            : `${entry.months != null ? `${entry.months} month` : `${entry.weeks} week`}${(entry.months ?? entry.weeks ?? 0) !== 1 ? "s" : ""} wait`}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <span className="ml-1">
                  <i className="bi bi-question-circle text-black" />
                </span>
              )}
            </div>
          )}

          {showNotes && (
            <div className="text-sm mb-3">
              <span className="text-zinc-600">Notes:</span>
              <ul className="mt-1 space-y-1 pl-4">
                {ct.minimumCommitment ? (
                  <li className="flex items-baseline gap-1.5">
                    <i className="bi bi-exclamation-triangle-fill text-yellow-700 shrink-0" />
                    <span>{formatMinimumCommitment(ct.minimumCommitment)}</span>
                  </li>
                ) : ct.minimumCommitment === false ? (
                  <li className="flex items-baseline gap-1.5">
                    <i className="bi bi-check-circle-fill text-green-600 shrink-0" />
                    <span>No minimum commitment</span>
                  </li>
                ) : (
                  <li className="flex items-baseline gap-1.5">
                    <i className="bi bi-question-circle text-black shrink-0" />
                    <span>Minimum commitment unknown</span>
                  </li>
                )}
                {ct.notes?.map((note, noteIdx) => (
                  <li key={noteIdx} className="flex items-baseline gap-1.5">
                    <i
                      className={`bi ${note.type === "warn" ? "bi-exclamation-triangle-fill text-yellow-700" : "bi-check-circle-fill text-green-600"} shrink-0`}
                    />
                    <span>{note.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </Modal>
  );
}

import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import type { Provider } from "@/types/provider";
import type { ProviderSearchEntry } from "@/lib/filterSortDedup";
import type {
  CostDisplayMode,
  SortOption,
} from "@/components/providers/ProviderFilters";
import type { PostcodeAreaCosts } from "@/types/costs";
import { ProviderCard } from "@/components/ui/ProviderCard";
import { ProviderCardSkeleton } from "@/components/ui/ProviderCardSkeleton";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { useLastInputWasKeyboard } from "@/hooks/useLastInputWasKeyboard";

const typeLabelsPlural: Record<string, string> = {
  private_nursery: "nurseries (Private, Voluntary or Independent)",
  school_based_nursery: "school-based nurseries",
  childminder: "childminders",
  breakfast_club: "breakfast clubs",
  after_school_club: "after school clubs",
  holiday_club: "holiday clubs",
};

interface ProviderListProps {
  entries: ProviderSearchEntry[];
  loadedProviders: Map<string, Provider>;
  totalCount: number;
  hasMore: boolean;
  onShowMore: () => void;
  shortlistedIds: string[];
  onSelect: (provider: Provider) => void;
  onToggleShortlist: (providerId: string) => void;
  costDisplayMode: CostDisplayMode;
  includeAdditionalCharges: boolean;
  sortBy?: SortOption;
  postcode?: string;
  fundedHoursOnly?: boolean;
  selectedTypes?: string[];
  childAgesMonths?: number[];
  bboxCount?: number;
  beyondCount?: number;
  beyondMaxMiles?: number;
  areaCosts?: PostcodeAreaCosts | null;
  missingBboxCount?: number;
  onZoomToLa?: () => void;
  onRetryProvider?: (providerId: string) => void;
  listVersion?: number;
}

export function ProviderList({
  entries,
  loadedProviders,
  totalCount,
  hasMore,
  onShowMore,
  shortlistedIds,
  onSelect,
  onToggleShortlist,
  costDisplayMode,
  includeAdditionalCharges,
  sortBy,
  postcode,
  fundedHoursOnly,
  selectedTypes,
  childAgesMonths,
  bboxCount = 0,
  beyondCount,
  beyondMaxMiles,
  areaCosts,
  missingBboxCount = 0,
  onZoomToLa,
  onRetryProvider,
  listVersion = 0,
}: ProviderListProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [listFocused, setListFocused] = useState(false);
  const cardRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const listboxRef = useRef<HTMLDivElement>(null);
  const prevVersionRef = useRef(listVersion);
  const lastInputWasKeyboard = useLastInputWasKeyboard();

  const setCardRef = useCallback(
    (index: number) => (el: HTMLDivElement | null) => {
      if (el) cardRefs.current.set(index, el);
      else cardRefs.current.delete(index);
    },
    [],
  );

  const loadedEntries = entries.filter((e) =>
    loadedProviders.has(e.providerId),
  );

  const providerNoun =
    selectedTypes?.length === 1
      ? (typeLabelsPlural[selectedTypes[0]] ?? "providers")
      : "providers";

  const [statusAnnouncement, setStatusAnnouncement] = useState("");
  const statusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const statusText = useMemo(() => {
    if (totalCount === 0 && (postcode ?? "").trim().length > 0)
      return `No ${providerNoun} found`;
    if (totalCount === 0) return "";
    return `Showing ${entries.length} of ${totalCount} ${providerNoun}`;
  }, [totalCount, entries.length, providerNoun, postcode]);

  useEffect(() => {
    if (statusTimerRef.current) clearTimeout(statusTimerRef.current);
    statusTimerRef.current = setTimeout(() => {
      setStatusAnnouncement(statusText);
    }, 800);
    return () => {
      if (statusTimerRef.current) clearTimeout(statusTimerRef.current);
    };
  }, [statusText]);

  useEffect(() => {
    if (prevVersionRef.current !== listVersion) {
      prevVersionRef.current = listVersion;
      setActiveIndex(0);
    }
  }, [listVersion]);

  function getStickyOffset(): number {
    const header = document.getElementById("sticky-header");
    const headerH = header ? header.getBoundingClientRect().height : 0;
    const listContainer = listboxRef.current?.parentElement?.parentElement;
    const mapWrapper =
      listContainer?.previousElementSibling as HTMLElement | null;
    const mapH =
      mapWrapper && getComputedStyle(mapWrapper).position === "sticky"
        ? mapWrapper.getBoundingClientRect().height
        : 0;
    return headerH + mapH;
  }

  function scrollCardIntoSafeView(
    index: number,
    direction: "up" | "down" | "center",
  ) {
    const el = cardRefs.current.get(index);
    if (!el) return;
    const offset = getStickyOffset();
    const rect = el.getBoundingClientRect();
    const vh = window.innerHeight;

    if (direction === "up") {
      const targetTop = offset + 80;
      if (rect.top < targetTop) {
        window.scrollBy({ top: rect.top - targetTop, behavior: "smooth" });
      }
    } else if (direction === "down") {
      const peekEl = cardRefs.current.get(index + 1);
      const nextEl =
        peekEl ??
        (listboxRef.current?.nextElementSibling as HTMLElement | null);
      const bottomEdge = nextEl
        ? nextEl.getBoundingClientRect().bottom
        : rect.bottom;
      if (bottomEdge > vh - 16) {
        window.scrollBy({ top: bottomEdge - (vh - 16), behavior: "smooth" });
      }
    } else {
      const targetTop = offset + 80;
      if (rect.top < targetTop || rect.bottom > vh - 16) {
        window.scrollBy({ top: rect.top - targetTop, behavior: "instant" });
      }
    }
  }

  const handleListKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Tab" && e.shiftKey) {
      requestAnimationFrame(() => {
        const mapEl = document.querySelector<HTMLElement>(
          '[role="application"]',
        );
        if (!mapEl) return;
        const header = document.getElementById("sticky-header");
        const topOffset = header ? header.getBoundingClientRect().bottom : 0;
        const mapRect = mapEl.getBoundingClientRect();
        if (mapRect.top < topOffset + 8) {
          window.scrollBy({
            top: mapRect.top - topOffset - 8,
            behavior: "smooth",
          });
        }
      });
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    let nextIndex = activeIndex;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        nextIndex = Math.min(activeIndex + 1, loadedEntries.length - 1);
        break;
      case "ArrowUp":
        e.preventDefault();
        nextIndex = Math.max(activeIndex - 1, 0);
        break;
      case "Home":
        e.preventDefault();
        nextIndex = 0;
        break;
      case "End":
        e.preventDefault();
        nextIndex = loadedEntries.length - 1;
        break;
      case "Enter": {
        e.preventDefault();
        const entry = loadedEntries[activeIndex];
        const provider = entry && loadedProviders.get(entry.providerId);
        if (provider) onSelect(provider);
        return;
      }
      default:
        return;
    }
    if (nextIndex !== activeIndex) {
      setActiveIndex(nextIndex);
      scrollCardIntoSafeView(
        nextIndex,
        nextIndex > activeIndex ? "down" : "up",
      );
    }
  };

  const fisList = areaCosts?.familyInformationServices ?? [];

  const providerStatsEntries = Object.entries(
    areaCosts?.providerStats ?? {},
  ).filter(
    ([type, s]) =>
      s.total > 0 &&
      (s.bboxOnly > 0 || s.insufficient > 0) &&
      (!selectedTypes?.length || selectedTypes.includes(type)),
  );

  const bboxStatsTypes = Object.entries(areaCosts?.providerStats ?? {})
    .filter(
      ([type, s]) =>
        s.bboxOnly > 0 &&
        (!selectedTypes?.length || selectedTypes.includes(type)),
    )
    .map(([type]) => type);
  const missingBboxNoun =
    bboxStatsTypes.length === 1
      ? (typeLabelsPlural[bboxStatsTypes[0]] ?? "providers")
      : providerNoun;

  const hasSearched = (postcode ?? "").trim().length > 0;

  return (
    <div className="space-y-3">
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {statusAnnouncement}
      </p>
      {totalCount === 0 ? (
        <div className="bg-white rounded-xl border border-zinc-200 p-8 text-center">
          <p className="text-lg font-bold mb-2">
            {hasSearched ? `No ${providerNoun} found` : "Enter a postcode"}
          </p>
          <p className="text-sm text-zinc-600 max-w-prose mx-auto ">
            {hasSearched ? (
              "Try adjusting your childcare search filters, or change your search area by zooming out or moving the map around."
            ) : (
              <>
                Put a postcode into the search box above the map and filters to
                find childcare providers near you. If you're not in our beta,
                you can also find more local childcare options using{" "}
                <ExternalLink
                  href="https://www.gov.uk/find-free-early-education"
                  className="text-purple-700 underline hover:text-purple-900"
                >
                  Find free early education and childcare
                </ExternalLink>
              </>
            )}
          </p>
        </div>
      ) : (
        <p className="text-sm text-zinc-600">
          Showing {entries.length} of {totalCount} {providerNoun}
          {bboxCount > 0 && ` (including ${bboxCount} without map pins)`}
          {beyondCount != null && beyondCount > 0 && (
            <>
              , {beyondCount} more within {Math.ceil(beyondMaxMiles!)} miles
            </>
          )}
        </p>
      )}
      {totalCount > 0 && (
        <>
          <div
            ref={listboxRef}
            role="listbox"
            aria-label="Provider results"
            aria-activedescendant={
              listFocused && loadedEntries[activeIndex]
                ? `provider-${loadedEntries[activeIndex].providerId}`
                : undefined
            }
            tabIndex={0}
            onKeyDown={handleListKeyDown}
            onFocus={() => {
              if (!lastInputWasKeyboard.current) return;
              setListFocused(true);
              const idx = activeIndex >= loadedEntries.length ? 0 : activeIndex;
              if (idx !== activeIndex) setActiveIndex(idx);
              scrollCardIntoSafeView(idx, "center");
            }}
            onBlur={() => setListFocused(false)}
            className="grid grid-cols-1 xl:grid-cols-2 gap-3 outline-none rounded-xl"
          >
            {(() => {
              let loadedIndex = 0;
              return entries.map((entry) => {
                const provider = loadedProviders.get(entry.providerId);
                if (provider) {
                  const idx = loadedIndex++;
                  return (
                    <ProviderCard
                      key={entry.providerId}
                      ref={setCardRef(idx)}
                      id={`provider-${entry.providerId}`}
                      provider={provider}
                      isShortlisted={shortlistedIds.includes(entry.providerId)}
                      onSelect={() => {
                        setActiveIndex(idx);
                        onSelect(provider);
                      }}
                      onToggleShortlist={() =>
                        onToggleShortlist(entry.providerId)
                      }
                      costDisplayMode={costDisplayMode}
                      includeAdditionalCharges={includeAdditionalCharges}
                      sortBy={sortBy}
                      postcode={postcode}
                      fundedHoursOnly={fundedHoursOnly}
                      selectedTypes={selectedTypes}
                      childAgesMonths={childAgesMonths}
                      active={listFocused && idx === activeIndex}
                    />
                  );
                }
                return (
                  <ProviderCardSkeleton
                    key={entry.providerId}
                    distanceMiles={entry.distanceMiles}
                    postcode={postcode}
                    onRetry={
                      onRetryProvider
                        ? () => onRetryProvider(entry.providerId)
                        : undefined
                    }
                  />
                );
              });
            })()}
          </div>
          {hasMore && (
            <button
              onClick={() => {
                onShowMore();
                if (!lastInputWasKeyboard.current) return;
                requestAnimationFrame(() => {
                  setListFocused(true);
                  listboxRef.current?.focus({ preventScroll: true });
                  scrollCardIntoSafeView(activeIndex, "center");
                });
              }}
              className="btn-dark w-full"
            >
              Show more {providerNoun} ({entries.length} of {totalCount})
            </button>
          )}
        </>
      )}
      {((!hasMore && beyondCount != null && beyondCount > 0) ||
        (missingBboxCount > 0 && areaCosts) ||
        providerStatsEntries.length > 0 ||
        fisList.length > 0) && (
        <div className="mt-10 space-y-8 rounded-xl border border-zinc-200 py-6 px-4 sm:py-8 sm:px-12 mx-auto w-fit">
          {!hasMore && beyondCount != null && beyondCount > 0 && (
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-3 max-w-prose mx-auto text-sm sm:text-base text-zinc-600">
              <i
                className="bi bi-map text-zinc-600 text-3xl sm:text-4xl leading-none flex-shrink-0 sm:mt-1"
                aria-hidden="true"
              />
              <p className="text-center sm:text-left">
                Pan or zoom your map to find more {providerNoun}. There{" "}
                {beyondCount === 1 ? "is" : "are"}{" "}
                <strong>{beyondCount}</strong> more within{" "}
                {Math.ceil(beyondMaxMiles!)} miles.
              </p>
            </div>
          )}
          {missingBboxCount > 0 && areaCosts && (
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-3 max-w-prose mx-auto text-sm sm:text-base text-zinc-600">
              <i
                className="bi bi-patch-question text-zinc-600 text-3xl sm:text-4xl leading-none flex-shrink-0 sm:mt-1"
                aria-hidden="true"
              />
              <div className="text-center sm:text-left">
                <p>
                  There are <strong>{missingBboxCount}</strong> further{" "}
                  {missingBboxNoun} in <strong>{areaCosts.laName}</strong> which
                  don&apos;t have map pins.
                </p>
                {onZoomToLa && areaCosts.laBounds && (
                  <div className="mt-2 flex justify-center sm:justify-start sm:ml-4">
                    <button onClick={onZoomToLa} className="btn">
                      Show me
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
          {providerStatsEntries.length > 0 && (
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-3 max-w-prose mx-auto text-sm sm:text-base text-zinc-600">
              <i
                className="bi bi-shield-check text-zinc-600 text-3xl sm:text-4xl leading-none flex-shrink-0 sm:mt-1"
                aria-hidden="true"
              />
              <div className="text-center sm:text-left">
                {providerStatsEntries.map(([type, stat]) => (
                  <p key={type}>
                    <strong>{areaCosts!.laName}</strong> has{" "}
                    <strong>
                      {stat.total} {typeLabelsPlural[type] ?? type}
                    </strong>{" "}
                    in our dataset
                    {stat.insufficient > 0 && (
                      <>
                        , but we think there are{" "}
                        <strong>{stat.insufficient} others</strong> whose online
                        details have been removed to protect their privacy. You
                        might be able to find out more at your local family
                        information service
                      </>
                    )}
                    .
                  </p>
                ))}
              </div>
            </div>
          )}
          {fisList.length > 0 && (
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-3 max-w-prose mx-auto text-sm sm:text-base text-zinc-600">
              <i
                className="bi bi-globe2 text-zinc-600 text-3xl sm:text-4xl leading-none flex-shrink-0 sm:mt-1"
                aria-hidden="true"
              />
              <div className="text-center sm:text-left">
                <p>
                  You can find more childcare information and providers near{" "}
                  <strong>{postcode}</strong> in the{" "}
                  <strong>{areaCosts!.laName}</strong> Family Information
                  Service.
                </p>
                {fisList.map((fis) => (
                  <ExternalLink
                    key={fis.url}
                    href={fis.url}
                    showIcon={false}
                    className="inline-flex items-center gap-1 break-all underline hover:text-zinc-900"
                  >
                    {fis.url}
                  </ExternalLink>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

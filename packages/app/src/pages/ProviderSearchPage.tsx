import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { usePostHog } from "posthog-js/react";
import { useFamily } from "@/hooks/useFamily";
import { useProviderSearch } from "@/hooks/useProviderSearch";
import { PageHero } from "@/components/layout/PageHero";
import { Container } from "@/components/layout/Container";
import { ProviderSearch } from "@/components/providers/ProviderSearch";
import {
  ProviderFilters,
  type CostDisplayMode,
  type SortOption,
} from "@/components/providers/ProviderFilters";
import { sortOptions } from "@/components/providers/sortOptions";
import { ProviderMap } from "@/components/providers/ProviderMap";
import { ProviderList } from "@/components/providers/ProviderList";
import { ProviderDetail } from "@/components/providers/ProviderDetail";
import type { Provider } from "@/types/provider";
import { usePostcodeLookup, type PostcodeGeo } from "@/hooks/usePostcodeLookup";
import { initPmtilesProtocol } from "@/data/pmtilesProtocol";
import { loadProvider, loadLaCosts } from "@/data/loader";
import type { PostcodeAreaCosts } from "@/types/costs";
import { Modal } from "@/components/ui/Modal";
import { BetaBanner } from "@/components/ui/BetaBanner";
import { getChildAgeMonths } from "@/lib/childAge";
import { filterProviderIdsInViewport } from "@/lib/viewportFilter";
import { capBboxByPointDistance, computeMissingBboxCount } from "@/lib/bboxCap";
import { normalisePostcode } from "@/lib/postcode";
import type { ProviderSearchEntry } from "@/lib/filterSortDedup";
import {
  getProviderSearchState,
  saveProviderSearchState,
} from "@/lib/providerSearchStore";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { distanceBand, childAgeBands } from "@/lib/providerAnalytics";

initPmtilesProtocol();

const PAGE_SIZE = 20;

const LAD_PREFIX: Record<string, number> = { E: 1, S: 2, W: 3, N: 4 };
function encodeLad(code: string | null): number {
  if (!code || code.length < 2) return 0;
  const prefix = LAD_PREFIX[code[0]] ?? 0;
  return prefix * 100_000_000 + parseInt(code.slice(1), 10);
}

export default function ProviderSearchPage() {
  const posthog = usePostHog();
  const { selectedFamily, sisSchema, shortlistedProviders, toggleShortlist } =
    useFamily();

  const [areaCosts, setAreaCosts] = useState<PostcodeAreaCosts | null>(null);
  const [searchedLaCode, setSearchedLaCode] = useState<string | null>(null);
  // areaCosts is intentionally local to this page, not read from FamilyContext.
  // The provider search postcode (searchedPostcode) may differ from the user's home
  // address in the cost form. Using a separate state ensures that searching providers
  // in a different area does not affect cost estimates on the CostResults page.

  // Restore UI state from previous visit (module-level store survives navigation)
  const [snapshot] = useState(() => getProviderSearchState());

  const [postcode, setPostcode] = useState(snapshot?.postcode ?? "");
  const [searchedPostcode, setSearchedPostcode] = useState(
    snapshot?.searchedPostcode ?? "",
  );
  const [selectedTypes, setSelectedTypes] = useState<string[]>(
    snapshot?.selectedTypes ?? [],
  );
  const [selectedChildren, setSelectedChildren] = useState<string[]>(() => {
    const saved = snapshot?.selectedChildren ?? [];
    const validNames = new Set(
      selectedFamily?.localStorage.children.map((c) => c.firstName) ?? [],
    );
    return saved.filter((name) => validNames.has(name));
  });
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null,
  );
  const [coLocatedProviders, setCoLocatedProviders] = useState<Provider[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(snapshot?.filtersOpen ?? true);
  const [shortlistedOnly, setShortlistedOnly] = useState(
    snapshot?.shortlistedOnly ?? false,
  );
  const [costDisplayMode, setCostDisplayMode] = useState<CostDisplayMode>(
    snapshot?.costDisplayMode ?? "detailed",
  );
  const [includeAdditionalCharges, setIncludeAdditionalCharges] = useState(
    snapshot?.includeAdditionalCharges ?? true,
  );
  const [sortBy, setSortBy] = useState<SortOption>(
    snapshot?.sortBy ?? "distance",
  );
  const [fundedHoursOnly, setFundedHoursOnly] = useState(
    snapshot?.fundedHoursOnly ?? false,
  );
  const [mapResetKey, setMapResetKey] = useState(snapshot?.mapResetKey ?? 0);
  const [animatingPinId, setAnimatingPinId] = useState<string | null>(null);
  const [showAllBbox, setShowAllBbox] = useState(false);
  const [highlightedLaCode, setHighlightedLaCode] = useState<string | null>(
    null,
  );
  const fitBoundsActiveRef = useRef(false);
  const [initialBounds, setInitialBounds] = useState<
    [number, number, number, number] | null
  >(snapshot?.initialBounds ?? null);
  // On restore, start the map at the user's last viewport, not the postcode area.
  // mapBounds is [south, west, north, east] but initialBounds is [west, south, east, north],
  // so convert when using mapBounds as the map's starting position.
  const [mapInitialBounds, setMapInitialBounds] = useState<
    [number, number, number, number] | null
  >(() => {
    if (snapshot?.mapBounds) {
      const [s, w, n, e] = snapshot.mapBounds;
      return [w, s, e, n];
    }
    return snapshot?.initialBounds ?? null;
  });
  const [mapBounds, setMapBounds] = useState<
    [number, number, number, number] | null
  >(snapshot?.mapBounds ?? null);
  const [mapCenter, setMapCenter] = useState<[number, number] | null>(
    snapshot?.mapCenter ?? null,
  );
  const [mapZoom, setMapZoom] = useState<number | null>(
    snapshot?.mapZoom ?? null,
  );
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  // On restore, seed pendingSearchRef so the first handleBoundsChange triggers sisSearch
  const restoredGeo =
    snapshot?.postcodeBbox && snapshot?.postcodeCentroid
      ? { bbox: snapshot.postcodeBbox, centroid: snapshot.postcodeCentroid }
      : null;
  const pendingSearchRef = useRef<{
    bbox: [number, number, number, number];
    centroid: [number, number];
  } | null>(restoredGeo);
  // Track last searched geo for saving to snapshot on unmount
  const lastSearchGeoRef = useRef<{
    bbox: [number, number, number, number];
    centroid: [number, number];
  } | null>(restoredGeo);

  const zoomTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stableZoomRef = useRef<number | null>(null);
  const lastZoomSourceRef = useRef<"keyboard" | "button">("button");

  const requeryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const adHocCacheRef = useRef<Map<string, Provider>>(new Map());
  const [adHocProviders, setAdHocProviders] = useState<Map<string, Provider>>(
    new Map(),
  );
  const [pendingLoadId, setPendingLoadId] = useState<string | null>(null);

  const { getGeo, ensureInward, getLaCodes } = usePostcodeLookup();
  const [validatingPostcode, setValidatingPostcode] = useState(false);

  // Save UI state to module-level store on unmount (survives navigation)
  const snapshotRef = useRef(snapshot);
  useEffect(() => {
    snapshotRef.current = {
      postcode,
      searchedPostcode,
      selectedTypes,
      selectedChildren,
      shortlistedOnly,
      costDisplayMode,
      includeAdditionalCharges,
      sortBy,
      fundedHoursOnly,
      filtersOpen,
      initialBounds,
      mapBounds,
      mapResetKey,
      postcodeBbox: lastSearchGeoRef.current?.bbox ?? null,
      postcodeCentroid: lastSearchGeoRef.current?.centroid ?? null,
      mapCenter,
      mapZoom,
    };
  });
  useEffect(() => {
    return () => {
      if (zoomTimerRef.current) clearTimeout(zoomTimerRef.current);
      if (snapshotRef.current) saveProviderSearchState(snapshotRef.current);
      if (requeryTimerRef.current) clearTimeout(requeryTimerRef.current);
    };
  }, []);

  // Load per-LA cost/FIS data for the searched postcode. Writes to local areaCosts only —
  // not to FamilyContext — to keep provider search data isolated from cost estimates.
  useEffect(() => {
    if (!searchedPostcode?.includes(" ")) return;
    const [outward, inward] = searchedPostcode.split(" ");
    if (!outward || !inward) return;
    let cancelled = false;
    (async () => {
      await ensureInward(outward);
      if (cancelled) return;
      const laCodes = getLaCodes(outward, inward);
      for (const code of laCodes) {
        if (cancelled) return;
        try {
          const costs = await loadLaCosts(code);
          if (cancelled) return;
          setAreaCosts(costs);
          setSearchedLaCode(code);
          return;
        } catch {
          continue;
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [searchedPostcode, ensureInward, getLaCodes, setAreaCosts]);

  const children = useMemo(
    () => selectedFamily?.localStorage.children || [],
    [selectedFamily],
  );

  const childAgesMonths = useMemo(() => {
    if (selectedChildren.length === 0) return [];
    return selectedChildren.map((name) => {
      const child = children.find((c) => c.firstName === name);
      return child && child.birthMonth !== null && child.birthYear !== null
        ? getChildAgeMonths(child.birthMonth, child.birthYear)
        : 0;
    });
  }, [selectedChildren, children]);

  const [requestedIds, setRequestedIds] = useState<string[]>([]);

  const {
    entries,
    loadedProviders,
    loading: providersLoading,
    bboxMap,
    pointMap,
    search: sisSearch,
    requery: sisRequery,
    retryProvider,
  } = useProviderSearch(
    sisSchema,
    selectedTypes,
    childAgesMonths,
    fundedHoursOnly,
    sortBy,
    shortlistedOnly,
    shortlistedProviders,
    requestedIds,
  );

  const sisSearchRef = useRef(sisSearch);
  const sisRequeryRef = useRef(sisRequery);
  useEffect(() => {
    sisSearchRef.current = sisSearch;
    sisRequeryRef.current = sisRequery;
  });

  const entryIds = useMemo(() => entries.map((e) => e.providerId), [entries]);

  function handleToggleShortlist(providerId: string) {
    toggleShortlist(providerId);
    setAnimatingPinId(providerId);
    if (posthog) {
      const isRemoving = shortlistedProviders.includes(providerId);
      const nextIds = isRemoving
        ? shortlistedProviders.filter((id) => id !== providerId)
        : [...shortlistedProviders, providerId];
      const careTypes = new Set<string>();
      for (const id of nextIds) {
        const p = loadedProviders.get(id) ?? adHocCacheRef.current.get(id);
        if (p) for (const ct of p.careTypes) careTypes.add(ct.type);
      }
      posthog.capture("provider_shortlisted", {
        shortlist_care_types: [...careTypes].sort(),
      });
    }
  }

  function handleRequestProviders(ids: string[]) {
    const toLoad = ids.filter(
      (id) => !loadedProviders.has(id) && !adHocCacheRef.current.has(id),
    );
    if (toLoad.length === 0) return;
    Promise.allSettled(toLoad.map((id) => loadProvider(id)))
      .then((results) => {
        const loaded = new Map(adHocCacheRef.current);
        results.forEach((r, i) => {
          if (r.status === "fulfilled") {
            r.value.distanceMiles = 0;
            loaded.set(toLoad[i], r.value);
          }
        });
        adHocCacheRef.current = loaded;
        setAdHocProviders(loaded);
      })
      .catch((err) =>
        console.error("[ProviderSearch] handleRequestProviders failed:", err),
      );
  }

  function captureDetailViewed(provider: Provider) {
    posthog?.capture("provider_detail_viewed", {
      distance_band: distanceBand(provider.distanceMiles),
    });
  }

  async function handleProviderPending(id: string) {
    const sisProvider = loadedProviders.get(id);
    if (sisProvider) {
      setSelectedProvider(sisProvider);
      captureDetailViewed(sisProvider);
      return;
    }
    const cached = adHocCacheRef.current.get(id);
    if (cached) {
      setSelectedProvider(cached);
      captureDetailViewed(cached);
      return;
    }
    setPendingLoadId(id);
    try {
      const p = await loadProvider(id);
      p.distanceMiles = 0;
      adHocCacheRef.current.set(id, p);
      setAdHocProviders(new Map(adHocCacheRef.current));
      setSelectedProvider(p);
      captureDetailViewed(p);
    } catch (err) {
      console.error("[ProviderSearch] handleProviderPending failed:", err);
    }
    setPendingLoadId(null);
  }

  // Refs for scroll targets
  const gridRef = useRef<HTMLDivElement>(null);
  const mainContentRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [listVersion, setListVersion] = useState(0);
  const prevBoundsRef = useRef<[number, number, number, number] | null>(null);

  // Sticky map: stick when map height < 2/3 of viewport
  const mapWrapperRef = useRef<HTMLDivElement>(null);

  // Fit-to-LA-bounds request for the map
  const [fitBoundsRequest, setFitBoundsRequest] = useState<{
    key: number;
    bounds: [number, number, number, number];
  } | null>(null);
  const fitKeyRef = useRef(0);
  const [stickyTop, setStickyTop] = useState<number | null>(null);
  const [isStuck, setIsStuck] = useState(false);

  useEffect(() => {
    const el = mapWrapperRef.current;
    if (!el) return;

    function check() {
      const vh = window.innerHeight;
      const mapH = el!.getBoundingClientRect().height;
      const header = document.getElementById("sticky-header");
      const headerH = header ? header.getBoundingClientRect().height : 0;

      const singleColumn = window.innerWidth < 1024;
      setStickyTop(
        singleColumn && mapH > 0 && mapH < (2 / 3) * vh ? headerH : null,
      );
    }

    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    window.addEventListener("resize", check);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", check);
    };
  }, []);

  useEffect(() => {
    if (stickyTop == null) return;
    const el = mapWrapperRef.current;
    if (!el) return;

    let wasStuck = false;
    function onScroll() {
      const stuck = el!.getBoundingClientRect().top <= stickyTop! + 1;
      if (stuck !== wasStuck) {
        wasStuck = stuck;
        setIsStuck(stuck);
      }
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, [stickyTop]);

  useEffect(() => {
    if (stickyTop != null) {
      mainContentRef.current?.style.removeProperty("--grid-scroll-margin");
      return;
    }
    const main = mainContentRef.current;
    const grid = gridRef.current;
    if (!main || !grid) return;

    function updateScrollMargin() {
      const header = document.getElementById("sticky-header");
      const headerH = header ? header.offsetHeight : 0;
      const gridTop = grid!.getBoundingClientRect().top;
      const mainTop = main!.getBoundingClientRect().top;
      const offset = mainTop - gridTop;
      main!.style.setProperty(
        "--grid-scroll-margin",
        `${offset + headerH + 8}px`,
      );
    }

    updateScrollMargin();
    window.addEventListener("resize", updateScrollMargin);
    return () => window.removeEventListener("resize", updateScrollMargin);
  }, [stickyTop]);

  const scrollToElement = useCallback(
    (ref: React.RefObject<HTMLDivElement | null>) => {
      const el = ref.current;
      if (!el) return;
      const header = document.getElementById("sticky-header");
      const headerH = header ? header.offsetHeight : 0;
      const mapEl = mapWrapperRef.current;
      const mapH = stickyTop != null && mapEl ? mapEl.offsetHeight : 0;
      el.style.scrollMarginTop = `${headerH + mapH + 8}px`;
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    [stickyTop],
  );

  const handleZoomToLa = useCallback(() => {
    if (!areaCosts?.laBounds) return;
    posthog?.capture("provider_zoom_to_la", { lad25cd: searchedLaCode });
    const { south, west, north, east } = areaCosts.laBounds;
    fitKeyRef.current += 1;
    setFitBoundsRequest({
      key: fitKeyRef.current,
      bounds: [south, west, north, east],
    });
    setShowAllBbox(true);
    setHighlightedLaCode(searchedLaCode);
    fitBoundsActiveRef.current = true;
    scrollToElement(stickyTop != null ? listRef : gridRef);
    requestAnimationFrame(() => {
      const mapEl = mapWrapperRef.current?.querySelector<HTMLElement>(
        '[role="application"]',
      );
      mapEl?.focus({ preventScroll: true });
    });
  }, [areaCosts, searchedLaCode, scrollToElement, stickyTop, posthog]);

  function triggerSearch(geo: PostcodeGeo, normalised: string) {
    setPostcode(normalised);
    setSearchedPostcode(normalised);
    setInitialBounds(geo.bbox);
    setMapInitialBounds(geo.bbox);
    setMapCenter(null);
    setMapZoom(null);
    setShowAllBbox(false);
    setHighlightedLaCode(null);
    pendingSearchRef.current = { bbox: geo.bbox, centroid: geo.centroid };
    lastSearchGeoRef.current = pendingSearchRef.current;
    setMapResetKey((k) => k + 1);
    scrollToElement(stickyTop != null ? mapWrapperRef : gridRef);
    requestAnimationFrame(() => {
      const mapEl = mapWrapperRef.current?.querySelector<HTMLElement>(
        '[role="application"]',
      );
      mapEl?.focus({ preventScroll: true });
    });

    if (posthog) {
      const [outward, inward] = normalised.split(" ");
      (async () => {
        if (outward) await ensureInward(outward);
        const laCodes = getLaCodes(outward, inward);
        const lad25cd =
          laCodes.find((c) => c.startsWith("E")) ?? laCodes[0] ?? null;
        posthog.capture("provider_search", {
          lad25cd,
          iod_decile: geo.deprivationDecile ?? null,
          care_types: selectedTypes,
          sort_by: sortBy,
          funded_hours_only: fundedHoursOnly,
          child_age_bands: childAgeBands(childAgesMonths),
        });
      })();
    }
  }

  const handleViewStateChange = useCallback(
    (center: [number, number], zoom: number) => {
      setMapCenter(center);
      setMapZoom(zoom);
    },
    [],
  );

  const handleZoom = useCallback(
    (zoom: number, _direction: "in" | "out", source: "keyboard" | "button") => {
      lastZoomSourceRef.current = source;
      if (stableZoomRef.current === null) {
        stableZoomRef.current = _direction === "in" ? zoom - 1 : zoom + 1;
      }
      if (zoomTimerRef.current) clearTimeout(zoomTimerRef.current);
      zoomTimerRef.current = setTimeout(() => {
        const startZoom = stableZoomRef.current!;
        const netDirection =
          zoom > startZoom ? "in" : zoom < startZoom ? "out" : null;
        if (netDirection && posthog) {
          posthog.capture(
            netDirection === "in" ? "provider_zoom_in" : "provider_zoom_out",
            { zoom_level: Math.round(zoom), source: lastZoomSourceRef.current },
          );
        }
        stableZoomRef.current = zoom;
      }, 5000);
    },
    [posthog],
  );

  const handleBoundsChange = useCallback(
    (bounds: [number, number, number, number]) => {
      const prev = prevBoundsRef.current;
      const changed =
        !prev ||
        Math.abs(bounds[0] - prev[0]) > 1e-6 ||
        Math.abs(bounds[1] - prev[1]) > 1e-6 ||
        Math.abs(bounds[2] - prev[2]) > 1e-6 ||
        Math.abs(bounds[3] - prev[3]) > 1e-6;
      prevBoundsRef.current = bounds;
      if (changed) setListVersion((v) => v + 1);
      setMapBounds(bounds);
      if (fitBoundsActiveRef.current) {
        fitBoundsActiveRef.current = false;
      } else {
        setShowAllBbox(false);
        setHighlightedLaCode(null);
      }
      const pending = pendingSearchRef.current;
      if (pending) {
        pendingSearchRef.current = null;
        if (requeryTimerRef.current) {
          clearTimeout(requeryTimerRef.current);
          requeryTimerRef.current = null;
        }
        sisSearchRef
          .current(pending.bbox, pending.centroid, bounds)
          .catch((err) =>
            console.error("[ProviderSearch] sisSearch failed:", err),
          );
      } else {
        if (requeryTimerRef.current) clearTimeout(requeryTimerRef.current);
        requeryTimerRef.current = setTimeout(() => {
          requeryTimerRef.current = null;
          sisRequeryRef
            .current(bounds)
            .catch((err) =>
              console.error("[ProviderSearch] sisRequery failed:", err),
            );
        }, 400);
      }
    },
    [],
  );

  const handleSortByChange = useCallback(
    (v: SortOption) => {
      setListVersion((n) => n + 1);
      setSortBy(v);
      posthog?.capture("provider_filter_changed", {
        care_types: selectedTypes,
        sort_by: v,
        funded_hours_only: fundedHoursOnly,
        child_age_bands: childAgeBands(childAgesMonths),
      });
    },
    [posthog, selectedTypes, fundedHoursOnly, childAgesMonths],
  );

  const handleTypesChange = useCallback(
    (v: string[]) => {
      setListVersion((n) => n + 1);
      setSelectedTypes(v);
      if (v.length > 0) setShortlistedOnly(false);
      posthog?.capture("provider_filter_changed", {
        care_types: v,
        sort_by: sortBy,
        funded_hours_only: fundedHoursOnly,
        child_age_bands: childAgeBands(childAgesMonths),
      });
    },
    [posthog, sortBy, fundedHoursOnly, childAgesMonths],
  );

  const handleFundedHoursOnlyChange = useCallback(
    (v: boolean) => {
      setListVersion((n) => n + 1);
      setFundedHoursOnly(v);
      posthog?.capture("provider_filter_changed", {
        care_types: selectedTypes,
        sort_by: sortBy,
        funded_hours_only: v,
        child_age_bands: childAgeBands(childAgesMonths),
      });
    },
    [posthog, selectedTypes, sortBy, childAgesMonths],
  );

  const handleShortlistedOnlyChange = useCallback((v: boolean) => {
    setListVersion((n) => n + 1);
    setShortlistedOnly(v);
    if (v) setSelectedTypes([]);
  }, []);

  const handleChildrenChange = useCallback(
    (v: string[]) => {
      setSelectedChildren(v);
      const newAges = v.map((name) => {
        const child = children.find((c) => c.firstName === name);
        return child && child.birthMonth !== null && child.birthYear !== null
          ? getChildAgeMonths(child.birthMonth, child.birthYear)
          : 0;
      });
      posthog?.capture("provider_filter_changed", {
        care_types: selectedTypes,
        sort_by: sortBy,
        funded_hours_only: fundedHoursOnly,
        child_age_bands: childAgeBands(newAges),
      });
    },
    [posthog, children, selectedTypes, sortBy, fundedHoursOnly],
  );

  async function handleSearch(overridePostcode?: string, geo?: PostcodeGeo) {
    const normalised = normalisePostcode(overridePostcode ?? postcode);

    // If geo was passed from dropdown selection, use it directly
    if (geo) {
      triggerSearch(geo, normalised);
      return;
    }

    // Manual entry — look up geo from cached data
    // (ProviderSearch already validated + called ensureInward, so data should be cached)
    const parts = normalised.split(" ");
    if (parts.length === 2) {
      const lookedUp = getGeo(parts[0], parts[1]);
      if (lookedUp) {
        triggerSearch(lookedUp, normalised);
        return;
      }

      // Fallback: data may not be cached yet
      setValidatingPostcode(true);
      const data = await ensureInward(parts[0]);
      setValidatingPostcode(false);
      const entry = data[parts[1]];
      if (entry) {
        triggerSearch(
          { bbox: entry.b, centroid: entry.c, deprivationDecile: entry.d },
          normalised,
        );
      }
    }
  }

  function handlePostcodeChange(value: string) {
    setPostcode(value);
  }

  const allProvidersForMap = useMemo(() => {
    const merged = new Map(loadedProviders);
    for (const [id, p] of adHocProviders) {
      if (!merged.has(id)) merged.set(id, p);
    }
    return [...merged.values()];
  }, [loadedProviders, adHocProviders]);

  const viewportEntryIds = useMemo(() => {
    if (!mapBounds) return entryIds;
    return filterProviderIdsInViewport(entryIds, mapBounds, bboxMap, pointMap);
  }, [entryIds, mapBounds, bboxMap, pointMap]);

  const cappedViewportEntryIds = useMemo(() => {
    if (showAllBbox) return viewportEntryIds;
    return capBboxByPointDistance(
      viewportEntryIds,
      entries,
      pointMap,
      bboxMap,
      mapBounds,
    );
  }, [viewportEntryIds, entries, pointMap, bboxMap, showAllBbox, mapBounds]);

  const viewportTotalCount = cappedViewportEntryIds.length;

  const beyondViewportInfo = useMemo(() => {
    const viewportSet = new Set(cappedViewportEntryIds);
    const beyondEntries = entries.filter((e) => !viewportSet.has(e.providerId));
    if (beyondEntries.length === 0) return null;
    const maxMiles = Math.max(...beyondEntries.map((e) => e.distanceMiles));
    return { count: beyondEntries.length, maxMiles };
  }, [entries, cappedViewportEntryIds]);

  // Reset pagination when search/filter results change (not on pan)
  const [prevEntryIds, setPrevEntryIds] = useState(entryIds);
  if (prevEntryIds !== entryIds) {
    setPrevEntryIds(entryIds);
    setVisibleCount(PAGE_SIZE);
  }

  // Slice visible page from viewport-filtered entries
  const visibleEntryIds = useMemo(
    () => cappedViewportEntryIds.slice(0, visibleCount),
    [cappedViewportEntryIds, visibleCount],
  );

  // Sync requestedIds state so hook loads only visible page JSONs
  useEffect(() => {
    setRequestedIds(visibleEntryIds);
  }, [visibleEntryIds]);

  // Build visible entries (with distance) for skeleton rendering
  const visibleEntries: ProviderSearchEntry[] = useMemo(() => {
    const entryMap = new Map(entries.map((e) => [e.providerId, e]));
    return visibleEntryIds
      .map((id) => entryMap.get(id))
      .filter((e): e is ProviderSearchEntry => e != null);
  }, [visibleEntryIds, entries]);

  const bboxInViewport = useMemo(
    () => cappedViewportEntryIds.filter((id) => bboxMap.has(id)).length,
    [cappedViewportEntryIds, bboxMap],
  );

  const missingBboxCount = useMemo(() => {
    if (!areaCosts?.providerStats || !searchedLaCode) return 0;
    const ladInt = encodeLad(searchedLaCode);
    return computeMissingBboxCount(
      cappedViewportEntryIds,
      entries,
      bboxMap,
      ladInt,
      areaCosts.providerStats,
      selectedTypes,
    );
  }, [
    areaCosts,
    searchedLaCode,
    cappedViewportEntryIds,
    bboxMap,
    entries,
    selectedTypes,
  ]);

  const pilotBannerContent = (
    <>
      Currently we only cover{" "}
      <strong>Bristol, Bath, North East Somerset,</strong> and{" "}
      <strong>South Gloucestershire</strong>. Help us by{" "}
      <a
        href="https://dferesearch.fra1.qualtrics.com/jfe/form/SV_73U1lSDggAf4MPY"
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:no-underline"
      >
        giving feedback.
      </a>
    </>
  );

  return (
    <>
      <PageHero
        title="Find a childcare provider"
        subtitle="Search for nurseries, childminders, and clubs near you."
        breadcrumbs={[{ label: "Provider search" }]}
        date="Last updated: May 2026"
      />
      <Container className="py-10">
        <div
          ref={gridRef}
          className={`flex flex-col lg:grid lg:grid-cols-[260px_1fr] gap-8 lg:gap-y-4 items-start${providersLoading ? " opacity-50 pointer-events-none" : ""}`}
        >
          {/* Banner — first in DOM for tab order, grid places it in right column on desktop */}
          <div className="w-full lg:col-start-2 lg:row-start-1">
            <BetaBanner>{pilotBannerContent}</BetaBanner>
          </div>

          {/* Sidebar: search + filters */}
          <div className="w-full shrink-0 space-y-6 lg:col-start-1 lg:row-start-1 lg:row-span-2">
            <ProviderSearch
              postcode={postcode}
              loading={validatingPostcode}
              onPostcodeChange={handlePostcodeChange}
              onSearch={handleSearch}
            />
            <ProviderFilters
              selectedTypes={selectedTypes}
              onTypesChange={handleTypesChange}
              selectedChildren={selectedChildren}
              onChildrenChange={handleChildrenChange}
              areaCosts={areaCosts}
              children={children}
              shortlistedOnly={shortlistedOnly}
              onShortlistedOnlyChange={handleShortlistedOnlyChange}
              shortlistedCount={shortlistedProviders.length}
              isOpen={filtersOpen}
              onToggle={() => setFiltersOpen(!filtersOpen)}
              costDisplayMode={costDisplayMode}
              onCostDisplayModeChange={setCostDisplayMode}
              includeAdditionalCharges={includeAdditionalCharges}
              onIncludeAdditionalChargesChange={setIncludeAdditionalCharges}
              sortBy={sortBy}
              onSortByChange={handleSortByChange}
              fundedHoursOnly={fundedHoursOnly}
              onFundedHoursOnlyChange={handleFundedHoursOnlyChange}
              postcode={searchedPostcode}
              toolbarMode
            />
          </div>

          {/* Main content */}
          <div
            ref={mainContentRef}
            data-scroll-grid
            className="w-full flex-1 min-w-0 lg:col-start-2 lg:row-start-2"
          >
            <div
              ref={mapWrapperRef}
              className={
                stickyTop != null
                  ? `sticky z-50 py-2 -mx-4 px-4 bg-neutral-200${isStuck ? " shadow-[0_4px_4px_-3px_rgba(0,0,0,0.1)]" : ""}`
                  : ""
              }
              style={stickyTop != null ? { top: stickyTop } : undefined}
            >
              <ProviderMap
                allProviders={allProvidersForMap}
                bboxMap={bboxMap}
                pointMap={pointMap}
                onProviderSelect={(provider, coLocated) => {
                  setSelectedProvider(provider);
                  setCoLocatedProviders(coLocated ?? []);
                  captureDetailViewed(provider);
                }}
                onRequestProviders={handleRequestProviders}
                onProviderPending={handleProviderPending}
                resetKey={mapResetKey}
                shortlistedIds={shortlistedProviders}
                animatingPinId={animatingPinId}
                onAnimationEnd={() => setAnimatingPinId(null)}
                includeAdditionalCharges={includeAdditionalCharges}
                selectedTypes={selectedTypes}
                childAgesMonths={childAgesMonths}
                fundedHoursOnly={fundedHoursOnly}
                shortlistedOnly={shortlistedOnly}
                onShortlistedOnlyChange={handleShortlistedOnlyChange}
                initialBounds={mapInitialBounds}
                initialCenter={mapCenter}
                initialZoom={mapZoom}
                onBoundsChange={handleBoundsChange}
                onViewStateChange={handleViewStateChange}
                onZoom={handleZoom}
                fitBoundsRequest={fitBoundsRequest}
                highlightedLaCode={highlightedLaCode}
                sortBy={sortBy}
                onSortByChange={handleSortByChange}
                onTypesChange={handleTypesChange}
                availableSortOptions={sortOptions.map((o) => ({
                  ...o,
                  label: o.label.replace(
                    "{postcode}",
                    searchedPostcode || "your postcode",
                  ),
                }))}
              />
            </div>
            <div ref={listRef} className="mt-6">
              {areaCosts?.showBetaWarning ? (
                <div className="bg-white rounded-xl border border-zinc-200 p-8 text-center">
                  <p className="text-lg font-bold mb-2">
                    Sorry, your area isn&apos;t part of our pilot yet
                  </p>
                  <p className="text-sm text-zinc-600 max-w-prose mx-auto">
                    {searchedPostcode} is not part of our beta programme. At the
                    moment we&apos;re only piloting this app in: Bristol, Bath,
                    North East Somerset, and South Gloucestershire. You can find
                    more local childcare options using{" "}
                    <ExternalLink
                      href="https://www.gov.uk/find-free-early-education"
                      className="text-purple-700 underline hover:text-purple-900"
                    >
                      Find free early education and childcare
                    </ExternalLink>
                  </p>
                </div>
              ) : (
                <ProviderList
                  entries={visibleEntries}
                  loadedProviders={loadedProviders}
                  totalCount={viewportTotalCount}
                  hasMore={visibleCount < cappedViewportEntryIds.length}
                  onShowMore={() => {
                    const page = Math.floor(visibleCount / PAGE_SIZE) + 1;
                    setVisibleCount((c) => c + PAGE_SIZE);
                    posthog?.capture("provider_show_more", { page });
                  }}
                  shortlistedIds={shortlistedProviders}
                  onSelect={setSelectedProvider}
                  onToggleShortlist={handleToggleShortlist}
                  areaCosts={areaCosts}
                  costDisplayMode={costDisplayMode}
                  includeAdditionalCharges={includeAdditionalCharges}
                  sortBy={sortBy}
                  postcode={searchedPostcode}
                  fundedHoursOnly={fundedHoursOnly}
                  selectedTypes={selectedTypes}
                  childAgesMonths={childAgesMonths}
                  bboxCount={bboxInViewport}
                  beyondCount={beyondViewportInfo?.count}
                  beyondMaxMiles={beyondViewportInfo?.maxMiles}
                  missingBboxCount={missingBboxCount}
                  onZoomToLa={handleZoomToLa}
                  onRetryProvider={retryProvider}
                  listVersion={listVersion}
                />
              )}
            </div>
          </div>
        </div>

        {/* Loading modal for on-demand provider fetch */}
        {pendingLoadId && !selectedProvider && (
          <Modal
            onClose={() => setPendingLoadId(null)}
            title="Loading provider..."
            maxWidth="max-w-2xl"
          >
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin w-8 h-8 border-4 border-neutral-700 border-t-transparent rounded-full" />
            </div>
          </Modal>
        )}

        {/* Detail modal */}
        {selectedProvider && (
          <ProviderDetail
            provider={selectedProvider}
            onClose={() => {
              setSelectedProvider(null);
              setCoLocatedProviders([]);
              setPendingLoadId(null);
            }}
            isShortlisted={shortlistedProviders.includes(selectedProvider.id)}
            onToggleShortlist={() => handleToggleShortlist(selectedProvider.id)}
            postcode={searchedPostcode}
            childAgesMonths={childAgesMonths}
            coLocatedProviders={coLocatedProviders}
            onNavigate={setSelectedProvider}
          />
        )}
      </Container>
    </>
  );
}

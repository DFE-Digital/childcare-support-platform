import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import MapGL, {
  Source,
  Layer,
  Marker,
  NavigationControl,
  AttributionControl,
} from "react-map-gl/maplibre";
import type { MapRef, MapLayerMouseEvent } from "react-map-gl/maplibre";
import type { FilterSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Provider } from "@/types/provider";
import type { BBox, ProviderPoint } from "@/lib/filterSortDedup";
import { buildTileFilter } from "@/lib/tileFilter";
import {
  REPORT_CARD_GRADES,
  getOfstedRatingLabel,
  getOfstedBadgeClasses,
  getReportCardJudgements,
  getReportCardBooleans,
} from "@/types/provider";
import { getProviderCostDisplay } from "@/utils/providerCosts";
import { featureFlags } from "@/hooks/useFeatureFlags";
import { useLastInputWasKeyboard } from "@/hooks/useLastInputWasKeyboard";
import type { SortOption } from "./sortOptions";

const { showFees } = featureFlags;

const DEFAULT_CENTER = { latitude: 51.45, longitude: -2.5 };
const DEFAULT_ZOOM = 10;
// Pilot area bounding box [west, south, east, north] — Bristol/Bath/South Glos
// with padding to show surrounding context
const UK_BOUNDS: [[number, number], [number, number]] = [
  [-3.1, 51.0],
  [-1.9, 51.9],
];
const MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

const CARE_TYPE_LABELS: Record<string, string> = {
  private_nursery: "Nursery",
  school_based_nursery: "School-based nursery",
  childminder: "Childminder",
  breakfast_club: "Breakfast club",
  free_breakfast_club: "Free breakfast club",
  after_school_club: "After school club",
  holiday_club: "Holiday club",
};

const TILE_LAYER_ID = "providers-tiles";
const SHORTLIST_LAYER_ID = "providers-shortlist";

const PROVIDER_TYPES_FOR_TRAY = [
  { value: "private_nursery", label: "Nursery (PVI)" },
  { value: "school_based_nursery", label: "School nursery" },
  { value: "childminder", label: "Childminder" },
  { value: "breakfast_club", label: "Breakfast club" },
  { value: "after_school_club", label: "After school" },
  { value: "holiday_club", label: "Holiday club" },
];

const SORT_KEYS = ["q", "w", "e", "r", "t", "y", "u"];

function MapKeyboardTray({
  selectedTypes,
  sortBy,
  availableSortOptions,
  shortlistedOnly,
}: {
  selectedTypes: string[];
  sortBy?: SortOption;
  availableSortOptions: { value: SortOption; label: string }[];
  shortlistedOnly: boolean;
}) {
  return (
    <div
      className="bg-white border border-t-0 border-zinc-200 rounded-b-xl px-4 py-3"
      aria-hidden="true"
    >
      <div className="flex items-center justify-center gap-4 flex-wrap text-xs">
        <span className="inline-flex items-center gap-1.5">
          <span className="text-zinc-500 font-medium">Zoom</span>
          <kbd className="inline-flex items-center justify-center w-6 h-6 rounded-md border border-zinc-300 bg-zinc-50 font-mono font-bold text-zinc-700">
            +
          </kbd>
          <kbd className="inline-flex items-center justify-center w-6 h-6 rounded-md border border-zinc-300 bg-zinc-50 font-mono font-bold text-zinc-700">
            &minus;
          </kbd>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="text-zinc-500 font-medium">Pan</span>
          <kbd className="inline-flex items-center justify-center w-6 h-6 rounded-md border border-zinc-300 bg-zinc-50 text-zinc-700">
            &#8593;
          </kbd>
          <kbd className="inline-flex items-center justify-center w-6 h-6 rounded-md border border-zinc-300 bg-zinc-50 text-zinc-700">
            &#8595;
          </kbd>
          <kbd className="inline-flex items-center justify-center w-6 h-6 rounded-md border border-zinc-300 bg-zinc-50 text-zinc-700">
            &#8592;
          </kbd>
          <kbd className="inline-flex items-center justify-center w-6 h-6 rounded-md border border-zinc-300 bg-zinc-50 text-zinc-700">
            &#8594;
          </kbd>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <kbd className="inline-flex items-center justify-center px-1.5 h-6 rounded-md border border-zinc-300 bg-zinc-50 font-mono text-zinc-700">
            Esc
          </kbd>
          <span className="text-zinc-500 font-medium">leave map</span>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <kbd className="inline-flex items-center justify-center px-1.5 h-6 rounded-md border border-zinc-300 bg-zinc-50 font-mono text-zinc-700">
            Tab
          </kbd>
          <span className="text-zinc-500 font-medium">focus cards, then</span>
          <kbd className="inline-flex items-center justify-center w-6 h-6 rounded-md border border-zinc-300 bg-zinc-50 text-zinc-700">
            &#8593;
          </kbd>
          <kbd className="inline-flex items-center justify-center w-6 h-6 rounded-md border border-zinc-300 bg-zinc-50 text-zinc-700">
            &#8595;
          </kbd>
          <span className="text-zinc-500 font-medium">to browse</span>
        </span>
      </div>
      <div className="flex items-center justify-center gap-2 mt-2 flex-wrap text-xs">
        <span className="text-zinc-500 font-medium shrink-0">Filter:</span>
        {PROVIDER_TYPES_FOR_TRAY.map((pt, i) => {
          const isActive =
            !shortlistedOnly &&
            (selectedTypes.length === 0 || selectedTypes.includes(pt.value));
          return (
            <span key={pt.value} className="inline-flex items-center gap-0.5">
              <kbd
                className={`inline-flex items-center justify-center w-5 h-5 rounded border font-mono font-bold ${isActive ? "border-blue-600 bg-blue-100 text-blue-800" : "border-zinc-300 bg-zinc-50 text-zinc-700"}`}
              >
                {i + 1}
              </kbd>
              <span
                className={
                  isActive ? "text-blue-800 font-semibold" : "text-zinc-500"
                }
                aria-label={`${pt.label}: ${isActive ? "showing" : "hidden"}`}
              >
                {pt.label}
              </span>
            </span>
          );
        })}
        <span className="inline-flex items-center gap-0.5">
          <kbd
            className={`inline-flex items-center justify-center w-5 h-5 rounded border font-mono font-bold ${shortlistedOnly ? "border-blue-600 bg-blue-100 text-blue-800" : "border-zinc-300 bg-zinc-50 text-zinc-700"}`}
          >
            0
          </kbd>
          <span
            className={
              shortlistedOnly ? "text-blue-800 font-semibold" : "text-zinc-500"
            }
            aria-label={`Shortlisted: ${shortlistedOnly ? "showing" : "off"}`}
          >
            Shortlisted
          </span>
        </span>
      </div>
      <div className="flex items-center justify-center gap-2 mt-2 flex-wrap text-xs">
        <span className="text-zinc-500 font-medium shrink-0">Sort:</span>
        {availableSortOptions.map((opt, i) => {
          const isActive = sortBy === opt.value;
          const key = SORT_KEYS[i];
          if (!key) return null;
          return (
            <span key={opt.value} className="inline-flex items-center gap-0.5">
              <kbd
                className={`inline-flex items-center justify-center w-5 h-5 rounded border font-mono font-bold ${isActive ? "border-blue-600 bg-blue-100 text-blue-800" : "border-zinc-300 bg-zinc-50 text-zinc-700"}`}
              >
                {key}
              </kbd>
              <span
                className={
                  isActive ? "text-blue-800 font-semibold" : "text-zinc-500"
                }
                aria-label={`Sort by ${opt.label}: ${isActive ? "selected" : ""}`}
              >
                {opt.label}
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

interface TileTooltipData {
  id: string;
  name: string;
  careTypes: string;
  address: string;
  postcode: string;
  ofsted?: string;
  cma?: string;
  lngLat: [number, number];
}

interface TooltipItem {
  data: TileTooltipData;
  provider?: Provider;
}

interface TooltipState {
  items: TooltipItem[];
  activeIndex: number;
  pinned: boolean;
  pos: { x: number; y: number };
  mapRect: DOMRect;
}

interface ProviderMapProps {
  allProviders: Provider[];
  bboxMap?: Map<string, BBox>;
  pointMap?: Map<string, ProviderPoint>;
  onProviderSelect?: (provider: Provider, coLocated?: Provider[]) => void;
  onRequestProviders?: (ids: string[]) => void;
  onProviderPending?: (id: string) => void;
  resetKey?: number;
  shortlistedIds?: string[];
  animatingPinId?: string | null;
  onAnimationEnd?: () => void;
  includeAdditionalCharges?: boolean;
  selectedTypes?: string[];
  childAgesMonths?: number[];
  fundedHoursOnly?: boolean;
  shortlistedOnly?: boolean;
  onShortlistedOnlyChange?: (v: boolean) => void;
  initialBounds?: [number, number, number, number] | null;
  initialCenter?: [number, number] | null;
  initialZoom?: number | null;
  onBoundsChange?: (bounds: [number, number, number, number]) => void;
  onViewStateChange?: (center: [number, number], zoom: number) => void;
  onZoom?: (
    zoom: number,
    direction: "in" | "out",
    source: "keyboard" | "button",
  ) => void;
  fitBoundsRequest?: {
    key: number;
    bounds: [number, number, number, number];
  } | null;
  highlightedLaCode?: string | null;
  sortBy?: SortOption;
  onSortByChange?: (sort: SortOption) => void;
  onTypesChange?: (types: string[]) => void;
  availableSortOptions?: { value: SortOption; label: string }[];
}

function parseTileOfsted(ofsted: string | undefined) {
  if (!ofsted) return null;

  if (ofsted === "T") {
    return { type: "legacy_transition" as const };
  }

  if (ofsted.startsWith("L:")) {
    return { type: "legacy" as const, rating: ofsted.slice(2) };
  }

  if (ofsted.startsWith("R:")) {
    const body = ofsted.slice(2);
    // Last 3 chars are booleans (safeguarding, ccr, vcr)
    const boolStr = body.slice(-3);
    const rankStr = body.slice(0, -3);
    const ranks = rankStr.split("").map(Number);
    const bools = boolStr
      .split("")
      .map((c) => (c === "Y" ? true : c === "N" ? false : null));
    return { type: "report_card" as const, ranks, bools };
  }

  return null;
}

function OfstedBadge({
  ofsted,
  cma,
  isTouch,
}: {
  ofsted: string | undefined;
  cma: string | undefined;
  isTouch: boolean;
}) {
  const parsed = parseTileOfsted(ofsted);
  const sizeClass = isTouch ? "text-sm" : "text-xs";

  if (!parsed) {
    if (cma) return null;
    return (
      <span
        className={`px-2 py-0.5 rounded font-bold text-center bg-zinc-100 text-zinc-600 ${sizeClass}`}
      >
        Not inspected
      </span>
    );
  }

  if (parsed.type === "legacy_transition") {
    return (
      <span
        className={`px-2 py-0.5 rounded font-bold text-center bg-zinc-100 text-zinc-600 ${sizeClass}`}
      >
        Ofsted: no summary
      </span>
    );
  }

  if (parsed.type === "legacy") {
    return (
      <span
        className={`px-2 py-0.5 rounded font-bold text-center ${getOfstedBadgeClasses(parsed.rating)} ${sizeClass}`}
      >
        Ofsted: {parsed.rating}
      </span>
    );
  }

  // report_card
  const boolLabels = ["Safeguarding", "CCR", "VCR"];
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-xs font-bold text-zinc-500">Ofsted:</span>
      {parsed.ranks.map((rank, i) => (
        <span
          key={i}
          role="img"
          aria-label={REPORT_CARD_GRADES[rank]?.grade ?? "Unknown"}
          className="inline-block w-3 h-3 rounded-full border border-black shrink-0"
          style={{
            backgroundColor: REPORT_CARD_GRADES[rank]?.colour ?? "#9ca3af",
          }}
        />
      ))}
      {parsed.bools.map((met, i) =>
        met === null ? null : (
          <i
            key={boolLabels[i]}
            role="img"
            aria-label={`${boolLabels[i]}: ${met ? "Met" : "Not met"}`}
            className={`bi ${met ? "bi-check-circle" : "bi-x-circle-fill"} shrink-0`}
            style={{
              color: met ? "#33903C" : "#CE1E02",
              fontSize: "0.75rem",
            }}
          />
        ),
      )}
    </span>
  );
}

function matchesTileFilters(
  p: Record<string, string | number | undefined>,
  selectedTypes: string[],
  fundedHoursOnly: boolean,
  childAgesMonths: number[],
): boolean {
  if (selectedTypes.length > 0) {
    const ct = ((p.care_types as string) ?? "").split(",").filter(Boolean);
    if (!selectedTypes.some((t) => ct.includes(t))) return false;
  }
  if (fundedHoursOnly && p.fh !== 1) return false;
  if (childAgesMonths.length > 0) {
    const lo = typeof p.age_lo === "number" ? p.age_lo : 0;
    const hi = typeof p.age_hi === "number" ? p.age_hi : 999;
    if (!childAgesMonths.some((age) => age >= lo && age <= hi)) return false;
  }
  return true;
}

export function ProviderMap({
  allProviders,
  bboxMap = new Map(),
  pointMap = new Map(),
  onProviderSelect,
  onRequestProviders,
  onProviderPending,
  resetKey = 0,
  shortlistedIds = [],
  animatingPinId,
  onAnimationEnd,
  includeAdditionalCharges = false,
  selectedTypes = [],
  childAgesMonths = [],
  fundedHoursOnly = false,
  shortlistedOnly = false,
  onShortlistedOnlyChange,
  initialBounds = null,
  initialCenter = null,
  initialZoom = null,
  onBoundsChange,
  onViewStateChange,
  onZoom,
  fitBoundsRequest = null,
  highlightedLaCode = null,
  sortBy,
  onSortByChange,
  onTypesChange,
  availableSortOptions = [],
}: ProviderMapProps) {
  const mapRef = useRef<MapRef>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const focusWrapperRef = useRef<HTMLDivElement>(null);
  const programmaticMove = useRef(false);
  const zoomSourceRef = useRef<"keyboard" | "button">("button");
  const prevZoomRef = useRef<number | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [isTouch, setIsTouch] = useState(false);
  const [isTrayOpen, setIsTrayOpen] = useState(false);
  useEffect(() => {
    setIsTrayOpen(false);
  }, [resetKey]);
  const [mapReady, setMapReady] = useState(false);
  const [mapStyleUrl, setMapStyleUrl] = useState(MAP_STYLE);
  const styleErrorRef = useRef(false);
  const mapTabObserver = useRef<MutationObserver | null>(null);

  // Build lookup map for loaded providers
  const providerMap = useMemo(() => {
    const lookup = new globalThis.Map<string, Provider>();
    for (const p of allProviders) lookup.set(p.id, p);
    return lookup;
  }, [allProviders]);

  const mapDescription = useMemo(() => {
    const filterLines = PROVIDER_TYPES_FOR_TRAY.map((pt, i) => {
      const active =
        !shortlistedOnly &&
        (selectedTypes.length === 0 || selectedTypes.includes(pt.value));
      return `${i + 1} ${pt.label}: ${active ? "showing" : "hidden"}`;
    });
    filterLines.push(`0 Shortlisted: ${shortlistedOnly ? "showing" : "off"}`);
    const sortLines = availableSortOptions
      .map((opt, i) => {
        const key = SORT_KEYS[i];
        if (!key) return null;
        return `${key} ${opt.label}${sortBy === opt.value ? ": selected" : ""}`;
      })
      .filter(Boolean);
    return `Filters: ${filterLines.join(", ")}. Sort: ${sortLines.join(", ")}.`;
  }, [selectedTypes, shortlistedOnly, sortBy, availableSortOptions]);

  // PMTiles source URL
  const tileUrl = useMemo(() => {
    const base = document.querySelector("base")?.href ?? window.location.origin;
    const origin = new URL(base).origin;
    const basePath = import.meta.env.BASE_URL?.replace(/\/$/, "") ?? "";
    return `pmtiles://${origin}${basePath}/data/tiles/providers.pmtiles`;
  }, []);

  // GeoJSON for shortlisted overlay — use full-precision coords from loaded providers
  const shortlistGeojson = useMemo(() => {
    const features = shortlistedIds
      .map((id) => {
        const provider = providerMap.get(id);
        const lon = provider?.longitude;
        const lat = provider?.latitude;
        if (lon == null || lat == null) return null;
        return {
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [lon, lat] },
          properties: { id },
        };
      })
      .filter((f): f is NonNullable<typeof f> => f !== null);
    return { type: "FeatureCollection" as const, features };
  }, [shortlistedIds, providerMap]);

  const tileCircleColor = "#0d0035";

  // Build MapLibre filter expression from active filters
  const tileFilter = useMemo(
    () => buildTileFilter(selectedTypes, fundedHoursOnly, childAgesMonths),
    [selectedTypes, fundedHoursOnly, childAgesMonths],
  );

  // Exclude shortlisted (and currently animating) providers from tile layer
  const combinedTileFilter = useMemo((): FilterSpecification => {
    const excludeIds = animatingPinId
      ? [...shortlistedIds, animatingPinId]
      : shortlistedIds;
    if (excludeIds.length === 0) return tileFilter;
    const base = tileFilter as unknown as unknown[];
    return [
      "all",
      ...base.slice(1),
      ["!", ["in", ["get", "id"], ["literal", excludeIds]]],
    ] as unknown as FilterSpecification;
  }, [tileFilter, shortlistedIds, animatingPinId]);

  const boundaryFilterCode = useRef<string | null>(null);
  if (highlightedLaCode) boundaryFilterCode.current = highlightedLaCode;

  const boundaryFilter = useMemo(
    () =>
      (boundaryFilterCode.current
        ? ["==", ["get", "LAD25CD"], boundaryFilterCode.current]
        : ["==", ["get", "LAD25CD"], "__none__"]) as FilterSpecification,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [highlightedLaCode],
  );

  const boundaryVisible = !!highlightedLaCode;

  // Animating pin coordinates from SIS maps
  const animatingCoord = useMemo(() => {
    if (!animatingPinId) return null;
    const provider = providerMap.get(animatingPinId);
    if (provider?.latitude != null && provider?.longitude != null) {
      return { lat: provider.latitude, lon: provider.longitude };
    }
    const pt = pointMap.get(animatingPinId);
    if (pt) return pt;
    const bb = bboxMap.get(animatingPinId);
    if (bb) return { lat: bb.north, lon: bb.west };
    return null;
  }, [animatingPinId, providerMap, pointMap, bboxMap]);

  useEffect(() => {
    const onTouch = () => setIsTouch(true);
    window.addEventListener("touchstart", onTouch, { once: true });
    return () => window.removeEventListener("touchstart", onTouch);
  }, []);

  function handleMapError() {
    styleErrorRef.current = true;
  }

  function handleMapLoad() {
    setMapReady(true);
    styleErrorRef.current = false;
    const map = mapRef.current;
    if (!map) return;
    prevZoomRef.current = map.getZoom();

    // Register shortlist pin icon — large SVG source for crisp rendering at all scales
    const pinSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="85" viewBox="2 0 12 16"><path d="M8 0C4.686 0 2 2.686 2 6c0 5.25 6 10 6 10s6-4.75 6-10c0-3.314-2.686-6-6-6z" fill="#6a0095" stroke="#fff" stroke-width="0.75"/><circle cx="8" cy="6" r="2.5" fill="#fff"/></svg>`;
    const img = new Image(64, 85);
    img.onload = () => map.addImage("shortlist-pin", img, { pixelRatio: 2 });
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(pinSvg)}`;

    // Set cursor to pointer on hover over provider features
    const canvas = map.getCanvas();
    map.on("mouseenter", TILE_LAYER_ID, () => {
      canvas.style.cursor = "pointer";
    });
    map.on("mouseleave", TILE_LAYER_ID, () => {
      canvas.style.cursor = "";
    });
    map.on("mouseenter", SHORTLIST_LAYER_ID, () => {
      canvas.style.cursor = "pointer";
    });
    map.on("mouseleave", SHORTLIST_LAYER_ID, () => {
      canvas.style.cursor = "";
    });

    // Remove MapLibre internal elements from tab order
    canvas.tabIndex = -1;
    canvas.setAttribute("aria-hidden", "true");
    const wrapperEl = focusWrapperRef.current;
    const suppressTabStops = () => {
      if (!wrapperEl) return;
      wrapperEl
        .querySelectorAll<HTMLElement>("button, a, input, [tabindex]")
        .forEach((el) => {
          if (el.tabIndex !== -1) el.tabIndex = -1;
        });
    };
    suppressTabStops();
    const observer = new MutationObserver(suppressTabStops);
    if (wrapperEl) {
      observer.observe(wrapperEl, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["tabindex"],
      });
    }
    mapTabObserver.current = observer;
  }

  useEffect(() => {
    return () => {
      mapTabObserver.current?.disconnect();
    };
  }, []);

  // Recover map style on reconnect if it failed to load
  useEffect(() => {
    const onOnline = () => {
      if (!mapReady || styleErrorRef.current) {
        styleErrorRef.current = false;
        setMapStyleUrl(MAP_STYLE + "?t=" + Date.now());
      }
    };
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [mapReady]);

  // Dismiss tooltip on tap/click outside the component
  useEffect(() => {
    if (!tooltip) return;
    function onPointerDown(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setTooltip(null);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [tooltip]);

  const handleMoveEnd = useCallback(() => {
    programmaticMove.current = false;
    const map = mapRef.current;
    if (map) {
      if (onBoundsChange) {
        const b = map.getBounds();
        onBoundsChange([b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]);
      }
      const currentZoom = map.getZoom();
      if (onViewStateChange) {
        const c = map.getCenter();
        onViewStateChange([c.lng, c.lat], currentZoom);
      }
      if (onZoom && prevZoomRef.current !== null) {
        const prev = prevZoomRef.current;
        if (Math.abs(currentZoom - prev) > 0.01) {
          const direction = currentZoom > prev ? "in" : "out";
          onZoom(currentZoom, direction, zoomSourceRef.current);
          zoomSourceRef.current = "button";
        }
      }
      prevZoomRef.current = currentZoom;
    }
  }, [onBoundsChange, onViewStateChange, onZoom]);

  // Query features at a point from both layers, returning all co-located providers
  const queryAllFeatures = useCallback(
    (point: { x: number; y: number }): TooltipItem[] => {
      const map = mapRef.current;
      if (!map) return [];
      const queryLayers = [TILE_LAYER_ID, SHORTLIST_LAYER_ID].filter((id) =>
        map.getLayer(id),
      );
      if (queryLayers.length === 0) return [];
      const features = map.queryRenderedFeatures(
        [point.x, point.y] as [number, number],
        { layers: queryLayers },
      );
      if (!features || features.length === 0) return [];

      const seen = new Set<string>();
      const items: TooltipItem[] = [];

      for (const f of features) {
        const props = f.properties;
        if (!props) continue;

        const count = (props.count as number) || 1;

        if (count > 1 && props.providers) {
          // Aggregated multi-provider feature (properties use snake_case from Python)
          const parsed = JSON.parse(props.providers as string) as Record<
            string,
            string | number | undefined
          >[];
          const lngLat: [number, number] =
            f.geometry.type === "Point"
              ? (f.geometry.coordinates as [number, number])
              : [0, 0];
          for (const p of parsed) {
            const id = (p.id as string) ?? "";
            if (!id || seen.has(id)) continue;
            if (
              !matchesTileFilters(
                p,
                selectedTypes,
                fundedHoursOnly,
                childAgesMonths,
              )
            )
              continue;
            seen.add(id);
            items.push({
              data: {
                id,
                name: (p.name as string) ?? "",
                careTypes: (p.care_types as string) ?? "",
                address: (p.address as string) ?? "",
                postcode: (p.postcode as string) ?? "",
                ofsted: p.ofsted as string | undefined,
                cma: p.cma as string | undefined,
                lngLat,
              },
              provider: providerMap.get(id),
            });
          }
        } else if (props.id) {
          const id = props.id as string;
          if (seen.has(id)) continue;
          seen.add(id);
          const provider = providerMap.get(id);

          if (f.layer?.id === SHORTLIST_LAYER_ID && provider) {
            items.push({
              data: {
                id: provider.id,
                name: provider.name,
                careTypes: provider.careTypes.map((ct) => ct.type).join(","),
                address: provider.address.line1,
                postcode: provider.address.postcode,
                lngLat: [provider.longitude ?? 0, provider.latitude ?? 0],
              },
              provider,
            });
          } else {
            items.push({
              data: {
                id,
                name: (props.name as string) || "",
                careTypes: (props.care_types as string) || "",
                address: (props.address as string) || "",
                postcode: (props.postcode as string) || "",
                ofsted: props.ofsted as string | undefined,
                lngLat:
                  f.geometry.type === "Point"
                    ? (f.geometry.coordinates as [number, number])
                    : [0, 0],
              },
              provider,
            });
          }
        }
      }
      return items;
    },
    [providerMap, selectedTypes, fundedHoursOnly, childAgesMonths],
  );

  const handleMouseMove = useCallback(
    (e: MapLayerMouseEvent) => {
      if (isTouch) return;
      if (tooltip?.pinned) return;
      const map = mapRef.current;
      if (!map) return;
      const items = queryAllFeatures(e.point);
      if (items.length === 0) {
        setTooltip(null);
        return;
      }
      setTooltip({
        items,
        activeIndex: 0,
        pinned: false,
        pos: e.point,
        mapRect: map.getContainer().getBoundingClientRect(),
      });
    },
    [isTouch, tooltip?.pinned, queryAllFeatures],
  );

  const handleMouseLeave = useCallback(() => {
    if (!isTouch && !tooltip?.pinned) setTooltip(null);
  }, [isTouch, tooltip?.pinned]);

  const handleClick = useCallback(
    (e: MapLayerMouseEvent) => {
      const items = queryAllFeatures(e.point);
      if (items.length === 0) {
        if (tooltip) setTooltip(null);
        return;
      }
      const map = mapRef.current;
      if (!map) return;
      const mapRect = map.getContainer().getBoundingClientRect();

      if (isTouch) {
        // Toggle pinned tooltip on touch
        const firstId = items[0].data.id;
        if (tooltip?.pinned && tooltip.items[0]?.data.id === firstId) {
          setTooltip(null);
        } else {
          setTooltip({
            items,
            activeIndex: 0,
            pinned: true,
            pos: e.point,
            mapRect,
          });
          const unloadedIds = items
            .filter((item) => !item.provider)
            .map((item) => item.data.id);
          if (unloadedIds.length > 0) onRequestProviders?.(unloadedIds);
        }
        return;
      }
      // Desktop click
      if (items.length === 1) {
        // Single provider — open detail directly or trigger load
        setTooltip(null);
        if (items[0].provider) {
          onProviderSelect?.(items[0].provider);
        } else {
          onProviderPending?.(items[0].data.id);
        }
      } else {
        // Multiple providers — pin interactive tooltip
        setTooltip({
          items,
          activeIndex: 0,
          pinned: true,
          pos: e.point,
          mapRect,
        });
        const unloadedIds = items
          .filter((item) => !item.provider)
          .map((item) => item.data.id);
        if (unloadedIds.length > 0) onRequestProviders?.(unloadedIds);
      }
    },
    [
      isTouch,
      tooltip,
      queryAllFeatures,
      onProviderSelect,
      onProviderPending,
      onRequestProviders,
    ],
  );

  // Fit map to providers in the searched area on load and when resetKey changes
  const prevFlyKey = useRef<number | null>(null);
  const hasFittedOnce = useRef(false);
  const hasCoords = pointMap.size + bboxMap.size > 0;
  useEffect(() => {
    const keyChanged = resetKey !== prevFlyKey.current;
    const needsInitialFit = !hasFittedOnce.current;
    if (!keyChanged && !needsInitialFit) return;

    const isInitial = prevFlyKey.current === null;
    const map = mapRef.current;
    if (!map) return;

    // On restore with saved center/zoom, skip fitBounds — MapGL already
    // initialized at the exact viewport. Manually fire onBoundsChange so
    // handleBoundsChange triggers sisSearch (moveend doesn't fire on initial render).
    if (isInitial && initialCenter && initialZoom != null) {
      prevFlyKey.current = resetKey;
      hasFittedOnce.current = true;
      if (onBoundsChange) {
        const b = map.getBounds();
        onBoundsChange([b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]);
      }
      return;
    }

    prevFlyKey.current = resetKey;
    hasFittedOnce.current = true;
    programmaticMove.current = true;
    const duration = isInitial ? 0 : 800;

    if (initialBounds) {
      const [west, south, east, north] = initialBounds;
      const dLng = (east - west) * 0.1;
      const dLat = (north - south) * 0.1;
      map.fitBounds(
        [
          [west - dLng, south - dLat],
          [east + dLng, north + dLat],
        ],
        { padding: 60, duration, maxZoom: 14 },
      );
    } else if (hasCoords) {
      let minLng = Infinity,
        maxLng = -Infinity;
      let minLat = Infinity,
        maxLat = -Infinity;
      for (const [, pt] of pointMap) {
        minLng = Math.min(minLng, pt.lon);
        maxLng = Math.max(maxLng, pt.lon);
        minLat = Math.min(minLat, pt.lat);
        maxLat = Math.max(maxLat, pt.lat);
      }
      for (const [, bb] of bboxMap) {
        minLng = Math.min(minLng, bb.west);
        maxLng = Math.max(maxLng, bb.east);
        minLat = Math.min(minLat, bb.south);
        maxLat = Math.max(maxLat, bb.north);
      }
      map.fitBounds(
        [
          [minLng, minLat],
          [maxLng, maxLat],
        ],
        { padding: 60, duration, maxZoom: 14 },
      );
    } else {
      map.fitBounds(UK_BOUNDS, { padding: 20, duration });
    }
  }, [
    resetKey,
    hasCoords,
    pointMap,
    bboxMap,
    mapReady,
    initialBounds,
    initialCenter,
    initialZoom,
    onBoundsChange,
  ]);

  const prevFitKey = useRef(0);
  useEffect(() => {
    if (!fitBoundsRequest || fitBoundsRequest.key === prevFitKey.current)
      return;
    prevFitKey.current = fitBoundsRequest.key;
    const map = mapRef.current;
    if (!map) return;
    const [south, west, north, east] = fitBoundsRequest.bounds;
    programmaticMove.current = true;
    map.fitBounds(
      [
        [west, south],
        [east, north],
      ],
      { padding: 60, duration: 500 },
    );
  }, [fitBoundsRequest]);

  const lastInputWasKeyboard = useLastInputWasKeyboard();

  const handleWrapperFocus = useCallback(
    (e: React.FocusEvent) => {
      if (isTouch) return;
      if (!focusWrapperRef.current?.contains(e.relatedTarget as Node)) {
        if (lastInputWasKeyboard.current) {
          setIsTrayOpen(true);
        }
      }
    },
    [isTouch],
  );

  const handleWrapperBlur = useCallback(() => {}, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isTrayOpen) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const map = mapRef.current;
      if (!map) return;

      switch (e.key) {
        case "+":
        case "=":
          e.preventDefault();
          zoomSourceRef.current = "keyboard";
          map.zoomIn({ duration: 200 });
          break;
        case "-":
        case "_":
          e.preventDefault();
          zoomSourceRef.current = "keyboard";
          map.zoomOut({ duration: 200 });
          break;
        case "ArrowUp":
          e.preventDefault();
          map.panBy([0, -100], { duration: 200 });
          break;
        case "ArrowDown":
          e.preventDefault();
          map.panBy([0, 100], { duration: 200 });
          break;
        case "ArrowLeft":
          e.preventDefault();
          map.panBy([-100, 0], { duration: 200 });
          break;
        case "ArrowRight":
          e.preventDefault();
          map.panBy([100, 0], { duration: 200 });
          break;
        case "0":
          e.preventDefault();
          onShortlistedOnlyChange?.(!shortlistedOnly);
          break;
        case "1":
        case "2":
        case "3":
        case "4":
        case "5":
        case "6": {
          e.preventDefault();
          const index = parseInt(e.key) - 1;
          if (index < PROVIDER_TYPES_FOR_TRAY.length) {
            const typeValue = PROVIDER_TYPES_FOR_TRAY[index].value;
            const newTypes = selectedTypes.includes(typeValue)
              ? selectedTypes.filter((t) => t !== typeValue)
              : [...selectedTypes, typeValue];
            onTypesChange?.(newTypes);
          }
          break;
        }
        case "q":
        case "w":
        case "e":
        case "r":
        case "t":
        case "y":
        case "u": {
          e.preventDefault();
          const sortIndex = SORT_KEYS.indexOf(e.key);
          if (sortIndex < availableSortOptions.length) {
            onSortByChange?.(availableSortOptions[sortIndex].value);
          }
          break;
        }
        case "Escape":
          e.preventDefault();
          setTooltip(null);
          setIsTrayOpen(false);
          focusWrapperRef.current?.blur();
          break;
      }
    },
    [
      isTrayOpen,
      selectedTypes,
      onTypesChange,
      availableSortOptions,
      onSortByChange,
    ],
  );

  // Tooltip positioning (preserved from original)
  const TOOLTIP_MAX_W = 240;
  const TOOLTIP_H = 130;
  const PIN_R = 8; // circle radius approximation
  const GAP = 4;
  const EDGE_PAD = 8;
  const TAIL_MARGIN = 14;

  let tooltipPlacement: "top" | "bottom" | "left" | "right" = "top";
  let tooltipW = isTouch ? Math.max(TOOLTIP_MAX_W, 280) : TOOLTIP_MAX_W;
  let shiftX = 0;
  let shiftY = 0;
  if (tooltip) {
    const rect = tooltip.mapRect;
    const vx = tooltip.pos.x + rect.left;
    const vy = tooltip.pos.y + rect.top;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const stickyHeader = document.getElementById("sticky-header");
    const topInset = stickyHeader
      ? stickyHeader.getBoundingClientRect().bottom
      : 0;
    const nearTop = vy - PIN_R - TOOLTIP_H < topInset + GAP;
    const nearBottom = vy + TOOLTIP_H + GAP > vh;

    if (!nearTop) {
      tooltipPlacement = "top";
    } else if (!nearBottom) {
      tooltipPlacement = "bottom";
    } else {
      const spaceLeft = vx - PIN_R - GAP - EDGE_PAD;
      const spaceRight = vw - vx - PIN_R - GAP - EDGE_PAD;
      if (spaceRight >= spaceLeft) {
        tooltipPlacement = "right";
        tooltipW = Math.min(tooltipW, spaceRight);
      } else {
        tooltipPlacement = "left";
        tooltipW = Math.min(tooltipW, spaceLeft);
      }
    }

    if (tooltipPlacement === "top" || tooltipPlacement === "bottom") {
      const leftEdge = vx - tooltipW / 2;
      const rightEdge = vx + tooltipW / 2;
      if (leftEdge < EDGE_PAD) shiftX = EDGE_PAD - leftEdge;
      else if (rightEdge > vw - EDGE_PAD) shiftX = vw - EDGE_PAD - rightEdge;
      const maxShift = tooltipW / 2 - TAIL_MARGIN;
      shiftX = Math.max(-maxShift, Math.min(maxShift, shiftX));
    } else {
      const topEdge = vy - TOOLTIP_H / 2;
      const bottomEdge = vy + TOOLTIP_H / 2;
      if (topEdge < topInset + EDGE_PAD) shiftY = topInset + EDGE_PAD - topEdge;
      else if (bottomEdge > vh - EDGE_PAD) shiftY = vh - EDGE_PAD - bottomEdge;
      const maxShift = TOOLTIP_H / 2 - TAIL_MARGIN;
      shiftY = Math.max(-maxShift, Math.min(maxShift, shiftY));
    }
  }

  // Active tooltip item
  const activeItem = tooltip ? tooltip.items[tooltip.activeIndex] : undefined;
  const activeProvider = activeItem
    ? providerMap.get(activeItem.data.id)
    : undefined;

  // Build tooltip content from tile data + optional full provider
  const tooltipName = activeProvider?.name ?? activeItem?.data.name ?? "";
  const tooltipCareTypes: string[] = activeProvider
    ? activeProvider.careTypes.map((ct) => ct.type)
    : (activeItem?.data.careTypes ?? "").split(",").filter(Boolean);
  const tooltipAddress = activeProvider
    ? activeProvider.address.line1
    : (activeItem?.data.address ?? "");
  const tooltipPostcode = activeProvider
    ? activeProvider.address.postcode
    : (activeItem?.data.postcode ?? "");

  // Cost display: only available when full provider is loaded
  const tooltipCost = activeProvider
    ? getProviderCostDisplay(
        activeProvider,
        "hourly",
        includeAdditionalCharges,
        selectedTypes,
        childAgesMonths,
      ).summary
    : null;

  return (
    <div ref={rootRef} className="relative">
      <div
        ref={focusWrapperRef}
        tabIndex={0}
        role="application"
        aria-roledescription="interactive map"
        aria-label="Provider map. Use arrow keys to pan, plus and minus to zoom. Press Escape or Tab to leave."
        aria-describedby="map-keyboard-description"
        onFocus={handleWrapperFocus}
        onBlur={handleWrapperBlur}
        onKeyDown={handleKeyDown}
        className="rounded-xl focus-visible:outline-[3px] focus-visible:outline-[#3b82f6] focus-visible:outline-offset-[3px] focus-visible:shadow-[0_0_0_3px_white]"
      >
        <span id="map-keyboard-description" className="sr-only">
          {mapDescription}
        </span>
        <div
          className={`h-[30vh] min-h-[200px] lg:h-[500px] overflow-hidden border border-zinc-200 relative z-0 ${isTrayOpen ? "rounded-t-xl border-b-0" : "rounded-xl"} [&_button]:!-outline-offset-[9999px] [&_a]:!-outline-offset-[9999px]`}
          tabIndex={-1}
        >
          <MapGL
            ref={mapRef}
            initialViewState={{
              latitude: initialCenter?.[1] ?? DEFAULT_CENTER.latitude,
              longitude: initialCenter?.[0] ?? DEFAULT_CENTER.longitude,
              zoom: initialZoom ?? DEFAULT_ZOOM,
            }}
            style={{ width: "100%", height: "100%" }}
            mapStyle={mapStyleUrl}
            scrollZoom={false}
            attributionControl={false}
            onError={handleMapError}
            onLoad={handleMapLoad}
            onMoveEnd={handleMoveEnd}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            onClick={handleClick}
            interactiveLayerIds={[TILE_LAYER_ID, SHORTLIST_LAYER_ID]}
          >
            <AttributionControl />
            <NavigationControl position="top-left" showCompass={false} />

            {/* Layer 1: All providers from vector tiles + LA boundaries */}
            <Source id="providers-tiles" type="vector" url={tileUrl}>
              <Layer
                id="la-boundary-fill"
                type="fill"
                source-layer="boundaries"
                filter={boundaryFilter}
                paint={{
                  "fill-color": "#6a0095",
                  "fill-opacity": boundaryVisible ? 0.06 : 0,
                  "fill-opacity-transition": { duration: 500, delay: 0 },
                }}
              />
              <Layer
                id="la-boundary-line"
                type="line"
                source-layer="boundaries"
                filter={boundaryFilter}
                paint={{
                  "line-color": "#6a0095",
                  "line-width": 2,
                  "line-opacity": boundaryVisible ? 0.5 : 0,
                  "line-opacity-transition": { duration: 500, delay: 0 },
                }}
              />
              <Layer
                id={TILE_LAYER_ID}
                type="circle"
                source-layer="providers"
                filter={combinedTileFilter}
                layout={{
                  visibility: shortlistedOnly ? "none" : "visible",
                }}
                paint={{
                  "circle-radius": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    4,
                    2,
                    8,
                    4,
                    12,
                    6,
                    16,
                    8,
                  ],
                  "circle-color": tileCircleColor,
                  "circle-stroke-color": "#ffffff",
                  "circle-stroke-width": 1,
                }}
              />
            </Source>

            {/* Layer 2: Shortlisted overlay (always visible) */}
            <Source
              id="providers-shortlist"
              type="geojson"
              data={shortlistGeojson}
            >
              <Layer
                id={SHORTLIST_LAYER_ID}
                type="symbol"
                layout={{
                  "icon-image": "shortlist-pin",
                  "icon-size": 1,
                  "icon-anchor": "bottom",
                  "icon-allow-overlap": true,
                }}
              />
            </Source>

            {/* Layer 3: Animation marker for shortlist feedback */}
            {animatingCoord && (
              <Marker
                latitude={animatingCoord.lat}
                longitude={animatingCoord.lon}
                anchor="bottom"
              >
                <div
                  className="pin-pop"
                  onAnimationEnd={onAnimationEnd}
                  aria-hidden="true"
                >
                  <svg width="32" height="43" viewBox="2 0 12 16">
                    <path
                      d="M8 0C4.686 0 2 2.686 2 6c0 5.25 6 10 6 10s6-4.75 6-10c0-3.314-2.686-6-6-6z"
                      fill="#6a0095"
                      stroke="#fff"
                      strokeWidth="1"
                    />
                    <circle cx="8" cy="6" r="2.5" fill="#fff" />
                  </svg>
                </div>
              </Marker>
            )}
          </MapGL>
        </div>
        {isTrayOpen && (
          <MapKeyboardTray
            selectedTypes={selectedTypes}
            sortBy={sortBy}
            availableSortOptions={availableSortOptions}
            shortlistedOnly={shortlistedOnly}
          />
        )}
      </div>
      {tooltip && (
        <div
          className={`absolute z-50 drop-shadow-lg ${isTouch || tooltip.pinned ? "" : "pointer-events-none"}`}
          style={
            tooltipPlacement === "top"
              ? {
                  left: tooltip.pos.x + shiftX,
                  top: tooltip.pos.y - PIN_R - GAP,
                  transform: "translate(-50%, -100%)",
                }
              : tooltipPlacement === "bottom"
                ? {
                    left: tooltip.pos.x + shiftX,
                    top: tooltip.pos.y + PIN_R + GAP,
                    transform: "translateX(-50%)",
                  }
                : tooltipPlacement === "right"
                  ? {
                      left: tooltip.pos.x + PIN_R + GAP,
                      top: tooltip.pos.y + shiftY,
                      transform: "translateY(-50%)",
                    }
                  : {
                      left: tooltip.pos.x - PIN_R - GAP,
                      top: tooltip.pos.y + shiftY,
                      transform: "translate(-100%, -50%)",
                    }
          }
        >
          {tooltipPlacement === "bottom" && (
            <div className="flex justify-center relative z-10 -mb-[1px]">
              <div
                className="relative"
                style={{
                  transform: `translateX(${-shiftX}px)`,
                  width: 14,
                  height: 7,
                }}
              >
                <div className="absolute inset-x-0 top-0 w-0 h-0 border-x-[7px] border-x-transparent border-b-[7px] border-b-zinc-200 mx-auto" />
                <div className="absolute top-[1px] inset-x-0 w-0 h-0 border-x-[6px] border-x-transparent border-b-[6px] border-b-white mx-auto" />
              </div>
            </div>
          )}
          <div
            className={`${tooltipPlacement === "left" || tooltipPlacement === "right" ? "flex items-center" : ""} ${tooltipPlacement === "left" ? "flex-row-reverse" : ""} ${tooltipPlacement === "right" ? "flex-row" : ""}`}
          >
            {(tooltipPlacement === "left" || tooltipPlacement === "right") && (
              <div
                className={`relative shrink-0 z-10 ${tooltipPlacement === "right" ? "-mr-[1px]" : "-ml-[1px]"}`}
                style={{
                  transform: `translateY(${-shiftY}px)`,
                  width: 7,
                  height: 14,
                }}
              >
                {tooltipPlacement === "right" ? (
                  <>
                    <div className="absolute inset-y-0 left-0 w-0 h-0 border-y-[7px] border-y-transparent border-r-[7px] border-r-zinc-200 my-auto" />
                    <div className="absolute inset-y-0 left-[1px] w-0 h-0 border-y-[6px] border-y-transparent border-r-[6px] border-r-white my-auto" />
                  </>
                ) : (
                  <>
                    <div className="absolute inset-y-0 right-0 w-0 h-0 border-y-[7px] border-y-transparent border-l-[7px] border-l-zinc-200 my-auto" />
                    <div className="absolute inset-y-0 right-[1px] w-0 h-0 border-y-[6px] border-y-transparent border-l-[6px] border-l-white my-auto" />
                  </>
                )}
              </div>
            )}
            <div
              className={`bg-white rounded-lg border border-zinc-200 relative ${isTouch ? "p-4" : "p-3"}`}
              style={{ width: tooltipW }}
            >
              {(isTouch || tooltip.pinned) && (
                <button
                  onClick={() => setTooltip(null)}
                  className="absolute top-2 right-2 w-10 h-10 flex items-center justify-center text-zinc-600 hover:text-zinc-700"
                  aria-label="Close"
                >
                  <i className="bi bi-x-lg text-base" />
                </button>
              )}
              <p
                className={`font-bold leading-tight ${isTouch ? "text-base pr-10" : "text-sm"} ${tooltip.pinned && !isTouch ? "pr-8" : ""}`}
              >
                {tooltipName}
              </p>
              <div className="flex flex-wrap gap-1 mt-1.5">
                {tooltipCareTypes.map((ct) => (
                  <span
                    key={ct}
                    className={`bg-purple-50 text-purple-800 px-2 rounded-full font-medium ${isTouch ? "text-sm py-1" : "text-xs py-0.5"}`}
                  >
                    {CARE_TYPE_LABELS[ct] || ct}
                  </span>
                ))}
              </div>
              <p
                className={`text-zinc-500 mt-1.5 ${isTouch ? "text-sm" : "text-xs"}`}
              >
                {tooltipAddress}
                {tooltipPostcode ? `, ${tooltipPostcode}` : ""}
              </p>
              <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                {showFees && tooltipCost && (
                  <span
                    className={`text-zinc-700 font-medium ${isTouch ? "text-sm" : "text-xs"}`}
                  >
                    {tooltipCost}
                  </span>
                )}
                {activeProvider ? (
                  (() => {
                    const ofsted = activeProvider.ofsted;
                    if (ofsted?.framework === "report_card") {
                      const judgements = getReportCardJudgements(ofsted);
                      const booleans = getReportCardBooleans(ofsted);
                      const sortedJudgements = [...judgements].sort(
                        (a, b) => a.rank - b.rank,
                      );
                      return (
                        <span className="inline-flex items-center gap-1">
                          <span
                            className={`font-bold text-zinc-500 ${isTouch ? "text-sm" : "text-xs"}`}
                          >
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
                              role="img"
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
                        <span
                          className={`px-2 py-0.5 rounded font-bold text-center bg-zinc-100 text-zinc-600 ${isTouch ? "text-sm" : "text-xs"}`}
                        >
                          Ofsted: no summary
                        </span>
                      );
                    }
                    const rating = getOfstedRatingLabel(ofsted);
                    if (!rating) return null;
                    return (
                      <span
                        className={`px-2 py-0.5 rounded font-bold text-center ${getOfstedBadgeClasses(rating)} ${isTouch ? "text-sm" : "text-xs"}`}
                      >
                        Ofsted: {rating}
                      </span>
                    );
                  })()
                ) : (
                  <OfstedBadge
                    ofsted={activeItem?.data.ofsted}
                    cma={activeItem?.data.cma}
                    isTouch={isTouch}
                  />
                )}
              </div>
              {!tooltip.pinned && tooltip.items.length > 1 && (
                <p className="text-xs text-zinc-600 mt-1.5">
                  Click to see +{tooltip.items.length - 1} more here
                </p>
              )}
              {(isTouch || tooltip.pinned) &&
                (activeProvider ? (
                  <button
                    onClick={() => {
                      const siblings = tooltip!.items
                        .map((item) => providerMap.get(item.data.id))
                        .filter((p): p is Provider => !!p);
                      setTooltip(null);
                      onProviderSelect?.(
                        activeProvider,
                        siblings.length > 1 ? siblings : undefined,
                      );
                    }}
                    className="mt-2 ml-auto block text-sm text-zinc-500 py-1"
                  >
                    View details <i className="bi bi-arrow-right" />
                  </button>
                ) : (
                  <button
                    disabled
                    className="mt-2 ml-auto flex items-center gap-2 text-sm text-zinc-600 py-1"
                  >
                    <div className="animate-spin w-4 h-4 border-2 border-zinc-400 border-t-transparent rounded-full" />
                    Loading...
                  </button>
                ))}
              {tooltip.pinned && tooltip.items.length > 1 && (
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-zinc-100">
                  <button
                    onClick={() =>
                      setTooltip((prev) =>
                        prev
                          ? {
                              ...prev,
                              activeIndex:
                                (prev.activeIndex - 1 + prev.items.length) %
                                prev.items.length,
                            }
                          : null,
                      )
                    }
                    className="w-7 h-7 flex items-center justify-center rounded hover:bg-zinc-100 text-zinc-500"
                    aria-label="Previous provider"
                  >
                    <i className="bi bi-chevron-left text-xs" />
                  </button>
                  <span className="text-xs text-zinc-600">
                    {tooltip.activeIndex + 1} of {tooltip.items.length}
                  </span>
                  <button
                    onClick={() =>
                      setTooltip((prev) =>
                        prev
                          ? {
                              ...prev,
                              activeIndex:
                                (prev.activeIndex + 1) % prev.items.length,
                            }
                          : null,
                      )
                    }
                    className="w-7 h-7 flex items-center justify-center rounded hover:bg-zinc-100 text-zinc-500"
                    aria-label="Next provider"
                  >
                    <i className="bi bi-chevron-right text-xs" />
                  </button>
                </div>
              )}
            </div>
          </div>
          {tooltipPlacement === "top" && (
            <div className="flex justify-center relative z-10 -mt-[1px]">
              <div
                className="relative"
                style={{
                  transform: `translateX(${-shiftX}px)`,
                  width: 14,
                  height: 7,
                }}
              >
                <div className="absolute inset-x-0 bottom-0 w-0 h-0 border-x-[7px] border-x-transparent border-t-[7px] border-t-zinc-200 mx-auto" />
                <div className="absolute bottom-[1px] inset-x-0 w-0 h-0 border-x-[6px] border-x-transparent border-t-[6px] border-t-white mx-auto" />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

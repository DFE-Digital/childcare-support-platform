import { useState, useCallback, useRef, useMemo, useEffect } from "react";
import type { SisSchema, SisResponse } from "@/data/sisParser";
import type { Provider } from "@/types/provider";
import type { SortOption } from "@/components/providers/ProviderFilters";
import { querySis, needsRequery } from "@/data/spatialQuery";
import { loadProvider } from "@/data/loader";
import {
  filterSortDedup,
  type ProviderSearchEntry,
  type BBox,
  type ProviderPoint,
} from "@/lib/filterSortDedup";

async function fetchInBatches<T>(
  items: T[],
  fn: (item: T) => Promise<void>,
  concurrency: number,
  onBatchDone?: () => void,
): Promise<void> {
  for (let i = 0; i < items.length; i += concurrency) {
    const batch = items.slice(i, i + concurrency);
    await Promise.all(batch.map(fn));
    onBatchDone?.();
  }
}

export type {
  ProviderSearchEntry,
  BBox,
  ProviderPoint,
} from "@/lib/filterSortDedup";

interface UseProviderSearchReturn {
  entries: ProviderSearchEntry[];
  allEntryIds: string[];
  loadedProviders: Map<string, Provider>;
  loading: boolean;
  bboxMap: Map<string, BBox>;
  pointMap: Map<string, ProviderPoint>;
  search: (
    postcodeBbox: [number, number, number, number],
    postcodeCentroid: [number, number],
    mapViewport: [number, number, number, number],
  ) => Promise<void>;
  requery: (mapViewport: [number, number, number, number]) => Promise<void>;
  retryProvider: (id: string) => void;
}

export function useProviderSearch(
  sisSchema: SisSchema | null,
  selectedTypes: string[],
  childAgesMonths: number[],
  fundedHoursOnly: boolean,
  sortBy: SortOption,
  shortlistedOnly: boolean,
  shortlistedProviders: string[],
  requestedIds: string[],
): UseProviderSearchReturn {
  const [sisResponse, setSisResponse] = useState<SisResponse | null>(null);
  const [loadedProviders, setLoadedProviders] = useState<Map<string, Provider>>(
    new Map(),
  );
  const [loading, setLoading] = useState(false);
  const [retryEpoch, setRetryEpoch] = useState(0);
  const queryGenRef = useRef(0);
  const failedIdsRef = useRef<Set<string>>(new Set());
  const providerCacheRef = useRef<Map<string, Provider>>(new Map());
  const lastPostcodeRef = useRef<{
    bbox: [number, number, number, number];
    centroid: [number, number];
  } | null>(null);
  const lastViewportRef = useRef<[number, number, number, number] | null>(null);

  // Compute care-type bitfield from selected types using schema
  const careTypeMask = useMemo(() => {
    if (shortlistedOnly) return 0;
    if (!sisSchema || selectedTypes.length === 0) return 0;
    const expanded = selectedTypes.flatMap((t) =>
      t === "breakfast_club" ? ["breakfast_club", "free_breakfast_club"] : [t],
    );
    return expanded.reduce(
      (m, t) => m | (sisSchema.SisCareTypeBits[t] ?? 0),
      0,
    );
  }, [sisSchema, selectedTypes, shortlistedOnly]);

  const search = useCallback(
    async (
      postcodeBbox: [number, number, number, number],
      postcodeCentroid: [number, number],
      mapViewport: [number, number, number, number],
    ) => {
      if (!sisSchema) return;
      if (failedIdsRef.current.size > 0) {
        failedIdsRef.current.clear();
        setRetryEpoch((e) => e + 1);
      }
      setLoading(true);
      lastPostcodeRef.current = {
        bbox: postcodeBbox,
        centroid: postcodeCentroid,
      };
      lastViewportRef.current = mapViewport;
      try {
        const resp = await querySis(
          sisSchema,
          postcodeBbox,
          postcodeCentroid,
          mapViewport,
          careTypeMask,
        );
        setSisResponse(resp);
      } catch (err) {
        console.error("[useProviderSearch] querySis failed:", err);
      } finally {
        setLoading(false);
      }
    },
    [sisSchema, careTypeMask],
  );

  const requery = useCallback(
    async (mapViewport: [number, number, number, number]) => {
      if (!sisSchema || !lastPostcodeRef.current) return;
      const { bbox, centroid } = lastPostcodeRef.current;
      if (!needsRequery(bbox, centroid, mapViewport, careTypeMask)) return;
      if (failedIdsRef.current.size > 0) {
        failedIdsRef.current.clear();
        setRetryEpoch((e) => e + 1);
      }
      const gen = ++queryGenRef.current;
      setLoading(true);
      lastViewportRef.current = mapViewport;
      try {
        const resp = await querySis(
          sisSchema,
          bbox,
          centroid,
          mapViewport,
          careTypeMask,
        );
        if (gen === queryGenRef.current) setSisResponse(resp);
      } catch (err) {
        console.error("[useProviderSearch] querySis failed:", err);
      } finally {
        if (gen === queryGenRef.current) setLoading(false);
      }
    },
    [sisSchema, careTypeMask],
  );

  // When careTypeMask changes, requery with the last known viewport
  useEffect(() => {
    if (!sisSchema || !lastPostcodeRef.current || !lastViewportRef.current)
      return;
    const { bbox, centroid } = lastPostcodeRef.current;
    const viewport = lastViewportRef.current;
    let cancelled = false;
    const gen = ++queryGenRef.current;
    failedIdsRef.current.clear();
    (async () => {
      setLoading(true);
      try {
        const resp = await querySis(
          sisSchema,
          bbox,
          centroid,
          viewport,
          careTypeMask,
        );
        if (!cancelled && gen === queryGenRef.current) setSisResponse(resp);
      } catch (err) {
        console.error("[useProviderSearch] querySis failed:", err);
      } finally {
        if (!cancelled && gen === queryGenRef.current) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sisSchema, careTypeMask]);

  // Filter/sort/dedup the cached SIS response (no network call)
  const { entries, bboxMap, pointMap } = useMemo(() => {
    if (!sisResponse)
      return {
        entries: [] as ProviderSearchEntry[],
        bboxMap: new Map<string, BBox>(),
        pointMap: new Map<string, ProviderPoint>(),
      };
    return filterSortDedup(
      sisResponse,
      childAgesMonths,
      fundedHoursOnly,
      sortBy,
    );
  }, [sisResponse, childAgesMonths, fundedHoursOnly, sortBy]);

  // All entries (before shortlist filter)
  const allEntries = entries;

  // Apply shortlist filter
  const filteredEntries = useMemo(() => {
    if (!shortlistedOnly) return allEntries;
    const set = new Set(shortlistedProviders);
    return allEntries.filter((e) => set.has(e.providerId));
  }, [allEntries, shortlistedOnly, shortlistedProviders]);

  const allProviderIds = useMemo(
    () => allEntries.map((e) => e.providerId),
    [allEntries],
  );

  // Distance map from SIS entries (ref avoids adding as effect dependency)
  const distanceMap = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of allEntries) m.set(e.providerId, e.distanceMiles);
    return m;
  }, [allEntries]);
  const distanceMapRef = useRef(distanceMap);
  distanceMapRef.current = distanceMap;

  // Load provider JSONs for requested entries (batched)
  useEffect(() => {
    const cache = providerCacheRef.current;
    const failed = failedIdsRef.current;
    const toLoad = requestedIds.filter(
      (id) => !cache.has(id) && !failed.has(id),
    );
    if (toLoad.length === 0) return;
    let cancelled = false;
    fetchInBatches(
      toLoad,
      (id) =>
        loadProvider(id)
          .then((p) => {
            const dist = distanceMapRef.current.get(id);
            if (dist !== undefined) p.distanceMiles = dist;
            cache.set(id, p);
          })
          .catch((err) => {
            failedIdsRef.current.add(id);
            console.error("[useProviderSearch] loadProvider failed:", err);
          }),
      5,
      () => {
        if (!cancelled) setLoadedProviders(new Map(cache));
      },
    )
      .then(() => {
        if (!cancelled) setLoadedProviders(new Map(cache));
      })
      .catch((err) =>
        console.error("[useProviderSearch] batch load failed:", err),
      );
    return () => {
      cancelled = true;
    };
  }, [requestedIds, retryEpoch]);

  // Re-patch distances when distanceMap changes (e.g. requery gives new distances)
  useEffect(() => {
    const cache = providerCacheRef.current;
    let changed = false;
    for (const [id, dist] of distanceMap) {
      const p = cache.get(id);
      if (p && p.distanceMiles !== dist) {
        p.distanceMiles = dist;
        changed = true;
      }
    }
    if (changed) setLoadedProviders(new Map(cache));
  }, [distanceMap]);

  const retryProvider = useCallback((id: string) => {
    failedIdsRef.current.delete(id);
    const cache = providerCacheRef.current;
    if (cache.has(id)) return;
    loadProvider(id)
      .then((p) => {
        const dist = distanceMapRef.current.get(id);
        if (dist !== undefined) p.distanceMiles = dist;
        cache.set(id, p);
        setLoadedProviders(new Map(cache));
      })
      .catch((err) => {
        failedIdsRef.current.add(id);
        console.error("[useProviderSearch] retryProvider failed:", err);
      });
  }, []);

  return {
    entries: filteredEntries,
    allEntryIds: allProviderIds,
    loadedProviders,
    loading,
    bboxMap,
    pointMap,
    search,
    requery,
    retryProvider,
  };
}

import { useState, useEffect, useRef, useCallback } from "react";
import { loadOutwardCodes, loadInwardCodes } from "@/data/loader";

interface InwardEntry {
  b: [number, number, number, number]; // [west, south, east, north]
  c: [number, number]; // [lon, lat]
  a?: number[]; // indices into file-level LAD code array ("_")
  d?: number; // IoD decile (1=most deprived, 10=least deprived, England only)
}

type InwardData = Record<string, InwardEntry>;

export interface PostcodeGeo {
  bbox: [number, number, number, number]; // [west, south, east, north]
  centroid: [number, number]; // [lon, lat]
  deprivationDecile?: number;
}

export function usePostcodeLookup() {
  const [outwardCodes, setOutwardCodes] = useState<string[] | null>(null);
  const inwardCache = useRef<Map<string, InwardData>>(new Map());
  const ladIndexCache = useRef<Map<string, string[]>>(new Map());
  const [loadingInward, setLoadingInward] = useState<string | null>(null);
  const pendingFetches = useRef<Map<string, Promise<InwardData>>>(new Map());

  const hasLoaded = useRef(false);

  // Load outward codes on mount
  useEffect(() => {
    loadOutwardCodes()
      .then((codes) => {
        setOutwardCodes(codes);
        hasLoaded.current = true;
      })
      .catch((err) => {
        console.error("[usePostcodeLookup] loadOutwardCodes failed:", err);
        setOutwardCodes([]);
      });
  }, []);

  // Retry on reconnect if initial load failed
  useEffect(() => {
    if (hasLoaded.current) return;
    const onOnline = () => {
      loadOutwardCodes()
        .then((codes) => {
          setOutwardCodes(codes);
          hasLoaded.current = true;
        })
        .catch((err) =>
          console.error(
            "[usePostcodeLookup] loadOutwardCodes retry failed:",
            err,
          ),
        );
    };
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, []);

  const prefetchInward = useCallback((outward: string) => {
    const key = outward.toUpperCase();
    if (inwardCache.current.has(key) || pendingFetches.current.has(key)) return;
    setLoadingInward(key);
    const promise = loadInwardCodes(key)
      .then((raw) => {
        const { _: ladIndex, ...entries } = raw as {
          _?: string[];
          [k: string]: unknown;
        };
        if (Array.isArray(ladIndex)) {
          ladIndexCache.current.set(key, ladIndex);
        }
        const data = entries as unknown as InwardData;
        inwardCache.current.set(key, data);
        return data;
      })
      .catch((err): InwardData => {
        console.error("[usePostcodeLookup] loadInwardCodes failed:", err);
        return {};
      })
      .finally(() => {
        pendingFetches.current.delete(key);
        setLoadingInward((cur) => (cur === key ? null : cur));
      });
    pendingFetches.current.set(key, promise);
  }, []);

  const ensureInward = useCallback(
    (outward: string): Promise<InwardData> => {
      const key = outward.toUpperCase();
      const cached = inwardCache.current.get(key);
      if (cached) return Promise.resolve(cached);
      const pending = pendingFetches.current.get(key);
      if (pending) return pending;
      prefetchInward(key);
      return pendingFetches.current.get(key)!;
    },
    [prefetchInward],
  );

  const filterOutward = useCallback(
    (prefix: string): string[] => {
      if (!outwardCodes) return [];
      const norm = prefix.toUpperCase().replace(/\s+/g, "");
      if (!norm) return [];
      return outwardCodes.filter((code) => code.startsWith(norm));
    },
    [outwardCodes],
  );

  const filterInward = useCallback(
    (outward: string, prefix: string): string[] => {
      const data = inwardCache.current.get(outward.toUpperCase());
      if (!data) return [];
      const norm = prefix.toUpperCase().replace(/\s+/g, "");
      return Object.keys(data)
        .filter((code) => code.startsWith(norm))
        .sort();
    },
    [],
  );

  const getGeo = useCallback(
    (outward: string, inward: string): PostcodeGeo | null => {
      const data = inwardCache.current.get(outward.toUpperCase());
      if (!data) return null;
      const entry = data[inward.toUpperCase()];
      if (!entry) return null;
      return { bbox: entry.b, centroid: entry.c, deprivationDecile: entry.d };
    },
    [],
  );

  const getLaCodes = useCallback(
    (outward: string, inward: string): string[] => {
      const key = outward.toUpperCase();
      const data = inwardCache.current.get(key);
      if (!data) return [];
      const entry = data[inward.toUpperCase()];
      if (!entry || entry.a === undefined) return [];
      const ladIndex = ladIndexCache.current.get(key);
      if (!ladIndex) return [];
      return entry.a.filter((i) => i < ladIndex.length).map((i) => ladIndex[i]);
    },
    [],
  );

  const isValid = useCallback(
    (postcode: string): boolean => {
      const raw = postcode.trim().toUpperCase().replace(/\s+/g, "");
      if (raw.length < 5) return false;
      const outward = raw.slice(0, -3);
      const inward = raw.slice(-3);
      if (!outwardCodes?.includes(outward)) return false;
      const data = inwardCache.current.get(outward);
      return data ? inward in data : false;
    },
    [outwardCodes],
  );

  return {
    filterOutward,
    filterInward,
    getGeo,
    getLaCodes,
    prefetchInward,
    ensureInward,
    isValid,
    isLoading: outwardCodes === null || loadingInward !== null,
    outwardLoaded: outwardCodes !== null,
  };
}

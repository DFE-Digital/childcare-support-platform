import type { SisSchema, SisResponse } from "./sisParser";
import { parseSisResponse } from "./sisParser";
import { fetchWithRetry } from "./fetchWithRetry";

const BASE = import.meta.env.BASE_URL;

// ---------------------------------------------------------------------------
// Geometry helpers
// ---------------------------------------------------------------------------

export function haversineKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const EARTH_R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return EARTH_R * 2 * Math.asin(Math.sqrt(a));
}

/** Does the boundary of circle *R* cross the boundary of rectangle *V*? See SIS README § Terminology. */
export function circleRectBoundaryIntersects(
  cLat: number,
  cLon: number,
  radiusKm: number,
  south: number,
  west: number,
  north: number,
  east: number,
): boolean {
  const dSW = haversineKm(cLat, cLon, south, west);
  const dSE = haversineKm(cLat, cLon, south, east);
  const dNW = haversineKm(cLat, cLon, north, west);
  const dNE = haversineKm(cLat, cLon, north, east);
  const maxCorner = Math.max(dSW, dSE, dNW, dNE);

  // All corners inside circle → V ⊂ R
  if (maxCorner <= radiusKm) return false;

  const centerInV =
    cLat >= south && cLat <= north && cLon >= west && cLon <= east;

  if (centerInV) {
    const dS = haversineKm(cLat, cLon, south, cLon);
    const dN = haversineKm(cLat, cLon, north, cLon);
    const dW = haversineKm(cLat, cLon, cLat, west);
    const dE = haversineKm(cLat, cLon, cLat, east);
    const minEdge = Math.min(dS, dN, dW, dE);
    return radiusKm > minEdge; // circle extends past V
  }

  // Center outside V — circle overlaps V if nearest point is within radius
  const nearestLat = Math.max(south, Math.min(north, cLat));
  const nearestLon = Math.max(west, Math.min(east, cLon));
  return haversineKm(cLat, cLon, nearestLat, nearestLon) < radiusKm;
}

/** Are all 4 corners of viewport V within radiusKm of center? (V ⊆ R check) */
export function viewportWithinCircle(
  cLat: number,
  cLon: number,
  radiusKm: number,
  south: number,
  west: number,
  north: number,
  east: number,
): boolean {
  return (
    haversineKm(cLat, cLon, south, west) <= radiusKm &&
    haversineKm(cLat, cLon, south, east) <= radiusKm &&
    haversineKm(cLat, cLon, north, west) <= radiusKm &&
    haversineKm(cLat, cLon, north, east) <= radiusKm
  );
}

// ---------------------------------------------------------------------------
// Inflation helpers (match SIS inflate_rect)
// ---------------------------------------------------------------------------

export function inflateRect(
  south: number,
  west: number,
  north: number,
  east: number,
  inflation: number,
): [number, number, number, number] {
  const halfInf = inflation * 0.5;
  const h = north - south;
  const w = east - west;
  return [
    south - halfInf * h,
    west - halfInf * w,
    north + halfInf * h,
    east + halfInf * w,
  ];
}

function viewportWithinInflated(
  viewport: [number, number, number, number],
  inflated: [number, number, number, number],
): boolean {
  return (
    viewport[0] >= inflated[0] &&
    viewport[1] >= inflated[1] &&
    viewport[2] <= inflated[2] &&
    viewport[3] <= inflated[3]
  );
}

// ---------------------------------------------------------------------------
// Cache
// ---------------------------------------------------------------------------

interface SisCache {
  response: SisResponse;
  postcodeBbox: [number, number, number, number] | null;
  postcodeCentroid: [number, number] | null;
  inflatedRect: [number, number, number, number];
  mapViewport: [number, number, number, number];
  /** Whether the response used *I* (true) or *V* (false). */
  inflated: boolean;
  /** Whether the result limit *N* was reached. */
  hitLimit: boolean;
  /** Radius of completeness circle *R* in km (only meaningful when hitLimit). */
  radiusKm: number;
  /** Care-type bitfield mask used for this cached query. */
  careTypeMask: number;
}

let cache: SisCache | null = null;

// ---------------------------------------------------------------------------
// Requery decision
// ---------------------------------------------------------------------------

/** Count unique *point* provider IDs in a SIS response.
 *
 * Bbox rows (bboxSouth is not NaN) are excluded — their limit is independent
 * and does not affect the R-circle completeness check.
 */
function countUniquePointProviders(sis: SisResponse): number {
  const seen = new Set<bigint>();
  for (let i = 0; i < sis.rowCount; i++) {
    if (isNaN(sis.bboxSouth(i))) {
      seen.add(sis.providerId(i));
    }
  }
  return seen.size;
}

/** Max sort_distance across *point* rows only (radius of R).
 *
 * Bbox rows are skipped so that bbox max-corner distances (which are
 * structurally larger) don't inflate the R-circle radius.
 */
export function maxPointDistance(sis: SisResponse): number {
  let max = 0;
  for (let i = 0; i < sis.rowCount; i++) {
    if (!isNaN(sis.bboxSouth(i))) continue; // skip bbox rows
    const d = sis.sortDistance(i);
    if (!isNaN(d) && d > max) max = d;
  }
  return max;
}

export function needsRequery(
  postcodeBbox: [number, number, number, number] | null,
  postcodeCentroid: [number, number] | null,
  mapViewport: [number, number, number, number],
  careTypeMask: number = 0,
): boolean {
  if (!cache) return true;

  // Care-type mask changed → always requery
  if (careTypeMask !== cache.careTypeMask) {
    return true;
  }

  // Postcode changed → always requery
  if (
    JSON.stringify(postcodeBbox) !== JSON.stringify(cache.postcodeBbox) ||
    JSON.stringify(postcodeCentroid) !== JSON.stringify(cache.postcodeCentroid)
  ) {
    return true;
  }

  // Non-inflated (exact *V*) response → requery on any viewport move
  if (!cache.inflated) {
    if (JSON.stringify(mapViewport) !== JSON.stringify(cache.mapViewport)) {
      return true;
    }
    return false;
  }

  // Inflated response — check if *V* left *I*
  if (!viewportWithinInflated(mapViewport, cache.inflatedRect)) {
    return true;
  }

  // If *N* was hit, requery unless V ⊆ R
  if (cache.hitLimit && cache.postcodeCentroid) {
    const [cLon, cLat] = cache.postcodeCentroid; // centroid is [lon, lat]
    const [south, west, north, east] = mapViewport;
    if (
      !viewportWithinCircle(
        cLat,
        cLon,
        cache.radiusKm,
        south,
        west,
        north,
        east,
      )
    ) {
      return true;
    }
  }

  return false;
}

// ---------------------------------------------------------------------------
// Query
// ---------------------------------------------------------------------------

export async function querySis(
  schema: SisSchema,
  postcodeBbox: [number, number, number, number],
  postcodeCentroid: [number, number],
  mapViewport: [number, number, number, number],
  careTypeMask: number = 0,
): Promise<SisResponse> {
  if (
    !needsRequery(postcodeBbox, postcodeCentroid, mapViewport, careTypeMask)
  ) {
    return cache!.response;
  }

  // PostcodeGeo bbox is [west, south, east, north], centroid is [lon, lat]
  const params = new URLSearchParams({
    pc_south: String(postcodeBbox[1]),
    pc_west: String(postcodeBbox[0]),
    pc_north: String(postcodeBbox[3]),
    pc_east: String(postcodeBbox[2]),
    pc_lat: String(postcodeCentroid[1]),
    pc_lon: String(postcodeCentroid[0]),
    // mapViewport is [south, west, north, east]
    map_south: String(mapViewport[0]),
    map_west: String(mapViewport[1]),
    map_north: String(mapViewport[2]),
    map_east: String(mapViewport[3]),
    ct: String(careTypeMask),
  });

  const buffer = await fetchWithRetry(async () => {
    const r = await fetch(`${BASE}api/spatial-query?${params}`);
    if (!r.ok) {
      const err = new Error(`SIS query failed: ${r.status}`);
      (err as Error & { status: number }).status = r.status;
      throw err;
    }
    const ct = r.headers.get("content-type") ?? "";
    if (ct.includes("text/html")) {
      const err = new Error(
        `Expected binary from ${BASE}api/spatial-query but got HTML (possible SPA fallback)`,
      );
      (err as Error & { status: number }).status = 404;
      throw err;
    }
    return r.arrayBuffer();
  });
  const response = parseSisResponse(schema, buffer);

  const uniquePointProviders = countUniquePointProviders(response);
  const hitLimit = uniquePointProviders >= schema.SisResultLimit;

  const radiusKm = hitLimit ? maxPointDistance(response) : 0;

  console.log(
    `[spatial-query] ${uniquePointProviders} point providers, ${response.rowCount} rows, ` +
      (response.inflated ? `inflation=${schema.SisBBoxInflation}` : "exact") +
      (hitLimit ? `, hit limit (R=${radiusKm.toFixed(1)}km)` : ""),
  );

  const ir = inflateRect(
    mapViewport[0],
    mapViewport[1],
    mapViewport[2],
    mapViewport[3],
    schema.SisBBoxInflation,
  );

  cache = {
    response,
    postcodeBbox,
    postcodeCentroid,
    inflatedRect: ir,
    mapViewport,
    inflated: response.inflated,
    hitLimit,
    radiusKm,
    careTypeMask,
  };

  return response;
}

export function getCachedResponse(): SisResponse | null {
  return cache?.response ?? null;
}

export function clearCache(): void {
  cache = null;
}

export function _setCacheForTest(
  c: Omit<SisCache, "response"> & { inflated: boolean },
): void {
  cache = {
    ...c,
    response: {
      rowCount: 0,
      columns: [],
      buffer: new ArrayBuffer(0),
      inflated: c.inflated,
    } as unknown as SisResponse,
  };
}

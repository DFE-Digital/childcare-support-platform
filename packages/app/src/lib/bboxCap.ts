import type {
  BBox,
  ProviderPoint,
  ProviderSearchEntry,
} from "@/lib/filterSortDedup";
import type { ProviderStatEntry } from "@/types/costs";

export function capBboxByPointDistance(
  viewportEntryIds: string[],
  entries: ProviderSearchEntry[],
  pointMap: Map<string, ProviderPoint>,
  bboxMap: Map<string, BBox>,
  mapBounds?: [number, number, number, number] | null,
): string[] {
  const entryMap = new Map(entries.map((e) => [e.providerId, e]));
  let maxPointDistance = 0;
  for (const id of viewportEntryIds) {
    if (pointMap.has(id)) {
      const dist = entryMap.get(id)?.distanceMiles ?? 0;
      if (dist > maxPointDistance) maxPointDistance = dist;
    }
  }
  if (maxPointDistance === 0)
    return viewportEntryIds.filter((id) => !bboxMap.has(id));

  const [mSouth, mWest, mNorth, mEast] = mapBounds ?? [0, 0, 0, 0];

  return viewportEntryIds.filter((id) => {
    if (!bboxMap.has(id)) return true;
    const dist = entryMap.get(id)?.distanceMiles ?? 0;
    if (dist <= maxPointDistance) return true;
    if (mapBounds) {
      const bb = bboxMap.get(id)!;
      return (
        bb.south >= mSouth &&
        bb.north <= mNorth &&
        bb.west >= mWest &&
        bb.east <= mEast
      );
    }
    return false;
  });
}

export function computeMissingBboxCount(
  cappedViewportEntryIds: string[],
  entries: ProviderSearchEntry[],
  bboxMap: Map<string, BBox>,
  searchedLadInt: number,
  providerStats: Record<string, ProviderStatEntry>,
  selectedTypes: string[],
): number {
  const ladCodeById = new Map(entries.map((e) => [e.providerId, e.ladCode]));
  const bboxFromLaInViewport = cappedViewportEntryIds.filter(
    (id) => bboxMap.has(id) && ladCodeById.get(id) === searchedLadInt,
  ).length;
  const relevantTypes =
    selectedTypes.length > 0 ? selectedTypes : Object.keys(providerStats);
  const totalBboxOnly = relevantTypes.reduce(
    (sum, type) => sum + (providerStats[type]?.bboxOnly ?? 0),
    0,
  );
  return Math.max(0, totalBboxOnly - bboxFromLaInViewport);
}

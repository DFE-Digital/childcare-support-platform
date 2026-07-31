import type { BBox, ProviderPoint } from "@/lib/filterSortDedup";

export function filterProviderIdsInViewport(
  providerIds: string[],
  mapBounds: [number, number, number, number],
  bboxMap: Map<string, BBox>,
  pointMap: Map<string, ProviderPoint>,
): string[] {
  const [south, west, north, east] = mapBounds;
  return providerIds.filter((id) => {
    const bbox = bboxMap.get(id);
    if (bbox) {
      // Bbox provider: include if any part of the bbox intersects the viewport
      return (
        bbox.south <= north &&
        bbox.north >= south &&
        bbox.west <= east &&
        bbox.east >= west
      );
    }
    const pt = pointMap.get(id);
    if (pt) {
      // Point provider: point-in-viewport
      return (
        pt.lat >= south && pt.lat <= north && pt.lon >= west && pt.lon <= east
      );
    }
    // Unlocated provider — exclude
    return false;
  });
}

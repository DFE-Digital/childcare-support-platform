import type { SisResponse } from "@/data/sisParser";
import type { SortOption } from "@/components/providers/ProviderFilters";

const KM_TO_MILES = 0.621371;

export interface ProviderSearchEntry {
  providerId: string;
  distanceMiles: number;
  ladCode: number;
}

export interface BBox {
  south: number;
  west: number;
  north: number;
  east: number;
}

export interface ProviderPoint {
  lat: number;
  lon: number;
}

export function getCostColumn(
  childAgesMonths: number[],
): (sis: SisResponse, row: number) => number {
  if (childAgesMonths.length === 0) {
    return (sis, row) => sis.sortCostAll(row);
  }
  if (childAgesMonths.length === 1) {
    const age = childAgesMonths[0];
    if (age < 24) return (sis, row) => sis.sortCostUnder2(row);
    if (age < 36) return (sis, row) => sis.sortCostAge2(row);
    if (age < 60) return (sis, row) => sis.sortCostAge3to4(row);
    return (sis, row) => sis.sortCostAge5plus(row);
  }
  // Multiple children: minimum across relevant age columns
  const fns: ((sis: SisResponse, row: number) => number)[] = [];
  const ages = new Set(
    childAgesMonths.map((a) => {
      if (a < 24) return "u2";
      if (a < 36) return "2";
      if (a < 60) return "3to4";
      return "5p";
    }),
  );
  if (ages.has("u2")) fns.push((sis, row) => sis.sortCostUnder2(row));
  if (ages.has("2")) fns.push((sis, row) => sis.sortCostAge2(row));
  if (ages.has("3to4")) fns.push((sis, row) => sis.sortCostAge3to4(row));
  if (ages.has("5p")) fns.push((sis, row) => sis.sortCostAge5plus(row));
  return (sis, row) => {
    let min = Infinity;
    for (const fn of fns) {
      const v = fn(sis, row);
      if (!isNaN(v) && v < min) min = v;
    }
    return min === Infinity ? NaN : min;
  };
}

export function filterSortDedup(
  sis: SisResponse,
  childAgesMonths: number[],
  fundedHoursOnly: boolean,
  sortBy: SortOption,
): {
  entries: ProviderSearchEntry[];
  bboxMap: Map<string, BBox>;
  pointMap: Map<string, ProviderPoint>;
} {
  // Start with all rows (care-type filtering is done server-side via SIS `ct` param)
  let rows: number[] = [];
  for (let i = 0; i < sis.rowCount; i++) rows.push(i);

  // Filter by child age eligibility
  if (childAgesMonths.length > 0) {
    rows = rows.filter((r) => {
      const minMonths = sis.filterEligibleMinMonths(r);
      const minYears = sis.filterEligibleMinYears(r);
      const maxYears = sis.filterEligibleMaxYears(r);
      const lo = minMonths >= 0 ? minMonths : minYears >= 0 ? minYears * 12 : 0;
      const hi = maxYears >= 0 ? (maxYears + 1) * 12 - 1 : 999;
      return childAgesMonths.some((age) => age >= lo && age <= hi);
    });
  }

  // Filter by funded hours
  if (fundedHoursOnly) {
    rows = rows.filter((r) => sis.filterAcceptsFundedHours(r));
  }

  // Sort
  const costFn = getCostColumn(childAgesMonths);

  const getSortValue = (r: number): number => {
    switch (sortBy) {
      case "distance":
        return sis.sortDistance(r);
      case "lowest_cost":
        return costFn(sis, r);
      case "most_graduate":
        return sis.sortGraduates(r);
      case "lowest_turnover":
        return sis.sortTurnover(r);
      case "longest_daily":
        return sis.sortDailyClose(r) - sis.sortDailyOpen(r);
      case "longest_annual":
        return sis.sortAnnualOpening(r);
      case "best_ofsted":
        return sis.sortOfsted(r);
      default:
        return sis.sortDistance(r);
    }
  };

  const isAsc =
    sortBy === "distance" ||
    sortBy === "lowest_cost" ||
    sortBy === "lowest_turnover";

  rows.sort((a, b) => {
    const va = getSortValue(a);
    const vb = getSortValue(b);
    const aNaN = isNaN(va) || va === -1;
    const bNaN = isNaN(vb) || vb === -1;
    if (aNaN && bNaN) return 0;
    if (aNaN) return 1;
    if (bNaN) return -1;
    return isAsc ? va - vb : vb - va;
  });

  // Deduplicate by provider_id (keep first = best per sort)
  const seen = new Set<string>();
  const results: ProviderSearchEntry[] = [];
  const bboxMap = new Map<string, BBox>();
  const pointMap = new Map<string, ProviderPoint>();
  for (const r of rows) {
    const pid = "p" + sis.providerId(r).toString();
    if (seen.has(pid)) continue;
    seen.add(pid);
    const distKm = sis.sortDistance(r);
    results.push({
      providerId: pid,
      distanceMiles: isNaN(distKm) ? 0 : distKm * KM_TO_MILES,
      ladCode: sis.ladCode(r),
    });
    if (sis.hasBbox(r)) {
      bboxMap.set(pid, {
        south: sis.bboxSouth(r),
        west: sis.bboxWest(r),
        north: sis.bboxNorth(r),
        east: sis.bboxEast(r),
      });
    } else {
      // Point provider: bbox_north=lat, bbox_west=lon (bbox_south/east are NaN)
      const lat = sis.bboxNorth(r);
      const lon = sis.bboxWest(r);
      if (!isNaN(lat) && !isNaN(lon)) {
        pointMap.set(pid, { lat, lon });
      }
    }
  }
  return { entries: results, bboxMap, pointMap };
}

const TYPE_SIZES: Record<string, number> = {
  int64: 8,
  int32: 4,
  int8: 1,
  uint8: 1,
  float32: 4,
};

/** Response from inflated rectangle *I* query. */
const MAGIC_INFLATED = 0x53495300;
/** Response from exact viewport *V* re-query (*R* crossed *V*). */
const MAGIC_EXACT = 0x53495301;

interface SisColumn {
  name: string;
  type: string;
  offset: number;
  size: number;
}

export interface SisSchema {
  SisDataSchema: [string, string][];
  SisBBoxInflation: number;
  SisResultLimit: number;
  SisCareTypes: Record<string, number>;
  SisCareTypeBits: Record<string, number>;
}

export interface SisResponse {
  rowCount: number;
  columns: SisColumn[];
  buffer: ArrayBuffer;
  /** True when served from inflated rectangle *I*; false when re-queried against exact viewport *V*. */
  inflated: boolean;
  providerId(row: number): bigint;
  careType(row: number): number;
  sortDistance(row: number): number;
  sortDailyOpen(row: number): number;
  sortDailyClose(row: number): number;
  sortAnnualOpening(row: number): number;
  sortOfsted(row: number): number;
  sortGraduates(row: number): number;
  sortTurnover(row: number): number;
  sortCostAll(row: number): number;
  sortCostUnder2(row: number): number;
  sortCostAge2(row: number): number;
  sortCostAge3to4(row: number): number;
  sortCostAge2plus(row: number): number;
  sortCostAge5plus(row: number): number;
  filterAcceptsFundedHours(row: number): boolean;
  filterEligibleMinMonths(row: number): number;
  filterEligibleMinYears(row: number): number;
  filterEligibleMaxYears(row: number): number;
  hasBbox(row: number): boolean;
  bboxSouth(row: number): number;
  bboxWest(row: number): number;
  bboxNorth(row: number): number;
  bboxEast(row: number): number;
  ladCode(row: number): number;
}

export function parseSisResponse(
  schema: SisSchema,
  buffer: ArrayBuffer,
): SisResponse {
  const view = new DataView(buffer);

  const magic = view.getUint32(0, true);
  if (magic !== MAGIC_INFLATED && magic !== MAGIC_EXACT)
    throw new Error(`Invalid SIS magic: 0x${magic.toString(16)}`);
  const inflated = magic === MAGIC_INFLATED;
  const rowCount = view.getUint32(4, true);

  const columns: SisColumn[] = [];
  let offset = 8;
  for (const [name, type] of schema.SisDataSchema) {
    const size = TYPE_SIZES[type];
    if (!size) throw new Error(`Unknown SIS type: ${type}`);
    columns.push({ name, type, offset, size });
    offset += size * rowCount;
  }

  const offsets: Record<string, number> = Object.fromEntries(
    columns.map((c) => [c.name, c.offset]),
  );

  const readInt64 = (row: number, o: number) =>
    view.getBigInt64(o + row * 8, true);
  const readInt32 = (row: number, o: number) =>
    view.getInt32(o + row * 4, true);
  const readInt8 = (row: number, o: number) => view.getInt8(o + row);
  const readUint8 = (row: number, o: number) => view.getUint8(o + row);
  const readFloat32 = (row: number, o: number) =>
    view.getFloat32(o + row * 4, true);

  return {
    rowCount,
    columns,
    buffer,
    inflated,
    providerId: (row) => readInt64(row, offsets.provider_id),
    careType: (row) => readInt8(row, offsets.care_type),
    sortDistance: (row) => readFloat32(row, offsets.sort_distance),
    sortDailyOpen: (row) => readFloat32(row, offsets.sort_daily_open),
    sortDailyClose: (row) => readFloat32(row, offsets.sort_daily_close),
    sortAnnualOpening: (row) => readInt8(row, offsets.sort_annual_opening),
    sortOfsted: (row) => readFloat32(row, offsets.sort_ofsted),
    sortGraduates: (row) => readFloat32(row, offsets.sort_graduates),
    sortTurnover: (row) => readFloat32(row, offsets.sort_turnover),
    sortCostAll: (row) => readFloat32(row, offsets.sort_cost_all),
    sortCostUnder2: (row) => readFloat32(row, offsets.sort_cost_under2),
    sortCostAge2: (row) => readFloat32(row, offsets.sort_cost_age2),
    sortCostAge3to4: (row) => readFloat32(row, offsets.sort_cost_age3to4),
    sortCostAge2plus: (row) => readFloat32(row, offsets.sort_cost_age2plus),
    sortCostAge5plus: (row) => readFloat32(row, offsets.sort_cost_age5plus),
    filterAcceptsFundedHours: (row) =>
      readUint8(row, offsets.filter_accepts_funded_hours) === 1,
    filterEligibleMinMonths: (row) =>
      readInt8(row, offsets.filter_eligible_min_months),
    filterEligibleMinYears: (row) =>
      readInt8(row, offsets.filter_eligible_min_years),
    filterEligibleMaxYears: (row) =>
      readInt8(row, offsets.filter_eligible_max_years),
    hasBbox: (row) => !isNaN(readFloat32(row, offsets.bbox_south)),
    bboxSouth: (row) => readFloat32(row, offsets.bbox_south),
    bboxWest: (row) => readFloat32(row, offsets.bbox_west),
    bboxNorth: (row) => readFloat32(row, offsets.bbox_north),
    bboxEast: (row) => readFloat32(row, offsets.bbox_east),
    ladCode: (row) => readInt32(row, offsets.lad_code),
  };
}

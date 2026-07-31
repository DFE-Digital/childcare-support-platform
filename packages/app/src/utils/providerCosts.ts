import type { Provider, ProviderCareType } from "@/types/provider";
import type { CostDisplayMode } from "@/components/providers/ProviderFilters";

/** Standard full-time assumptions for deriving comparable costs */
const FULL_TIME_HOURS_PER_DAY = 10;
const FULL_TIME_DAYS_PER_WEEK = 5;
const WEEKS_PER_MONTH = 4.33;

/** Map a single child's age (in months) to matching fee band keys. */
export function getMatchingAgeBands(childAgeMonths: number): string[] {
  const bands: string[] = [];
  if (childAgeMonths < 24) bands.push("under2");
  if (childAgeMonths >= 24 && childAgeMonths < 36) bands.push("age2");
  if (childAgeMonths >= 24) bands.push("age2plus");
  if (childAgeMonths >= 36 && childAgeMonths < 60) bands.push("age3to4");
  return bands;
}

/** Union of matching fee band keys for multiple children. Empty input → empty output (no filter). */
export function getAgeBandsForChildren(childAgesMonths: number[]): string[] {
  if (childAgesMonths.length === 0) return [];
  const set = new Set<string>();
  for (const age of childAgesMonths) {
    for (const band of getMatchingAgeBands(age)) {
      set.add(band);
    }
  }
  return [...set];
}

/** Filter care types to only those whose eligibleAgeRange includes at least one
 *  of the given child ages. No children → no filtering. Care types without an
 *  eligibleAgeRange are kept (we can't determine ineligibility). */
function filterCareTypesByChildAges(
  careTypes: ProviderCareType[],
  childAgesMonths: number[],
): ProviderCareType[] {
  if (childAgesMonths.length === 0) return careTypes;
  return careTypes.filter((ct) => {
    const ar = ct.eligibleAgeRange;
    if (!ar) return true;
    const minMonths = ar.minMonths ?? (ar.minYears ?? 0) * 12;
    const maxMonths = ar.maxYears ? (ar.maxYears + 1) * 12 - 1 : 999;
    return childAgesMonths.some((age) => age >= minMonths && age <= maxMonths);
  });
}

/** Filter banded fee entries to only those matching the age band filter.
 *  Flat fees and empty filters pass through unchanged. */
function filterFeesByAgeBands(
  fees: ProviderCareType["fees"],
  ageBandFilter: string[],
): ProviderCareType["fees"] {
  if (ageBandFilter.length === 0) return fees;
  if (isFlatFee(fees)) return fees;
  const filtered: Record<string, unknown> = {};
  for (const [band, value] of Object.entries(fees)) {
    if (ageBandFilter.includes(band)) {
      filtered[band] = value;
    }
  }
  return filtered as ProviderCareType["fees"];
}

interface CostRange {
  min: number;
  max: number;
}

export function getHourlyRates(
  ct: ProviderCareType,
  ageBandFilter: string[] = [],
): number[] {
  const rates: number[] = [];
  const fees = filterFeesByAgeBands(ct.fees, ageBandFilter);

  if (isFlatFee(fees)) {
    const f = fees as unknown as Record<string, number>;
    if (f.perHour != null && f.perHour > 0) {
      rates.push(f.perHour);
    } else if (f.perSession != null && f.perSession > 0) {
      const sessionHours = estimateSessionHours(ct);
      if (sessionHours > 0) rates.push(f.perSession / sessionHours);
    } else if (f.perDay != null && f.perDay > 0) {
      const dayHours = estimateDayHours(ct);
      if (dayHours > 0) rates.push(f.perDay / dayHours);
    }
    return rates;
  }

  for (const band of Object.values(fees)) {
    const f = band as Record<string, number>;

    if (f.perHour != null) {
      rates.push(f.perHour);
    } else if (f.fullDay != null && ct.sessionHours?.fullDay) {
      rates.push(f.fullDay / ct.sessionHours.fullDay);
    } else if (f.morningSession != null && ct.sessionHours?.morning) {
      rates.push(f.morningSession / ct.sessionHours.morning);
    } else if (f.afternoonSession != null && ct.sessionHours?.afternoon) {
      rates.push(f.afternoonSession / ct.sessionHours.afternoon);
    } else if (f.perSession != null) {
      const sessionHours = estimateSessionHours(ct);
      if (sessionHours > 0) rates.push(f.perSession / sessionHours);
    } else if (f.perDay != null) {
      const dayHours = estimateDayHours(ct);
      if (dayHours > 0) rates.push(f.perDay / dayHours);
    }
  }

  return rates;
}

function getLongestSpanHours(
  entries: { open: string; close: string }[],
): number {
  let best = 0;
  for (const e of entries) {
    const h = hoursFromRange(e.open, e.close);
    if (h > best) best = h;
  }
  return best;
}

function estimateSessionHours(ct: ProviderCareType): number {
  if (!ct.openingHours?.length) return 0;
  const total = getLongestSpanHours(ct.openingHours);
  // Breakfast clubs and after school clubs are partial day
  if (ct.type === "breakfast_club") return Math.min(total, 1.5);
  if (ct.type === "after_school_club") return Math.min(total, 3);
  return total;
}

function estimateDayHours(ct: ProviderCareType): number {
  if (!ct.openingHours?.length) return FULL_TIME_HOURS_PER_DAY;
  return getLongestSpanHours(ct.openingHours);
}

function hoursFromRange(open: string, close: string): number {
  const [oh, om] = open.split(":").map(Number);
  const [ch, cm] = close.split(":").map(Number);
  return ch + cm / 60 - (oh + om / 60);
}

export function additionalChargesPerHour(ct: ProviderCareType): number {
  const dayHours = estimateDayHours(ct);
  const sessionHours = estimateSessionHours(ct) || dayHours;
  let total = 0;
  for (const c of ct.additionalCharges) {
    if (c.cost <= 0) continue;
    if (c.unit === "per day") {
      total += c.cost / dayHours;
    } else if (c.unit === "per week") {
      total += c.cost / (dayHours * FULL_TIME_DAYS_PER_WEEK);
    } else if (c.unit === "per session") {
      total += c.cost / sessionHours;
    }
  }
  return total;
}

function additionalChargesPerMonth(ct: ProviderCareType): number {
  const dayHours = estimateDayHours(ct);
  const sessionHours = estimateSessionHours(ct) || dayHours;
  let total = 0;
  for (const c of ct.additionalCharges) {
    if (c.cost <= 0) continue;
    if (c.unit === "per day") {
      total += c.cost * FULL_TIME_DAYS_PER_WEEK * WEEKS_PER_MONTH;
    } else if (c.unit === "per week") {
      total += c.cost * WEEKS_PER_MONTH;
    } else if (c.unit === "per session") {
      total +=
        c.cost *
        (dayHours / sessionHours) *
        FULL_TIME_DAYS_PER_WEEK *
        WEEKS_PER_MONTH;
    }
  }
  return total;
}

function getRange(values: number[]): CostRange | null {
  if (values.length === 0) return null;
  return { min: Math.min(...values), max: Math.max(...values) };
}

function formatCurrency(value: number): string {
  return value < 10 ? `£${value.toFixed(2)}` : `£${Math.round(value)}`;
}

function formatRange(range: CostRange, suffix: string): string {
  if (Math.abs(range.min - range.max) < 0.01) {
    return `${formatCurrency(range.min)}${suffix}`;
  }
  return `${formatCurrency(range.min)} to ${formatCurrency(range.max)}${suffix}`;
}

export interface DetailedCostLine {
  label: string;
  value: string;
}

export interface DetailedCostTableRow {
  label: string;
  values: (string | null)[];
}

export interface DetailedCostTable {
  columns: string[];
  rows: DetailedCostTableRow[];
}

export interface DetailedCostExtra {
  label: string;
  value: string;
  description?: string;
}

export interface FeeRow {
  careType: string;
  age: string;
  period: string;
  cost: string;
}

export interface ProviderCostDisplay {
  summary: string;
  detailed?: DetailedCostLine[];
  table?: DetailedCostTable;
  feeRows?: FeeRow[];
  extras?: DetailedCostExtra[];
}

export function getProviderCostDisplay(
  provider: Provider,
  mode: CostDisplayMode,
  includeAdditional: boolean,
  typeFilter: string[] = [],
  childAgesMonths: number[] = [],
): ProviderCostDisplay {
  // Detailed mode always shows the full fee schedule — no filtering
  if (mode === "detailed") {
    return getDetailedCostDisplay(provider);
  }

  const ageBandFilter = getAgeBandsForChildren(childAgesMonths);

  let careTypes = provider.careTypes;
  if (typeFilter.length > 0) {
    careTypes = careTypes.filter((ct) => typeFilter.includes(ct.type));
  }
  careTypes = filterCareTypesByChildAges(careTypes, childAgesMonths);

  const filtered = { ...provider, careTypes };

  if (filtered.careTypes.length === 0) {
    return { summary: "Contact for fees" };
  }

  if (mode === "hourly") {
    return getHourlyCostDisplay(filtered, includeAdditional, ageBandFilter);
  }
  return getMonthlyCostDisplay(filtered, includeAdditional, ageBandFilter);
}

function getHourlyCostDisplay(
  provider: Provider,
  includeAdditional: boolean,
  ageBandFilter: string[] = [],
): ProviderCostDisplay {
  const allRates: number[] = [];

  for (const ct of provider.careTypes) {
    const rates = getHourlyRates(ct, ageBandFilter);
    const extras = includeAdditional ? additionalChargesPerHour(ct) : 0;
    for (const r of rates) {
      allRates.push(r + extras);
    }
  }

  const range = getRange(allRates);
  if (!range) return { summary: "Contact for fees" };
  return { summary: formatRange(range, " per\u00A0hour") };
}

function getMonthlyCostDisplay(
  provider: Provider,
  includeAdditional: boolean,
  ageBandFilter: string[] = [],
): ProviderCostDisplay {
  const allMonthlies: number[] = [];

  for (const ct of provider.careTypes) {
    const rates = getHourlyRates(ct, ageBandFilter);
    const monthlyBase =
      FULL_TIME_HOURS_PER_DAY * FULL_TIME_DAYS_PER_WEEK * WEEKS_PER_MONTH;
    const extras = includeAdditional ? additionalChargesPerMonth(ct) : 0;

    for (const r of rates) {
      allMonthlies.push(r * monthlyBase + extras);
    }
  }

  const range = getRange(allMonthlies);
  if (!range) return { summary: "Contact for fees" };
  return { summary: formatRange(range, " per\u00A0month") };
}

function isFlatFee(fees: ProviderCareType["fees"]): boolean {
  return Object.values(fees).some((v) => typeof v === "number");
}

function hasSessionBasedFees(ct: ProviderCareType): boolean {
  if (isFlatFee(ct.fees)) return false;
  return Object.values(ct.fees).some((band) => {
    const f = band as Record<string, number>;
    return (
      f.morningSession != null ||
      f.afternoonSession != null ||
      f.fullDay != null
    );
  });
}

function countSessionColumns(ct: ProviderCareType): number {
  const has = { am: false, pm: false, full: false };
  for (const band of Object.values(ct.fees)) {
    const f = band as Record<string, number>;
    if (f.morningSession != null) has.am = true;
    if (f.afternoonSession != null) has.pm = true;
    if (f.fullDay != null) has.full = true;
  }
  return [has.am, has.pm, has.full].filter(Boolean).length;
}

function buildSessionTable(
  ct: ProviderCareType,
  ageBandFilter: string[] = [],
): DetailedCostTable | null {
  if (!hasSessionBasedFees(ct) || countSessionColumns(ct) < 2) return null;

  const filteredFees = filterFeesByAgeBands(ct.fees, ageBandFilter);

  // Determine which columns exist
  const colFlags = { am: false, pm: false, full: false };
  for (const band of Object.values(filteredFees)) {
    const f = band as Record<string, number>;
    if (f.morningSession != null) colFlags.am = true;
    if (f.afternoonSession != null) colFlags.pm = true;
    if (f.fullDay != null) colFlags.full = true;
  }

  const columns: string[] = [];
  if (colFlags.am) columns.push("AM");
  if (colFlags.pm) columns.push("PM");
  if (colFlags.full) columns.push("Full day");

  const rows: { label: string; values: (string | null)[] }[] = [];
  for (const [band, fees] of Object.entries(filteredFees)) {
    const f = fees as Record<string, number>;
    const values: (string | null)[] = [];
    if (colFlags.am)
      values.push(
        f.morningSession != null ? `£${f.morningSession.toFixed(2)}` : null,
      );
    if (colFlags.pm)
      values.push(
        f.afternoonSession != null ? `£${f.afternoonSession.toFixed(2)}` : null,
      );
    if (colFlags.full)
      values.push(f.fullDay != null ? `£${f.fullDay.toFixed(2)}` : null);
    rows.push({ label: ageBandLabel(band), values });
  }

  return { columns, rows };
}

function getDetailedCostDisplay(
  provider: Provider,
  ageBandFilter: string[] = [],
): ProviderCostDisplay {
  const extras: DetailedCostExtra[] = [];
  const multiType = provider.careTypes.length > 1;

  for (const ct of provider.careTypes) {
    for (const charge of ct.additionalCharges) {
      if (charge.cost > 0) {
        extras.push({
          label: multiType
            ? `${careTypeShortLabel(ct.type)} · ${charge.item}`
            : charge.item,
          value: `£${charge.cost.toFixed(2)} ${charge.unit}`,
          description: charge.description,
        });
      }
    }
  }

  if (multiType) {
    return buildMultiTypeFeeDisplay(provider, extras, ageBandFilter);
  }
  return buildSingleTypeFeeDisplay(provider, extras, ageBandFilter);
}

function buildMultiTypeFeeDisplay(
  provider: Provider,
  extras: DetailedCostExtra[],
  ageBandFilter: string[] = [],
): ProviderCostDisplay {
  const feeRows: FeeRow[] = [];

  for (const ct of provider.careTypes) {
    const ctLabel = careTypeShortLabel(ct.type);
    const filteredFees = filterFeesByAgeBands(ct.fees, ageBandFilter);

    if (isFlatFee(filteredFees)) {
      const f = filteredFees as unknown as Record<string, number>;
      if (f.perHour != null) {
        feeRows.push({
          careType: ctLabel,
          age: "",
          period: "Per hour",
          cost: f.perHour > 0 ? `£${f.perHour.toFixed(2)}` : "Free",
        });
      }
      if (f.perSession != null) {
        feeRows.push({
          careType: ctLabel,
          age: "",
          period: "Per session",
          cost: f.perSession > 0 ? `£${f.perSession.toFixed(2)}` : "Free",
        });
      }
      if (f.perDay != null) {
        feeRows.push({
          careType: ctLabel,
          age: "",
          period: "Per day",
          cost: f.perDay > 0 ? `£${f.perDay.toFixed(2)}` : "Free",
        });
      }
    } else {
      for (const [band, fees] of Object.entries(filteredFees)) {
        const f = fees as Record<string, number>;
        const bandLabel = ageBandLabel(band);

        if (f.perHour != null) {
          feeRows.push({
            careType: ctLabel,
            age: bandLabel,
            period: "Per hour",
            cost: `£${f.perHour.toFixed(2)}`,
          });
        }
        if (f.morningSession != null) {
          feeRows.push({
            careType: ctLabel,
            age: bandLabel,
            period: "AM",
            cost: `£${f.morningSession.toFixed(2)}`,
          });
        }
        if (f.afternoonSession != null) {
          feeRows.push({
            careType: ctLabel,
            age: bandLabel,
            period: "PM",
            cost: `£${f.afternoonSession.toFixed(2)}`,
          });
        }
        if (f.fullDay != null) {
          feeRows.push({
            careType: ctLabel,
            age: bandLabel,
            period: "Full day",
            cost: `£${f.fullDay.toFixed(2)}`,
          });
        }
        if (f.perSession != null) {
          feeRows.push({
            careType: ctLabel,
            age: bandLabel,
            period: "Per session",
            cost: `£${f.perSession.toFixed(2)}`,
          });
        }
        if (f.perDay != null) {
          feeRows.push({
            careType: ctLabel,
            age: bandLabel,
            period: "Per day",
            cost: `£${f.perDay.toFixed(2)}`,
          });
        }
      }
    }
  }

  let summary = "Contact for fees";
  if (feeRows.length > 0) {
    summary = feeRows[0].cost;
  }

  return {
    summary,
    feeRows: feeRows.length > 0 ? feeRows : undefined,
    extras: extras.length > 0 ? extras : undefined,
  };
}

function buildSingleTypeFeeDisplay(
  provider: Provider,
  extras: DetailedCostExtra[],
  ageBandFilter: string[] = [],
): ProviderCostDisplay {
  const ct = provider.careTypes[0];
  if (!ct) {
    return {
      summary: "Contact for fees",
      extras: extras.length > 0 ? extras : undefined,
    };
  }

  // Session-based fees with at least 2 session columns → pivoted table
  if (hasSessionBasedFees(ct) && countSessionColumns(ct) >= 2) {
    const table = buildSessionTable(ct, ageBandFilter);
    let summary = "Contact for fees";
    if (table && table.rows.length > 0) {
      const firstVal = table.rows[0]?.values.find((v) => v != null);
      if (firstVal) summary = firstVal;
    }
    return {
      summary,
      table: table || undefined,
      extras: extras.length > 0 ? extras : undefined,
    };
  }

  const filteredFees = filterFeesByAgeBands(ct.fees, ageBandFilter);
  const lines: DetailedCostLine[] = [];

  if (isFlatFee(filteredFees)) {
    const f = filteredFees as unknown as Record<string, number>;
    if (f.perHour != null && f.perHour > 0) {
      lines.push({ label: "Per hour", value: `£${f.perHour.toFixed(2)}` });
    }
    if (f.perSession != null && f.perSession > 0) {
      lines.push({
        label: "Per session",
        value: `£${f.perSession.toFixed(2)}`,
      });
    } else if (f.perSession === 0) {
      lines.push({ label: "Per session", value: "Free" });
    }
    if (f.perDay != null && f.perDay > 0) {
      lines.push({ label: "Per day", value: `£${f.perDay.toFixed(2)}` });
    }
  } else {
    for (const [band, fees] of Object.entries(filteredFees)) {
      const f = fees as Record<string, number>;
      const bandLabel = ageBandLabel(band);

      if (f.perHour != null) {
        lines.push({
          label: bandLabel,
          value: `£${f.perHour.toFixed(2)} per\u00A0hour`,
        });
      }
      if (f.morningSession != null) {
        lines.push({
          label: `${bandLabel} AM`,
          value: `£${f.morningSession.toFixed(2)}`,
        });
      }
      if (
        f.afternoonSession != null &&
        f.morningSession !== f.afternoonSession
      ) {
        lines.push({
          label: `${bandLabel} PM`,
          value: `£${f.afternoonSession.toFixed(2)}`,
        });
      }
      if (f.fullDay != null) {
        lines.push({
          label: `${bandLabel} full day`,
          value: `£${f.fullDay.toFixed(2)}`,
        });
      }
      if (f.perSession != null) {
        lines.push({
          label: bandLabel,
          value: `£${f.perSession.toFixed(2)} per\u00A0session`,
        });
      }
      if (f.perDay != null) {
        lines.push({
          label: bandLabel,
          value: `£${f.perDay.toFixed(2)} per\u00A0day`,
        });
      }
    }
  }

  let summary = "Contact for fees";
  if (lines.length > 0) summary = lines[0].value;

  return {
    summary,
    detailed: lines.length > 0 ? lines : undefined,
    extras: extras.length > 0 ? extras : undefined,
  };
}

function ageBandLabel(band: string): string {
  const labels: Record<string, string> = {
    under2: "Under 2",
    age2: "Age 2",
    age2plus: "Age 2+",
    age3to4: "Age 3 to 4",
    perSession: "",
    perDay: "",
  };
  return labels[band] || band;
}

function careTypeShortLabel(type: string): string {
  const labels: Record<string, string> = {
    private_nursery: "Nursery",
    school_based_nursery: "Nursery",
    childminder: "Childminder",
    breakfast_club: "Breakfast",
    free_breakfast_club: "Breakfast club",
    after_school_club: "After school",
    holiday_club: "Holiday",
  };
  return labels[type] || type;
}

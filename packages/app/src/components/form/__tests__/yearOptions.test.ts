import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { yearOptions } from "../steps/yearOptions";

describe("yearOptions", () => {
  beforeEach(() => {
    // Fix the date to 15 March 2026
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 2, 15));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns plain year labels when birthMonth is null", () => {
    const opts = yearOptions(null);
    expect(opts[0]).toEqual({ value: "2026", label: "2026" });
    expect(opts[1]).toEqual({ value: "2025", label: "2025" });
    expect(opts[opts.length - 1]).toEqual({ value: "2008", label: "2008" });
  });

  it("returns 19 year options when birthMonth is null", () => {
    const opts = yearOptions(null);
    expect(opts).toHaveLength(19);
  });

  it("shows age labels when birthMonth is provided", () => {
    // Date is March 2026, birthMonth is January (1)
    const opts = yearOptions(1);
    // 2026 Jan → 2 months old
    expect(opts[0]).toEqual({ value: "2026", label: "2026 (2 months)" });
    // 2025 Jan → 1 year 2 months
    expect(opts[1]).toEqual({ value: "2025", label: "2025 (1 yr 2 mos)" });
    // 2024 Jan → 2 years 2 months
    expect(opts[2]).toEqual({ value: "2024", label: "2024 (2 yrs 2 mos)" });
  });

  it("shows 0 months for a child born in the current month and year", () => {
    // Date is March 2026, birthMonth is March (3)
    const opts = yearOptions(3);
    expect(opts[0]).toEqual({ value: "2026", label: "2026 (0 months)" });
  });

  it("handles exact year boundaries correctly", () => {
    // Date is March 2026, birthMonth is March (3)
    const opts = yearOptions(3);
    // 2025 March → exactly 1 year
    expect(opts[1]).toEqual({ value: "2025", label: "2025 (1 yr)" });
    // 2023 March → exactly 3 years
    expect(opts[3]).toEqual({ value: "2023", label: "2023 (3 yrs)" });
  });

  it("omits years label when age is less than 1 year", () => {
    // Date is March 2026, birthMonth is June (6)
    // 2026 is filtered out (June 2026 is future), so first option is 2025
    const opts = yearOptions(6);
    // 2025 June → 9 months (no years component)
    expect(opts[0]).toEqual({ value: "2025", label: "2025 (9 months)" });
  });

  it("handles singular year correctly", () => {
    // Date is March 2026, birthMonth is March (3)
    const opts = yearOptions(3);
    // 2025 March → 1 yr (singular)
    expect(opts[1].label).toBe("2025 (1 yr)");
    // 2024 March → 2 yrs (plural)
    expect(opts[2].label).toBe("2024 (2 yrs)");
  });

  it("handles singular month correctly", () => {
    // Date is March 2026, birthMonth is February (2)
    const opts = yearOptions(2);
    // 2026 Feb → 1 month
    expect(opts[0].label).toBe("2026 (1 month)");
  });

  it("excludes future year/month combinations", () => {
    // Date is March 2026, birthMonth is December (12)
    const opts = yearOptions(12);
    // 2026 December is in the future → excluded
    expect(opts[0]).toEqual({ value: "2025", label: "2025 (3 months)" });
    // No 2026 option at all
    expect(opts.find((o) => o.value === "2026")).toBeUndefined();
  });

  it("has fewer options when future months are filtered out", () => {
    // birthMonth null → 19 options (2026..2008)
    const allOpts = yearOptions(null);
    // birthMonth December → 2026 is excluded, so 18 options (2025..2008)
    const decOpts = yearOptions(12);
    expect(decOpts).toHaveLength(allOpts.length - 1);
  });

  it("keeps current year when birth month is not future", () => {
    // Date is March 2026, birthMonth is January (1) → Jan 2026 is in the past
    const opts = yearOptions(1);
    expect(opts[0].value).toBe("2026");
  });

  it("keeps current year when birth month is current month", () => {
    // Date is March 2026, birthMonth is March (3) → March 2026 is now
    const opts = yearOptions(3);
    expect(opts[0].value).toBe("2026");
  });
});

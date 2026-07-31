import { describe, it, expect, vi, afterEach } from "vitest";
import { getChildAgeMonths } from "../childAge";

describe("getChildAgeMonths", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 0 for a child born this month/year", () => {
    vi.useFakeTimers({ now: new Date(2026, 2, 15) }); // March 2026 (month index 2)
    expect(getChildAgeMonths(3, 2026)).toBe(0);
  });

  it("returns 6 for a child born 6 months ago", () => {
    vi.useFakeTimers({ now: new Date(2026, 2, 15) }); // March 2026
    expect(getChildAgeMonths(9, 2025)).toBe(6);
  });

  it("returns 24 for a child born 2 years ago", () => {
    vi.useFakeTimers({ now: new Date(2026, 2, 15) }); // March 2026
    expect(getChildAgeMonths(3, 2024)).toBe(24);
  });

  it("handles December-to-January rollover correctly", () => {
    vi.useFakeTimers({ now: new Date(2026, 0, 15) }); // January 2026 (month index 0)
    // Born December 2025: (2026 - 2025)*12 + (1 - 12) = 12 - 11 = 1
    expect(getChildAgeMonths(12, 2025)).toBe(1);
  });

  it("handles birth month in future of current year as negative", () => {
    vi.useFakeTimers({ now: new Date(2026, 0, 15) }); // January 2026
    // Born March 2026: (2026 - 2026)*12 + (1 - 3) = -2
    expect(getChildAgeMonths(3, 2026)).toBe(-2);
  });
});

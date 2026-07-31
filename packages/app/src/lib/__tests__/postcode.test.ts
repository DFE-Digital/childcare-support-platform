import { describe, it, expect } from "vitest";
import { normalisePostcode, isPostcodeFormatValid } from "../postcode";

describe("normalisePostcode", () => {
  it("normalises lowercase no-space input", () => {
    expect(normalisePostcode("sw1a1aa")).toBe("SW1A 1AA");
  });

  it("returns already-normalised input unchanged", () => {
    expect(normalisePostcode("SW1A 1AA")).toBe("SW1A 1AA");
  });

  it("does not insert space for short strings", () => {
    expect(normalisePostcode("SW1")).toBe("SW1");
  });

  it("returns empty string for empty input", () => {
    expect(normalisePostcode("")).toBe("");
  });

  it("strips leading/trailing whitespace", () => {
    expect(normalisePostcode("  sw1a 1aa  ")).toBe("SW1A 1AA");
  });

  it("normalises multiple internal spaces", () => {
    expect(normalisePostcode("SW1A   1AA")).toBe("SW1A 1AA");
  });

  it("handles spaceless GU format", () => {
    expect(normalisePostcode("gu151ds")).toBe("GU15 1DS");
  });
});

describe("isPostcodeFormatValid (prefix mode)", () => {
  it.each([
    "S",
    "SW",
    "SW1",
    "SW1A",
    "SW1A 1",
    "SW1A 1A",
    "SW1A 1AA",
    "M1",
    "M1 1",
    "EC1A",
    "e1",
  ])("accepts valid spaced prefix %s", (input) => {
    expect(isPostcodeFormatValid(input)).toBe(true);
  });

  it.each(["GU151", "GU151D", "GU151DS", "SW1A1", "SW1A1AA", "M11", "M11AE"])(
    "accepts valid spaceless prefix %s",
    (input) => {
      expect(isPostcodeFormatValid(input)).toBe(true);
    },
  );

  it.each(["1", "1S", "AAA", "SW1A A", "SW1A 1AAA", "SW1AA1"])(
    "rejects invalid prefix %s",
    (input) => {
      expect(isPostcodeFormatValid(input)).toBe(false);
    },
  );

  it("rejects empty string", () => {
    expect(isPostcodeFormatValid("")).toBe(false);
  });
});

describe("isPostcodeFormatValid (complete mode)", () => {
  it.each([
    "SW1A 1AA",
    "SW1A1AA",
    "M1 1AE",
    "M11AE",
    "EC1A 1BB",
    "GU15 1DS",
    "GU151DS",
    "e1w 1ab",
  ])("accepts valid complete postcode %s", (input) => {
    expect(isPostcodeFormatValid(input, true)).toBe(true);
  });

  it.each(["SW1A", "SW1A 1", "1SW 1AA", "AAAA BBB", "XXXX", ""])(
    "rejects invalid/incomplete postcode %s",
    (input) => {
      expect(isPostcodeFormatValid(input, true)).toBe(false);
    },
  );
});

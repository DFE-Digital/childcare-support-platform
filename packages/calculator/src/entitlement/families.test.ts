import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { LocalStorageData } from "../types/family.js";
import type { Scheme, SchemesData } from "../types/scheme.js";
import { calculateEntitlements } from "./calculate.js";
import { validateEntitlementResult } from "../validators/entitlement.js";

const dataDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../app/src/data",
);
const familiesDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../__fixtures__/families",
);
const schemesData: SchemesData = JSON.parse(
  readFileSync(join(dataDir, "schemes.json"), "utf-8"),
);
const schemes: Scheme[] = schemesData.schemes;

const REF = new Date(2026, 1, 22); // 2026-02-22

function loadFamily(filename: string): LocalStorageData {
  const raw = JSON.parse(readFileSync(join(familiesDir, filename), "utf-8"));
  return raw.localStorage;
}

function getScheme(
  result: ReturnType<typeof calculateEntitlements>,
  childIndex: number,
  schemeId: string,
) {
  return result.children[childIndex].schemes.find(
    (s) => s.schemeId === schemeId,
  );
}

const familyFiles = readdirSync(familiesDir).filter((f) => f.endsWith(".json"));

describe("family fixture integration", () => {
  it.each(familyFiles)("%s produces valid entitlement output", (filename) => {
    const data = loadFamily(filename);
    const result = calculateEntitlements(data, schemes, REF);
    const validation = validateEntitlementResult(result);
    expect(validation.errors).toEqual([]);
    expect(validation.valid).toBe(true);
  });

  describe("thomas-and-emily", () => {
    const data = loadFamily("thomas-and-emily.json");
    const result = calculateEntitlements(data, schemes, REF);

    // Thomas (born 2024-03) → ~23 months
    it("Thomas: eligible for 30h, TFC", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        true,
      );
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    // Emily (born 2019-09) → ~6yo, school age
    it("Emily: eligible for TFC, wraparound, breakfast clubs", () => {
      expect(getScheme(result, 1, "tax_free_childcare")?.eligible).toBe(true);
      expect(getScheme(result, 1, "wraparound_childcare")?.eligible).toBe(true);
      expect(getScheme(result, 1, "free_breakfast_clubs")?.eligible).toBe(true);
    });

    it("Emily: ineligible for funded hours (school age)", () => {
      expect(getScheme(result, 1, "30_hours_working_families")?.eligible).toBe(
        false,
      );
      expect(getScheme(result, 1, "15_hours_universal")?.eligible).toBe(false);
    });
  });

  describe("priya", () => {
    const data = loadFamily("priya.json");
    const result = calculateEntitlements(data, schemes, REF);

    // Amir (born 2024-02) → 24mo at ref date (age 2)
    it("Amir: eligible for 15h 2yo (UC low income)", () => {
      expect(getScheme(result, 0, "15_hours_2_year_olds")?.eligible).toBe(true);
    });

    it("Amir: eligible for UC childcare", () => {
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        true,
      );
    });

    // Zara (born 2018-05) → ~7yo
    it("Zara: eligible for UC childcare, wraparound, breakfast clubs", () => {
      expect(getScheme(result, 1, "universal_credit_childcare")?.eligible).toBe(
        true,
      );
      expect(getScheme(result, 1, "wraparound_childcare")?.eligible).toBe(true);
      expect(getScheme(result, 1, "free_breakfast_clubs")?.eligible).toBe(true);
    });
  });

  describe("nguyens", () => {
    const data = loadFamily("nguyens.json");
    const result = calculateEntitlements(data, schemes, REF);

    // Lily (born 2022-06) → ~3yo, Carer's Allowance exception
    it("Lily: eligible for 30h via Carer's Allowance exception", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        true,
      );
    });

    it("Lily: eligible for 15h universal", () => {
      expect(getScheme(result, 0, "15_hours_universal")?.eligible).toBe(true);
    });

    it("Lily: eligible for TFC", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });
  });

  describe("clarkes", () => {
    const data = loadFamily("clarkes.json");
    const result = calculateEntitlements(data, schemes, REF);

    // Olivia (born 2022-11) → 3yo, but partner income >£100k
    it("Olivia: eligible for 15h universal", () => {
      expect(getScheme(result, 0, "15_hours_universal")?.eligible).toBe(true);
    });

    it("Olivia: ineligible for 30h (income >£100k)", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    it("Olivia: ineligible for TFC (income >£100k)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });

    // Jack (born 2017-07) → ~8yo
    it("Jack: eligible for wraparound and breakfast clubs", () => {
      expect(getScheme(result, 1, "wraparound_childcare")?.eligible).toBe(true);
      expect(getScheme(result, 1, "free_breakfast_clubs")?.eligible).toBe(true);
    });
  });

  describe("jade", () => {
    const data = loadFamily("jade.json");
    const result = calculateEntitlements(data, schemes, REF);

    // Alfie (born 2025-03) → ~11mo, apprentice
    it("Alfie: eligible for 30h (apprentice threshold)", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        true,
      );
    });

    it("Alfie: eligible for TFC", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });
  });

  describe("kaurs", () => {
    const data = loadFamily("kaurs.json");
    const result = calculateEntitlements(data, schemes, REF);

    // Rajan (born 2015-08, disabled) → ~10yo
    it("Rajan: eligible for TFC (extended to 16)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("Rajan: eligible for wraparound (extended to 18)", () => {
      expect(getScheme(result, 0, "wraparound_childcare")?.eligible).toBe(true);
    });

    it("Rajan: eligible for breakfast clubs", () => {
      expect(getScheme(result, 0, "free_breakfast_clubs")?.eligible).toBe(true);
    });

    // Maya (born 2022-01) → 4yo, pre-school
    it("Maya: eligible for 30h, 15h universal, TFC", () => {
      expect(getScheme(result, 1, "30_hours_working_families")?.eligible).toBe(
        true,
      );
      expect(getScheme(result, 1, "15_hours_universal")?.eligible).toBe(true);
      expect(getScheme(result, 1, "tax_free_childcare")?.eligible).toBe(true);
    });
  });

  describe("sam-and-alex", () => {
    const data = loadFamily("sam-and-alex.json");
    const result = calculateEntitlements(data, schemes, REF);

    // Freddie (born 2024-06) → ~20mo, partner not working
    it("Freddie: ineligible for 30h (partner not working)", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    it("Freddie: ineligible for TFC (partner not working)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });

    it("Freddie: ineligible for UC childcare (not on UC)", () => {
      expect(getScheme(result, 0, "universal_credit_childcare")?.eligible).toBe(
        false,
      );
    });
  });

  describe("brennans", () => {
    const data = loadFamily("brennans.json");
    const result = calculateEntitlements(data, schemes, REF);

    // Isla (born 2025-11) → 3mo, under 9 months
    it("Isla: eligible for TFC only", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("Isla: ineligible for 30h (under 9mo)", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });
  });

  describe("michelle", () => {
    const data = loadFamily("michelle.json");
    const result = calculateEntitlements(data, schemes, REF);

    // Connor (born 2023-09) → ~2yo, not working, has incomeSupportOrEquivalent
    it("Connor: eligible for 15h 2yo", () => {
      expect(getScheme(result, 0, "15_hours_2_year_olds")?.eligible).toBe(true);
    });
  });

  describe("patel-johnsons", () => {
    const data = loadFamily("patel-johnsons.json");
    const result = calculateEntitlements(data, schemes, REF);

    // Mia (born 2011-04) → ~14yo
    it("Mia: ineligible for TFC (over 11)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
    });

    it("Mia: eligible for wraparound (≤14)", () => {
      expect(getScheme(result, 0, "wraparound_childcare")?.eligible).toBe(true);
    });

    it("Mia: ineligible for breakfast clubs (over 11)", () => {
      expect(getScheme(result, 0, "free_breakfast_clubs")?.eligible).toBe(
        false,
      );
    });

    // Leo (born 2017-10) → ~8yo
    it("Leo: eligible for TFC, wraparound, breakfast clubs", () => {
      expect(getScheme(result, 1, "tax_free_childcare")?.eligible).toBe(true);
      expect(getScheme(result, 1, "wraparound_childcare")?.eligible).toBe(true);
      expect(getScheme(result, 1, "free_breakfast_clubs")?.eligible).toBe(true);
    });

    // Ava (born 2022-02) → 4yo, pre-school (born Feb, starts school Sep 2026)
    it("Ava: eligible for 30h, 15h universal, TFC", () => {
      expect(getScheme(result, 2, "30_hours_working_families")?.eligible).toBe(
        true,
      );
      expect(getScheme(result, 2, "15_hours_universal")?.eligible).toBe(true);
      expect(getScheme(result, 2, "tax_free_childcare")?.eligible).toBe(true);
    });

    // Noah (born 2025-08) → 6mo
    it("Noah: eligible for TFC only", () => {
      expect(getScheme(result, 3, "tax_free_childcare")?.eligible).toBe(true);
    });

    it("Noah: ineligible for 30h (under 9mo)", () => {
      expect(getScheme(result, 3, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });
  });

  describe("okafors", () => {
    const data = loadFamily("okafors.json");
    const result = calculateEntitlements(data, schemes, REF);

    // Amara (born 2023-06) → 2yo, NRPF income route confirmed
    it("Amara: eligible for 15h 2yo via NRPF income route", () => {
      const scheme = getScheme(result, 0, "15_hours_2_year_olds");
      expect(scheme?.eligible).toBe(true);
      expect(scheme?.reasons).toContainEqual(
        expect.stringContaining("NRPF route"),
      );
    });

    it("Amara: ineligible for TFC (no parent has public funds access)", () => {
      expect(getScheme(result, 0, "tax_free_childcare")?.eligible).toBe(false);
      expect(
        getScheme(result, 0, "tax_free_childcare")?.reasons,
      ).toContainEqual(expect.stringContaining("access to public funds"));
    });

    it("Amara: ineligible for 30h (NRPF)", () => {
      expect(getScheme(result, 0, "30_hours_working_families")?.eligible).toBe(
        false,
      );
    });

    // Chidera (born 2022-03) → ~3yo
    it("Chidera: eligible for 15h universal", () => {
      expect(getScheme(result, 1, "15_hours_universal")?.eligible).toBe(true);
    });

    it("Chidera: ineligible for TFC (no parent has public funds access)", () => {
      expect(getScheme(result, 1, "tax_free_childcare")?.eligible).toBe(false);
      expect(
        getScheme(result, 1, "tax_free_childcare")?.reasons,
      ).toContainEqual(expect.stringContaining("access to public funds"));
    });
  });
});

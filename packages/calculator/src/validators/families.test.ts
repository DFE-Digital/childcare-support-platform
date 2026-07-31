import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { LocalStorageData } from "../types/family.js";
import { validateLocalStorageData } from "./household.js";

const familiesDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../__fixtures__/families",
);

const familyFiles = readdirSync(familiesDir).filter((f) => f.endsWith(".json"));

describe("validate family fixture data", () => {
  it.each(familyFiles)("%s passes validation", (filename) => {
    const raw = JSON.parse(readFileSync(join(familiesDir, filename), "utf-8"));
    const data: LocalStorageData = raw.localStorage;
    const result = validateLocalStorageData(data);
    expect(result.errors).toEqual([]);
    expect(result.valid).toBe(true);
  });
});

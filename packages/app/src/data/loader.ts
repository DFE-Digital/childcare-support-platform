import type { Provider } from "@/types/provider";
import type { PostcodeAreaCosts } from "@/types/costs";
import type { SisSchema } from "./sisParser";
import { fetchWithRetry } from "./fetchWithRetry";

const BASE = import.meta.env.BASE_URL;

async function fetchJson<T>(path: string): Promise<T> {
  const url = BASE + path.replace(/^\//, "");
  return fetchWithRetry(async () => {
    const res = await fetch(url);
    if (!res.ok) {
      const err = new Error(`Failed to fetch ${url}: ${res.status}`);
      (err as Error & { status: number }).status = res.status;
      throw err;
    }
    const ct = res.headers.get("content-type") ?? "";
    if (!ct.includes("application/json")) {
      const err = new Error(
        `Expected JSON from ${url} but got ${ct || "no content-type"} (possible SPA fallback)`,
      );
      (err as Error & { status: number }).status = 404;
      throw err;
    }
    return res.json() as Promise<T>;
  });
}

export async function loadProvider(id: string): Promise<Provider> {
  const p = await fetchJson<Provider>(`/data/providers/${id}.json`);
  p.address ??= { line1: "", line2: "", city: "", postcode: "" };
  p.phone ??= "";
  p.email ??= "";
  p.website ??= "";
  p.careTypes ??= [];
  for (const ct of p.careTypes) {
    ct.fees ??= {} as Provider["careTypes"][number]["fees"];
    ct.additionalCharges ??= [];
  }
  return p;
}

export async function loadLaCosts(laCode: string): Promise<PostcodeAreaCosts> {
  return fetchJson<PostcodeAreaCosts>(
    `/data/lad/${encodeURIComponent(laCode)}.json`,
  );
}

export async function loadOutwardCodes(): Promise<string[]> {
  return fetchJson<string[]>("/data/outward.json");
}

export async function loadInwardCodes(
  outward: string,
): Promise<Record<string, unknown>> {
  return fetchJson("/data/inward/" + encodeURIComponent(outward) + ".json");
}

export async function loadSisSchema(): Promise<SisSchema> {
  const schema = await fetchJson<SisSchema>("/data/sis_schema.json");
  if (!Array.isArray(schema.SisDataSchema)) {
    throw new Error("Invalid SIS schema: missing SisDataSchema array");
  }
  return schema;
}

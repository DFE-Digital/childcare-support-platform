import type { FilterSpecification } from "maplibre-gl";

export const CARE_TYPE_TILE_KEYS: Record<string, string> = {
  private_nursery: "ct_pn",
  school_based_nursery: "ct_sn",
  childminder: "ct_cm",
  breakfast_club: "ct_bc",
  free_breakfast_club: "ct_fb",
  after_school_club: "ct_ac",
  holiday_club: "ct_hc",
};

export function buildTileFilter(
  selectedTypes: string[],
  fundedHoursOnly: boolean,
  childAgesMonths: number[],
): FilterSpecification {
  const conditions: unknown[] = ["all"];

  if (selectedTypes.length > 0) {
    const typeConditions: unknown[] = ["any"];
    for (const t of selectedTypes) {
      const key = CARE_TYPE_TILE_KEYS[t];
      if (key) typeConditions.push(["==", ["get", key], 1]);
      if (t === "breakfast_club") {
        typeConditions.push(["==", ["get", "ct_fb"], 1]);
      }
    }
    if (typeConditions.length > 1) conditions.push(typeConditions);
  }

  if (fundedHoursOnly) {
    conditions.push(["==", ["get", "fh"], 1]);
  }

  if (childAgesMonths.length > 0) {
    const youngest = Math.min(...childAgesMonths);
    const oldest = Math.max(...childAgesMonths);
    conditions.push([
      "any",
      ["!", ["has", "age_lo"]],
      ["<=", ["get", "age_lo"], oldest],
    ]);
    conditions.push([
      "any",
      ["!", ["has", "age_hi"]],
      [">=", ["get", "age_hi"], youngest],
    ]);
  }

  return (conditions.length > 1 ? conditions : ["all"]) as FilterSpecification;
}

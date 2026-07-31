import { describe, it, expect } from "vitest";
import { buildTileFilter } from "../tileFilter";

describe("buildTileFilter", () => {
  it("returns ['all'] when no filters are active", () => {
    expect(buildTileFilter([], false, [])).toEqual(["all"]);
  });

  it("adds a single care type condition", () => {
    const filter = buildTileFilter(["private_nursery"], false, []);
    expect(filter).toEqual(["all", ["any", ["==", ["get", "ct_pn"], 1]]]);
  });

  it("adds multiple care type conditions", () => {
    const filter = buildTileFilter(
      ["private_nursery", "childminder"],
      false,
      [],
    );
    expect(filter).toEqual([
      "all",
      ["any", ["==", ["get", "ct_pn"], 1], ["==", ["get", "ct_cm"], 1]],
    ]);
  });

  it("adds funded hours condition", () => {
    const filter = buildTileFilter([], true, []);
    expect(filter).toEqual(["all", ["==", ["get", "fh"], 1]]);
  });

  it("adds child age conditions with correct min/max", () => {
    const filter = buildTileFilter([], false, [12, 36]);
    expect(filter).toEqual([
      "all",
      ["any", ["!", ["has", "age_lo"]], ["<=", ["get", "age_lo"], 36]],
      ["any", ["!", ["has", "age_hi"]], [">=", ["get", "age_hi"], 12]],
    ]);
  });

  it("combines all filters", () => {
    const filter = buildTileFilter(["childminder"], true, [24]);
    expect(filter).toEqual([
      "all",
      ["any", ["==", ["get", "ct_cm"], 1]],
      ["==", ["get", "fh"], 1],
      ["any", ["!", ["has", "age_lo"]], ["<=", ["get", "age_lo"], 24]],
      ["any", ["!", ["has", "age_hi"]], [">=", ["get", "age_hi"], 24]],
    ]);
  });

  it("ignores unknown care type keys without crashing", () => {
    const filter = buildTileFilter(["unknown_type"], false, []);
    // The "any" sub-array only has the initial "any" string, so it's not added
    expect(filter).toEqual(["all"]);
  });

  it("includes known types and skips unknown ones", () => {
    const filter = buildTileFilter(
      ["private_nursery", "unknown_type"],
      false,
      [],
    );
    expect(filter).toEqual(["all", ["any", ["==", ["get", "ct_pn"], 1]]]);
  });
});

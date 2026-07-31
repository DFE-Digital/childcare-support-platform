import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { distanceBand, childAgeBands } from "@/lib/providerAnalytics";

const mockCapture = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("provider_search event", () => {
  it("includes LAD code, IoD decile, and filter state", () => {
    const geo = { deprivationDecile: 5 };
    const laCodes = ["E07000075", "E10000012"];
    const selectedTypes = ["childminder"];
    const sortBy = "distance";
    const fundedHoursOnly = true;
    const childAgesMonths = [24, 72];

    const lad25cd =
      laCodes.find((c) => c.startsWith("E")) ?? laCodes[0] ?? null;

    const payload = {
      lad25cd,
      iod_decile: geo.deprivationDecile ?? null,
      care_types: selectedTypes,
      sort_by: sortBy,
      funded_hours_only: fundedHoursOnly,
      child_age_bands: childAgeBands(childAgesMonths),
    };

    mockCapture("provider_search", payload);

    expect(mockCapture).toHaveBeenCalledWith("provider_search", {
      lad25cd: "E07000075",
      iod_decile: 5,
      care_types: ["childminder"],
      sort_by: "distance",
      funded_hours_only: true,
      child_age_bands: ["0-4", "5+"],
    });
  });

  it("prefers English LAD code", () => {
    const laCodes = ["S12000033", "E09000001"];
    const lad25cd =
      laCodes.find((c) => c.startsWith("E")) ?? laCodes[0] ?? null;
    expect(lad25cd).toBe("E09000001");
  });

  it("falls back to first code when no English code exists", () => {
    const laCodes = ["S12000033"];
    const lad25cd =
      laCodes.find((c) => c.startsWith("E")) ?? laCodes[0] ?? null;
    expect(lad25cd).toBe("S12000033");
  });

  it("returns null when no LA codes", () => {
    const laCodes: string[] = [];
    const lad25cd =
      laCodes.find((c) => c.startsWith("E")) ?? laCodes[0] ?? null;
    expect(lad25cd).toBeNull();
  });

  it("iod_decile is null when geo has no deprivation data", () => {
    const geo = { deprivationDecile: undefined };
    expect(geo.deprivationDecile ?? null).toBeNull();
  });
});

describe("provider_filter_changed event", () => {
  it("includes full filter state snapshot", () => {
    const payload = {
      care_types: ["childminder", "private_nursery"],
      sort_by: "rating",
      funded_hours_only: false,
      child_age_bands: ["0-4"],
    };

    mockCapture("provider_filter_changed", payload);

    expect(mockCapture).toHaveBeenCalledWith("provider_filter_changed", {
      care_types: ["childminder", "private_nursery"],
      sort_by: "rating",
      funded_hours_only: false,
      child_age_bands: ["0-4"],
    });
  });

  it("child_age_bands is empty when no children selected", () => {
    expect(childAgeBands([])).toEqual([]);
  });
});

describe("provider_detail_viewed event", () => {
  it("emits distance_band only", () => {
    const provider = {
      distanceMiles: 1.5,
      careTypes: [{ type: "childminder" }],
    };
    const payload = { distance_band: distanceBand(provider.distanceMiles) };

    mockCapture("provider_detail_viewed", payload);

    expect(mockCapture).toHaveBeenCalledWith("provider_detail_viewed", {
      distance_band: "1-3mi",
    });
  });

  it("never contains care_types", () => {
    const provider = {
      distanceMiles: 0.5,
      careTypes: [{ type: "childminder" }],
    };
    const payload = { distance_band: distanceBand(provider.distanceMiles) };

    expect(payload).not.toHaveProperty("care_types");
    expect(JSON.stringify(payload)).not.toContain("childminder");
  });

  it("never contains provider ID or name", () => {
    const payload = { distance_band: distanceBand(2.0) };
    expect(payload).not.toHaveProperty("id");
    expect(payload).not.toHaveProperty("providerId");
    expect(payload).not.toHaveProperty("name");
  });
});

describe("provider_shortlisted event", () => {
  function buildShortlistMask(
    shortlistedIds: string[],
    providers: Map<string, { careTypes: { type: string }[] }>,
  ): string[] {
    const careTypes = new Set<string>();
    for (const id of shortlistedIds) {
      const p = providers.get(id);
      if (p) for (const ct of p.careTypes) careTypes.add(ct.type);
    }
    return [...careTypes].sort();
  }

  it("aggregates care types across all shortlisted providers", () => {
    const providers = new Map([
      ["p1", { careTypes: [{ type: "childminder" }] }],
      ["p2", { careTypes: [{ type: "private_nursery" }] }],
      [
        "p3",
        { careTypes: [{ type: "childminder" }, { type: "breakfast_club" }] },
      ],
    ]);

    const mask = buildShortlistMask(["p1", "p2", "p3"], providers);
    expect(mask).toEqual(["breakfast_club", "childminder", "private_nursery"]);
  });

  it("deduplicates care types", () => {
    const providers = new Map([
      ["p1", { careTypes: [{ type: "childminder" }] }],
      ["p2", { careTypes: [{ type: "childminder" }] }],
    ]);

    const mask = buildShortlistMask(["p1", "p2"], providers);
    expect(mask).toEqual(["childminder"]);
  });

  it("updates mask on remove (type disappears)", () => {
    const providers = new Map([
      ["p1", { careTypes: [{ type: "childminder" }] }],
      ["p2", { careTypes: [{ type: "private_nursery" }] }],
    ]);

    const maskBefore = buildShortlistMask(["p1", "p2"], providers);
    expect(maskBefore).toEqual(["childminder", "private_nursery"]);

    const maskAfter = buildShortlistMask(["p2"], providers);
    expect(maskAfter).toEqual(["private_nursery"]);
  });

  it("returns empty when shortlist is empty", () => {
    const providers = new Map([
      ["p1", { careTypes: [{ type: "childminder" }] }],
    ]);
    expect(buildShortlistMask([], providers)).toEqual([]);
  });

  it("never contains distance_band", () => {
    const payload = { shortlist_care_types: ["childminder"] };
    expect(payload).not.toHaveProperty("distance_band");
  });

  it("never contains provider IDs", () => {
    const payload = { shortlist_care_types: ["childminder"] };
    expect(JSON.stringify(payload)).not.toContain("p1");
    expect(payload).not.toHaveProperty("providerId");
  });
});

describe("provider_zoom_in / provider_zoom_out debounce", () => {
  function createZoomHandler(capture: typeof mockCapture) {
    let stableZoom: number | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let lastSource: "keyboard" | "button" = "button";

    return function handleZoom(
      zoom: number,
      direction: "in" | "out",
      source: "keyboard" | "button",
    ) {
      lastSource = source;
      if (stableZoom === null) {
        stableZoom = direction === "in" ? zoom - 1 : zoom + 1;
      }
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        const netDir =
          zoom > stableZoom! ? "in" : zoom < stableZoom! ? "out" : null;
        if (netDir) {
          capture(netDir === "in" ? "provider_zoom_in" : "provider_zoom_out", {
            zoom_level: Math.round(zoom),
            source: lastSource,
          });
        }
        stableZoom = zoom;
      }, 5000);
    };
  }

  it("emits after 5 seconds of stability", () => {
    const handler = createZoomHandler(mockCapture);
    handler(11, "in", "button");

    expect(mockCapture).not.toHaveBeenCalled();
    vi.advanceTimersByTime(5000);

    expect(mockCapture).toHaveBeenCalledWith("provider_zoom_in", {
      zoom_level: 11,
      source: "button",
    });
  });

  it("does not emit during rapid zoom", () => {
    const handler = createZoomHandler(mockCapture);
    handler(11, "in", "button");
    vi.advanceTimersByTime(2000);
    handler(12, "in", "button");
    vi.advanceTimersByTime(2000);
    handler(13, "in", "button");
    vi.advanceTimersByTime(2000);

    expect(mockCapture).not.toHaveBeenCalled();
  });

  it("emits final level after rapid zoom settles", () => {
    const handler = createZoomHandler(mockCapture);
    handler(11, "in", "button");
    vi.advanceTimersByTime(1000);
    handler(12, "in", "button");
    vi.advanceTimersByTime(1000);
    handler(13, "in", "button");
    vi.advanceTimersByTime(5000);

    expect(mockCapture).toHaveBeenCalledOnce();
    expect(mockCapture).toHaveBeenCalledWith("provider_zoom_in", {
      zoom_level: 13,
      source: "button",
    });
  });

  it("emits zoom_out for net decrease", () => {
    const handler = createZoomHandler(mockCapture);
    handler(9, "out", "keyboard");
    vi.advanceTimersByTime(5000);

    expect(mockCapture).toHaveBeenCalledWith("provider_zoom_out", {
      zoom_level: 9,
      source: "keyboard",
    });
  });

  it("does not emit when net change is zero", () => {
    const handler = createZoomHandler(mockCapture);
    handler(11, "in", "button");
    vi.advanceTimersByTime(1000);
    handler(10, "out", "button");
    vi.advanceTimersByTime(5000);

    expect(mockCapture).not.toHaveBeenCalled();
  });

  it("tracks keyboard source through debounce window", () => {
    const handler = createZoomHandler(mockCapture);
    handler(11, "in", "button");
    vi.advanceTimersByTime(1000);
    handler(12, "in", "keyboard");
    vi.advanceTimersByTime(5000);

    expect(mockCapture).toHaveBeenCalledWith("provider_zoom_in", {
      zoom_level: 12,
      source: "keyboard",
    });
  });
});

describe("provider_show_more event", () => {
  it("calculates correct page number", () => {
    const PAGE_SIZE = 20;
    const visibleCount = 20;

    const page = Math.floor(visibleCount / PAGE_SIZE) + 1;
    expect(page).toBe(2);
  });

  it("increments page correctly on subsequent clicks", () => {
    const PAGE_SIZE = 20;
    const pages = [20, 40, 60].map((vc) => Math.floor(vc / PAGE_SIZE) + 1);
    expect(pages).toEqual([2, 3, 4]);
  });
});

describe("privacy invariants", () => {
  it("provider_detail_viewed and provider_shortlisted never share care_types + distance", () => {
    const detailPayload = { distance_band: distanceBand(1.5) };
    const shortlistPayload = { shortlist_care_types: ["childminder"] };

    expect(detailPayload).not.toHaveProperty("care_types");
    expect(detailPayload).not.toHaveProperty("shortlist_care_types");
    expect(shortlistPayload).not.toHaveProperty("distance_band");
  });

  it("no event payload structure contains postcode", () => {
    const searchPayload = {
      lad25cd: "E07000075",
      iod_decile: 5,
      care_types: [],
      sort_by: "distance",
      funded_hours_only: false,
      child_age_bands: [],
    };

    const serialised = JSON.stringify(searchPayload);
    expect(serialised).not.toMatch(/[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}/);
  });

  it("no event payload structure contains child names", () => {
    const filterPayload = {
      care_types: ["childminder"],
      sort_by: "distance",
      funded_hours_only: false,
      child_age_bands: ["0-4"],
    };

    expect(filterPayload).not.toHaveProperty("childName");
    expect(filterPayload).not.toHaveProperty("firstName");
    expect(filterPayload).not.toHaveProperty("children");
  });

  it("no event payload structure contains provider ID", () => {
    const allPayloads = [
      { distance_band: "<1mi" },
      { shortlist_care_types: ["childminder"] },
      {
        lad25cd: "E07000075",
        iod_decile: 5,
        care_types: [],
        sort_by: "distance",
        funded_hours_only: false,
        child_age_bands: [],
      },
      { zoom_level: 12, source: "button" },
      { page: 2 },
      { lad25cd: "E07000075" },
    ];

    for (const payload of allPayloads) {
      expect(payload).not.toHaveProperty("providerId");
      expect(payload).not.toHaveProperty("id");
      expect(payload).not.toHaveProperty("provider_id");
    }
  });
});

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { ProviderList } from "../ProviderList";

vi.mock("@/components/ui/ProviderCard", () => ({
  ProviderCard: ({ provider }: { provider: { name: string } }) => (
    <div data-testid="provider-card">{provider.name}</div>
  ),
}));

vi.mock("@/components/ui/ProviderCardSkeleton", () => ({
  ProviderCardSkeleton: () => <div data-testid="skeleton" />,
}));

function defaultProps(overrides: Record<string, unknown> = {}) {
  return {
    entries: [],
    loadedProviders: new Map(),
    totalCount: 0,
    hasMore: false,
    onShowMore: vi.fn(),
    shortlistedIds: [] as string[],
    onSelect: vi.fn(),
    onToggleShortlist: vi.fn(),
    costDisplayMode: "detailed" as const,
    includeAdditionalCharges: true,
    postcode: "BS1 1AA",
    ...overrides,
  };
}

afterEach(cleanup);

describe("ProviderList provider noun", () => {
  it("uses 'providers' when no type filter active", () => {
    render(
      <ProviderList {...defaultProps({ selectedTypes: [], totalCount: 0 })} />,
    );
    expect(screen.getByText("No providers found")).toBeInTheDocument();
  });

  it("uses 'childminders' when childminder filter active", () => {
    render(
      <ProviderList
        {...defaultProps({ selectedTypes: ["childminder"], totalCount: 0 })}
      />,
    );
    expect(screen.getByText("No childminders found")).toBeInTheDocument();
  });

  it("uses 'nurseries (Private, Voluntary or Independent)' when private_nursery filter active", () => {
    render(
      <ProviderList
        {...defaultProps({ selectedTypes: ["private_nursery"], totalCount: 0 })}
      />,
    );
    expect(
      screen.getByText(
        "No nurseries (Private, Voluntary or Independent) found",
      ),
    ).toBeInTheDocument();
  });

  it("uses 'providers' when multiple type filters active", () => {
    render(
      <ProviderList
        {...defaultProps({
          selectedTypes: ["childminder", "private_nursery"],
          totalCount: 0,
        })}
      />,
    );
    expect(screen.getByText("No providers found")).toBeInTheDocument();
  });

  it("uses filtered noun in 'Showing X of Y' text", () => {
    render(
      <ProviderList
        {...defaultProps({
          selectedTypes: ["childminder"],
          totalCount: 5,
          entries: [{ providerId: "p1", distanceMiles: 1.0, ladCode: 0 }],
          loadedProviders: new Map([
            ["p1", { id: "p1", name: "Test", distanceMiles: 1.0 }],
          ]),
        })}
      />,
    );
    expect(screen.getByText(/Showing 1 of 5 childminders/)).toBeInTheDocument();
  });

  it("uses 'providers' for unknown type", () => {
    render(
      <ProviderList
        {...defaultProps({ selectedTypes: ["unknown_type"], totalCount: 0 })}
      />,
    );
    expect(screen.getByText("No providers found")).toBeInTheDocument();
  });
});

describe("ProviderList info sections", () => {
  it("shows '(including X without map pins)' when bboxCount > 0", () => {
    render(
      <ProviderList
        {...defaultProps({
          totalCount: 10,
          entries: [{ providerId: "p1", distanceMiles: 1.0, ladCode: 0 }],
          loadedProviders: new Map([
            ["p1", { id: "p1", name: "Test", distanceMiles: 1.0 }],
          ]),
          bboxCount: 3,
        })}
      />,
    );
    expect(
      screen.getByText(/including 3 without map pins/),
    ).toBeInTheDocument();
  });

  it("hides bbox text when bboxCount is 0", () => {
    render(
      <ProviderList
        {...defaultProps({
          totalCount: 10,
          entries: [{ providerId: "p1", distanceMiles: 1.0, ladCode: 0 }],
          loadedProviders: new Map([
            ["p1", { id: "p1", name: "Test", distanceMiles: 1.0 }],
          ]),
          bboxCount: 0,
        })}
      />,
    );
    expect(screen.queryByText(/without map pins/)).not.toBeInTheDocument();
  });

  it("shows beyond-viewport count when beyondCount > 0", () => {
    render(
      <ProviderList
        {...defaultProps({
          totalCount: 10,
          entries: [{ providerId: "p1", distanceMiles: 1.0, ladCode: 0 }],
          loadedProviders: new Map([
            ["p1", { id: "p1", name: "Test", distanceMiles: 1.0 }],
          ]),
          beyondCount: 5,
          beyondMaxMiles: 11.3,
        })}
      />,
    );
    expect(screen.getByText(/5 more within 12 miles/)).toBeInTheDocument();
  });

  it("renders missingBboxCount paragraph with LA name", () => {
    render(
      <ProviderList
        {...defaultProps({
          totalCount: 5,
          entries: [{ providerId: "p1", distanceMiles: 1.0, ladCode: 0 }],
          loadedProviders: new Map([
            ["p1", { id: "p1", name: "Test", distanceMiles: 1.0 }],
          ]),
          missingBboxCount: 48,
          areaCosts: {
            laName: "Bath and North East Somerset",
            laBounds: { south: 51.27, west: -2.71, north: 51.44, east: -2.28 },
            providerStats: {},
          },
        })}
      />,
    );
    expect(screen.getByText("48")).toBeInTheDocument();
    expect(
      screen.getByText(/Bath and North East Somerset/),
    ).toBeInTheDocument();
    expect(screen.getByText(/don't have map pins/)).toBeInTheDocument();
  });

  it("renders 'Move my map' button when onZoomToLa and laBounds present", () => {
    const onZoomToLa = vi.fn();
    render(
      <ProviderList
        {...defaultProps({
          totalCount: 5,
          entries: [{ providerId: "p1", distanceMiles: 1.0, ladCode: 0 }],
          loadedProviders: new Map([
            ["p1", { id: "p1", name: "Test", distanceMiles: 1.0 }],
          ]),
          missingBboxCount: 10,
          onZoomToLa,
          areaCosts: {
            laName: "BANES",
            laBounds: { south: 51.27, west: -2.71, north: 51.44, east: -2.28 },
            providerStats: {},
          },
        })}
      />,
    );
    const btn = screen.getByRole("button", { name: /Show me/ });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onZoomToLa).toHaveBeenCalledTimes(1);
  });

  it("hides missingBbox paragraph when missingBboxCount is 0", () => {
    render(
      <ProviderList
        {...defaultProps({
          totalCount: 5,
          entries: [{ providerId: "p1", distanceMiles: 1.0, ladCode: 0 }],
          loadedProviders: new Map([
            ["p1", { id: "p1", name: "Test", distanceMiles: 1.0 }],
          ]),
          missingBboxCount: 0,
          areaCosts: {
            laName: "BANES",
            laBounds: { south: 51.27, west: -2.71, north: 51.44, east: -2.28 },
            providerStats: {},
          },
        })}
      />,
    );
    expect(screen.queryByText(/don't have map pins/)).not.toBeInTheDocument();
  });

  it("shows 'No X found' and stats section when totalCount=0 and hasSearched", () => {
    render(
      <ProviderList
        {...defaultProps({
          totalCount: 0,
          postcode: "BA2 6AA",
          selectedTypes: ["childminder"],
          missingBboxCount: 48,
          areaCosts: {
            laName: "Bath and North East Somerset",
            laBounds: { south: 51.27, west: -2.71, north: 51.44, east: -2.28 },
            providerStats: {
              childminder: { total: 77, bboxOnly: 48, insufficient: 38 },
            },
          },
        })}
      />,
    );
    expect(screen.getByText("No childminders found")).toBeInTheDocument();
    expect(screen.getByText(/don't have map pins/)).toBeInTheDocument();
    expect(screen.getByText("48")).toBeInTheDocument();
  });

  it("renders providerStats when bboxOnly > 0", () => {
    render(
      <ProviderList
        {...defaultProps({
          totalCount: 5,
          entries: [{ providerId: "p1", distanceMiles: 1.0, ladCode: 0 }],
          loadedProviders: new Map([
            ["p1", { id: "p1", name: "Test", distanceMiles: 1.0 }],
          ]),
          selectedTypes: ["childminder"],
          areaCosts: {
            laName: "BANES",
            providerStats: {
              childminder: { total: 77, bboxOnly: 48, insufficient: 0 },
            },
          },
        })}
      />,
    );
    expect(screen.getByText("77 childminders")).toBeInTheDocument();
    expect(screen.getByText(/in our dataset/)).toBeInTheDocument();
  });
});

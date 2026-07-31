import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProviderFilters } from "../ProviderFilters";

vi.mock("@/hooks/useFeatureFlags", () => {
  const flags = {
    showFees: true,
    showMetrics: false,
    showEligibility: false,
    showAvailability: false,
    showNotes: false,
  };
  return { featureFlags: flags, useFeatureFlags: () => flags };
});

vi.mock("react-router-dom", () => ({
  Link: ({
    to,
    children,
    ...props
  }: {
    to: string;
    children: React.ReactNode;
  }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

function defaultProps(overrides: Record<string, unknown> = {}) {
  return {
    selectedTypes: [] as string[],
    onTypesChange: vi.fn(),
    selectedChildren: [] as string[],
    onChildrenChange: vi.fn(),
    children: [],
    shortlistedOnly: false,
    onShortlistedOnlyChange: vi.fn(),
    shortlistedCount: 0,
    isOpen: true,
    onToggle: vi.fn(),
    costDisplayMode: "detailed" as const,
    onCostDisplayModeChange: vi.fn(),
    includeAdditionalCharges: true,
    onIncludeAdditionalChargesChange: vi.fn(),
    sortBy: "distance" as const,
    onSortByChange: vi.fn(),
    fundedHoursOnly: false,
    onFundedHoursOnlyChange: vi.fn(),
    postcode: "SW1A 1AA",
    areaCosts: null,
    ...overrides,
  };
}

describe("ProviderFilters (showFees enabled)", () => {
  let user: ReturnType<typeof userEvent.setup>;

  beforeEach(() => {
    cleanup();
    user = userEvent.setup();
  });

  it("calls onSortByChange when sort dropdown value changes", async () => {
    const onSortByChange = vi.fn();
    render(<ProviderFilters {...defaultProps({ onSortByChange })} />);

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "lowest_cost");
    expect(onSortByChange).toHaveBeenCalledWith("lowest_cost");
  });
});

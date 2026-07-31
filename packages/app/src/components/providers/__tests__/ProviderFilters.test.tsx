import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProviderFilters } from "../ProviderFilters";

// Mock react-router-dom Link to a plain anchor
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

vi.mock("@/hooks/useFeatureFlags", () => ({
  featureFlags: { showFundedHoursFilter: true },
  useFeatureFlags: () => ({ showFundedHoursFilter: true }),
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

describe("ProviderFilters", () => {
  let user: ReturnType<typeof userEvent.setup>;

  beforeEach(() => {
    cleanup();
    user = userEvent.setup();
  });

  it("calls onTypesChange with type added when toggling a care type on", async () => {
    const onTypesChange = vi.fn();
    render(<ProviderFilters {...defaultProps({ onTypesChange })} />);

    const checkbox = screen.getByRole("checkbox", {
      name: "Nursery Private, Voluntary or Independent",
    });
    await user.click(checkbox);
    expect(onTypesChange).toHaveBeenCalledWith(["private_nursery"]);
  });

  it("calls onTypesChange with type removed when toggling a care type off", async () => {
    const onTypesChange = vi.fn();
    render(
      <ProviderFilters
        {...defaultProps({
          selectedTypes: ["private_nursery", "childminder"],
          onTypesChange,
        })}
      />,
    );

    const checkboxes = screen.getAllByRole("checkbox", {
      name: "Nursery Private, Voluntary or Independent",
    });
    const checked = checkboxes.find((el) => (el as HTMLInputElement).checked)!;
    await user.click(checked);
    expect(onTypesChange).toHaveBeenCalledWith(["childminder"]);
  });

  it("calls onFundedHoursOnlyChange when toggling funded hours", async () => {
    const onFundedHoursOnlyChange = vi.fn();
    render(<ProviderFilters {...defaultProps({ onFundedHoursOnlyChange })} />);

    const checkboxes = screen.getAllByRole("checkbox", {
      name: "Accepts funded hours",
    });
    const unchecked = checkboxes.find(
      (el) => !(el as HTMLInputElement).checked,
    )!;
    await user.click(unchecked);
    expect(onFundedHoursOnlyChange).toHaveBeenCalledWith(true);
  });

  it("calls onChildrenChange when toggling a child filter", async () => {
    const onChildrenChange = vi.fn();
    render(
      <ProviderFilters
        {...defaultProps({
          children: [
            { id: "1", firstName: "Alice", birthMonth: 3, birthYear: 2024 },
          ],
          onChildrenChange,
        })}
      />,
    );

    const checkboxes = screen.getAllByRole("checkbox", { name: /Alice/ });
    await user.click(checkboxes[0]);
    expect(onChildrenChange).toHaveBeenCalledWith(["Alice"]);
  });

  it("calls all reset callbacks when clear all filters is clicked", async () => {
    const onTypesChange = vi.fn();
    const onChildrenChange = vi.fn();
    const onShortlistedOnlyChange = vi.fn();
    const onFundedHoursOnlyChange = vi.fn();
    render(
      <ProviderFilters
        {...defaultProps({
          selectedTypes: ["private_nursery"],
          onTypesChange,
          onChildrenChange,
          onShortlistedOnlyChange,
          onFundedHoursOnlyChange,
        })}
      />,
    );

    const clearButton = screen.getByRole("button", {
      name: "Clear all filters",
    });
    await user.click(clearButton);

    expect(onTypesChange).toHaveBeenCalledWith([]);
    expect(onChildrenChange).toHaveBeenCalledWith([]);
    expect(onShortlistedOnlyChange).toHaveBeenCalledWith(false);
    expect(onFundedHoursOnlyChange).toHaveBeenCalledWith(false);
  });

  it("does not show clear all filters when no filters are active", () => {
    render(<ProviderFilters {...defaultProps()} />);
    expect(
      screen.queryByRole("button", { name: "Clear all filters" }),
    ).not.toBeInTheDocument();
  });
});

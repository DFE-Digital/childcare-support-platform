import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { PostcodeInput } from "../PostcodeInput";
import type { PostcodeGeo } from "@/hooks/usePostcodeLookup";

// --- Mock usePostcodeLookup ---
const mockFilterOutward = vi.fn<(prefix: string) => string[]>(() => []);
const mockFilterInward = vi.fn<(outward: string, prefix: string) => string[]>(
  () => [],
);
const mockGetGeo = vi.fn<
  (outward: string, inward: string) => PostcodeGeo | null
>(() => null);
const mockPrefetchInward = vi.fn();
const mockState = { isLoading: false };

vi.mock("@/hooks/usePostcodeLookup", () => ({
  usePostcodeLookup: () => ({
    filterOutward: mockFilterOutward,
    filterInward: mockFilterInward,
    getGeo: mockGetGeo,
    getLaCodes: () => [],
    prefetchInward: mockPrefetchInward,
    isLoading: mockState.isLoading,
    outwardLoaded: true,
  }),
}));

beforeEach(() => {
  vi.resetAllMocks();
  mockFilterOutward.mockReturnValue([]);
  mockFilterInward.mockReturnValue([]);
  mockGetGeo.mockReturnValue(null);
  mockState.isLoading = false;
  cleanup();
});

function renderInput(
  overrides: Partial<React.ComponentProps<typeof PostcodeInput>> = {},
) {
  const defaultProps = {
    value: "",
    onChange: vi.fn(),
    ...overrides,
  };
  return {
    ...render(<PostcodeInput {...defaultProps} />),
    props: defaultProps,
  };
}

// ---------------------------------------------------------------------------
// 3a. Outward suggestions
// ---------------------------------------------------------------------------

describe("outward suggestions", () => {
  it("shows outward suggestions when typing", () => {
    mockFilterOutward.mockReturnValue(["SW1A", "SW1H"]);
    renderInput({ value: "S" });

    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "S" } });

    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(2);
    expect(screen.getByText("SW1A")).toBeInTheDocument();
    expect(screen.getByText("SW1H")).toBeInTheDocument();
  });

  it("selects outward and appends space", () => {
    mockFilterOutward.mockReturnValue(["SW1A", "SW1H"]);
    const { props } = renderInput({ value: "SW" });

    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "SW" } });

    fireEvent.mouseDown(screen.getByText("SW1A"));
    expect(props.onChange).toHaveBeenCalledWith("SW1A ");
  });

  it("shows no suggestions when input is empty", () => {
    mockFilterOutward.mockReturnValue([]);
    renderInput({ value: "" });

    const input = screen.getByRole("combobox");
    fireEvent.focus(input);

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 3b. Inward suggestions
// ---------------------------------------------------------------------------

describe("inward suggestions", () => {
  it("shows inward suggestions after outward", () => {
    mockFilterInward.mockReturnValue(["1AA", "1AB"]);
    renderInput({ value: "SW1A 1" });

    const input = screen.getByRole("combobox");
    fireEvent.focus(input);

    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(screen.getByText("SW1A 1AA")).toBeInTheDocument();
    expect(screen.getByText("SW1A 1AB")).toBeInTheDocument();
  });

  it("selects inward and calls onSelect with geo", () => {
    const mockGeo: PostcodeGeo = {
      bbox: [-0.1416, 51.4993, -0.1393, 51.5013],
      centroid: [-0.1405, 51.5003],
    };
    mockFilterInward.mockReturnValue(["1AA"]);
    mockGetGeo.mockReturnValue(mockGeo);

    const onSelect = vi.fn();
    renderInput({ value: "SW1A 1", onSelect });

    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "SW1A 1" } });

    fireEvent.mouseDown(screen.getByText("SW1A 1AA"));
    expect(onSelect).toHaveBeenCalledWith("SW1A 1AA", mockGeo);
  });
});

// ---------------------------------------------------------------------------
// 3c. Keyboard navigation
// ---------------------------------------------------------------------------

describe("keyboard navigation", () => {
  it("ArrowDown highlights next suggestion", () => {
    mockFilterOutward.mockReturnValue(["SW1A", "SW1H"]);
    renderInput({ value: "SW" });

    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "SW" } });

    fireEvent.keyDown(input, { key: "ArrowDown" });
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(options[1]).toHaveAttribute("aria-selected", "true");
  });

  it("Enter selects highlighted suggestion", () => {
    mockFilterOutward.mockReturnValue(["SW1A", "SW1H"]);
    const { props } = renderInput({ value: "SW" });

    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "SW" } });

    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(props.onChange).toHaveBeenCalledWith("SW1A ");
  });

  it("Escape closes the dropdown", () => {
    mockFilterOutward.mockReturnValue(["SW1A", "SW1H"]);
    renderInput({ value: "SW" });

    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "SW" } });

    expect(screen.getByRole("listbox")).toBeInTheDocument();
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 3d. Loading state
// ---------------------------------------------------------------------------

describe("loading state", () => {
  it("shows loading indicator during inward phase", () => {
    mockState.isLoading = true;
    mockFilterInward.mockReturnValue([]);

    renderInput({ value: "SW1A 1" });

    const input = screen.getByRole("combobox");
    fireEvent.focus(input);

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});

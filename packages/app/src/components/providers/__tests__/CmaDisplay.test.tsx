import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import type { Provider } from "@/types/provider";

vi.mock("@/components/ui/ExternalLink", () => ({
  ExternalLink: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
}));
vi.mock("@/components/ui/Modal", () => ({
  Modal: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/data/loader", () => ({
  loadLaCosts: vi.fn().mockResolvedValue({ laName: "Test LA" }),
}));
vi.mock("@/hooks/useFeatureFlags", () => ({
  featureFlags: { showMetrics: false },
}));
vi.mock("@/utils/providerCosts", () => ({
  getProviderCostDisplay: () => ({ summary: "", detailed: "" }),
}));

import type { CostDisplayMode } from "@/components/providers/ProviderFilters";
import { ProviderCard } from "@/components/ui/ProviderCard";
import { ProviderDetail } from "../ProviderDetail";

afterEach(cleanup);

function makeProvider(overrides: Partial<Provider> = {}): Provider {
  return {
    id: "p123",
    name: "Test Provider",
    latitude: null,
    longitude: null,
    distanceMiles: 1.5,
    phone: "",
    email: "",
    website: "",
    address: { line1: "", line2: "", city: "", postcode: "BS1" },
    institutionType: "childminder",
    careTypes: [
      {
        type: "childminder",
        fees: null,
        openingHours: null,
        eligibility: null,
        operatingWeeksPerYear: null,
        sessionHours: null,
        website: null,
        fisUrl: null,
        additionalCharges: [],
        waitingList: null,
        notes: null,
      },
    ],
    ofsted: null,
    cma: null,
    ...overrides,
  } as unknown as Provider;
}

function renderCard(provider: Provider) {
  return render(
    <ProviderCard
      id="p123"
      provider={provider}
      isShortlisted={false}
      onSelect={vi.fn()}
      onToggleShortlist={vi.fn()}
      costDisplayMode={"summary" as CostDisplayMode}
      includeAdditionalCharges={false}
      sortBy="distance"
      postcode="BS1 1AA"
    />,
  );
}

describe("CMA badge on ProviderCard", () => {
  it("renders agency + grading for inspected CMA provider", () => {
    const provider = makeProvider({
      cma: { agency: "Tiney", qaGrading: "good" },
    });
    renderCard(provider);
    expect(screen.getByText("Tiney: Good")).toBeInTheDocument();
  });

  it("renders awaiting first visit for uninspected CMA provider", () => {
    const provider = makeProvider({
      cma: { agency: "Tiney" },
    });
    renderCard(provider);
    expect(screen.getByText("Tiney: Awaiting first visit")).toBeInTheDocument();
  });

  it("does not render 'Not inspected' when CMA is present", () => {
    const provider = makeProvider({
      cma: { agency: "Tiney", qaGrading: "good" },
      ofsted: null,
    });
    renderCard(provider);
    expect(screen.queryByText("Not inspected")).not.toBeInTheDocument();
  });

  it("still renders 'Not inspected' when no CMA and no Ofsted", () => {
    const provider = makeProvider({
      cma: null,
      ofsted: null,
    });
    renderCard(provider);
    expect(screen.getByText("Not inspected")).toBeInTheDocument();
  });

  it("renders support-required with amber styling", () => {
    const provider = makeProvider({
      cma: { agency: "Tiney", qaGrading: "support-required" },
    });
    renderCard(provider);
    const badge = screen.getByText("Tiney: Support Required");
    expect(badge.className).toContain("bg-amber-50");
  });

  it("renders support-plan with red styling", () => {
    const provider = makeProvider({
      cma: { agency: "Tiney", qaGrading: "support-plan" },
    });
    renderCard(provider);
    const badge = screen.getByText("Tiney: Support Plan");
    expect(badge.className).toContain("bg-red-50");
  });

  it("renders good-with-actions with amber styling", () => {
    const provider = makeProvider({
      cma: { agency: "Tiney", qaGrading: "good-with-actions" },
    });
    renderCard(provider);
    const badge = screen.getByText("Tiney: Good With Actions");
    expect(badge.className).toContain("bg-amber-50");
  });
});

describe("CMA section in ProviderDetail", () => {
  function renderDetail(provider: Provider) {
    return render(
      <ProviderDetail
        provider={provider}
        onClose={vi.fn()}
        isShortlisted={false}
        onToggleShortlist={vi.fn()}
        postcode="BS1 1AA"
        coLocatedProviders={[provider]}
      />,
    );
  }

  it("renders CMA header with agency name", () => {
    const provider = makeProvider({
      cma: { agency: "Tiney", qaGrading: "good", inspectionDate: "2026-03-18" },
    });
    renderDetail(provider);
    expect(screen.getByText("Quality Assurance (Tiney)")).toBeInTheDocument();
  });

  it("renders awaiting first visit when no grading", () => {
    const provider = makeProvider({
      cma: { agency: "Tiney" },
    });
    renderDetail(provider);
    expect(screen.getByText("Awaiting first visit")).toBeInTheDocument();
  });

  it("does not render 'No Ofsted inspection' when CMA present", () => {
    const provider = makeProvider({
      cma: { agency: "Tiney", qaGrading: "good" },
      ofsted: null,
    });
    renderDetail(provider);
    expect(screen.queryByText("No Ofsted inspection")).not.toBeInTheDocument();
  });

  it("still renders 'No Ofsted inspection' when no CMA", () => {
    const provider = makeProvider({
      cma: null,
      ofsted: null,
    });
    renderDetail(provider);
    expect(screen.getByText("No Ofsted inspection")).toBeInTheDocument();
  });
});

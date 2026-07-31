import { Link, Navigate } from "react-router-dom";
import { PageHero } from "@/components/layout/PageHero";
import { Container } from "@/components/layout/Container";
import { BetaBanner } from "@/components/ui/BetaBanner";
import { CostResults } from "@/components/costs/CostResults";
import { useFamily } from "@/hooks/useFamily";

const HERO_PROPS = {
  title: "Your estimated childcare costs",
  subtitle:
    "A breakdown of childcare costs and government support for your family.",
  breadcrumbs: [{ label: "Cost estimate", to: "/costs" }, { label: "Results" }],
};

export default function CostResultsPage() {
  const { loading, isDisclaimerValid } = useFamily();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" role="status">
        <div
          className="animate-spin w-8 h-8 border-4 border-neutral-700 border-t-transparent rounded-full"
          aria-hidden="true"
        />
        <span className="sr-only">Loading</span>
      </div>
    );
  }

  if (!isDisclaimerValid) {
    return <Navigate to="/costs/disclaimer#main-content" replace />;
  }

  return (
    <>
      <div className="flex flex-col">
        <div className="order-2 py-4 px-5 md:px-7">
          <div className="mx-auto" style={{ maxWidth: 960 }}>
            <BetaBanner />
          </div>
        </div>
        <PageHero {...HERO_PROPS} />
      </div>
      <Container className="py-10" maxWidth={960}>
        <Link
          to="/costs#main-content"
          className="flex items-center gap-1 text-base font-bold text-neutral-700 hover:text-neutral-600 mb-8 transition-colors"
        >
          <span aria-hidden="true">&larr;</span> Change my answers
        </Link>

        <CostResults
          footer={
            <div className="mt-10 mb-8">
              <Link to="/providers#main-content" className="btn-dark">
                Search for providers <span aria-hidden="true">&rarr;</span>
              </Link>
            </div>
          }
        />
      </Container>
    </>
  );
}

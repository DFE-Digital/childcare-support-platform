import { Link } from "react-router-dom";
import { PageHero } from "@/components/layout/PageHero";
import { Container } from "@/components/layout/Container";
import { BetaBanner } from "@/components/ui/BetaBanner";
import { SupportResults } from "@/components/support/SupportResults";
import { useFamily } from "@/hooks/useFamily";
import { featureFlags } from "@/hooks/useFeatureFlags";
import { areAllChildrenBigKids } from "@/lib/childAge";

export default function SupportResultsPage() {
  const { selectedFamily, loading } = useFamily();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin w-8 h-8 border-4 border-neutral-700 border-t-transparent rounded-full" />
      </div>
    );
  }

  const children = selectedFamily.localStorage.children;
  const allBigKids =
    featureFlags.noBigKidEstimates && areAllChildrenBigKids(children);

  return (
    <>
      <div className="flex flex-col">
        <div className="order-2 py-4 px-5 md:px-7">
          <div className="mx-auto" style={{ maxWidth: 960 }}>
            <BetaBanner />
          </div>
        </div>
        <PageHero
          title="Your support options"
          subtitle="Based on your family's details, here are the government schemes you may be eligible for."
          breadcrumbs={[
            { label: "Support checker", to: "/support" },
            { label: "Results" },
          ]}
        />
      </div>
      <Container className="py-10" maxWidth={960}>
        <Link
          to="/support#main-content"
          className="flex items-center gap-1 text-base font-bold text-neutral-700 hover:text-neutral-600 mb-8 transition-colors"
        >
          <span aria-hidden="true">&larr;</span> Change my answers
        </Link>

        <SupportResults />

        {allBigKids && (
          <p className="mt-10 text-base text-zinc-600">
            Unfortunately, we can&rsquo;t provide a cost estimate for older
            children at the moment. We don&rsquo;t currently have reliable
            average cost data for children aged 5 and over. You should contact
            childcare providers directly to see how much they charge.
          </p>
        )}

        <div className="mt-6 mb-12 flex flex-col items-start gap-3">
          <Link
            to="/costs#main-content"
            className={`btn-dark${allBigKids ? " opacity-50 cursor-not-allowed" : ""}`}
            aria-disabled={allBigKids || undefined}
            tabIndex={allBigKids ? -1 : undefined}
            onClick={allBigKids ? (e) => e.preventDefault() : undefined}
          >
            Estimate your costs <span aria-hidden="true">&rarr;</span>
          </Link>
          <Link to="/support/schemes#main-content" className="btn">
            View all schemes <span aria-hidden="true">&rarr;</span>
          </Link>
          {allBigKids && (
            <Link to="/providers#main-content" className="btn">
              Search for childcare providers{" "}
              <span aria-hidden="true">&rarr;</span>
            </Link>
          )}
        </div>
      </Container>
    </>
  );
}

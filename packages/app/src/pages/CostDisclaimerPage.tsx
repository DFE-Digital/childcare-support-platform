import { Link, useNavigate } from "react-router-dom";
import { PageHero } from "@/components/layout/PageHero";
import { Container } from "@/components/layout/Container";
import { BetaBanner } from "@/components/ui/BetaBanner";
import { CostDisclaimer } from "@/components/costs/CostDisclaimer";
import { useFamily } from "@/hooks/useFamily";

export default function CostDisclaimerPage() {
  const { acknowledgeDisclaimer } = useFamily();
  const navigate = useNavigate();

  return (
    <>
      <div className="flex flex-col">
        <div className="order-2 py-4 px-5 md:px-7">
          <div className="mx-auto" style={{ maxWidth: 960 }}>
            <BetaBanner />
          </div>
        </div>
        <PageHero
          title="Your estimated childcare costs"
          subtitle="A breakdown of childcare costs and government support for your family."
          breadcrumbs={[
            { label: "Cost estimate", to: "/costs" },
            { label: "Results" },
          ]}
        />
      </div>
      <Container className="py-10" maxWidth={960}>
        <Link
          to="/costs#main-content"
          className="flex items-center gap-1 text-base font-bold text-neutral-700 hover:text-neutral-600 mb-8 transition-colors"
        >
          <span aria-hidden="true">&larr;</span> Change my answers
        </Link>
        <CostDisclaimer
          onAccept={() => {
            acknowledgeDisclaimer();
            navigate("/costs/results#main-content");
          }}
        />
      </Container>
    </>
  );
}

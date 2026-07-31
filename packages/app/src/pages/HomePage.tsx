import { PageHero } from "@/components/layout/PageHero";
import { Container } from "@/components/layout/Container";
import { BetaBanner } from "@/components/ui/BetaBanner";
import { Link } from "react-router-dom";

export default function HomePage() {
  return (
    <>
      <div className="flex flex-col">
        <div className="order-2 py-4 px-5 md:px-7">
          <div className="mx-auto" style={{ maxWidth: 640 }}>
            <BetaBanner />
          </div>
        </div>
        <PageHero
          title="Childcare checker"
          subtitle="Find out what childcare support you could get, how much childcare might cost, and search for providers near you."
        />
      </div>
      <Container className="py-10">
        <div className="max-w-[640px] mx-auto mb-12 lg:text-center">
          <h2 className="text-[27px] md:text-[31px] xl:text-[36px] font-bold mb-4">
            Get personalised results
          </h2>
          <p className="text-lg mb-6 leading-relaxed">
            Answer a few questions about your family and we'll show you what
            government schemes you may be eligible for, estimate your childcare
            costs, and help you find providers in your area.
          </p>
          <Link to="/support#main-content" className="btn-dark">
            GET STARTED
            <span aria-hidden="true">&rarr;</span>
          </Link>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <Link
            to="/support#main-content"
            className="bg-white rounded-xl p-6 border-t-4 border-t-green-600 border border-zinc-200 hover:shadow-lg transition-shadow group"
          >
            <h3 className="font-bold text-lg mb-2 group-hover:text-green-700">
              What support am I entitled to?
            </h3>
            <p className="text-sm text-zinc-600">
              Find out which government schemes your family may be eligible for.
            </p>
          </Link>
          <Link
            to="/costs#main-content"
            className="bg-white rounded-xl p-6 border-t-4 border-t-blue-600 border border-zinc-200 hover:shadow-lg transition-shadow group"
          >
            <h3 className="font-bold text-lg mb-2 group-hover:text-blue-700">
              How much might your childcare cost?
            </h3>
            <p className="text-sm text-zinc-600">
              Get an estimate of your childcare costs based on your answers.
            </p>
          </Link>
          <Link
            to="/providers#main-content"
            className="bg-white rounded-xl p-6 border-t-4 border-t-purple-600 border border-zinc-200 hover:shadow-lg transition-shadow group"
          >
            <h3 className="font-bold text-lg mb-2 group-hover:text-purple-700">
              How do I find a provider?
            </h3>
            <p className="text-sm text-zinc-600">
              Search for nurseries, childminders, and clubs near you.
            </p>
          </Link>
        </div>
      </Container>
    </>
  );
}

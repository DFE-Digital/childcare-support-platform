import { Link } from "react-router-dom";
import { PageHero } from "@/components/layout/PageHero";
import { Container } from "@/components/layout/Container";
import { BetaBanner } from "@/components/ui/BetaBanner";
import { useFamily } from "@/hooks/useFamily";
import { isInternalUrl } from "@/lib/url";

export default function AllSchemesPage() {
  const { schemes, devolvedNationLinks } = useFamily();

  return (
    <>
      <div className="flex flex-col">
        <div className="order-2 py-4 px-5 md:px-7">
          <div className="mx-auto" style={{ maxWidth: 960 }}>
            <BetaBanner />
          </div>
        </div>
        <PageHero
          title="View all schemes"
          subtitle="An overview of the childcare support schemes available across the UK."
          breadcrumbs={[
            { label: "Support checker", to: "/support" },
            { label: "All schemes" },
          ]}
        />
      </div>
      <Container className="py-10" maxWidth={960}>
        <Link
          to="/support#main-content"
          className="flex items-center gap-1 text-base font-bold text-neutral-700 hover:text-neutral-600 mb-8 transition-colors"
        >
          <span aria-hidden="true">&larr;</span> Back to support checker
        </Link>

        <div className="space-y-4 mb-4">
          {schemes.map((scheme) => (
            <div
              key={scheme.id}
              className="bg-white border border-gray-200 rounded-xl p-6"
            >
              <h2 className="text-2xl font-bold mb-2">{scheme.name}</h2>
              <p className="text-lg text-zinc-600 mb-4">
                {scheme.allSchemesDescription ?? scheme.description}
              </p>
              {(scheme.links.info ||
                scheme.links.apply ||
                scheme.secondaryLinks) && (
                <div className="flex flex-wrap gap-3">
                  {scheme.links.info && (
                    <a
                      href={scheme.links.info}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-dark inline-flex items-center gap-2"
                    >
                      Learn more{" "}
                      {isInternalUrl(scheme.links.info) ? (
                        <span aria-hidden="true">&rarr;</span>
                      ) : (
                        <i
                          className="bi bi-box-arrow-up-right"
                          aria-hidden="true"
                        />
                      )}
                      <span className="sr-only">(opens in new tab)</span>
                    </a>
                  )}
                  {scheme.links.apply && (
                    <a
                      href={scheme.links.apply}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn inline-flex items-center gap-2"
                    >
                      Apply now{" "}
                      <i
                        className="bi bi-box-arrow-up-right"
                        aria-hidden="true"
                      />
                      <span className="sr-only">(opens in new tab)</span>
                    </a>
                  )}
                  {scheme.secondaryLinks?.map((link) => (
                    <a
                      key={link.url}
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn inline-flex items-center gap-2"
                    >
                      {link.label}{" "}
                      <i
                        className="bi bi-box-arrow-up-right"
                        aria-hidden="true"
                      />
                      <span className="sr-only">(opens in new tab)</span>
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="space-y-4 mb-12">
          {devolvedNationLinks.map((link) => (
            <div
              key={link.nation}
              className="bg-white border border-gray-200 rounded-xl p-6"
            >
              <h2 className="text-2xl font-bold mb-2">
                More schemes for {link.nation}
              </h2>
              <p className="text-lg text-zinc-600 mb-4">
                Find out what other schemes you may be eligible for if you live
                in {link.nation}.
              </p>
              <a
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-dark inline-flex items-center gap-2"
              >
                Find out more{" "}
                <i className="bi bi-box-arrow-up-right" aria-hidden="true" />
                <span className="sr-only">(opens in new tab)</span>
              </a>
            </div>
          ))}
        </div>
      </Container>
    </>
  );
}

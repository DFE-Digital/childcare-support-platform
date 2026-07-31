import { PageHero } from "@/components/layout/PageHero";
import { Container } from "@/components/layout/Container";

export default function PlaceholderPage() {
  return (
    <>
      <PageHero title="Placeholder Content" />
      <Container className="py-10">
        <div className="max-w-2xl mx-auto">
          <p className="text-lg leading-relaxed">
            This site is a prototype checker tool developed by the No10
            Innovation Fellowship Scheme. Once completed it's intended to be an
            add-on to the existing Best Start In Life website:{" "}
            <a
              href="https://beststartinlife.gov.uk"
              className="text-purple-800 underline hover:text-purple-600 transition-colors"
            >
              beststartinlife.gov.uk
            </a>
            . The link you followed will eventually take you back into that
            content.
          </p>
        </div>
      </Container>
    </>
  );
}

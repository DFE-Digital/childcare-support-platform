import { Container } from "./Container";
import { ExternalLink } from "@/components/ui/ExternalLink";
import logoDark from "@/assets/logo-dark.webp";
import copyrightLogo from "@/assets/copyright-logo.png";

const moreLinks = [
  {
    label: "Partner resources",
    href: "https://beststartinlife.gov.uk/partners-resources/",
  },
  { label: "Cookies", href: "https://beststartinlife.gov.uk/cookies/" },
  {
    label: "Accessibility",
    href: "https://beststartinlife.gov.uk/accessibility/",
  },
  {
    label: "Terms & Conditions",
    href: "https://beststartinlife.gov.uk/terms-conditions/",
  },
  {
    label: "Privacy Policy",
    href: "https://www.gov.uk/government/organisations/department-for-education/about/personal-information-charter",
  },
  { label: "Cymraeg", href: "https://beststartinlife.gov.uk/cymraeg/" },
];

const bodyTextScale =
  "text-lg lg:text-[1.1875rem] xl:text-xl 3xl:text-[1.3125rem] leading-[1.4]";
const headingScale =
  "text-[1.3125rem] lg:text-[1.375rem] xl:text-2xl 3xl:text-[1.625rem] leading-[1.2]";
const straplineScale =
  "text-[1.3125rem] lg:text-[1.375rem] xl:text-2xl 3xl:text-[1.625rem] leading-[1.3]";

export function Footer() {
  const pageUrl = typeof window !== "undefined" ? window.location.href : "";

  return (
    <footer className="bg-neutral-700 text-white py-16 md:py-20">
      <Container>
        <a
          className="mb-8 block"
          href="https://beststartinlife.gov.uk/"
          title="Best Start in Life"
        >
          <img
            src={logoDark}
            alt="Best Start in Life logo"
            className="h-[54px] w-auto"
            loading="lazy"
          />
        </a>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {/* Strapline */}
          <div className={straplineScale}>
            <p>Advice and support for your child's development.</p>
          </div>

          {/* More links */}
          <div>
            <h3 className={`font-bold ${headingScale} mb-4`}>More</h3>
            <ul className={`space-y-3 ${bodyTextScale}`}>
              {moreLinks.map((link) => (
                <li key={link.label}>
                  <a href={link.href} className="underline hover:opacity-80">
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Newsletter */}
          <div>
            <h3 className={`font-bold ${headingScale} mb-4`}>
              The parent newsletter: news, updates and support
            </h3>
            <p className="text-base leading-[1.4] mb-4">
              A regular newsletter with the latest updates, news and
              announcements about government support available for
              parents.&nbsp;Great for staying informed.
            </p>
            <a
              href="https://beststartinlife.gov.uk/the-parent-newsletter/"
              className={`inline-block border-2 border-white text-white font-bold ${bodyTextScale} px-6 py-3 rounded-full hover:bg-white hover:text-neutral-700 transition-colors`}
            >
              Sign up
            </a>
          </div>

          {/* Share + Crown copyright */}
          <div className={`lg:text-right ${bodyTextScale}`}>
            <h3 className={`font-bold ${headingScale} mb-4`}>
              Share this page
            </h3>
            <p className="mb-3">
              <ExternalLink
                href={`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(pageUrl)}&title=Best+Start+in+Life`}
                showIcon={false}
                className="underline hover:opacity-80"
              >
                Facebook
              </ExternalLink>
            </p>
            <p className="mb-3">
              <ExternalLink
                href={`https://twitter.com/intent/tweet?text=Best+Start+in+Life+${encodeURIComponent(pageUrl)}`}
                showIcon={false}
                className="underline hover:opacity-80"
              >
                X
              </ExternalLink>
            </p>
            <p className="mb-3">
              <ExternalLink
                href={`mailto:?body=${encodeURIComponent(pageUrl)}`}
                showIcon={false}
                className="underline hover:opacity-80"
              >
                Email
              </ExternalLink>
            </p>
            <div className="h-9" aria-hidden="true" />
            <img
              src={copyrightLogo}
              alt="Crown copyright"
              className="w-[92px] lg:ml-auto"
              loading="lazy"
            />
          </div>
        </div>
      </Container>
    </footer>
  );
}

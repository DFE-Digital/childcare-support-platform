import { Container } from "./Container";
import { Breadcrumb } from "./Breadcrumb";

interface PageHeroProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: Array<{ label: string; to?: string }>;
  date?: string;
}

const ROOT_BREADCRUMBS = [
  { label: "Best Start in Life", to: "https://beststartinlife.gov.uk/" },
  { label: "Childcare Checker", to: "/" },
];

export function PageHero({
  title,
  subtitle,
  breadcrumbs,
  date,
}: PageHeroProps) {
  const pageCrumbs = breadcrumbs ?? [];
  const allBreadcrumbs =
    pageCrumbs.length > 0
      ? [...ROOT_BREADCRUMBS, ...pageCrumbs]
      : [
          {
            label: "Best Start in Life",
            to: "https://beststartinlife.gov.uk/",
          },
          { label: "Childcare Checker" },
        ];

  return (
    <div id="page-hero" className="bg-neutral-700 text-white py-12 md:py-20">
      <Container>
        <div className="lg:text-center">
          <div className="max-w-[640px] mx-auto">
            <Breadcrumb items={allBreadcrumbs} />
            <h1
              id="main-content"
              tabIndex={-1}
              className="text-[35px] md:text-[44px] xl:text-[54px] 2xl:text-[66px] font-bold leading-tight outline-none"
            >
              {title}
            </h1>
            {subtitle && (
              <p className="mt-4 text-lg md:text-xl opacity-90">{subtitle}</p>
            )}
            {date && <p className="mt-3 text-base opacity-70">{date}</p>}
          </div>
        </div>
      </Container>
    </div>
  );
}

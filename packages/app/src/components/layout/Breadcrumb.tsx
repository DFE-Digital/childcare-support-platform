import { Link } from "react-router-dom";

interface BreadcrumbItem {
  label: string;
  to?: string;
}

const ChevronRight = () => (
  <span className="inline-block mx-1" aria-hidden="true">
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
  </span>
);

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  const isExternal = (url: string) => url.startsWith("http");

  return (
    <nav aria-label="Breadcrumb" className="text-base mb-4">
      <ol className="flex items-center gap-1 flex-wrap lg:justify-center">
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-1">
            {item.to ? (
              isExternal(item.to) ? (
                <a
                  href={item.to}
                  className="underline hover:no-underline opacity-80 hover:opacity-100"
                >
                  {item.label}
                </a>
              ) : (
                <Link
                  to={item.to}
                  className="underline hover:no-underline opacity-80 hover:opacity-100"
                >
                  {item.label}
                </Link>
              )
            ) : (
              <span aria-current="page" className="opacity-60">
                {item.label}
              </span>
            )}
            {i < items.length - 1 && <ChevronRight />}
          </li>
        ))}
      </ol>
    </nav>
  );
}

import type { Scheme } from "@/types/scheme";
import { isInternalUrl } from "@/lib/url";

interface SchemeCardProps {
  scheme: Scheme;
  note?: string;
  description?: string;
  caveats?: Array<{ text: string; type: "warn" | "info" }>;
}

const FINANCIAL_TYPES = [
  "funded_hours",
  "top_up",
  "reimbursement",
  "free_service",
] as const;

function isFinancialScheme(type: string): boolean {
  return (FINANCIAL_TYPES as readonly string[]).includes(type);
}

export function SchemeCard({
  scheme,
  note,
  description,
  caveats,
}: SchemeCardProps) {
  const financial = isFinancialScheme(scheme.financialType);

  return (
    <div className="bg-white rounded-xl border border-zinc-200 p-6 pl-8 relative overflow-hidden">
      <div
        className={`absolute left-0 top-0 bottom-0 w-1.5 ${financial ? "bg-green-600" : "bg-blue-600"}`}
      />
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <span
              className={`text-xs font-bold uppercase tracking-wide px-2 py-0.5 rounded text-center ${financial ? "text-green-700 bg-green-50" : "text-blue-700 bg-blue-50"}`}
            >
              {scheme.financialType === "funded_hours"
                ? "Funded Hours"
                : scheme.financialType === "top_up"
                  ? "Top Up"
                  : scheme.financialType === "reimbursement"
                    ? "Reimbursement"
                    : scheme.financialType === "free_service"
                      ? "Free Service"
                      : "Information"}
            </span>
            {note && <span className="text-xs text-zinc-500">{note}</span>}
          </div>
          <h3 className="font-bold text-lg mb-2">{scheme.name}</h3>
          <p className="text-sm text-zinc-600 leading-relaxed">
            {description ?? scheme.description}
          </p>
          {(caveats?.length || scheme.caveats.length > 0) && (
            <ul className="mt-3 space-y-1">
              {caveats?.map((c, i) => (
                <li
                  key={`d-${i}`}
                  className="text-xs text-zinc-600 flex items-baseline gap-1"
                >
                  <i
                    className={`bi shrink-0 ${c.type === "warn" ? "bi-exclamation-circle-fill" : "bi-dash"}`}
                  />
                  <span>{c.text}</span>
                </li>
              ))}
              {scheme.caveats.map((c, i) => (
                <li
                  key={`s-${i}`}
                  className="text-xs text-zinc-600 flex items-baseline gap-1"
                >
                  <i
                    className={`bi shrink-0 ${c.type === "warn" ? "bi-exclamation-circle-fill" : "bi-dash"}`}
                  />
                  <span>{c.text}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="shrink-0 flex flex-col min-[390px]:flex-row-reverse md:flex-col items-center min-[390px]:justify-center gap-2">
          {scheme.links.info && (
            <a
              href={scheme.links.info}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-dark text-sm py-2 px-4 inline-flex items-center gap-2"
            >
              Learn more{" "}
              {isInternalUrl(scheme.links.info) ? (
                <span aria-hidden="true">&rarr;</span>
              ) : (
                <i className="bi bi-box-arrow-up-right" aria-hidden="true" />
              )}
              <span className="sr-only">(opens in new tab)</span>
            </a>
          )}
          {scheme.links.apply && (
            <a
              href={scheme.links.apply}
              target="_blank"
              rel="noopener noreferrer"
              className="btn text-sm py-2 px-4 inline-flex items-center gap-2"
            >
              Apply now{" "}
              <i className="bi bi-box-arrow-up-right" aria-hidden="true" />
              <span className="sr-only">(opens in new tab)</span>
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

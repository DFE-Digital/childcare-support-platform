import type { Scheme } from "@/types/scheme";
import { isInternalUrl } from "@/lib/url";

interface FutureSchemeCardProps {
  scheme: Scheme;
  reason: string;
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

export function FutureSchemeCard({ scheme, reason }: FutureSchemeCardProps) {
  const financial = isFinancialScheme(scheme.financialType);

  const href = scheme.links.info;

  return (
    <div className="bg-white rounded-xl border border-zinc-200 p-6 pl-8 relative overflow-hidden">
      <div
        className={`absolute left-0 top-0 bottom-0 w-1.5 ${financial ? "bg-green-600" : "bg-blue-600"}`}
      />
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
        </div>
        <h3 className="font-bold text-lg mb-2">{scheme.name}</h3>
        <p className="text-sm text-zinc-600 leading-relaxed">
          {scheme.description}
        </p>
        <p className="text-sm text-green-700 font-medium mt-1">{reason}</p>
        {href && (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-700 no-underline hover:underline inline-flex items-center gap-1 mt-2"
          >
            Learn more
            {isInternalUrl(href) ? (
              <span aria-hidden="true">&rarr;</span>
            ) : (
              <i
                className="bi bi-box-arrow-up-right text-xs"
                aria-hidden="true"
              />
            )}
            <span className="sr-only">(opens in new tab)</span>
          </a>
        )}
      </div>
    </div>
  );
}

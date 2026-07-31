import type { ReactNode } from "react";
import { CostBar } from "@/components/ui/CostBar";
import { ExternalLink } from "@/components/ui/ExternalLink";
import type { SupportEntry, FamilyTotal } from "@bsil/calculator";

function fmt(n: number): string {
  return n.toLocaleString("en-GB", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

function SupportRow({
  entry,
  testId,
  divisor = 1,
}: {
  entry: SupportEntry;
  testId?: string;
  divisor?: number;
}) {
  if (entry.savingToParent === 0) return null;
  return (
    <div className="flex justify-between gap-4">
      <span className="text-green-700">{entry.scheme}</span>
      <span
        className="font-bold text-green-700 whitespace-nowrap"
        data-testid={testId}
        aria-label={`minus £${fmt(entry.savingToParent / divisor)}`}
      >
        −£{fmt(entry.savingToParent / divisor)}
      </span>
    </div>
  );
}

export function FamilyTotalSummary({
  familyTotal,
  costRange,
  hasFreeBreakfastClub,
  title,
  familyPaysLabel,
  period,
  onPeriodChange,
}: {
  familyTotal: FamilyTotal;
  costRange?: { lower: number; upper: number };
  hasFreeBreakfastClub?: boolean;
  title?: ReactNode;
  familyPaysLabel?: ReactNode;
  period: "yearly" | "monthly";
  onPeriodChange: (p: "yearly" | "monthly") => void;
}) {
  if (!familyTotal) return null;

  const d = period === "monthly" ? 12 : 1;
  const periodLabel = period === "monthly" ? "monthly" : "annual";

  const {
    totalCostOfChildcare,
    totalGovernmentSupport,
    estimatedAnnualCostToFamily,
  } = familyTotal;
  const totalCost = totalCostOfChildcare.total;
  const govSaving = totalGovernmentSupport.totalSavingToParent;
  const familyPays = estimatedAnnualCostToFamily;
  const showRange = costRange != null && costRange.lower !== costRange.upper;

  return (
    <div className="bg-white rounded-xl border border-zinc-200 p-6 mb-8">
      {/* Headline figure */}
      <div className="bg-neutral-700 text-white rounded-xl p-6 mb-6">
        <div
          className={
            showRange
              ? "grid grid-cols-1 md:grid-cols-2 gap-2 md:gap-6 items-start"
              : ""
          }
        >
          <div>
            <p className="text-sm font-bold mb-2">
              {title ?? `Estimated ${periodLabel} cost to your family`}
            </p>
            <p
              className="text-5xl md:text-6xl font-bold"
              data-testid="family-pays-headline"
            >
              £{fmt(familyPays / d)}
            </p>
            <p className="text-sm opacity-80 mt-2">After government support</p>
            {!showRange && (
              <div className="mt-3">
                <div className="inline-flex rounded-full border border-white/40 text-sm">
                  <button
                    className={`rounded-full px-3 py-1 transition-all duration-200 ${period === "monthly" ? "bg-white text-neutral-700 font-bold" : "opacity-70 hover:opacity-100"}`}
                    onClick={() => onPeriodChange("monthly")}
                    aria-pressed={period === "monthly"}
                  >
                    Monthly
                  </button>
                  <button
                    className={`rounded-full px-3 py-1 transition-all duration-200 ${period === "yearly" ? "bg-white text-neutral-700 font-bold" : "opacity-70 hover:opacity-100"}`}
                    onClick={() => onPeriodChange("yearly")}
                    aria-pressed={period === "yearly"}
                  >
                    Yearly
                  </button>
                </div>
              </div>
            )}
          </div>
          {showRange && (
            <div data-testid="cost-range-message">
              <p className="text-sm opacity-80 mb-2">
                Providers&apos; fees and services vary, we think {periodLabel}{" "}
                costs near you are likely to be between:
              </p>
              <p className="text-2xl md:text-3xl font-bold">
                <span data-testid="cost-range-lower">
                  £{fmt(costRange.lower / d)}
                </span>{" "}
                &ndash;{" "}
                <span data-testid="cost-range-upper">
                  £{fmt(costRange.upper / d)}
                </span>
              </p>
              <div className="mt-3">
                <div className="inline-flex rounded-full border border-white/40 text-sm">
                  <button
                    className={`rounded-full px-3 py-1 transition-all duration-200 ${period === "monthly" ? "bg-white text-neutral-700 font-bold" : "opacity-70 hover:opacity-100"}`}
                    onClick={() => onPeriodChange("monthly")}
                    aria-pressed={period === "monthly"}
                  >
                    Monthly
                  </button>
                  <button
                    className={`rounded-full px-3 py-1 transition-all duration-200 ${period === "yearly" ? "bg-white text-neutral-700 font-bold" : "opacity-70 hover:opacity-100"}`}
                    onClick={() => onPeriodChange("yearly")}
                    aria-pressed={period === "yearly"}
                  >
                    Yearly
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Cost bar */}
      <div className="mb-6">
        <CostBar
          total={totalCost / d}
          governmentSupport={govSaving / d}
          familyPays={familyPays / d}
        />
      </div>

      {/* Breakdown */}
      <div className="space-y-1 text-base">
        <div className="flex justify-between gap-4">
          <span>Total childcare costs</span>
          <span className="font-bold" data-testid="family-total-cost">
            £{fmt(totalCost / d)}
          </span>
        </div>

        {totalGovernmentSupport.fundedHours && (
          <SupportRow
            entry={totalGovernmentSupport.fundedHours}
            testId="family-support-funded-hours"
            divisor={d}
          />
        )}
        {totalGovernmentSupport.taxFreeChildcare && (
          <SupportRow
            entry={totalGovernmentSupport.taxFreeChildcare}
            testId="family-support-tfc"
            divisor={d}
          />
        )}
        {totalGovernmentSupport.ucChildcare && (
          <SupportRow
            entry={totalGovernmentSupport.ucChildcare}
            testId="family-support-uc"
            divisor={d}
          />
        )}
        {hasFreeBreakfastClub && (
          <div className="flex justify-between gap-4">
            <span className="text-green-700">Free breakfast club</span>
            <span className="font-bold text-green-700 whitespace-nowrap">
              £{fmt(0)}
            </span>
          </div>
        )}

        <div className="flex justify-between gap-4 py-3 border-t-2 border-neutral-700 text-xl font-bold">
          <span>{familyPaysLabel ?? "Estimated cost"}</span>
          <span data-testid="family-pays">£{fmt(familyPays / d)}</span>
        </div>
        {totalGovernmentSupport.ucChildcare &&
          totalGovernmentSupport.ucChildcare.savingToParent > 0 && (
            <p className="text-base text-green-700 mt-2 mb-6 max-w-prose">
              Universal Credit childcare pays up to 85% of eligible childcare
              costs. But this depends on your circumstances, you may receive
              less. Find out more by using a{" "}
              <ExternalLink
                href="https://www.gov.uk/benefits-calculators"
                className="underline"
              >
                benefits calculator
              </ExternalLink>
            </p>
          )}
        <p className="text-xs text-zinc-600 mt-2 max-w-prose">
          This is an estimated cost. Your entitlement to government support is
          subject to confirmation during the application process. Any fees used
          in these calculations must be confirmed directly with the provider.
          Area averages should be treated as rough estimates only. Your
          childcare provider might offer optional chargeable extras, such as
          nappies, suncream, food and snacks, or additional classes or services.
          Purchasing these is voluntary. Choosing to purchase these extras would
          increase childcare costs. Your provider might also offer extra
          childcare hours, in addition to those accessed through the
          entitlements, which would also increase your costs. Please speak to
          your provider for more information.
        </p>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { usePostHog } from "posthog-js/react";
import { useFamily } from "@/hooks/useFamily";
import { usePostcodeLookup } from "@/hooks/usePostcodeLookup";
import { featureFlags } from "@/hooks/useFeatureFlags";
import * as analytics from "@/lib/analytics";
import { resolveTemplate } from "@/lib/resolveTemplate";
import {
  areAllChildrenBigKids,
  BIG_KID_MONTHS,
  getChildAgeMonths,
} from "@/lib/childAge";
import { formatHoursMinutes } from "@/lib/formatHours";
import { resolveFormData } from "@/types/formData";
import { calculateEntitlements, calculateCostRange } from "@bsil/calculator";
import type { CostRangeResult, FeeSource, Scheme } from "@bsil/calculator";
import {
  ChildCostBreakdown,
  careTypeLabel,
  areaExplanation,
} from "./ChildCostBreakdown";
import { formatAge } from "@/lib/childAge";
import { FamilyTotalSummary } from "./FamilyTotalSummary";
import { Explainer } from "@/components/ui/Explainer";

function boldNames(names: string[]): React.ReactNode {
  if (names.length === 0) return null;
  if (names.length === 1) return <strong>{names[0]}</strong>;
  return (
    <>
      {names.slice(0, -1).map((n, i) => (
        <span key={i}>
          {i > 0 && ", "}
          <strong>{n}</strong>
        </span>
      ))}
      {" and "}
      <strong>{names[names.length - 1]}</strong>
    </>
  );
}

export function CostResults({ footer }: { footer?: React.ReactNode }) {
  const { selectedFamily, schemes, areaCosts, getProviderById } = useFamily();
  // areaCosts here is derived from the family form postcode (home address), not from any
  // provider search the user may have performed. See FamilyContext.tsx for the loading logic.
  const navigate = useNavigate();
  const posthog = usePostHog();
  const { getGeo, ensureInward } = usePostcodeLookup();
  const emittedRef = useRef(false);

  const resolved = useMemo(() => {
    try {
      return resolveFormData(selectedFamily.localStorage);
    } catch (err) {
      console.error("[CostResults] resolveFormData failed:", err);
      return null;
    }
  }, [selectedFamily]);

  useEffect(() => {
    if (!resolved) navigate("/costs#main-content", { replace: true });
  }, [resolved, navigate]);

  const allBigKids =
    featureFlags.noBigKidEstimates &&
    resolved !== null &&
    areAllChildrenBigKids(resolved.children);

  const hasBigKids =
    featureFlags.noBigKidEstimates &&
    !allBigKids &&
    resolved !== null &&
    resolved.children.some(
      (c) => getChildAgeMonths(c.birthMonth, c.birthYear) >= BIG_KID_MONTHS,
    );

  const { smallKidIndices, bigKidIndices } = useMemo(() => {
    const small: number[] = [];
    const big: number[] = [];
    if (resolved && hasBigKids) {
      resolved.children.forEach((c, i) => {
        if (getChildAgeMonths(c.birthMonth, c.birthYear) >= BIG_KID_MONTHS) {
          big.push(i);
        } else {
          small.push(i);
        }
      });
    }
    return { smallKidIndices: small, bigKidIndices: big };
  }, [resolved, hasBigKids]);

  // Compute entitlements for big kid scheme display
  const entitlementResult = useMemo(() => {
    if (!hasBigKids || !resolved || schemes.length === 0) return null;
    try {
      return calculateEntitlements(resolved, schemes, new Date());
    } catch {
      return null;
    }
  }, [resolved, schemes, hasBigKids]);

  function getEligibleSchemesForChild(childId: number): Scheme[] {
    if (!entitlementResult) return [];
    const childResult = entitlementResult.children.find(
      (c) => c.childId === childId,
    );
    if (!childResult) return [];
    return childResult.schemes
      .filter((s) => s.eligible)
      .map((s) => schemes.find((sc) => sc.id === s.schemeId))
      .filter((s): s is Scheme => s !== undefined);
  }

  const [period, setPeriod] = useState<"yearly" | "monthly">("monthly");

  const result: CostRangeResult | null = useMemo(() => {
    if (!resolved || !selectedFamily || schemes.length === 0) return null;
    if (allBigKids) return null;

    // Step 1: run entitlements (same as SupportResults)
    const entitlements = calculateEntitlements(resolved, schemes, new Date());

    // Step 2: build providers array from cached providers referenced in selections
    const providerIds = new Set<string>();
    for (const child of resolved.children) {
      for (const sel of child.childcareSelections) {
        if (sel.providerId) providerIds.add(sel.providerId);
      }
    }
    const providers = [...providerIds]
      .map((id) => getProviderById(id))
      .filter((p): p is NonNullable<typeof p> => p !== undefined);

    // Step 3: run cost range calculator
    return calculateCostRange({
      data: resolved,
      schemes,
      entitlements,
      providers,
      areaCosts,
      referenceDate: new Date(),
      rounding: "nearest10",
      includeAdditionalCharges: !featureFlags.noAdditionalCharges,
    });
  }, [
    selectedFamily,
    schemes,
    areaCosts,
    getProviderById,
    resolved,
    allBigKids,
  ]);

  useEffect(() => {
    if (!posthog || !result || !resolved || emittedRef.current) return;
    if (schemes.length === 0) return;
    emittedRef.current = true;

    const formData = selectedFamily.localStorage;
    const [outward, inward] = (formData.location.postcode || " ").split(" ");

    (async () => {
      if (outward) await ensureInward(outward);
      const geo = getGeo(outward, inward);

      const eligibleSchemes = new Set<string>();
      try {
        const entitlements = calculateEntitlements(
          resolved,
          schemes,
          new Date(),
        );
        for (const child of entitlements.children) {
          for (const s of child.schemes) {
            if (s.eligible) eligibleSchemes.add(s.schemeId);
          }
        }
      } catch {
        // If entitlement calc fails, emit without schemes
      }

      posthog.capture("schemes_eligible", {
        ...analytics.getLocationProps(formData, geo?.deprivationDecile),
        ...analytics.getPartnerProps(formData),
        ...analytics.getImmigrationProps(formData),
        ...analytics.getWorkingProps(formData),
        ...analytics.getBenefitsProps(formData),
        ...analytics.getChildrenProps(formData),
        ...analytics.getChildcareProps(formData),
        schemes: [...eligibleSchemes].sort(),
        form: "costs",
      });
    })();
  }, [
    posthog,
    result,
    resolved,
    schemes,
    selectedFamily,
    getGeo,
    ensureInward,
  ]);

  if (allBigKids) {
    return (
      <p className="text-base text-zinc-600 max-w-prose">
        Unfortunately, we can&rsquo;t provide a cost estimate for older children
        at the moment. We don&rsquo;t currently have reliable average cost data
        for children aged 5 and over. You should contact childcare providers
        directly to see how much they charge.
      </p>
    );
  }

  if (!resolved || !selectedFamily || !result) return null;

  const isUC = resolved.qualifyingBenefits.includes("universal_credit");
  const showRange = result.range.lower !== result.range.upper;

  const smallKidNames = hasBigKids
    ? boldNames(smallKidIndices.map((i) => resolved.children[i].firstName))
    : null;

  const summaryTitle = smallKidNames ? (
    <>
      Estimated {period === "monthly" ? "monthly" : "annual"} cost for{" "}
      {smallKidNames}
    </>
  ) : undefined;

  const familyPaysLabel = smallKidNames ? (
    <>For {smallKidNames} you pay</>
  ) : undefined;

  return (
    <div>
      <FamilyTotalSummary
        familyTotal={result.mean.familyTotal}
        costRange={result.range}
        hasFreeBreakfastClub={result.mean.children.some((child) =>
          [
            ...(child.selections ?? []),
            ...(child.termTimeCare?.selections ?? []),
            ...(child.yearRoundCare?.selections ?? []),
          ].some((s) => s.careType === "free_breakfast_club"),
        )}
        title={summaryTitle}
        familyPaysLabel={familyPaysLabel}
        period={period}
        onPeriodChange={setPeriod}
      />

      {/* Child breakdowns: when hasBigKids, show only small kids; otherwise show all */}
      {(hasBigKids
        ? smallKidIndices
        : result.mean.children.map((_, i) => i)
      ).map((idx) => (
        <ChildCostBreakdown
          key={idx}
          childData={result.mean.children[idx]}
          inputChild={resolved.children[idx]}
          isUC={isUC}
          period={period}
        />
      ))}

      {/* Big kid panels */}
      {bigKidIndices.map((idx) => {
        const child = resolved.children[idx];
        const name = child.firstName;
        const eligibleSchemes = getEligibleSchemesForChild(child.id);
        return (
          <div
            key={idx}
            className="bg-white rounded-xl border border-zinc-200 p-6 mb-6"
          >
            <h2 className="font-bold text-xl mb-4 capitalize">
              For {name} ({formatAge(child.birthMonth, child.birthYear)})
            </h2>
            <p className="text-sm text-zinc-700 max-w-prose">
              Unfortunately, we can&rsquo;t provide a cost estimate for{" "}
              <strong>{name}</strong> at the moment. We don&rsquo;t currently
              have reliable average cost data for children aged 5 and over. You
              should contact childcare providers directly to see how much they
              charge.
            </p>
            {eligibleSchemes.length > 0 && (
              <>
                <p className="text-sm text-zinc-700 mt-3 max-w-prose">
                  However, <strong>{name}</strong> may still be eligible for a
                  range of government support:
                </p>
                <ul className="list-disc pl-5 space-y-1 mt-1">
                  {eligibleSchemes.map((scheme) => (
                    <li key={scheme.id} className="text-sm text-zinc-700">
                      <strong>{scheme.name}</strong> &mdash;{" "}
                      {resolveTemplate(
                        scheme.description,
                        scheme.defaultDescriptionParams,
                      )}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        );
      })}

      {footer}

      {(() => {
        const allSelections = result.mean.children.flatMap((child) => [
          ...(child.selections ?? []),
          ...(child.termTimeCare?.selections ?? []),
          ...(child.yearRoundCare?.selections ?? []),
        ]);
        const uniqueRateExplainers = allSelections
          .filter(
            (sel) =>
              sel.feeSource.rateDetails && sel.feeSource.rateDetails.length > 0,
          )
          .reduce<{ careType: string; feeSource: FeeSource }[]>((acc, sel) => {
            if (!acc.some((e) => e.careType === sel.careType)) {
              acc.push({
                careType: sel.careType ?? "",
                feeSource: sel.feeSource,
              });
            }
            return acc;
          }, []);

        if (!showRange && uniqueRateExplainers.length === 0) return null;

        return (
          <div className="mt-8 space-y-3">
            {showRange && (
              <Explainer label="Why have you calculated a cost range?">
                <p>Childcare costs and services vary between providers.</p>
                <p>
                  To give you the best idea, we use average childcare costs from
                  the DfE Early Years Childcare Provider Survey (2025) to
                  estimate what you might pay in your area.
                </p>
                <p>
                  Where we can, we calculate an estimate of the likely cost
                  range for your local authority.
                </p>
                <p>
                  Where there are insufficient responses, we use regional or
                  national calculations.
                </p>
                <p>
                  Because the way some of your government entitlements are
                  applied depend on the actual childcare costs, we then
                  calculate a full estimate for these lower and upper bounds.
                </p>
              </Explainer>
            )}
            {uniqueRateExplainers.map(({ careType, feeSource }) => (
              <Explainer
                key={careType}
                label={`How were my ${careTypeLabel(careType)} costs calculated?`}
              >
                <p>
                  These figures are based on data from the DfE Early Years
                  Childcare Provider Survey (2025), which collects cost
                  information from childcare providers across England.
                </p>
                <p>{areaExplanation(feeSource)}</p>
                <p>
                  The table below shows the range of rates used in our
                  calculations. The <strong>lower</strong> and{" "}
                  <strong>upper</strong> represent a likely range of costs. They
                  aren&apos;t the absolute highest and lowest costs in your
                  area. The <strong>average</strong> is a weighted mean rate,
                  which gives you a best estimate.
                </p>
                <p>
                  You should always check with local providers directly to get
                  the best possible estimate of your costs.
                </p>
                <table className="w-full text-sm">
                  <caption className="sr-only">Area fee rates</caption>
                  <thead>
                    <tr className="border-b border-zinc-200 text-left">
                      <th className="py-1 pr-2 font-semibold">Rate</th>
                      <th className="py-1 pr-2 font-semibold text-right">
                        Lower
                      </th>
                      <th className="py-1 pr-2 font-semibold text-right">
                        Average
                      </th>
                      <th className="py-1 font-semibold text-right">Upper</th>
                    </tr>
                  </thead>
                  <tbody>
                    {feeSource.rateDetails!.map((rd, i) => (
                      <tr key={i} className="border-b border-zinc-100">
                        <td className="py-1 pr-2">{rd.label}</td>
                        <td className="py-1 pr-2 text-right">
                          £{rd.lower.toFixed(2)}
                        </td>
                        <td className="py-1 pr-2 text-right font-medium">
                          £{rd.mean.toFixed(2)}
                        </td>
                        <td className="py-1 text-right">
                          £{rd.upper.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {feeSource.sessionHours && (
                  <>
                    <p>
                      Session rates are calculated from average hourly rates
                      using typical session durations:
                    </p>
                    <table className="w-full text-sm">
                      <caption className="sr-only">Session durations</caption>
                      <thead>
                        <tr className="border-b border-zinc-200 text-left">
                          <th className="py-1 pr-2 font-semibold">Session</th>
                          <th className="py-1 font-semibold text-right">
                            Hours
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b border-zinc-100">
                          <td className="py-1 pr-2">Morning</td>
                          <td className="py-1 text-right">
                            {formatHoursMinutes(feeSource.sessionHours.morning)}
                          </td>
                        </tr>
                        <tr className="border-b border-zinc-100">
                          <td className="py-1 pr-2">Afternoon</td>
                          <td className="py-1 text-right">
                            {formatHoursMinutes(
                              feeSource.sessionHours.afternoon,
                            )}
                          </td>
                        </tr>
                        {feeSource.sessionHours.fullDay != null && (
                          <tr className="border-b border-zinc-100">
                            <td className="py-1 pr-2">Full day</td>
                            <td className="py-1 text-right">
                              {formatHoursMinutes(
                                feeSource.sessionHours.fullDay,
                              )}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </>
                )}
              </Explainer>
            ))}
          </div>
        );
      })()}
    </div>
  );
}

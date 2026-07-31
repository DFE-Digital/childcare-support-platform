import type { LocalStorageData } from "../types/family.js";
import type { Scheme } from "../types/scheme.js";
import type {
  SchemeTransition,
  ChildTimeline,
  TimelineResult,
  TransitionDirection,
} from "../types/timeline.js";
import { calculateEntitlements } from "./calculate.js";
import { getChildAgeInMonths } from "./helpers.js";

/**
 * Detect eligibility transitions over the next `horizonMonths` months.
 *
 * Uses a monthly sweep: samples entitlements on the 1st of each month
 * and diffs against the baseline at `referenceDate`. Birth data is
 * month-granularity and all scheme cutoffs fall on the 1st, so monthly
 * sampling captures every transition exactly.
 */
export function calculateTimeline(
  data: LocalStorageData,
  schemes: Scheme[],
  referenceDate: Date,
  horizonMonths: number = 12,
): TimelineResult {
  const baseline = calculateEntitlements(data, schemes, referenceDate);

  // Build map of baseline eligibility per child per scheme
  const baselineMap: Map<number, Map<string, boolean>> = new Map();
  for (const child of baseline.children) {
    const schemeMap = new Map<string, boolean>();
    for (const s of child.schemes) {
      schemeMap.set(s.schemeId, s.eligible);
    }
    baselineMap.set(child.childId, schemeMap);
  }

  // Sample the 1st of each month within the horizon
  const sampleDates: Date[] = [];
  const refYear = referenceDate.getFullYear();
  const refMonth = referenceDate.getMonth(); // 0-based
  for (let i = 1; i <= horizonMonths; i++) {
    const d = new Date(refYear, refMonth + i, 1);
    sampleDates.push(d);
  }

  // Track earliest transition per child per scheme per direction
  type TransitionKey = string; // "childId:schemeId:direction"
  const found = new Map<TransitionKey, SchemeTransition>();

  for (const sampleDate of sampleDates) {
    const result = calculateEntitlements(data, schemes, sampleDate);

    for (const childResult of result.children) {
      const childBaseline = baselineMap.get(childResult.childId);
      if (!childBaseline) continue;

      const child = data.children.find((c) => c.id === childResult.childId);
      if (!child) continue;

      for (const scheme of childResult.schemes) {
        const wasEligible = childBaseline.get(scheme.schemeId) ?? false;
        const isEligible = scheme.eligible;

        if (wasEligible === isEligible) continue;

        const direction: TransitionDirection = isEligible ? "gain" : "loss";
        const key = `${childResult.childId}:${scheme.schemeId}:${direction}`;

        // Keep only the earliest transition
        if (found.has(key)) continue;

        found.set(key, {
          schemeId: scheme.schemeId,
          direction,
          effectiveDate: sampleDate,
          effectiveDateLabel: sampleDate.toLocaleDateString("en-GB", {
            month: "long",
            year: "numeric",
          }),
          ageAtTransitionMonths: getChildAgeInMonths(child, sampleDate),
        });
      }
    }
  }

  // Group transitions by child
  const children: ChildTimeline[] = baseline.children.map((childResult) => {
    const childTransitions: SchemeTransition[] = [];
    for (const [key, transition] of found) {
      if (key.startsWith(`${childResult.childId}:`)) {
        childTransitions.push(transition);
      }
    }
    childTransitions.sort(
      (a, b) => a.effectiveDate.getTime() - b.effectiveDate.getTime(),
    );
    return {
      childId: childResult.childId,
      childName: childResult.childName,
      transitions: childTransitions,
    };
  });

  return { children };
}

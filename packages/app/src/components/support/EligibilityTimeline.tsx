import { useRef, useEffect, useState } from "react";
import type { Scheme } from "@/types/scheme";
import type { SchemeTransition } from "@bsil/calculator";
import { FutureSchemeCard } from "@/components/ui/FutureSchemeCard";
import { IneligibleSchemeCard } from "@/components/ui/IneligibleSchemeCard";
import { resolveTemplate } from "@/lib/resolveTemplate";

interface EligibilityTimelineProps {
  childName: string;
  transitions: SchemeTransition[];
  schemes: Scheme[];
}

interface TransitionGroup {
  dateLabel: string;
  ageLabel: string;
  transitions: SchemeTransition[];
}

function formatAgeFromMonths(months: number): string {
  const y = Math.floor(months / 12);
  const m = months % 12;
  if (y === 0) return `${m} month${m !== 1 ? "s" : ""}`;
  if (m === 0) return `${y} year${y !== 1 ? "s" : ""}`;
  return `${y} year${y !== 1 ? "s" : ""}, ${m} month${m !== 1 ? "s" : ""}`;
}

function groupByDate(transitions: SchemeTransition[]): TransitionGroup[] {
  const groups: TransitionGroup[] = [];
  for (const t of transitions) {
    const key = t.effectiveDate.getTime();
    const existing = groups.find(
      (g) => g.transitions[0].effectiveDate.getTime() === key,
    );
    if (existing) {
      existing.transitions.push(t);
    } else {
      groups.push({
        dateLabel: t.effectiveDateLabel,
        ageLabel: formatAgeFromMonths(t.ageAtTransitionMonths),
        transitions: [t],
      });
    }
  }
  return groups;
}

function renderCard(t: SchemeTransition, schemes: Scheme[], childName: string) {
  const scheme = schemes.find((s) => s.id === t.schemeId);
  if (!scheme) return null;
  const reason = resolveTransitionReason(scheme, t, childName);
  if (!reason) return null;
  return t.direction === "gain" ? (
    <FutureSchemeCard
      key={`${t.schemeId}-${t.direction}`}
      scheme={scheme}
      reason={reason}
    />
  ) : (
    <IneligibleSchemeCard
      key={`${t.schemeId}-${t.direction}`}
      scheme={scheme}
      reason={reason}
    />
  );
}

interface GroupMetrics {
  boxBottom: number;
  lastCardMid: number;
}

function measureGroup(el: HTMLElement): GroupMetrics {
  const box = el.querySelector<HTMLElement>("[data-timepoint-box]");
  const cards = el.querySelectorAll<HTMLElement>("[data-scheme-card]");
  const lastCard = cards[cards.length - 1];
  const containerRect = el.getBoundingClientRect();
  const boxBottom = box
    ? box.getBoundingClientRect().bottom - containerRect.top
    : 0;
  const lastCardMid = lastCard
    ? lastCard.getBoundingClientRect().top -
      containerRect.top +
      lastCard.getBoundingClientRect().height / 2
    : boxBottom;
  return { boxBottom, lastCardMid };
}

/** Measures timepoint box heights and card midpoints, re-measuring on resize. */
function useTimelineMetrics(groupCount: number) {
  const containerRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [metrics, setMetrics] = useState<GroupMetrics[]>([]);

  useEffect(() => {
    const els = containerRefs.current.filter(Boolean) as HTMLElement[];
    if (els.length === 0) return;

    function recalc() {
      setMetrics(els.map(measureGroup));
    }

    recalc();

    const ro = new ResizeObserver(recalc);
    for (const el of els) ro.observe(el);
    return () => ro.disconnect();
  }, [groupCount]);

  return { containerRefs, metrics };
}

export function EligibilityTimeline({
  childName,
  transitions,
  schemes,
}: EligibilityTimelineProps) {
  const groups = groupByDate(transitions).filter((group) =>
    group.transitions.some((t) => {
      const scheme = schemes.find((s) => s.id === t.schemeId);
      if (!scheme) return false;
      return !!scheme.transitionDescriptions?.[t.direction];
    }),
  );
  const { containerRefs, metrics } = useTimelineMetrics(groups.length);

  if (groups.length === 0) return null;

  return (
    <div className="mt-6">
      <h3 className="text-xl font-bold mb-4">But over the next year:</h3>
      <div className="space-y-0">
        {groups.map((group, groupIdx) => {
          const m = metrics[groupIdx];
          return (
            <div key={group.dateLabel}>
              {/* Desktop: grid layout with connecting lines */}
              <div
                className="hidden md:block relative"
                ref={(el) => {
                  containerRefs.current[groupIdx] = el;
                }}
              >
                {/* Vertical line: connects timepoint box to cards, and to adjacent groups */}
                {m && (
                  <div
                    className="absolute border-l-2 border-dashed border-zinc-300 w-0"
                    aria-hidden="true"
                    style={{
                      left: 110,
                      top: groupIdx === 0 ? m.boxBottom : 0,
                      ...(groupIdx === groups.length - 1
                        ? {
                            height:
                              m.lastCardMid -
                              (groupIdx === 0 ? m.boxBottom : 0),
                          }
                        : { bottom: 0 }),
                    }}
                  />
                )}

                <div className="grid grid-cols-[220px_1fr] gap-x-6">
                  {/* Left: timepoint box — z-10 so vertical line paints behind it */}
                  <div className="self-start relative z-10" data-timepoint-box>
                    <div className="bg-white border border-zinc-200 rounded-lg px-4 py-3 text-sm font-medium text-center">
                      When {childName} reaches {group.ageLabel}
                    </div>
                  </div>

                  {/* Right: scheme cards, pushed below the timepoint box */}
                  <div
                    className="space-y-3"
                    style={m ? { paddingTop: m.boxBottom } : undefined}
                  >
                    {group.transitions.map((t) => (
                      <div
                        key={`${t.schemeId}-${t.direction}`}
                        className="relative"
                        data-scheme-card
                      >
                        <div
                          className="absolute top-1/2 -translate-y-1/2 border-t-2 border-dashed border-zinc-300 h-0"
                          aria-hidden="true"
                          style={{ left: -134, width: 134 }}
                        />
                        {renderCard(t, schemes, childName)}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Desktop: vertical connector between groups */}
              {groupIdx < groups.length - 1 && (
                <div
                  className="hidden md:block relative h-6"
                  aria-hidden="true"
                >
                  <div
                    className="absolute border-l-2 border-dashed border-zinc-300 w-0 h-full"
                    style={{ left: 110 }}
                  />
                </div>
              )}

              {/* Mobile: single column */}
              <div className="md:hidden">
                <div className="bg-white border border-zinc-200 rounded-lg px-4 py-3 text-sm font-medium text-center">
                  When {childName} reaches {group.ageLabel}
                </div>
                <div className="mx-auto w-0.5 h-4 bg-zinc-300" />
                <div>
                  {group.transitions.map((t, i) => (
                    <div key={`${t.schemeId}-${t.direction}`}>
                      {i > 0 && (
                        <div className="mx-auto w-0.5 h-3 bg-zinc-300" />
                      )}
                      {renderCard(t, schemes, childName)}
                    </div>
                  ))}
                </div>
              </div>

              {/* Mobile: connector between groups */}
              {groupIdx < groups.length - 1 && (
                <div className="md:hidden mx-auto w-0.5 h-6 bg-zinc-300" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function resolveTransitionReason(
  scheme: Scheme,
  transition: SchemeTransition,
  childName: string,
): string | null {
  const template = scheme.transitionDescriptions?.[transition.direction];
  if (!template) return null;
  return resolveTemplate(template, {
    childName,
    date: transition.effectiveDateLabel,
    age: String(Math.floor(transition.ageAtTransitionMonths / 12)),
  });
}

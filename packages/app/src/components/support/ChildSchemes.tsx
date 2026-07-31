import type { Scheme } from "@/types/scheme";
import type {
  SchemeEntitlement,
  SchemeTransition,
  Caveat,
} from "@bsil/calculator";
import { SchemeCard } from "@/components/ui/SchemeCard";
import { EligibilityTimeline } from "./EligibilityTimeline";
import { resolveTemplate } from "@/lib/resolveTemplate";

interface ChildSchemesProps {
  childName: string;
  birthMonth?: number;
  birthYear?: number;
  eligibleSchemes: SchemeEntitlement[];
  schemes: Scheme[];
  caveatMessages: Record<string, { text: string; type: "warn" | "info" }>;
  transitions: SchemeTransition[];
}

function resolveCaveat(
  caveat: Caveat,
  messages: Record<string, { text: string; type: "warn" | "info" }>,
): { text: string; type: "warn" | "info" } {
  const message = messages[caveat.code];
  const text = resolveTemplate(message?.text ?? caveat.code, caveat.params);
  return { text, type: message?.type ?? "info" };
}

function formatAge(birthMonth: number, birthYear: number): string {
  const now = new Date();
  let years = now.getFullYear() - birthYear;
  if (now.getMonth() + 1 < birthMonth) years--;
  if (years < 1) {
    const months =
      (now.getFullYear() - birthYear) * 12 + (now.getMonth() + 1 - birthMonth);
    return months <= 1 ? "1 month" : `${months} months`;
  }
  return years === 1 ? "1 year old" : `${years} years old`;
}

export function ChildSchemes({
  childName,
  birthMonth,
  birthYear,
  eligibleSchemes,
  schemes,
  caveatMessages,
  transitions,
}: ChildSchemesProps) {
  const ageLabel =
    birthMonth !== undefined && birthYear !== undefined
      ? formatAge(birthMonth, birthYear)
      : undefined;
  if (eligibleSchemes.length === 0) {
    return (
      <div className="mb-8">
        <h2
          className="text-[27px] md:text-[31px] font-bold mb-4"
          aria-label={`Schemes for ${childName}${ageLabel ? ` (${ageLabel})` : ""}`}
        >
          Schemes for {childName}
          {ageLabel && (
            <>
              {" "}
              <span className="whitespace-nowrap">({ageLabel})</span>
            </>
          )}
        </h2>
        <div className="bg-white rounded-xl border border-zinc-200 p-6 pl-8 relative overflow-hidden">
          <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-orange-500" />
          <p className="text-base text-zinc-600">
            No government schemes are currently available for {childName} based
            on your family's circumstances.
          </p>
        </div>
        <EligibilityTimeline
          childName={childName}
          transitions={transitions}
          schemes={schemes}
        />
      </div>
    );
  }

  return (
    <div className="mb-8">
      <h2
        className="text-[27px] md:text-[31px] font-bold mb-4"
        aria-label={`Right now ${childName}${ageLabel ? ` (${ageLabel})` : ""} may be eligible for:`}
      >
        Right now {childName}
        {ageLabel && (
          <>
            {" "}
            <span className="whitespace-nowrap">({ageLabel})</span>
          </>
        )}{" "}
        may be eligible for:
      </h2>
      <div className="space-y-4">
        {eligibleSchemes.map((entitlement) => {
          const scheme = schemes.find((s) => s.id === entitlement.schemeId);
          if (!scheme) return null;
          return (
            <SchemeCard
              key={scheme.id}
              scheme={scheme}
              description={resolveTemplate(
                scheme.description,
                entitlement.descriptionParams,
              )}
              caveats={entitlement.caveats.map((c) =>
                resolveCaveat(c, caveatMessages),
              )}
            />
          );
        })}
      </div>
      <EligibilityTimeline
        childName={childName}
        transitions={transitions}
        schemes={schemes}
      />
    </div>
  );
}

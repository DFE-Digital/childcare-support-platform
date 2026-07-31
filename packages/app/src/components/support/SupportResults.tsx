import { useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { usePostHog } from "posthog-js/react";
import { useFamily } from "@/hooks/useFamily";
import { usePostcodeLookup } from "@/hooks/usePostcodeLookup";
import { resolveFormData } from "@/types/formData";
import { calculateEntitlements, calculateTimeline } from "@bsil/calculator";
import * as analytics from "@/lib/analytics";
import { ChildSchemes } from "./ChildSchemes";

export function SupportResults({
  form = "support",
}: {
  form?: "support" | "costs";
}) {
  const { selectedFamily, schemes, caveatMessages } = useFamily();
  const navigate = useNavigate();
  const posthog = usePostHog();
  const { getGeo, ensureInward } = usePostcodeLookup();
  const emittedRef = useRef(false);

  const resolved = useMemo(() => {
    try {
      return resolveFormData(selectedFamily.localStorage);
    } catch (err) {
      console.error("[SupportResults] resolveFormData failed:", err);
      return null;
    }
  }, [selectedFamily]);

  useEffect(() => {
    if (!resolved) navigate("/support#main-content", { replace: true });
  }, [resolved, navigate]);

  const result = useMemo(() => {
    if (!resolved || !selectedFamily || schemes.length === 0) return null;
    return calculateEntitlements(resolved, schemes, new Date());
  }, [selectedFamily, schemes, resolved]);

  const timeline = useMemo(() => {
    if (!resolved || schemes.length === 0) return null;
    return calculateTimeline(resolved, schemes, new Date());
  }, [resolved, schemes]);

  useEffect(() => {
    if (!posthog || !result || emittedRef.current) return;
    emittedRef.current = true;

    const formData = selectedFamily.localStorage;
    const [outward, inward] = (formData.location.postcode || " ").split(" ");

    (async () => {
      if (outward) await ensureInward(outward);
      const geo = getGeo(outward, inward);

      const eligibleSchemes = new Set<string>();
      for (const child of result.children) {
        for (const s of child.schemes) {
          if (s.eligible) eligibleSchemes.add(s.schemeId);
        }
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
        form,
      });
    })();
  }, [posthog, result, selectedFamily, getGeo, ensureInward, form]);

  if (!resolved || !selectedFamily || !result) return null;

  return (
    <div>
      {result.children.map((childResult) => {
        const eligible = childResult.schemes.filter((s) => s.eligible);
        const child = resolved.children.find(
          (c) => c.id === childResult.childId,
        );
        const childTimeline = timeline?.children.find(
          (c) => c.childId === childResult.childId,
        );
        return (
          <ChildSchemes
            key={childResult.childId}
            childName={childResult.childName}
            birthMonth={child?.birthMonth}
            birthYear={child?.birthYear}
            eligibleSchemes={eligible}
            schemes={schemes}
            caveatMessages={caveatMessages}
            transitions={childTimeline?.transitions ?? []}
          />
        );
      })}
    </div>
  );
}

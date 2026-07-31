import { usePostHog } from "posthog-js/react";
import { useCallback, useRef } from "react";
import type { FormLocalStorageData } from "@/types/formData";
import * as analytics from "@/lib/analytics";

export function useFormAnalytics(form: "support" | "costs") {
  const posthog = usePostHog();
  const iodDecileRef = useRef<number | undefined>(undefined);

  const setIodDecile = useCallback((d: number | undefined) => {
    iodDecileRef.current = d;
  }, []);

  const captureStep = useCallback(
    (step: string, formData: FormLocalStorageData) => {
      if (!posthog) return;
      const props: Record<string, unknown> = { step, form };

      switch (step) {
        case "postcode":
          Object.assign(
            props,
            analytics.getLocationProps(formData, iodDecileRef.current),
          );
          break;
        case "partner":
          Object.assign(props, analytics.getPartnerProps(formData));
          break;
        case "immigration":
          Object.assign(props, analytics.getImmigrationProps(formData));
          break;
        case "working":
          Object.assign(props, analytics.getWorkingProps(formData));
          break;
        case "benefits":
          Object.assign(props, analytics.getBenefitsProps(formData));
          break;
        case "children":
          Object.assign(props, analytics.getChildrenProps(formData));
          break;
        case "childcare":
          Object.assign(props, analytics.getChildcareProps(formData));
          break;
      }

      posthog.capture("step_completed", props);
    },
    [posthog, form],
  );

  return { captureStep, setIodDecile };
}

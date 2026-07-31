import {
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import type { Family } from "@/types/family";
import { normaliseFormData } from "@/types/formData";
import type { FormLocalStorageData } from "@/types/formData";
import type { Provider } from "@/types/provider";
import type { Scheme, DevolvedNationLink } from "@/types/scheme";
import type { PostcodeAreaCosts } from "@/types/costs";
import type { SisSchema } from "@/data/sisParser";
import { loadProvider, loadLaCosts, loadSisSchema } from "@/data/loader";
import schemesData from "@/data/schemes";
import { usePostcodeLookup } from "@/hooks/usePostcodeLookup";
import { FamilyContext } from "./familyContextValue";

const PERSISTENCE_ENABLED = import.meta.env.VITE_DISABLE_PERSISTENCE !== "true";

const LS_KEY_FORM = "bsil_form_data";
const LS_KEY_STEPS = "bsil_completed_steps";
const LS_KEY_SHORTLIST = "bsil_shortlisted_providers";
const LS_KEY_DISCLAIMER = "bsil_cost_disclaimer_ack";

function loadFromStorage<T>(key: string): T | null {
  if (!PERSISTENCE_ENABLED) return null;
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function saveToStorage(key: string, value: unknown): void {
  if (!PERSISTENCE_ENABLED) return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage full or unavailable — silently ignore
  }
}

function migrateWorkingStatus(status: string | null): string | null {
  if (!status) return status;
  const map: Record<string, string> = {
    earning_above_203_per_week: "earning_above_nmw",
    earning_above_173_per_week: "earning_above_nmw",
    earning_above_128_per_week: "earning_above_apprentice_nmw",
    earning_below_203_per_week: "earning_below_nmw",
    earning_below_173_per_week: "earning_below_nmw",
    earning_below_128_per_week: "earning_below_nmw",
  };
  return map[status] ?? status;
}

function migrateV5toV6(data: FormLocalStorageData): FormLocalStorageData {
  return {
    ...data,
    schemaVersion: 6,
    user: {
      ...data.user,
      workingStatus: migrateWorkingStatus(
        data.user.workingStatus,
      ) as FormLocalStorageData["user"]["workingStatus"],
    },
    partner: data.partner
      ? {
          ...data.partner,
          workingStatus: migrateWorkingStatus(
            data.partner.workingStatus,
          ) as FormLocalStorageData["user"]["workingStatus"],
        }
      : null,
  };
}

function migrateV6toV7(data: FormLocalStorageData): FormLocalStorageData {
  return { ...data, schemaVersion: 7 };
}

const BLANK_DATA: FormLocalStorageData = {
  schemaVersion: 7,
  location: { postcode: "", ladCodes: [] },
  household: { hasPartner: null },
  user: {
    isApprentice: null,
    firstYearApprentice: null,
    isSelfEmployed: null,
    selfEmployedLessThanTwelveMonths: null,
    ageBracket: null,
    workingStatus: null,
    receivesQualifyingAllowance: null,
    startingWorkNextMonth: null,
    hasLimitedCapacityForWork: null,
    hasNationalInsuranceNumber: null,
    residencyStatus: null,
    isStudying: null,
    studyLevel: null,
    isFullTimeStudent: null,
    courseIsPubliclyFunded: null,
    eligibleForStudentFinance: null,
  },
  partner: null,
  ucIncomeBelowThreshold: null,
  nrpfIncomeUnderThreshold: null,
  nrpfSavingsUnderLimit: null,
  qualifyingBenefits: null,
  children: [],
  shortlistedProviders: [],
};

export interface FamilyContextValue {
  selectedFamily: Family;
  schemes: Scheme[];
  caveatMessages: Record<string, { text: string; type: "warn" | "info" }>;
  devolvedNationLinks: DevolvedNationLink[];
  // Loaded from the family form postcode (selectedFamily.localStorage.location.postcode —
  // the user's home address). Used by the cost estimator and entitlement checker. Must not
  // be written to by the provider search page, which maintains its own local areaCosts — see
  // ProviderSearchPage.tsx. Keeping these separate ensures a provider search in a different
  // area cannot corrupt estimates for the user's actual location.
  areaCosts: PostcodeAreaCosts | null;
  sisSchema: SisSchema | null;
  loading: boolean;
  shortlistedProviders: string[];
  completedSteps: Record<string, boolean>;
  updateFamilyData: (data: FormLocalStorageData) => void;
  toggleShortlist: (providerId: string) => void;
  markStepCompleted: (key: string) => void;
  unmarkSteps: (keys: string[]) => void;
  resetSteps: () => void;
  getProviderById: (id: string) => Provider | undefined;
  isDisclaimerValid: boolean;
  acknowledgeDisclaimer: () => void;
}

function checkDisclaimerExpiry(acknowledgedAt: string | null): boolean {
  if (!acknowledgedAt) return false;
  const ackTime = new Date(acknowledgedAt).getTime();
  if (Number.isNaN(ackTime)) return false;
  const threeHoursLater = ackTime + 3 * 60 * 60 * 1000;
  const nextMidnight = new Date(acknowledgedAt);
  nextMidnight.setHours(24, 0, 0, 0);
  return Date.now() < Math.max(threeHoursLater, nextMidnight.getTime());
}

const savedFormData = loadFromStorage<FormLocalStorageData>(LS_KEY_FORM);
const migratedFormData = (() => {
  let data = savedFormData;
  if (data?.schemaVersion === 5) data = migrateV5toV6(data);
  if (data?.schemaVersion === 6) data = migrateV6toV7(data);
  return data;
})();
const schemaValid =
  migratedFormData?.schemaVersion === BLANK_DATA.schemaVersion;

export function FamilyProvider({ children }: { children: ReactNode }) {
  const [selectedFamily, setSelectedFamily] = useState<Family>(() => ({
    description: "",
    localStorage: (schemaValid ? migratedFormData : null) ?? BLANK_DATA,
  }));
  const [schemes] = useState<Scheme[]>(schemesData.schemes);
  const [caveatMessages] = useState<
    Record<string, { text: string; type: "warn" | "info" }>
  >(schemesData.caveatMessages);
  const [devolvedNationLinks] = useState<DevolvedNationLink[]>(
    schemesData.devolvedNationLinks ?? [],
  );
  const [areaCosts, setAreaCosts] = useState<PostcodeAreaCosts | null>(null);
  const [sisSchema, setSisSchema] = useState<SisSchema | null>(null);
  const [loading] = useState(false);
  const [shortlistedProviders, setShortlistedProviders] = useState<string[]>(
    () => loadFromStorage<string[]>(LS_KEY_SHORTLIST) ?? [],
  );
  const [completedSteps, setCompletedSteps] = useState<Record<string, boolean>>(
    () => {
      if (!schemaValid) return {};
      const steps =
        loadFromStorage<Record<string, boolean>>(LS_KEY_STEPS) ?? {};
      if (savedFormData?.schemaVersion === 5) {
        delete steps["Working situation"];
      }
      return steps;
    },
  );
  const [disclaimerAcknowledgedAt, setDisclaimerAcknowledgedAt] = useState<
    string | null
  >(
    () =>
      loadFromStorage<{ acknowledgedAt: string }>(LS_KEY_DISCLAIMER)
        ?.acknowledgedAt ?? null,
  );

  const [isDisclaimerValid, setIsDisclaimerValid] = useState(() =>
    checkDisclaimerExpiry(disclaimerAcknowledgedAt),
  );

  useEffect(() => {
    setIsDisclaimerValid(checkDisclaimerExpiry(disclaimerAcknowledgedAt));
  }, [disclaimerAcknowledgedAt]);

  const acknowledgeDisclaimer = useCallback(() => {
    const now = new Date().toISOString();
    setDisclaimerAcknowledgedAt(now);
    setIsDisclaimerValid(true);
  }, []);

  const providerCacheRef = useRef<Map<string, Provider>>(new Map());
  const { ensureInward, getLaCodes } = usePostcodeLookup();

  // Load SIS schema on mount + reconnect
  const loadInitialData = useCallback(() => {
    if (!sisSchema)
      loadSisSchema()
        .then(setSisSchema)
        .catch((err) =>
          console.error("[FamilyContext] loadSisSchema failed:", err),
        );
  }, [sisSchema]);

  useEffect(() => {
    loadInitialData();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (sisSchema) return;
    const onOnline = () => loadInitialData();
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [sisSchema, loadInitialData]);

  // Load per-LA cost/FIS data for the family's home postcode. This is the postcode the
  // user entered in the cost form and is the basis for cost estimates. The provider search
  // page has a separate effect for its own searched postcode — see ProviderSearchPage.tsx.
  useEffect(() => {
    const postcode = selectedFamily.localStorage.location.postcode;
    if (!postcode || !postcode.includes(" ")) return;

    const [outward, inward] = postcode.split(" ");
    if (!outward || !inward) return;

    let cancelled = false;

    (async () => {
      await ensureInward(outward);
      if (cancelled) return;

      const laCodes = getLaCodes(outward, inward);
      for (const code of laCodes) {
        if (cancelled) return;
        try {
          const costs = await loadLaCosts(code);
          if (cancelled) return;
          setAreaCosts(costs);
          return;
        } catch {
          continue;
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedFamily.localStorage.location.postcode, ensureInward, getLaCodes]);

  // Persist state to localStorage (when persistence is enabled)
  useEffect(() => {
    saveToStorage(LS_KEY_FORM, selectedFamily.localStorage);
  }, [selectedFamily.localStorage]);

  useEffect(() => {
    saveToStorage(LS_KEY_STEPS, completedSteps);
  }, [completedSteps]);

  useEffect(() => {
    saveToStorage(LS_KEY_SHORTLIST, shortlistedProviders);
  }, [shortlistedProviders]);

  useEffect(() => {
    if (disclaimerAcknowledgedAt) {
      saveToStorage(LS_KEY_DISCLAIMER, {
        acknowledgedAt: disclaimerAcknowledgedAt,
      });
    }
  }, [disclaimerAcknowledgedAt]);

  const markStepCompleted = useCallback((key: string) => {
    setCompletedSteps((prev) => ({ ...prev, [key]: true }));
  }, []);

  const unmarkSteps = useCallback((keys: string[]) => {
    setCompletedSteps((prev) => {
      const next = { ...prev };
      for (const k of keys) {
        if (k in next) next[k] = false;
      }
      return next;
    });
  }, []);

  const resetSteps = useCallback(() => {
    setCompletedSteps({});
  }, []);

  const updateFamilyData = useCallback((data: FormLocalStorageData) => {
    setSelectedFamily((prev) => ({
      ...prev,
      localStorage: normaliseFormData(data),
    }));
  }, []);

  const toggleShortlist = useCallback((providerId: string) => {
    setShortlistedProviders((prev) =>
      prev.includes(providerId)
        ? prev.filter((id) => id !== providerId)
        : [...prev, providerId],
    );
  }, []);

  const getProviderById = useCallback((id: string): Provider | undefined => {
    const cached = providerCacheRef.current.get(id);
    if (cached) return cached;
    // Trigger async load (result will be available on next call)
    loadProvider(id)
      .then((p) => providerCacheRef.current.set(id, p))
      .catch((err) =>
        console.error("[FamilyContext] loadProvider failed:", err),
      );
    return undefined;
  }, []);

  return (
    <FamilyContext.Provider
      value={{
        selectedFamily,
        schemes,
        caveatMessages,
        devolvedNationLinks,
        areaCosts,
        sisSchema,
        loading,
        shortlistedProviders,
        completedSteps,
        updateFamilyData,
        toggleShortlist,
        markStepCompleted,
        unmarkSteps,
        resetSteps,
        getProviderById,
        isDisclaimerValid,
        acknowledgeDisclaimer,
      }}
    >
      {children}
    </FamilyContext.Provider>
  );
}

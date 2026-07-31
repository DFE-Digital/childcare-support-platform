import type { FormLocalStorageData } from "@/types/formData";

export function getLocationProps(
  formData: FormLocalStorageData,
  iodDecile?: number,
) {
  return {
    lad25cd:
      formData.location.ladCodes.find((c) => c.startsWith("E")) ??
      formData.location.ladCodes[0] ??
      null,
    iod_decile: iodDecile ?? null,
  };
}

export function getPartnerProps(formData: FormLocalStorageData) {
  return { has_partner: formData.household.hasPartner ?? false };
}

export function getImmigrationProps(formData: FormLocalStorageData) {
  const status = formData.user.residencyStatus;
  const settled = ["british_irish_citizen", "settled_status"].includes(
    status ?? "",
  );
  return { settled_in_uk: settled };
}

export function getWorkingProps(formData: FormLocalStorageData) {
  const userWorking =
    formData.user.workingStatus !== "not_working" &&
    formData.user.workingStatus !== null;
  const partnerWorking =
    formData.partner?.workingStatus !== "not_working" &&
    formData.partner?.workingStatus !== null &&
    formData.partner?.workingStatus !== undefined;
  return {
    working: userWorking || partnerWorking,
    is_studying: formData.user.isStudying ?? false,
  };
}

export function getBenefitsProps(formData: FormLocalStorageData) {
  const benefits = formData.qualifyingBenefits ?? [];
  return {
    receives_benefits: benefits.length > 0 && !benefits.includes("none"),
  };
}

export function getChildrenProps(formData: FormLocalStorageData) {
  const children = formData.children;
  const count = Math.min(children.length, 3) as 1 | 2 | 3;
  const now = new Date();
  const ages = children
    .filter((c) => c.birthYear != null && c.birthMonth != null)
    .map(
      (c) =>
        (now.getFullYear() - c.birthYear!) * 12 +
        (now.getMonth() + 1 - c.birthMonth!),
    );
  const youngestMonths = ages.length > 0 ? Math.min(...ages) : null;
  const youngest_band: "0-4" | "5+" =
    youngestMonths !== null && youngestMonths < 60 ? "0-4" : "5+";
  return { child_count: count || 1, youngest_band };
}

export function getChildcareProps(formData: FormLocalStorageData) {
  const types = new Set<string>();
  for (const child of formData.children) {
    for (const sel of child.childcareSelections ?? []) {
      if (sel.careType) types.add(sel.careType);
    }
  }
  return { care_types_sought: [...types].sort() };
}

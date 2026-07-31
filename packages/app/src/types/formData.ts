import type {
  AgeBracket,
  WorkingStatus,
  ResidencyStatus,
  StudyLevel,
  ChildcareSelection,
  SENDDetails,
  PersonData,
  ChildData,
  LocalStorageData,
} from "@bsil/calculator";
import {
  getChildAgeMonths,
  BIG_KID_MONTHS,
  isTermEligible2YO,
} from "@/lib/childAge";

export interface FormPersonData {
  isApprentice: boolean | null;
  firstYearApprentice: boolean | null;
  isSelfEmployed: boolean | null;
  selfEmployedLessThanTwelveMonths: boolean | null;
  ageBracket: AgeBracket | null;
  workingStatus: WorkingStatus | null;
  receivesQualifyingAllowance: boolean | null;
  startingWorkNextMonth: boolean | null;
  hasLimitedCapacityForWork: boolean | null;
  hasNationalInsuranceNumber: boolean | null;
  residencyStatus: ResidencyStatus | null;
  isStudying: boolean | null;
  studyLevel: StudyLevel | null;
  isFullTimeStudent: boolean | null;
  courseIsPubliclyFunded: boolean | null;
  eligibleForStudentFinance: boolean | null;
}

export interface FormChildData {
  id: number;
  firstName: string;
  birthMonth: number | null;
  birthYear: number | null;
  hasSEND: boolean | null;
  sendDetails: SENDDetails | null;
  isFostered: boolean | null;
  hasEHCP: boolean | null;
  hasLeftCareForAdoptionOrSpecialGuardianship: boolean | null;
  childcareSelections: ChildcareSelection[];
}

export interface FormLocalStorageData {
  schemaVersion: number;
  location: { postcode: string; ladCodes: string[] };
  household: { hasPartner: boolean | null };
  user: FormPersonData;
  partner: FormPersonData | null;
  ucIncomeBelowThreshold: boolean | null;
  nrpfIncomeUnderThreshold: number | null;
  nrpfSavingsUnderLimit: number | null;
  qualifyingBenefits: string[] | null;
  children: FormChildData[];
  shortlistedProviders: string[];
}

function assertNotNull<T>(value: T | null, field: string): T {
  if (value === null) {
    throw new Error(
      `Form field "${field}" is null — validation should have caught this`,
    );
  }
  return value;
}

function resolvePerson(person: FormPersonData, label: string): PersonData {
  return {
    isApprentice: assertNotNull(person.isApprentice, `${label}.isApprentice`),
    firstYearApprentice: person.firstYearApprentice,
    isSelfEmployed: assertNotNull(
      person.isSelfEmployed,
      `${label}.isSelfEmployed`,
    ),
    selfEmployedLessThanTwelveMonths: person.selfEmployedLessThanTwelveMonths,
    ageBracket:
      person.isApprentice && person.firstYearApprentice
        ? person.ageBracket
        : assertNotNull(person.ageBracket, `${label}.ageBracket`),
    workingStatus: assertNotNull(
      person.workingStatus,
      `${label}.workingStatus`,
    ),
    receivesQualifyingAllowance: person.receivesQualifyingAllowance,
    startingWorkNextMonth: person.startingWorkNextMonth,
    hasLimitedCapacityForWork: person.hasLimitedCapacityForWork,
    hasNationalInsuranceNumber: assertNotNull(
      person.hasNationalInsuranceNumber,
      `${label}.hasNationalInsuranceNumber`,
    ),
    residencyStatus: assertNotNull(
      person.residencyStatus,
      `${label}.residencyStatus`,
    ),
    isStudying: person.isStudying ?? false,
    studyLevel: person.studyLevel,
    isFullTimeStudent: person.isFullTimeStudent,
    courseIsPubliclyFunded: person.courseIsPubliclyFunded,
    eligibleForStudentFinance: person.eligibleForStudentFinance,
  };
}

function resolveChild(child: FormChildData, index: number): ChildData {
  const firstName =
    child.firstName.trim() === "" ? `Child ${index + 1}` : child.firstName;
  return {
    id: child.id,
    firstName,
    birthMonth: assertNotNull(
      child.birthMonth,
      `child[${child.id}].birthMonth`,
    ),
    birthYear: assertNotNull(child.birthYear, `child[${child.id}].birthYear`),
    hasSEND: assertNotNull(child.hasSEND, `child[${child.id}].hasSEND`),
    sendDetails: child.sendDetails,
    isFostered: assertNotNull(
      child.isFostered,
      `child[${child.id}].isFostered`,
    ),
    hasEHCP: child.hasEHCP ?? false,
    hasLeftCareForAdoptionOrSpecialGuardianship:
      child.hasLeftCareForAdoptionOrSpecialGuardianship ?? false,
    childcareSelections: child.childcareSelections,
  };
}

export function validateFormData(
  form: FormLocalStorageData,
  stepLabels: string[],
): string[] {
  const invalid: string[] = [];

  if (
    stepLabels.includes("Living situation") &&
    form.household.hasPartner === null
  ) {
    invalid.push("Living situation");
  }

  if (stepLabels.includes("Immigration status")) {
    const userBad =
      form.user.residencyStatus === null ||
      form.user.hasNationalInsuranceNumber === null;
    const partnerBad =
      form.household.hasPartner &&
      form.partner &&
      (form.partner.residencyStatus === null ||
        form.partner.hasNationalInsuranceNumber === null);
    if (userBad || partnerBad) invalid.push("Immigration status");
  }

  if (stepLabels.includes("Working situation")) {
    const personBad = (p: FormPersonData) =>
      p.isApprentice === null ||
      p.workingStatus === null ||
      (p.isApprentice === false && p.isSelfEmployed === null) ||
      p.isStudying === null ||
      (p.isStudying === true && p.studyLevel === null) ||
      (p.isStudying === true &&
        p.studyLevel === "higher_education" &&
        p.isFullTimeStudent === null) ||
      (p.isStudying === true &&
        p.studyLevel === "higher_education" &&
        p.eligibleForStudentFinance === null) ||
      (p.isStudying === true &&
        (p.studyLevel === "school_sixth_form" ||
          p.studyLevel === "further_education") &&
        p.courseIsPubliclyFunded === null);
    const userBad = personBad(form.user);
    const partnerBad =
      form.household.hasPartner && form.partner && personBad(form.partner);
    if (userBad || partnerBad) invalid.push("Working situation");
  }

  if (stepLabels.includes("Benefits")) {
    if (form.qualifyingBenefits === null) {
      invalid.push("Benefits");
    } else {
      const allNRPF =
        form.user.residencyStatus === "no_recourse_to_public_funds" &&
        (!form.partner ||
          form.partner.residencyStatus === "no_recourse_to_public_funds");
      const hasRealBenefit =
        form.qualifyingBenefits.length > 0 &&
        !form.qualifyingBenefits.every((b) => b === "none");
      if (allNRPF && hasRealBenefit) {
        invalid.push("Benefits");
      }
    }
  }

  if (stepLabels.includes("Your children")) {
    const isEngland = form.location.ladCodes.some((c) => c.startsWith("E"));
    let anyBad = form.children.some((c) => {
      if (
        c.birthMonth === null ||
        c.birthYear === null ||
        c.hasSEND === null ||
        c.isFostered === null ||
        (c.hasSEND === true && c.sendDetails === null)
      )
        return true;
      if (isEngland && c.birthMonth !== null && c.birthYear !== null) {
        const termEligible = isTermEligible2YO(c.birthMonth, c.birthYear);
        const autoEligible =
          c.isFostered === true || !!c.sendDetails?.receivesDLA;
        if (termEligible && !autoEligible) {
          if (
            c.hasEHCP === null ||
            c.hasLeftCareForAdoptionOrSpecialGuardianship === null
          )
            return true;
        }
      }
      return false;
    });
    const hasNonAutoEligible2YO =
      isEngland &&
      form.children.some((c) => {
        if (c.birthMonth === null || c.birthYear === null) return false;
        if (!isTermEligible2YO(c.birthMonth, c.birthYear)) return false;
        if (c.isFostered === true) return false;
        if (c.sendDetails?.receivesDLA) return false;
        if (c.hasEHCP === true) return false;
        if (c.hasLeftCareForAdoptionOrSpecialGuardianship === true)
          return false;
        return true;
      });
    if (
      (form.qualifyingBenefits ?? []).includes("universal_credit") &&
      hasNonAutoEligible2YO &&
      form.ucIncomeBelowThreshold === null
    ) {
      anyBad = true;
    }
    const allNRPF =
      form.user.residencyStatus === "no_recourse_to_public_funds" &&
      (!form.partner ||
        form.partner.residencyStatus === "no_recourse_to_public_funds");
    if (allNRPF && hasNonAutoEligible2YO) {
      if (
        form.nrpfIncomeUnderThreshold === null ||
        form.nrpfSavingsUnderLimit === null
      )
        anyBad = true;
    }
    if (form.children.length === 0 || anyBad) invalid.push("Your children");
  }

  if (stepLabels.includes("Childcare arrangements")) {
    const estimatable = form.children.filter(
      (c) =>
        c.birthMonth !== null &&
        c.birthYear !== null &&
        getChildAgeMonths(c.birthMonth, c.birthYear) < BIG_KID_MONTHS,
    );
    if (
      estimatable.length > 0 &&
      !estimatable.some((c) => c.childcareSelections.length > 0)
    ) {
      invalid.push("Childcare arrangements");
    }
  }

  return invalid;
}

function isCareTypeAvailable(careType: string, ageMonths: number): boolean {
  switch (careType) {
    case "private_nursery":
      return ageMonths < 60;
    case "school_based_nursery":
      return ageMonths >= 24 && ageMonths < 60;
    case "childminder":
      return true;
    case "breakfast_club":
    case "free_breakfast_club":
    case "after_school_club":
    case "holiday_club":
      return ageMonths >= 48;
    default:
      return true;
  }
}

function stripIneligibleSelections(child: FormChildData): ChildcareSelection[] {
  if (child.birthMonth === null || child.birthYear === null) {
    return child.childcareSelections;
  }
  const ageMonths = getChildAgeMonths(child.birthMonth, child.birthYear);
  return child.childcareSelections.filter((sel) =>
    isCareTypeAvailable(sel.careType, ageMonths),
  );
}

export function normaliseFormData(
  form: FormLocalStorageData,
): FormLocalStorageData {
  return {
    ...form,
    children: form.children.map((child) => ({
      ...child,
      childcareSelections: stripIneligibleSelections(child),
    })),
  };
}

export function resolveFormData(form: FormLocalStorageData): LocalStorageData {
  return {
    schemaVersion: form.schemaVersion,
    location: form.location,
    household: {
      hasPartner: assertNotNull(
        form.household.hasPartner,
        "household.hasPartner",
      ),
    },
    user: resolvePerson(form.user, "user"),
    partner: form.partner ? resolvePerson(form.partner, "partner") : null,
    ucIncomeBelowThreshold: (form.qualifyingBenefits ?? []).includes(
      "universal_credit",
    )
      ? (form.ucIncomeBelowThreshold ?? false)
      : false,
    nrpfIncomeUnderThreshold:
      form.user.residencyStatus === "no_recourse_to_public_funds" &&
      (!form.partner ||
        form.partner.residencyStatus === "no_recourse_to_public_funds")
        ? (form.nrpfIncomeUnderThreshold ?? 0)
        : 0,
    nrpfSavingsUnderLimit:
      form.user.residencyStatus === "no_recourse_to_public_funds" &&
      (!form.partner ||
        form.partner.residencyStatus === "no_recourse_to_public_funds")
        ? (form.nrpfSavingsUnderLimit ?? 0)
        : 0,
    qualifyingBenefits: form.qualifyingBenefits ?? [],
    children: form.children.map(resolveChild),
    shortlistedProviders: form.shortlistedProviders,
  };
}

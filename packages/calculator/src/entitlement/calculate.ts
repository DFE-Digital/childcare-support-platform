import type {
  LocalStorageData,
  PersonData,
  ChildData,
} from "../types/family.js";
import type { Scheme } from "../types/scheme.js";
import type {
  Caveat,
  SchemeEntitlement,
  ChildEntitlement,
  EntitlementResult,
} from "../types/entitlement.js";
import {
  getChildAgeInMonths,
  getChildAgeInYears,
  nextTermStart,
  formatTermDate,
  isPreSchool,
} from "./helpers.js";

export function calculateEntitlements(
  data: LocalStorageData,
  schemes: Scheme[],
  referenceDate: Date,
): EntitlementResult {
  const children = data.children.map((child) => {
    const schemeResults = schemes.map((scheme) =>
      evaluateScheme(scheme, child, data, referenceDate),
    );
    return {
      childId: child.id,
      childName: child.firstName,
      schemes: schemeResults,
    } satisfies ChildEntitlement;
  });
  return { children };
}

function evaluateScheme(
  scheme: Scheme,
  child: ChildData,
  data: LocalStorageData,
  referenceDate: Date,
): SchemeEntitlement {
  switch (scheme.id) {
    case "30_hours_working_families":
      return evaluate30Hours(scheme, child, data, referenceDate);
    case "15_hours_universal":
      return evaluate15HoursUniversal(scheme, child, data, referenceDate);
    case "15_hours_2_year_olds":
      return evaluate15Hours2YearOlds(scheme, child, data, referenceDate);
    case "tax_free_childcare":
      return evaluateTaxFreeChildcare(scheme, child, data, referenceDate);
    case "universal_credit_childcare":
      return evaluateUCChildcare(scheme, child, data, referenceDate);
    case "wraparound_childcare":
      return evaluateWraparound(scheme, child, referenceDate);
    case "free_breakfast_clubs":
      return evaluateBreakfastClubs(scheme, child, referenceDate);
    case "haf":
      return evaluateHAF(scheme, child, data, referenceDate);
    case "care_to_learn":
      return evaluateCareToLearn(scheme, child, data);
    case "learner_support":
      return evaluateLearnerSupport(scheme, child, data);
    case "childcare_grant":
      return evaluateChildcareGrant(scheme, child, data, referenceDate);
    default:
      return {
        schemeId: scheme.id,
        eligible: false,
        reasons: ["Unknown scheme."],
        caveats: [],
      };
  }
}

// Re-export for external consumers (e.g. costs/age-band.ts)
export { getChildAgeInMonths, isParentWorking };

// --- Helpers ---

function isEligibleFor15Hours2YO(
  child: ChildData,
  referenceDate: Date,
): { eligible: boolean; reason: string } {
  // Eligible from: start of the term FOLLOWING the child's 2nd birthday
  // Eligible until: end of the term IN WHICH the child turns 3
  // (i.e. the start of the NEXT term after they turn 3)
  const eligibleFrom = nextTermStart(child.birthYear + 2, child.birthMonth);
  const eligibleUntil = nextTermStart(child.birthYear + 3, child.birthMonth);

  if (referenceDate < eligibleFrom) {
    return {
      eligible: false,
      reason: `Child is not yet eligible — entitlement begins ${formatTermDate(eligibleFrom)}.`,
    };
  }
  if (referenceDate >= eligibleUntil) {
    return {
      eligible: false,
      reason: "Child is 3 or older — see universal 15 hours instead.",
    };
  }
  return { eligible: true, reason: "" };
}

function isParentWorking(person: PersonData): boolean {
  return person.workingStatus !== "not_working";
}

/** UC Childcare treats "starting paid work in the next month" as working. */
function isWorkingOrStartingSoon(person: PersonData): boolean {
  return isParentWorking(person) || person.startingWorkNextMonth === true;
}

export function isParentMeetingEarningsThreshold(person: PersonData): boolean {
  if (person.workingStatus === "income_over_100k") return true;
  if (person.workingStatus === "earning_above_nmw") return true;
  if (
    person.workingStatus === "earning_above_apprentice_nmw" &&
    person.isApprentice &&
    person.firstYearApprentice
  ) {
    return true;
  }
  return false;
}

function hasIncomeOver100k(person: PersonData): boolean {
  return person.workingStatus === "income_over_100k";
}

export function hasNonWorkingPartnerException(person: PersonData): boolean {
  // From the data we can only determine Carer's Allowance
  return person.receivesQualifyingAllowance === true;
}

function hasSelfEmployedStartupException(person: PersonData): boolean {
  return (
    person.isSelfEmployed && person.selfEmployedLessThanTwelveMonths === true
  );
}

function hasEligibleResidency(person: PersonData): boolean {
  return (
    person.residencyStatus === "british_irish_citizen" ||
    person.residencyStatus === "settled_status" ||
    person.residencyStatus === "pre_settled_status" ||
    person.residencyStatus === "permission_to_access_public_funds"
  );
}

function isNRPF(person: PersonData): boolean {
  return person.residencyStatus === "no_recourse_to_public_funds";
}

function isUkLocation(data: LocalStorageData): boolean {
  return data.location.ladCodes.some((c) => /^[EWSN]/.test(c));
}

function isEnglandLocation(data: LocalStorageData): boolean {
  return data.location.ladCodes.some((c) => c.startsWith("E"));
}

function allParentsAreNRPF(data: LocalStorageData): boolean {
  if (!isNRPF(data.user)) return false;
  if (data.partner && !isNRPF(data.partner)) return false;
  return true;
}

function isLondonLocation(data: LocalStorageData): boolean {
  return data.location.ladCodes.some((c) => c.startsWith("E09"));
}

function hasDisabilityBenefit(child: ChildData): boolean {
  return !!(
    child.sendDetails?.receivesDLA ||
    child.sendDetails?.receivesPIP ||
    child.sendDetails?.isRegisteredBlind
  );
}

function bothParentsWorkCheck(data: LocalStorageData): {
  pass: boolean;
  reasons: string[];
  caveats: Caveat[];
} {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  const userWorks = isParentWorking(data.user);

  if (!data.household.hasPartner) {
    // Single parent — only the user needs to work
    if (!userWorks) {
      reasons.push("Parent is not working.");
      return { pass: false, reasons, caveats };
    }
    return { pass: true, reasons, caveats };
  }

  // Couple
  const partnerWorks = data.partner ? isParentWorking(data.partner) : false;

  if (userWorks && partnerWorks) {
    return { pass: true, reasons, caveats };
  }

  // Check non-working partner exception
  if (userWorks && data.partner && !partnerWorks) {
    if (hasNonWorkingPartnerException(data.partner)) {
      caveats.push({ code: "partner_carers_allowance_exemption" });
      return { pass: true, reasons, caveats };
    }
    reasons.push(
      "Partner is not working and does not have an identified exemption.",
    );
    return { pass: false, reasons, caveats };
  }

  if (!userWorks && data.partner && partnerWorks) {
    if (hasNonWorkingPartnerException(data.user)) {
      caveats.push({ code: "user_carers_allowance_exemption" });
      return { pass: true, reasons, caveats };
    }
    reasons.push(
      "You are not working and do not have an identified exemption.",
    );
    return { pass: false, reasons, caveats };
  }

  reasons.push("Neither parent is working.");
  return { pass: false, reasons, caveats };
}

function earningsThresholdCheck(data: LocalStorageData): {
  pass: boolean;
  reasons: string[];
  caveats: Caveat[];
} {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  const userMeets = isParentMeetingEarningsThreshold(data.user);
  const userStartup = hasSelfEmployedStartupException(data.user);

  if (!userMeets && !userStartup && isParentWorking(data.user)) {
    reasons.push(
      "Your earnings are below the minimum threshold for your age bracket.",
    );
  }
  if (!userMeets && userStartup) {
    caveats.push({ code: "user_self_employed_startup" });
  }

  if (
    data.household.hasPartner &&
    data.partner &&
    isParentWorking(data.partner)
  ) {
    const partnerMeets = isParentMeetingEarningsThreshold(data.partner);
    const partnerStartup = hasSelfEmployedStartupException(data.partner);
    if (!partnerMeets && !partnerStartup) {
      reasons.push(
        "Partner's earnings are below the minimum threshold for their age bracket.",
      );
    }
    if (!partnerMeets && partnerStartup) {
      caveats.push({ code: "partner_self_employed_startup" });
    }
  }

  const pass = reasons.length === 0;
  return { pass, reasons, caveats };
}

// --- Scheme evaluators ---

function evaluate30Hours(
  scheme: Scheme,
  child: ChildData,
  data: LocalStorageData,
  referenceDate: Date,
): SchemeEntitlement {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  // Age check: child must be ≥9 months and pre-school
  const ageMonths = getChildAgeInMonths(child, referenceDate);
  if (ageMonths < 9) {
    reasons.push("Child is under 9 months old.");
  }
  if (!isPreSchool(child, referenceDate)) {
    reasons.push("Child has reached school age.");
  }

  // Both parents working check
  const workCheck = bothParentsWorkCheck(data);
  reasons.push(...workCheck.reasons);
  caveats.push(...workCheck.caveats);

  // Earnings threshold (only if work check passed)
  if (workCheck.pass) {
    const earningsCheck = earningsThresholdCheck(data);
    reasons.push(...earningsCheck.reasons);
    caveats.push(...earningsCheck.caveats);
  }

  // Income cap
  if (hasIncomeOver100k(data.user)) {
    reasons.push("Your adjusted net income is over £100,000.");
  }
  if (data.partner && hasIncomeOver100k(data.partner)) {
    reasons.push("Partner's adjusted net income is over £100,000.");
  }

  // England location
  if (!isEnglandLocation(data)) {
    reasons.push(
      "You must live in England to be eligible for 30 Hours Working Families.",
    );
  }

  // Public funds access — at least one parent must have eligible residency
  const userHasAccess = hasEligibleResidency(data.user);
  const partnerHasAccess = data.partner
    ? hasEligibleResidency(data.partner)
    : false;
  if (!userHasAccess && !partnerHasAccess) {
    reasons.push("At least one parent must have access to public funds.");
  } else if (userHasAccess !== partnerHasAccess && data.household.hasPartner) {
    caveats.push({ code: "apply_with_public_funds_parent" });
  }

  // NI number
  if (!data.user.hasNationalInsuranceNumber) {
    reasons.push("You do not have a National Insurance number.");
  }
  if (data.partner && !data.partner.hasNationalInsuranceNumber) {
    reasons.push("Partner does not have a National Insurance number.");
  }

  const eligible = reasons.length === 0;
  if (eligible) {
    reasons.push(
      "Both parents working, earnings above threshold, child aged 9 months to school age.",
    );
  }

  return { schemeId: scheme.id, eligible, reasons, caveats };
}

function evaluate15HoursUniversal(
  scheme: Scheme,
  child: ChildData,
  data: LocalStorageData,
  referenceDate: Date,
): SchemeEntitlement {
  const reasons: string[] = [];

  const eligibleFrom = nextTermStart(child.birthYear + 3, child.birthMonth);
  const preSchool = isPreSchool(child, referenceDate);

  if (referenceDate < eligibleFrom) {
    reasons.push(
      `Child is not yet eligible — entitlement begins ${formatTermDate(eligibleFrom)}.`,
    );
  }
  if (!preSchool) {
    reasons.push("Child has reached school age.");
  }

  // England location
  if (!isEnglandLocation(data)) {
    reasons.push(
      "You must live in England to be eligible for 15 Hours Universal.",
    );
  }

  const eligible = reasons.length === 0;
  if (eligible) {
    reasons.push("All 3 and 4-year-olds are entitled to 15 funded hours.");
  }

  return { schemeId: scheme.id, eligible, reasons, caveats: [] };
}

function evaluate15Hours2YearOlds(
  scheme: Scheme,
  child: ChildData,
  data: LocalStorageData,
  referenceDate: Date,
): SchemeEntitlement {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  // England only
  if (!isEnglandLocation(data)) {
    reasons.push("This scheme is only available in England.");
    return { schemeId: scheme.id, eligible: false, reasons, caveats };
  }

  const ageCheck = isEligibleFor15Hours2YO(child, referenceDate);
  if (!ageCheck.eligible) {
    reasons.push(ageCheck.reason);
    return { schemeId: scheme.id, eligible: false, reasons, caveats };
  }

  // Looked-after children and DLA recipients are automatically eligible
  if (child.isFostered) {
    reasons.push(
      "Children looked-after by a local authority in England or Wales, such as children in foster care, are entitled to 15 funded hours from the term after age 2.",
    );
    return { schemeId: scheme.id, eligible: true, reasons, caveats };
  }
  if (child.sendDetails?.receivesDLA) {
    reasons.push(
      "Children receiving Disability Living Allowance are entitled to 15 funded hours from the term after age 2.",
    );
    return { schemeId: scheme.id, eligible: true, reasons, caveats };
  }
  if (child.hasEHCP) {
    reasons.push(
      "Children with an education, health and care plan are entitled to 15 funded hours from the term after age 2.",
    );
    return { schemeId: scheme.id, eligible: true, reasons, caveats };
  }
  if (child.hasLeftCareForAdoptionOrSpecialGuardianship) {
    reasons.push(
      "Children who have left care under an adoption order or special guardianship are entitled to 15 funded hours from the term after age 2.",
    );
    return { schemeId: scheme.id, eligible: true, reasons, caveats };
  }

  // Child is age-eligible. Eligibility depends on benefits/circumstances.

  let potentiallyEligible = false;
  const benefits = data.qualifyingBenefits;
  const hasUC = benefits.includes("universal_credit");

  // UC route
  if (hasUC && data.ucIncomeBelowThreshold) {
    potentiallyEligible = true;
    reasons.push(
      "Household receives Universal Credit with income below £15,400/year after tax.",
    );
  }

  // NRPF route
  if (allParentsAreNRPF(data)) {
    const isLondon = isLondonLocation(data);
    const childCount = data.children.length;
    const expectedThreshold = isLondon
      ? childCount >= 2
        ? 38600
        : 34500
      : childCount >= 2
        ? 30600
        : 26500;

    const incomeConfirmed = data.nrpfIncomeUnderThreshold === expectedThreshold;
    const savingsConfirmed = data.nrpfSavingsUnderLimit === 16000;

    if (incomeConfirmed && savingsConfirmed) {
      potentiallyEligible = true;
      reasons.push(
        `Household income is below £${expectedThreshold.toLocaleString()} and savings are below £16,000 (NRPF route).`,
      );
    } else {
      if (!incomeConfirmed) {
        caveats.push({
          code: "nrpf_income_above_threshold",
          params: { threshold: expectedThreshold.toLocaleString() },
        });
      }
      if (!savingsConfirmed) {
        caveats.push({ code: "nrpf_savings_above_limit" });
      }
    }
  }

  // ESA/Pension Credit route — definitive eligibility
  // (Income Support and income-based JSA have migrated to Universal Credit)
  const qualifyingBenefitIds = ["esa", "pension_credit"];
  const matchedBenefits = qualifyingBenefitIds.filter((b) =>
    benefits.includes(b),
  );
  if (matchedBenefits.length > 0) {
    potentiallyEligible = true;
    const benefitLabels: Record<string, string> = {
      esa: "income-related ESA",
      pension_credit: "Pension Credit",
    };
    reasons.push(
      `Receiving ${matchedBenefits.map((b) => benefitLabels[b]).join(", ")}.`,
    );
  }

  if (potentiallyEligible) {
    if (reasons.length === 0) {
      reasons.push(
        "Child is 2 years old and family may meet eligibility criteria.",
      );
    }
    return { schemeId: scheme.id, eligible: true, reasons, caveats };
  }

  reasons.push(
    "Based on available information, eligibility criteria for this scheme are not met.",
  );
  return { schemeId: scheme.id, eligible: false, reasons, caveats };
}

function evaluateTaxFreeChildcare(
  scheme: Scheme,
  child: ChildData,
  data: LocalStorageData,
  referenceDate: Date,
): SchemeEntitlement {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  // Age check: eligible until 1 September after 11th birthday (or 16th if disabled)
  const disabled = hasDisabilityBenefit(child);
  const thresholdAge = disabled ? 16 : 11;
  const turnsThresholdYear = child.birthYear + thresholdAge;
  const cutoffYear =
    child.birthMonth >= 9 ? turnsThresholdYear + 1 : turnsThresholdYear;
  const cutoffDate = new Date(cutoffYear, 8, 1); // 1 September
  if (referenceDate >= cutoffDate) {
    reasons.push(
      disabled
        ? "Child has passed the 31 August after their 16th birthday."
        : "Child has passed the 31 August after their 11th birthday.",
    );
  }

  // Both parents working
  const workCheck = bothParentsWorkCheck(data);
  reasons.push(...workCheck.reasons);
  caveats.push(...workCheck.caveats);

  // Earnings threshold (only if work check passed)
  if (workCheck.pass) {
    const earningsCheck = earningsThresholdCheck(data);
    reasons.push(...earningsCheck.reasons);
    caveats.push(...earningsCheck.caveats);
  }

  // Income cap
  if (hasIncomeOver100k(data.user)) {
    reasons.push("Your adjusted net income is over £100,000.");
  }
  if (data.partner && hasIncomeOver100k(data.partner)) {
    reasons.push("Partner's adjusted net income is over £100,000.");
  }

  // UC exclusion
  if (data.qualifyingBenefits.includes("universal_credit")) {
    reasons.push(
      "You cannot use Tax-Free Childcare while receiving Universal Credit.",
    );
  }

  // UK residency
  if (!isUkLocation(data)) {
    reasons.push(
      "You must live in the UK to be eligible for Tax-Free Childcare.",
    );
  }

  // Public funds access — at least one parent must have eligible residency
  const userHasAccess = hasEligibleResidency(data.user);
  const partnerHasAccess = data.partner
    ? hasEligibleResidency(data.partner)
    : false;
  if (!userHasAccess && !partnerHasAccess) {
    reasons.push("At least one parent must have access to public funds.");
  } else if (userHasAccess !== partnerHasAccess && data.household.hasPartner) {
    caveats.push({ code: "apply_with_public_funds_parent" });
  }

  // NI number
  if (!data.user.hasNationalInsuranceNumber) {
    reasons.push("You do not have a National Insurance number.");
  }
  if (data.partner && !data.partner.hasNationalInsuranceNumber) {
    reasons.push("Partner does not have a National Insurance number.");
  }

  // Foster children are not eligible
  if (child.isFostered) {
    reasons.push("Tax-Free Childcare is not available for foster children.");
  }

  const eligible = reasons.length === 0;
  if (eligible) {
    reasons.push(
      "Working parent(s), earnings above threshold, income under £100,000.",
    );
  }

  return {
    schemeId: scheme.id,
    eligible,
    reasons,
    caveats,
    descriptionParams: {
      annualCap: disabled ? "4,000" : "2,000",
    },
  };
}

function evaluateUCChildcare(
  scheme: Scheme,
  child: ChildData,
  data: LocalStorageData,
  referenceDate: Date,
): SchemeEntitlement {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  // Age check: eligible until 1 September after turning 16
  const turns16Year = child.birthYear + 16;
  const cutoffYear = child.birthMonth >= 9 ? turns16Year + 1 : turns16Year;
  const cutoffDate = new Date(cutoffYear, 8, 1); // 1 September
  if (referenceDate >= cutoffDate) {
    reasons.push("Child has passed the 31 August after their 16th birthday.");
  }

  // Foster children are not eligible
  if (child.isFostered) {
    reasons.push("UC Childcare is not available for foster children.");
  }

  // Must be on UC
  if (!data.qualifyingBenefits.includes("universal_credit")) {
    reasons.push("You are not on Universal Credit.");
  }

  // UK location
  if (!isUkLocation(data)) {
    reasons.push(
      "You must live in the UK to be eligible for Universal Credit childcare.",
    );
  }

  // At least one parent working or starting soon (both if partner, with exceptions)
  if (data.household.hasPartner && data.partner) {
    const userWorks = isWorkingOrStartingSoon(data.user);
    const partnerWorks = isWorkingOrStartingSoon(data.partner);

    if (!userWorks && !partnerWorks) {
      reasons.push("Neither parent is working.");
    } else if (userWorks && !partnerWorks) {
      if (
        !hasNonWorkingPartnerException(data.partner) &&
        !data.partner.hasLimitedCapacityForWork
      ) {
        reasons.push("Your partner is not working.");
      }
    } else if (!userWorks && partnerWorks) {
      if (
        !hasNonWorkingPartnerException(data.user) &&
        !data.user.hasLimitedCapacityForWork
      ) {
        reasons.push("You are not working.");
      }
    }
  } else {
    // Single parent
    if (!isWorkingOrStartingSoon(data.user)) {
      reasons.push("You are not working.");
    }
  }

  // Public funds access — at least one parent must have eligible residency
  const userHasAccess = hasEligibleResidency(data.user);
  const partnerHasAccess = data.partner
    ? hasEligibleResidency(data.partner)
    : false;
  if (!userHasAccess && !partnerHasAccess) {
    reasons.push("At least one parent must have access to public funds.");
  } else if (userHasAccess !== partnerHasAccess && data.household.hasPartner) {
    caveats.push({ code: "apply_with_public_funds_parent" });
  }

  const eligible = reasons.length === 0;
  if (eligible) {
    reasons.push("On Universal Credit with at least one parent working.");
  }

  return { schemeId: scheme.id, eligible, reasons, caveats };
}

function evaluateWraparound(
  scheme: Scheme,
  child: ChildData,
  referenceDate: Date,
): SchemeEntitlement {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  const ageYears = getChildAgeInYears(child, referenceDate);
  const maxAge = child.hasSEND ? 18 : 14;

  if (isPreSchool(child, referenceDate)) {
    reasons.push("Child has not yet started school.");
  }
  if (ageYears > maxAge) {
    reasons.push(
      child.hasSEND
        ? "Child is over 18 years old."
        : "Child is over 14 years old.",
    );
  }

  // I don't think this is correct - there's no general eligibility criteria for wraparound care
  // where there is insufficient provision, parents have the right to request that their school
  // consider offering wraparound, and this right applies to children upto 14, or 18 yo if SEND.
  // Here I take this as appropriate logic for showing the wraparound scheme, but not strong
  // enough to justify the following caveat.
  //
  // if (child.hasSEND && reasons.length === 0) {
  //   caveats.push(
  //     "Wraparound childcare is available up to age 18 for children with disabilities.",
  //   );
  // }

  const eligible = reasons.length === 0;
  if (eligible) {
    reasons.push(
      "Child is school age (Reception–Year 9, or up to 18 if disabled).",
    );
  }

  return { schemeId: scheme.id, eligible, reasons, caveats };
}

function evaluateBreakfastClubs(
  scheme: Scheme,
  child: ChildData,
  referenceDate: Date,
): SchemeEntitlement {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  const ageYears = getChildAgeInYears(child, referenceDate);

  if (isPreSchool(child, referenceDate)) {
    reasons.push("Child has not yet started school.");
  }
  if (ageYears > 11) {
    reasons.push("Child is over 11 years old.");
  }

  const eligible = reasons.length === 0;
  if (eligible) {
    reasons.push("Child is primary school age (Reception–Year 6).");
  }

  return { schemeId: scheme.id, eligible, reasons, caveats };
}

function evaluateHAF(
  scheme: Scheme,
  child: ChildData,
  data: LocalStorageData,
  referenceDate: Date,
): SchemeEntitlement {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  const ageYears = getChildAgeInYears(child, referenceDate);

  if (isPreSchool(child, referenceDate)) {
    reasons.push("Child has not yet started school.");
    return { schemeId: scheme.id, eligible: false, reasons, caveats };
  }
  if (ageYears > 16) {
    reasons.push("Child is over 16 years old.");
    return { schemeId: scheme.id, eligible: false, reasons, caveats };
  }

  const benefits = data.qualifyingBenefits;
  const hasQualifyingBenefit =
    benefits.includes("universal_credit") ||
    benefits.includes("pension_credit") ||
    benefits.includes("esa");

  if (!hasQualifyingBenefit) {
    reasons.push(
      "Based on available information, free school meal eligibility criteria are not met.",
    );
    return { schemeId: scheme.id, eligible: false, reasons, caveats };
  }

  reasons.push(
    "Child is school age and family receives a qualifying benefit aligned with free school meal eligibility.",
  );
  return { schemeId: scheme.id, eligible: true, reasons, caveats };
}

// --- Study scheme evaluators (information only) ---

function isStudyingParent(person: PersonData): boolean {
  return person.isStudying;
}

function evaluateCareToLearn(
  scheme: Scheme,
  _child: ChildData,
  data: LocalStorageData,
): SchemeEntitlement {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  // Check either parent qualifies: under 20, studying school/FE, publicly funded, not apprentice
  const qualifyingParent = [
    data.user,
    ...(data.partner ? [data.partner] : []),
  ].find((p) => {
    const youngEnough = p.ageBracket === "16-17" || p.ageBracket === "18-20";
    const studying = isStudyingParent(p);
    const rightLevel =
      p.studyLevel === "school_sixth_form" ||
      p.studyLevel === "further_education";
    const notApprentice = !p.isApprentice;
    return youngEnough && studying && rightLevel && notApprentice;
  });

  if (!qualifyingParent) {
    // Check specific failure reasons
    const anyStudying = [
      data.user,
      ...(data.partner ? [data.partner] : []),
    ].some((p) => isStudyingParent(p));

    if (!anyStudying) {
      reasons.push("No parent is currently studying.");
    } else {
      const anyYoung = [
        data.user,
        ...(data.partner ? [data.partner] : []),
      ].some((p) => p.ageBracket === "16-17" || p.ageBracket === "18-20");
      if (!anyYoung) {
        reasons.push("No parent is in the eligible age range (under 20).");
      }
      const anyRightLevel = [
        data.user,
        ...(data.partner ? [data.partner] : []),
      ].some(
        (p) =>
          p.studyLevel === "school_sixth_form" ||
          p.studyLevel === "further_education",
      );
      if (!anyRightLevel) {
        reasons.push(
          "No parent is studying at school, sixth form, or further education level.",
        );
      }
    }
  }

  if (qualifyingParent && !qualifyingParent.courseIsPubliclyFunded) {
    reasons.push("The course is not publicly funded.");
  }

  if (!isEnglandLocation(data)) {
    reasons.push("You must live in England to be eligible for Care to Learn.");
  }

  if (qualifyingParent && !hasEligibleResidency(qualifyingParent)) {
    reasons.push(
      "The studying parent does not have eligible residency status.",
    );
  }

  const eligible = reasons.length === 0 && !!qualifyingParent;
  if (eligible) {
    reasons.push(
      "Parent is under 20, studying a publicly-funded course at school or FE level.",
    );
    caveats.push({ code: "care_to_learn_age_caveat" });
  }

  return { schemeId: scheme.id, eligible, reasons, caveats };
}

function evaluateLearnerSupport(
  scheme: Scheme,
  _child: ChildData,
  data: LocalStorageData,
): SchemeEntitlement {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  // Check either parent qualifies: age 19+, studying FE
  const qualifyingParent = [
    data.user,
    ...(data.partner ? [data.partner] : []),
  ].find((p) => {
    const oldEnough = p.ageBracket === "18-20" || p.ageBracket === "21+";
    const studying = isStudyingParent(p);
    const rightLevel = p.studyLevel === "further_education";
    return oldEnough && studying && rightLevel;
  });

  if (!qualifyingParent) {
    const anyStudyingFE = [
      data.user,
      ...(data.partner ? [data.partner] : []),
    ].some((p) => isStudyingParent(p) && p.studyLevel === "further_education");

    if (!anyStudyingFE) {
      const anyStudying = [
        data.user,
        ...(data.partner ? [data.partner] : []),
      ].some((p) => isStudyingParent(p));
      if (!anyStudying) {
        reasons.push("No parent is currently studying.");
      } else {
        reasons.push("No parent is studying at further education level.");
      }
    } else {
      reasons.push(
        "No parent studying FE is in the eligible age range (19 or over).",
      );
    }
  }

  const eligible = reasons.length === 0 && !!qualifyingParent;
  if (eligible) {
    reasons.push("Parent is studying a further education course.");
    caveats.push({ code: "learner_support_age_caveat" });
  }

  return { schemeId: scheme.id, eligible, reasons, caveats };
}

function evaluateChildcareGrant(
  scheme: Scheme,
  child: ChildData,
  data: LocalStorageData,
  referenceDate: Date,
): SchemeEntitlement {
  const reasons: string[] = [];
  const caveats: Caveat[] = [];

  // Check either parent qualifies: studying HE, full-time, eligible for student finance
  const qualifyingParent = [
    data.user,
    ...(data.partner ? [data.partner] : []),
  ].find((p) => {
    const studying = isStudyingParent(p);
    const rightLevel = p.studyLevel === "higher_education";
    const fullTime = p.isFullTimeStudent === true;
    const hasFinance = p.eligibleForStudentFinance === true;
    return studying && rightLevel && fullTime && hasFinance;
  });

  if (!qualifyingParent) {
    const anyStudyingHE = [
      data.user,
      ...(data.partner ? [data.partner] : []),
    ].some((p) => isStudyingParent(p) && p.studyLevel === "higher_education");

    if (!anyStudyingHE) {
      const anyStudying = [
        data.user,
        ...(data.partner ? [data.partner] : []),
      ].some((p) => isStudyingParent(p));
      if (!anyStudying) {
        reasons.push("No parent is currently studying.");
      } else {
        reasons.push("No parent is studying at higher education level.");
      }
    } else {
      const anyFullTime = [
        data.user,
        ...(data.partner ? [data.partner] : []),
      ].some(
        (p) =>
          isStudyingParent(p) &&
          p.studyLevel === "higher_education" &&
          p.isFullTimeStudent === true,
      );
      if (!anyFullTime) {
        reasons.push(
          "The parent studying HE is not a full-time student (120+ credits per year).",
        );
      }
      const anyFinance = [
        data.user,
        ...(data.partner ? [data.partner] : []),
      ].some(
        (p) =>
          isStudyingParent(p) &&
          p.studyLevel === "higher_education" &&
          p.eligibleForStudentFinance === true,
      );
      if (!anyFinance) {
        reasons.push(
          "The parent studying HE is not eligible for student finance.",
        );
      }
    }
  }

  // Child age check: under 15, or under 17 if SEND
  const maxAge = child.hasSEND ? 17 : 15;
  const ageYears = getChildAgeInYears(child, referenceDate);
  if (ageYears >= maxAge) {
    reasons.push(
      child.hasSEND ? "Child is 17 or older." : "Child is 15 or older.",
    );
  }

  if (!isEnglandLocation(data)) {
    reasons.push(
      "You must live in England to be eligible for Childcare Grant.",
    );
  }

  const eligible = reasons.length === 0 && !!qualifyingParent;
  if (eligible) {
    reasons.push(
      "Parent is a full-time HE student eligible for student finance.",
    );
    caveats.push({ code: "childcare_grant_income_caveat" });
  }

  return { schemeId: scheme.id, eligible, reasons, caveats };
}

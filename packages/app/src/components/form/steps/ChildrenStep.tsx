import { useEffect, useRef, useState } from "react";
import type { FormLocalStorageData, FormChildData } from "@/types/formData";
import { FormStep } from "@/components/ui/FormStep";
import { TextInput } from "@/components/ui/TextInput";
import { SelectField } from "@/components/ui/SelectField";
import { RadioGroup } from "@/components/ui/RadioGroup";
import { CheckboxGroup } from "@/components/ui/CheckboxGroup";
import { ValidationWrapper } from "@/components/ui/ValidationWrapper";
import { Explainer } from "@/components/ui/Explainer";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { scrollToFirstError } from "@/lib/scrollToFirstError";
import { isTermEligible2YO } from "@/lib/childAge";
import { yearOptions } from "./yearOptions";

interface Props {
  formData: FormLocalStorageData;
  updateFormData: (patch: Partial<FormLocalStorageData>) => void;
  onContinue: () => void;
  onBack: () => void;
}

interface ChildErrors {
  birthMonth?: boolean;
  birthYear?: boolean;
  send?: boolean;
  sendDetails?: boolean;
  fostered?: boolean;
  ehcp?: boolean;
  careLeaver?: boolean;
}

function sendDetailsToValues(details: FormChildData["sendDetails"]): string[] {
  if (!details) return [];
  if (
    !details.receivesDLA &&
    !details.receivesPIP &&
    !details.isRegisteredBlind
  )
    return ["none"];
  const vals: string[] = [];
  if (details.receivesDLA) vals.push("dla");
  if (details.receivesPIP) vals.push("pip");
  if (details.isRegisteredBlind) vals.push("blind");
  return vals;
}

function valuesToSendDetails(values: string[]): FormChildData["sendDetails"] {
  if (values.length === 0) return null;
  if (values.includes("none"))
    return { receivesDLA: false, receivesPIP: false, isRegisteredBlind: false };
  return {
    receivesDLA: values.includes("dla"),
    receivesPIP: values.includes("pip"),
    isRegisteredBlind: values.includes("blind"),
  };
}

function shouldShowEhcpQuestions(
  child: FormChildData,
  ladCodes: string[],
): boolean {
  if (!ladCodes.some((code) => code.startsWith("E"))) return false;
  if (child.birthMonth === null || child.birthYear === null) return false;
  if (!isTermEligible2YO(child.birthMonth, child.birthYear)) return false;
  // Wait until fostering question is answered
  if (child.isFostered === null) return false;
  if (child.isFostered === true) return false;
  // Wait until disability path is resolved
  if (child.hasSEND === true && child.sendDetails === null) return false;
  if (child.sendDetails?.receivesDLA) return false;
  return true;
}

function shouldShowUcIncomeQuestion(formData: FormLocalStorageData): boolean {
  if (!(formData.qualifyingBenefits ?? []).includes("universal_credit"))
    return false;
  const ladCodes = formData.location.ladCodes;
  if (!ladCodes.some((code) => code.startsWith("E"))) return false;
  return formData.children.some((child) => {
    if (child.birthMonth === null || child.birthYear === null) return false;
    if (!isTermEligible2YO(child.birthMonth, child.birthYear)) return false;
    if (child.isFostered === true) return false;
    if (child.sendDetails?.receivesDLA) return false;
    if (child.hasEHCP === true) return false;
    if (child.hasLeftCareForAdoptionOrSpecialGuardianship === true)
      return false;
    // Prerequisite questions must be answered
    if (child.isFostered === null) return false;
    if (child.hasSEND === true && child.sendDetails === null) return false;
    if (child.hasEHCP === null) return false;
    if (child.hasLeftCareForAdoptionOrSpecialGuardianship === null)
      return false;
    return true;
  });
}

function shouldShowNrpfQuestions(formData: FormLocalStorageData): boolean {
  if (formData.user.residencyStatus !== "no_recourse_to_public_funds")
    return false;
  if (
    formData.partner &&
    formData.partner.residencyStatus !== "no_recourse_to_public_funds"
  )
    return false;
  const ladCodes = formData.location.ladCodes;
  if (!ladCodes.some((code) => code.startsWith("E"))) return false;
  return formData.children.some((child) => {
    if (child.birthMonth === null || child.birthYear === null) return false;
    if (!isTermEligible2YO(child.birthMonth, child.birthYear)) return false;
    if (child.isFostered === true) return false;
    if (child.sendDetails?.receivesDLA) return false;
    if (child.hasEHCP === true) return false;
    if (child.hasLeftCareForAdoptionOrSpecialGuardianship === true)
      return false;
    if (child.isFostered === null) return false;
    if (child.hasSEND === true && child.sendDetails === null) return false;
    if (child.hasEHCP === null) return false;
    if (child.hasLeftCareForAdoptionOrSpecialGuardianship === null)
      return false;
    return true;
  });
}

function getNrpfThreshold(formData: FormLocalStorageData): number {
  const isLondon = formData.location.ladCodes.some((c) => c.startsWith("E09"));
  const childCount = formData.children.length;
  return isLondon
    ? childCount >= 2
      ? 38600
      : 34500
    : childCount >= 2
      ? 30600
      : 26500;
}

const months = [
  { value: "1", label: "January" },
  { value: "2", label: "February" },
  { value: "3", label: "March" },
  { value: "4", label: "April" },
  { value: "5", label: "May" },
  { value: "6", label: "June" },
  { value: "7", label: "July" },
  { value: "8", label: "August" },
  { value: "9", label: "September" },
  { value: "10", label: "October" },
  { value: "11", label: "November" },
  { value: "12", label: "December" },
];

export function ChildrenStep({
  formData,
  updateFormData,
  onContinue,
  onBack,
}: Props) {
  const children = formData.children;
  const [childErrors, setChildErrors] = useState<Map<number, ChildErrors>>(
    new Map(),
  );
  const [ucIncomeError, setUcIncomeError] = useState(false);
  const [nrpfIncomeError, setNrpfIncomeError] = useState(false);
  const [nrpfSavingsError, setNrpfSavingsError] = useState(false);
  const childrenContainerRef = useRef<HTMLDivElement>(null);
  const pendingFocusChild = useRef(false);

  useEffect(() => {
    if (children.length === 0) {
      updateFormData({
        children: [
          {
            id: 1,
            firstName: "",
            birthMonth: null,
            birthYear: null,
            hasSEND: null,
            sendDetails: null,
            isFostered: null,
            hasEHCP: null,
            hasLeftCareForAdoptionOrSpecialGuardianship: null,
            childcareSelections: [],
          },
        ],
      });
    }
  }, [children.length, updateFormData]);

  const handleContinue = () => {
    const errors = new Map<number, ChildErrors>();
    children.forEach((c, i) => {
      const e: ChildErrors = {};
      if (c.birthMonth === null) e.birthMonth = true;
      if (c.birthYear === null) e.birthYear = true;
      if (c.hasSEND === null) e.send = true;
      if (c.hasSEND === true && c.sendDetails === null) e.sendDetails = true;
      if (c.isFostered === null) e.fostered = true;
      const showEhcp = shouldShowEhcpQuestions(c, formData.location.ladCodes);
      if (showEhcp && c.hasEHCP === null) e.ehcp = true;
      if (showEhcp && c.hasLeftCareForAdoptionOrSpecialGuardianship === null)
        e.careLeaver = true;
      if (Object.keys(e).length > 0) errors.set(i, e);
    });
    setChildErrors(errors);
    if (errors.size > 0) {
      scrollToFirstError();
      return;
    }

    const showUcIncome = shouldShowUcIncomeQuestion(formData);
    setUcIncomeError(showUcIncome && formData.ucIncomeBelowThreshold === null);
    if (showUcIncome && formData.ucIncomeBelowThreshold === null) {
      scrollToFirstError();
      return;
    }

    const showNrpf = shouldShowNrpfQuestions(formData);
    const nrpfIncBad = showNrpf && formData.nrpfIncomeUnderThreshold === null;
    const nrpfSavBad = showNrpf && formData.nrpfSavingsUnderLimit === null;
    setNrpfIncomeError(nrpfIncBad);
    setNrpfSavingsError(nrpfSavBad);
    if (nrpfIncBad || nrpfSavBad) {
      scrollToFirstError();
      return;
    }

    // Backfill empty names before proceeding
    const hasEmptyNames = children.some((c) => c.firstName.trim() === "");
    if (hasEmptyNames) {
      updateFormData({
        children: children.map((c, i) => ({
          ...c,
          firstName: c.firstName.trim() === "" ? `Child ${i + 1}` : c.firstName,
        })),
      });
    }

    onContinue();
  };

  const updateChild = (index: number, patch: Partial<FormChildData>) => {
    setChildErrors((prev) => {
      if (!prev.has(index)) return prev;
      const next = new Map(prev);
      const errs = { ...next.get(index) };
      if ("birthMonth" in patch) delete errs.birthMonth;
      if ("birthYear" in patch) delete errs.birthYear;
      if ("hasSEND" in patch) delete errs.send;
      if ("sendDetails" in patch) delete errs.sendDetails;
      if ("isFostered" in patch) delete errs.fostered;
      if ("hasEHCP" in patch) delete errs.ehcp;
      if ("hasLeftCareForAdoptionOrSpecialGuardianship" in patch)
        delete errs.careLeaver;
      if (Object.keys(errs).length === 0) next.delete(index);
      else next.set(index, errs);
      return next;
    });
    const updated = children.map((c, i) =>
      i === index ? { ...c, ...patch } : c,
    );
    updateFormData({ children: updated });
  };

  const addChild = () => {
    const newId =
      children.length > 0 ? Math.max(...children.map((c) => c.id)) + 1 : 1;
    pendingFocusChild.current = true;
    requestAnimationFrame(() => {
      if (pendingFocusChild.current) {
        const container = childrenContainerRef.current;
        if (container) {
          const cards =
            container.querySelectorAll<HTMLElement>("[data-child-card]");
          const lastCard = cards[cards.length - 1];
          lastCard?.querySelector<HTMLInputElement>("input")?.focus();
        }
        pendingFocusChild.current = false;
      }
    });
    updateFormData({
      children: [
        ...children,
        {
          id: newId,
          firstName: "",
          birthMonth: null,
          birthYear: null,
          hasSEND: null,
          sendDetails: null,
          isFostered: null,
          hasEHCP: null,
          hasLeftCareForAdoptionOrSpecialGuardianship: null,
          childcareSelections: [],
        },
      ],
    });
  };

  const removeChild = (index: number) => {
    if (children.length <= 1) return;
    updateFormData({ children: children.filter((_, i) => i !== index) });
  };

  return (
    <>
      <FormStep
        title="Your children"
        onContinue={handleContinue}
        onBack={onBack}
        footer={
          <>
            <Explainer label="Why have you asked my child's name?">
              <p>
                Your child&apos;s name is only used to make later screens easier
                to follow. When you have more than one child, it helps you see
                which results and cost estimates belong to which child.
              </p>
              <p>
                This field is optional. If you leave it blank, we&apos;ll use
                &ldquo;Child 1&rdquo;, &ldquo;Child 2&rdquo; and so on
                automatically.
              </p>
              <p className="font-bold">Your privacy</p>
              <p>
                The name stays entirely within your browser. It is never sent to
                a server, stored in a database, or shared with anyone.
              </p>
            </Explainer>
            <Explainer label="What if I am expecting, or still planning my family?">
              <p>
                You can still use this tool to get an idea of what childcare
                might cost and which government support you could be eligible
                for. Simply enter a birth year in the past to see what support
                would be available for a child of that age today. You can also
                edit your responses to see how that support changes as they get
                older.
              </p>
              <p className="font-bold">A few things to keep in mind</p>
              <ul className="list-disc pl-5 space-y-2">
                <li>
                  <strong>Eligibility depends on age at the time</strong> —
                  funded hours and other schemes start at specific ages (from 9
                  months for working families, age 2 for some benefits-based
                  support, and age 3 for universal hours). The estimate will
                  reflect what would be available once your child reaches those
                  ages.
                </li>
                <li>
                  <strong>Costs may change</strong> — provider fees, government
                  funding rates, and scheme rules can change between now and
                  when your child starts childcare. Treat the figures as a guide
                  based on today&apos;s rates.
                </li>
                <li>
                  <strong>Your circumstances may change too</strong> — your
                  working status, income, and household situation at the time
                  you actually apply will determine your eligibility, not what
                  you enter today.
                </li>
                <li>
                  <strong>Parental leave</strong> — if you or your partner (if
                  you live with one) will be on maternity, paternity, or shared
                  parental leave, you are still treated as being in paid work
                  for scheme eligibility purposes.
                </li>
              </ul>
              <p>
                This tool is designed to help you plan ahead. You can come back
                and run it again at any time as your circumstances become
                clearer.
              </p>
            </Explainer>
            <Explainer label="Why does my child's age matter?">
              <p>
                Different childcare schemes become available at different ages.
                Your child&apos;s date of birth determines which support they
                can access:
              </p>
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-zinc-200">
                    <th className="text-left py-2 pr-4 font-bold">Age</th>
                    <th className="text-left py-2 font-bold">
                      Available support
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-zinc-100">
                    <td className="py-2 pr-4">From 9 months</td>
                    <td className="py-2">
                      30 Hours Childcare (if parents are working)
                    </td>
                  </tr>
                  <tr className="border-b border-zinc-100">
                    <td className="py-2 pr-4">Age 2</td>
                    <td className="py-2">
                      Early Learning for 2 year olds (if on certain benefits)
                    </td>
                  </tr>
                  <tr className="border-b border-zinc-100">
                    <td className="py-2 pr-4">Age 3</td>
                    <td className="py-2">
                      15 Hours universal (all 3 and 4 year old children, no
                      conditions)
                    </td>
                  </tr>
                  <tr className="border-b border-zinc-100">
                    <td className="py-2 pr-4">School age</td>
                    <td className="py-2">
                      Free breakfast clubs, wraparound childcare
                    </td>
                  </tr>
                  <tr className="border-b border-zinc-100">
                    <td className="py-2 pr-4">Up to 11</td>
                    <td className="py-2">Tax-Free Childcare</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4">Up to 16</td>
                    <td className="py-2">Universal Credit childcare</td>
                  </tr>
                </tbody>
              </table>
              <p>
                Funded hours entitlements start from{" "}
                <strong>the term after</strong> your child reaches the
                qualifying age. For example, if your child turns 3 in February,
                they can access 15 hours from the following April.
              </p>
              <p className="pt-2">
                <ExternalLink
                  href="https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/"
                  className="text-purple-700 underline hover:text-purple-900"
                >
                  Full age eligibility details on Best Start in Life
                </ExternalLink>
              </p>
            </Explainer>
            <Explainer label="How does a disability affect childcare support?">
              <p>
                Children with disabilities or long-term health conditions may
                qualify for additional childcare support:
              </p>
              <ul className="list-disc pl-5 space-y-2">
                <li>
                  <strong>15 Hours Early Learning for 2-year-olds</strong> — a
                  child receiving Disability Living Allowance or with an
                  Education, Health and Care (EHC) plan automatically qualifies,
                  regardless of family income.
                </li>
                <li>
                  <strong>Tax-Free Childcare</strong> — the government top-up
                  doubles to <strong>£4,000 per year</strong> (instead of
                  £2,000) and extends until the child turns <strong>16</strong>{" "}
                  (instead of 11). Payments can also cover specialist equipment.
                </li>
                <li>
                  <strong>Universal Credit childcare</strong> — support extends
                  until the 31st August after the child's 16th birthday.
                </li>
              </ul>
              <p className="pt-2">
                <ExternalLink
                  href="https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/additional-support/eligibility/"
                  className="text-purple-700 underline hover:text-purple-900"
                >
                  Early Learning for 2-year-olds eligibility
                </ExternalLink>
              </p>
            </Explainer>
            <Explainer label="What if I'm a foster carer?">
              <p>
                Foster children are not eligible for certain government
                childcare schemes. This is because local authorities are
                expected to cover childcare costs for looked-after children
                through foster care allowances.
              </p>
              <p>The following schemes are affected:</p>
              <ul className="list-disc pl-5 space-y-2">
                <li>
                  <strong>Tax-Free Childcare</strong> — you cannot use a
                  Tax-Free Childcare account to pay for childcare for a foster
                  child.
                </li>
                <li>
                  <strong>Universal Credit childcare</strong> — childcare costs
                  for foster children cannot be claimed through Universal
                  Credit.
                </li>
              </ul>
              <p>
                Funded hours entitlements (15 and 30 hours) are not affected by
                fostering status and remain available where the child meets the
                age and other eligibility criteria.
              </p>
              <p>
                If you are fostering and need help with childcare costs, contact
                your local authority fostering team to discuss what support is
                available through your foster care allowance.
              </p>
            </Explainer>
            {children.some((c) =>
              shouldShowEhcpQuestions(c, formData.location.ladCodes),
            ) && (
              <>
                <Explainer
                  label="What is an EHCP?"
                  modalTitle="What is an education, health and care plan (EHCP)?"
                >
                  <p>
                    An EHCP is a legal document for children and young people
                    aged 0&ndash;25 with special educational needs or
                    disabilities. It describes their needs and the extra support
                    they should receive.
                  </p>
                  <p>
                    EHCPs are issued by the local authority after a formal
                    assessment known as an <strong>EHC needs assessment</strong>
                    . Not all children with additional needs will have one
                    &mdash; many receive informal &ldquo;SEN support&rdquo; at
                    their setting instead.
                  </p>
                  <p className="font-bold">Why it matters for childcare</p>
                  <p>
                    If your child has an EHCP, they{" "}
                    <strong>automatically qualify</strong> for 15 funded hours
                    per week of early learning from age 2, regardless of family
                    income or benefits. This is the same automatic entitlement
                    as children receiving Disability Living Allowance.
                  </p>
                  <p className="font-bold">
                    SEN support is different from an EHCP
                  </p>
                  <p>
                    If your child receives SEN support but does not have a
                    formal EHCP, they do not automatically qualify through this
                    route. However, they may still qualify through other routes
                    such as benefits or income.
                  </p>
                  <p>
                    If you think your child may need an EHCP, you can request an
                    assessment from your local authority.
                  </p>
                  <p className="pt-2">
                    <ExternalLink
                      href="https://www.gov.uk/children-with-special-educational-needs/extra-SEN-help"
                      className="text-purple-700 underline hover:text-purple-900"
                    >
                      EHC plans on GOV.UK
                    </ExternalLink>
                  </p>
                </Explainer>
                <Explainer label="What does &lsquo;left care&rsquo; mean here?">
                  <p>
                    This question applies to children who were previously{" "}
                    <strong>
                      looked after by a local authority in England or Wales
                    </strong>{" "}
                    (for example, in foster care or residential care) and have
                    since left care through one of these legal routes:
                  </p>
                  <ul className="list-disc pl-5 space-y-2">
                    <li>
                      <strong>An adoption order</strong> &mdash; the child has
                      been legally adopted.
                    </li>
                    <li>
                      <strong>A special guardianship order (SGO)</strong>{" "}
                      &mdash; a court order giving a non-parent (often a
                      relative or former foster carer) parental responsibility.
                    </li>
                    <li>
                      <strong>A child arrangements order</strong> &mdash; a
                      court order specifying who the child lives with.
                    </li>
                  </ul>
                  <p className="font-bold">Why it matters for childcare</p>
                  <p>
                    If your child left care under one of these routes, they{" "}
                    <strong>automatically qualify</strong> for 15 funded hours
                    per week of early learning from age 2, regardless of family
                    income or benefits. This is the same automatic entitlement
                    as children receiving Disability Living Allowance or with an
                    EHCP.
                  </p>
                  <p>
                    If your child was adopted privately (not from local
                    authority care) or has always lived with you, this question
                    does not apply &mdash; select &ldquo;No&rdquo;.
                  </p>
                </Explainer>
              </>
            )}
            {(shouldShowUcIncomeQuestion(formData) ||
              shouldShowNrpfQuestions(formData)) && (
              <Explainer label="What counts as household income?">
                <p>
                  &ldquo;Household income&rdquo; means the combined income of
                  you and your partner (if you live with one), after tax.
                </p>
                <p className="font-bold">What to include</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>Employment income (wages, salary)</li>
                  <li>Self-employment profit</li>
                  <li>Pension income</li>
                </ul>
                <p className="font-bold">What NOT to include</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>Universal Credit or other benefit payments</li>
                  <li>Child Benefit</li>
                  <li>Housing Benefit or housing element of UC</li>
                </ul>
                <p className="font-bold">Why it matters</p>
                <p>
                  This determines whether your 2-year-old qualifies for{" "}
                  <strong>
                    15 funded hours per week (over 38 weeks of the year)
                  </strong>{" "}
                  of early learning.
                </p>
                {shouldShowUcIncomeQuestion(formData) && (
                  <p>
                    For families on Universal Credit, the threshold is{" "}
                    <strong>&pound;15,400 per year</strong> after tax, not
                    including benefit payments.
                  </p>
                )}
                {shouldShowNrpfQuestions(formData) && (
                  <>
                    <p>
                      For families with no recourse to public funds, household
                      income includes earned income and unearned income, such as
                      payments received from charities, local authorities, or
                      from friends and family. Parents should complete a
                      self-declaration form of their income as part of their
                      application and it is up to the local authority to
                      determine if the income threshold has been met.
                    </p>
                    <p>
                      For families with no recourse to public funds, the
                      threshold also depends on where you live and how many
                      children you have:
                    </p>
                    <table className="w-full text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-zinc-200">
                          <th className="text-left py-2 pr-4 font-bold">
                            Area
                          </th>
                          <th className="text-left py-2 pr-4 font-bold">
                            1 child
                          </th>
                          <th className="text-left py-2 font-bold">
                            2+ children
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b border-zinc-100">
                          <td className="py-2 pr-4">London</td>
                          <td className="py-2 pr-4">&pound;34,500</td>
                          <td className="py-2">&pound;38,600</td>
                        </tr>
                        <tr>
                          <td className="py-2 pr-4">Rest of England</td>
                          <td className="py-2 pr-4">&pound;26,500</td>
                          <td className="py-2">&pound;30,600</td>
                        </tr>
                      </tbody>
                    </table>
                  </>
                )}
                <p className="pt-2">
                  <ExternalLink
                    href="https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/additional-support/eligibility/"
                    className="text-purple-700 underline hover:text-purple-900"
                  >
                    15 Hours Early Learning eligibility on Best Start in Life
                  </ExternalLink>
                </p>
              </Explainer>
            )}
            {shouldShowNrpfQuestions(formData) && (
              <Explainer label="What counts as savings and investments?">
                <p>
                  The &pound;16,000 savings limit is your combined savings with
                  your partner (if you have one).
                </p>
                <p className="font-bold">What to include</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>Bank and building society accounts</li>
                  <li>Cash ISAs</li>
                  <li>Stocks, shares, and other investments</li>
                  <li>Property you own but do not live in</li>
                </ul>
                <p className="font-bold">What NOT to include</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>The home you live in</li>
                  <li>Personal possessions</li>
                  <li>Business assets (if you are self-employed)</li>
                </ul>
                <p className="font-bold">Why it matters</p>
                <p>
                  Families with no recourse to public funds must meet{" "}
                  <strong>both</strong> the income threshold and the savings
                  limit to qualify for 15 funded hours per week of early
                  learning for their 2-year-old.
                </p>
              </Explainer>
            )}
          </>
        }
      >
        <p className="text-base text-zinc-600">
          Tell us about your children so we can find the right support for each
          of them.
        </p>

        <div ref={childrenContainerRef}>
          {children.map((child, idx) => {
            const errors = childErrors.get(idx);
            return (
              <div
                key={child.id}
                data-child-card
                className="bg-white rounded-xl p-6 border border-zinc-200 space-y-4 mt-4 first:mt-0"
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-lg">Child {idx + 1}</h3>
                  {children.length > 1 && (
                    <button
                      onClick={() => removeChild(idx)}
                      className="text-sm text-red-600 hover:text-red-800 font-medium underline hover:no-underline"
                      aria-label={`Remove child ${child.firstName || `Child ${idx + 1}`}`}
                    >
                      Remove
                    </button>
                  )}
                </div>

                <TextInput
                  label="First name (optional)"
                  value={child.firstName}
                  onChange={(e) =>
                    updateChild(idx, { firstName: e.currentTarget.value })
                  }
                  placeholder={`Child ${idx + 1}`}
                />

                <ValidationWrapper
                  error={errors?.birthMonth || errors?.birthYear}
                  message="Please select the child's date of birth"
                >
                  <div className="grid grid-cols-2 gap-4">
                    <SelectField
                      label="Birth month"
                      placeholder="Select month"
                      options={months}
                      value={
                        child.birthMonth === null
                          ? ""
                          : String(child.birthMonth)
                      }
                      onChange={(e) => {
                        const newMonth = Number(e.currentTarget.value);
                        const now = new Date();
                        const isFuture =
                          child.birthYear === now.getFullYear() &&
                          newMonth > now.getMonth() + 1;
                        updateChild(idx, {
                          birthMonth: newMonth,
                          ...(isFuture ? { birthYear: null } : {}),
                        });
                      }}
                    />
                    <SelectField
                      label="Birth year"
                      placeholder="Select year"
                      options={yearOptions(child.birthMonth)}
                      value={
                        child.birthYear === null ? "" : String(child.birthYear)
                      }
                      onChange={(e) =>
                        updateChild(idx, {
                          birthYear: Number(e.currentTarget.value),
                        })
                      }
                    />
                  </div>
                </ValidationWrapper>

                <ValidationWrapper
                  error={errors?.send}
                  message="Please answer this question to continue"
                >
                  {({ errorId, invalid }) => (
                    <RadioGroup
                      name={`disability-${child.id}`}
                      label="Does this child have a disability or special educational needs?"
                      options={[
                        { value: "no", label: "No" },
                        { value: "yes", label: "Yes" },
                      ]}
                      value={
                        child.hasSEND === null
                          ? ""
                          : child.hasSEND
                            ? "yes"
                            : "no"
                      }
                      onChange={(v) =>
                        updateChild(idx, {
                          hasSEND: v === "yes",
                          ...(v === "no"
                            ? {
                                sendDetails: null,
                                hasEHCP: null,
                                hasLeftCareForAdoptionOrSpecialGuardianship:
                                  null,
                              }
                            : {}),
                        })
                      }
                      aria-describedby={errorId}
                      aria-invalid={invalid}
                    />
                  )}
                </ValidationWrapper>

                {child.hasSEND === true && (
                  <div className="ml-6 border-l-2 border-zinc-200 pl-5">
                    <ValidationWrapper
                      error={errors?.sendDetails}
                      message="Please answer this question to continue"
                    >
                      {({ errorId, invalid }) => (
                        <CheckboxGroup
                          name={`send-details-${child.id}`}
                          label="Select any of the following:"
                          options={[
                            {
                              value: "dla",
                              label:
                                "This child gets Disability Living Allowance (DLA)",
                            },
                            {
                              value: "pip",
                              label:
                                "This child gets a Personal Independence Payment (PIP)",
                            },
                            {
                              value: "blind",
                              label: "This child is registered blind",
                            },
                            {
                              value: "none",
                              label: "None of the above",
                            },
                          ]}
                          value={sendDetailsToValues(child.sendDetails)}
                          onChange={(values) => {
                            const prev = sendDetailsToValues(child.sendDetails);
                            const justSelectedNone =
                              values.includes("none") && !prev.includes("none");
                            const justSelectedOther =
                              !justSelectedNone &&
                              values.some(
                                (v) => v !== "none" && !prev.includes(v),
                              );
                            let resolved: string[];
                            if (justSelectedNone) {
                              resolved = ["none"];
                            } else if (justSelectedOther) {
                              resolved = values.filter((v) => v !== "none");
                            } else {
                              resolved = values;
                            }
                            const newDetails = valuesToSendDetails(resolved);
                            updateChild(idx, {
                              sendDetails: newDetails,
                              ...(newDetails?.receivesDLA
                                ? {
                                    hasEHCP: null,
                                    hasLeftCareForAdoptionOrSpecialGuardianship:
                                      null,
                                  }
                                : {}),
                            });
                          }}
                          aria-describedby={errorId}
                          aria-invalid={invalid}
                        />
                      )}
                    </ValidationWrapper>
                  </div>
                )}

                <ValidationWrapper
                  error={errors?.fostered}
                  message="Please answer this question to continue"
                >
                  {({ errorId, invalid }) => (
                    <RadioGroup
                      name={`fostered-${child.id}`}
                      label="Are you a foster carer to this child?"
                      options={[
                        { value: "no", label: "No" },
                        { value: "yes", label: "Yes" },
                      ]}
                      value={
                        child.isFostered === null
                          ? ""
                          : child.isFostered
                            ? "yes"
                            : "no"
                      }
                      onChange={(v) =>
                        updateChild(idx, {
                          isFostered: v === "yes",
                          ...(v === "yes"
                            ? {
                                hasEHCP: null,
                                hasLeftCareForAdoptionOrSpecialGuardianship:
                                  null,
                              }
                            : {}),
                        })
                      }
                      aria-describedby={errorId}
                      aria-invalid={invalid}
                    />
                  )}
                </ValidationWrapper>

                {shouldShowEhcpQuestions(child, formData.location.ladCodes) && (
                  <div className="ml-6 border-l-2 border-zinc-200 pl-5 space-y-4">
                    <ValidationWrapper
                      error={errors?.ehcp}
                      message="Please answer this question to continue"
                    >
                      {({ errorId, invalid }) => (
                        <RadioGroup
                          name={`ehcp-${child.id}`}
                          label="Does this child have an education, health and care plan (EHCP)?"
                          options={[
                            { value: "no", label: "No" },
                            { value: "yes", label: "Yes" },
                          ]}
                          value={
                            child.hasEHCP === null
                              ? ""
                              : child.hasEHCP
                                ? "yes"
                                : "no"
                          }
                          onChange={(v) =>
                            updateChild(idx, { hasEHCP: v === "yes" })
                          }
                          aria-describedby={errorId}
                          aria-invalid={invalid}
                        />
                      )}
                    </ValidationWrapper>

                    <ValidationWrapper
                      error={errors?.careLeaver}
                      message="Please answer this question to continue"
                    >
                      {({ errorId, invalid }) => (
                        <RadioGroup
                          name={`care-leaver-${child.id}`}
                          label="Has this child left care (in England or Wales) under an adoption order or special guardianship?"
                          options={[
                            { value: "no", label: "No" },
                            { value: "yes", label: "Yes" },
                          ]}
                          value={
                            child.hasLeftCareForAdoptionOrSpecialGuardianship ===
                            null
                              ? ""
                              : child.hasLeftCareForAdoptionOrSpecialGuardianship
                                ? "yes"
                                : "no"
                          }
                          onChange={(v) =>
                            updateChild(idx, {
                              hasLeftCareForAdoptionOrSpecialGuardianship:
                                v === "yes",
                            })
                          }
                          aria-describedby={errorId}
                          aria-invalid={invalid}
                        />
                      )}
                    </ValidationWrapper>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <button onClick={addChild} className="btn">
          Add a child <span aria-hidden="true">+</span>
        </button>

        {shouldShowUcIncomeQuestion(formData) && (
          <div className="ml-6 border-l-2 border-zinc-200 pl-5">
            <ValidationWrapper
              error={ucIncomeError}
              message="Please answer this question to continue"
            >
              {({ errorId, invalid }) => (
                <RadioGroup
                  name="uc-income-threshold"
                  label="Is your household income less than £15,400 per year, after tax and not including benefit payments?"
                  options={[
                    { value: "no", label: "No" },
                    { value: "yes", label: "Yes" },
                  ]}
                  value={
                    formData.ucIncomeBelowThreshold === null
                      ? ""
                      : formData.ucIncomeBelowThreshold
                        ? "yes"
                        : "no"
                  }
                  onChange={(v) => {
                    setUcIncomeError(false);
                    updateFormData({ ucIncomeBelowThreshold: v === "yes" });
                  }}
                  aria-describedby={errorId}
                  aria-invalid={invalid}
                />
              )}
            </ValidationWrapper>
          </div>
        )}

        {shouldShowNrpfQuestions(formData) && (
          <div className="ml-6 border-l-2 border-zinc-200 pl-5 space-y-4">
            <ValidationWrapper
              error={nrpfIncomeError}
              message="Please answer this question to continue"
            >
              {({ errorId, invalid }) => (
                <RadioGroup
                  name="nrpf-income-threshold"
                  label={`Is your household income less than £${getNrpfThreshold(formData).toLocaleString()} per year, after tax?`}
                  options={[
                    { value: "no", label: "No" },
                    { value: "yes", label: "Yes" },
                  ]}
                  value={
                    formData.nrpfIncomeUnderThreshold === null
                      ? ""
                      : formData.nrpfIncomeUnderThreshold > 0
                        ? "yes"
                        : "no"
                  }
                  onChange={(v) => {
                    setNrpfIncomeError(false);
                    updateFormData({
                      nrpfIncomeUnderThreshold:
                        v === "yes" ? getNrpfThreshold(formData) : 0,
                    });
                  }}
                  aria-describedby={errorId}
                  aria-invalid={invalid}
                />
              )}
            </ValidationWrapper>

            <ValidationWrapper
              error={nrpfSavingsError}
              message="Please answer this question to continue"
            >
              {({ errorId, invalid }) => (
                <RadioGroup
                  name="nrpf-savings"
                  label="Do you have less than £16,000 in savings or investments?"
                  options={[
                    { value: "no", label: "No" },
                    { value: "yes", label: "Yes" },
                  ]}
                  value={
                    formData.nrpfSavingsUnderLimit === null
                      ? ""
                      : formData.nrpfSavingsUnderLimit > 0
                        ? "yes"
                        : "no"
                  }
                  onChange={(v) => {
                    setNrpfSavingsError(false);
                    updateFormData({
                      nrpfSavingsUnderLimit: v === "yes" ? 16000 : 0,
                    });
                  }}
                  aria-describedby={errorId}
                  aria-invalid={invalid}
                />
              )}
            </ValidationWrapper>
          </div>
        )}
      </FormStep>
    </>
  );
}

# Get Support — Questionnaire Text for Policy Sign-Off

All user-facing text from the multi-step "What support am I entitled to?" form, extracted from the React components in `packages/app/src/components/form/`. This document is for the policy team to review and sign off the wording, question logic, and explanatory content.

**Page title:** What support am I entitled to?

**Page subtitle:** Answer a few questions and we'll show you which government schemes your family may be eligible for.

**Page date line:** Last updated: February 2026

---

## Step order

| #   | Step label         | Component           | Step title shown to user    |
| --- | ------------------ | ------------------- | --------------------------- |
| 1   | Where you live     | PostcodeStep        | Where do you live?          |
| 2   | Living situation   | PartnerStep         | Do you live with a partner? |
| 3   | Immigration status | ImmigrationStep     | Immigration status          |
| 4   | Working situation  | WorkingStep         | Your working situation      |
| 5   | Benefits           | UniversalCreditStep | Benefits                    |
| 6   | Your children      | ChildrenStep        | Your children               |

After all steps are completed, a **Summary screen** is shown (see section at end).

---

## Step 1 — Where do you live?

### Intro text

> Enter your postcode to find more about what you may be eligible for.

### Questions

| #   | Label    | Type       | Options   |
| --- | -------- | ---------- | --------- |
| 1   | Postcode | Text input | Free text |

### Validation

| Error message                           | Trigger                                  |
| --------------------------------------- | ---------------------------------------- |
| "Enter a valid UK postcode to continue" | Invalid postcode format or failed lookup |

### Modal: "Why do you need my postcode?"

**Title:** Why we ask for your postcode

**Body:**

> Your postcode helps us work out which childcare support you may be eligible for and show you local providers and estimated costs. If you are interested in childcare in another area, such as your place of work, you can enter that postcode instead.
>
> **Your privacy**
>
> Your postcode is only used in your browser to look up local information. It is never sent to a server, stored in a database, or linked to you personally.
>
> We use your postcode to:
>
> - Find childcare providers near you
> - Show average childcare costs for your area
> - Determine your country within the UK, which affects which schemes are available.

### Modal: "What if I don't live in England?"

**Body:**

> This tool covers childcare support schemes available in England. If you live in Scotland, Wales, or Northern Ireland, you can find information about childcare support in your nation here:

_(Dynamic list of devolved nation links from `schemesData.devolvedNationLinks`)_

---

## Step 2 — Do you live with a partner?

### Questions

| #   | Label                   | Type  | Options     |
| --- | ----------------------- | ----- | ----------- |
| 1   | _(implicit from title)_ | Radio | "Yes", "No" |

### Validation

| Error message                             | Trigger            |
| ----------------------------------------- | ------------------ |
| "Please answer this question to continue" | No option selected |

### Modal: "Why does my living situation matter?"

**Title:** Why your living situation matters

**Body:**

> Some childcare schemes require you and your partner (if you live with one) to meet work and income criteria. For example:
>
> - **30 Hours Childcare** and **Tax-Free Childcare** both require you and your partner (if you live with one) to be working and earning above a minimum threshold.
> - **Universal Credit childcare** requires you and your partner (if you live with one) to be in paid work, unless your partner has a particular health condition or caring responsibilities.

**Link:** [30 Hours eligibility on Best Start in Life](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/)

### Modal: "What if my partner is away or overseas?"

**Title:** What if my partner is away or overseas?

**Body:**

> If your partner normally lives with you but is temporarily away, they still count as living with you for childcare scheme purposes. This includes partners who work away, such as Crown servants, members of the armed forces, mariners, and workers on offshore installations.
>
> In these cases, you should answer **"Yes"** to the question "Do you live with a partner?". Your partner's work and income will still be assessed as part of your household when determining eligibility for schemes like 30 Hours Childcare and Tax-Free Childcare.

**Links:**

- [30 Hours Childcare on GOV.UK](https://www.gov.uk/30-hours-free-childcare)
- [Tax-Free Childcare on GOV.UK](https://www.gov.uk/tax-free-childcare)

---

## Step 3 — Immigration status

The step has two sections. The "About your partner" section is only shown when the user answered "Yes" at step 2.

### Questions — About you

| #   | Label                                         | Type  | Options     | Condition          |
| --- | --------------------------------------------- | ----- | ----------- | ------------------ |
| 1   | Are you a British or Irish citizen?           | Radio | "Yes", "No" | Always shown       |
| 1a  | What is your residency or immigration status? | Radio | See below   | Shown if Q1 = "No" |
| 2   | Do you have a National Insurance number?      | Radio | "Yes", "No" | Always shown       |

**Q1a options:**

1. "I am a citizen of an EU or EEA country, or Switzerland, with settled status"
2. "I am a citizen of an EU or EEA country, or Switzerland, with pre-settled status"
3. "Permission to access public funds"
4. "No recourse to public funds"
5. "Other or unsure"

### Questions — About your partner

| #   | Label                                                   | Type  | Options     | Condition                         |
| --- | ------------------------------------------------------- | ----- | ----------- | --------------------------------- |
| 3   | Is your partner a British or Irish citizen?             | Radio | "Yes", "No" | Always shown (in partner section) |
| 3a  | What is your partner's residency or immigration status? | Radio | Same as Q1a | Shown if Q3 = "No"                |
| 4   | Does your partner have a National Insurance number?     | Radio | "Yes", "No" | Always shown (in partner section) |

### Validation

All questions use the same error message:

| Error message                             | Trigger                                          |
| ----------------------------------------- | ------------------------------------------------ |
| "Please answer this question to continue" | Any unanswered question when Continue is clicked |

### Modal: "Why do you need to know my immigration status?"

**Title:** Why we ask about immigration status

**Body:**

> For schemes like **30 Hours Childcare** and **Tax-Free Childcare**, you (and your partner) must have a National Insurance number and have at least one of the following:
>
> - British or Irish citizenship
> - Settled or pre-settled status (or have applied and are awaiting a decision)
> - Permission to access public funds
>
> If your immigration status says **"no recourse to public funds"**, you may still qualify for the **Early Learning for 2-year-olds** scheme if your household income is below a certain threshold.
>
> All 3 to 4 year olds can access up to 15 hours childcare (over 38 weeks of the year), regardless of family circumstances.
>
> **Your privacy**
>
> Your answers stay in your browser. They are never sent to a server, stored, or linked to you in any way.

**Links:**

- [30 Hours eligibility on Best Start in Life](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/)
- [Early Learning for 2-year-olds eligibility](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/additional-support/eligibility/)
- [How 15 hours for all 3 to 4 year olds works](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/universal-offer/how-it-works/)

### Modal: "What is a National Insurance number?"

**Title:** What is a National Insurance number?

**Body:**

> A National Insurance (NI) number is a unique personal number used for tax and benefits in the UK. It looks like this: **AB 12 34 56 C** (two letters, six digits, one letter).
>
> You can find it on:
>
> - Your payslip
> - Your P60 or tax letters from HMRC
> - The HMRC app or personal tax account
>
> If you were born in the UK and a parent claimed Child Benefit for you, you should have received your NI number automatically before your 16th birthday. If not, you can apply for one.
>
> A National Insurance number is required for most childcare support schemes, including 30 Hours Childcare and Tax-Free Childcare.

**Link:** [Apply for a National Insurance number on GOV.UK](https://www.gov.uk/apply-national-insurance-number)

---

## Step 4 — Your working situation

The step has two sections. The "About your partner" section is only shown when the user has a partner. All questions below repeat for "About your partner" with partner-specific wording (e.g. "Is your partner on an apprenticeship?").

### Questions — About you

| #   | Label                                                                                                                                                                                                           | Type  | Options            | Condition                                            |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ------------------ | ---------------------------------------------------- |
| 1   | Are you on an apprenticeship?                                                                                                                                                                                   | Radio | "Yes", "No"        | Always shown                                         |
| 1a  | Are you in your first year?                                                                                                                                                                                     | Radio | "Yes", "No"        | Shown if Q1 = "Yes"                                  |
| 1b  | Are you self-employed?                                                                                                                                                                                          | Radio | "Yes", "No"        | Shown if Q1 = "No"                                   |
| 2   | Your age bracket                                                                                                                                                                                                | Radio | See below          | Hidden if apprentice AND first year; shown otherwise |
| 3   | Your working and expected income situation                                                                                                                                                                      | Radio | See below (varies) | Always shown                                         |
| 3a  | Do you receive any of the following allowances: Carer's Allowance?, Carer Support Payment (Scotland)?, Incapacity Benefit?, Severe Disablement Allowance?, Contribution-based Employment and Support Allowance? | Radio | "Yes", "No"        | Shown if Q3 = "Not working"                          |
| 3b  | Has your business been trading for less than 12 months?                                                                                                                                                         | Radio | "Yes", "No"        | Shown if self-employed AND earning below threshold   |

**Q2 — Age bracket options:**

- "16-17"
- "18-20"
- "21 or over"

**Q3 — Working status options (vary by apprentice status):**

Threshold values are derived from `NMW_WEEKLY[ageBracket]` in `packages/calculator/src/nmwThresholds.ts`. The age-bracket thresholds are: 21+ = £203.36/week, 18-20 = £173.60/week, 16-17 = £128.00/week.

_Non-apprentice:_

1. "Earning £{NMW_WEEKLY[ageBracket]} or more per week" → `earning_above_nmw`
2. "Earning less than £{NMW_WEEKLY[ageBracket]} per week" → `earning_below_nmw`
3. "Adjusted net income over £100,000" → `income_over_100k`
4. "Not working" → `not_working`

_Apprentice (first-year):_ Age bracket hidden; threshold is always `NMW_WEEKLY[APPRENTICE_BRACKET]` (£128.00).

1. "Earning £128.00 or more per week" → `earning_above_nmw`
2. "Earning less than £128.00 per week" → `earning_below_nmw`
3. "Not working" → `not_working`

_Apprentice (not first-year):_ Age bracket shown; threshold is `NMW_WEEKLY[ageBracket]`.

1. "Earning £{NMW_WEEKLY[ageBracket]} or more per week" → `earning_above_nmw`
2. "Earning less than £{NMW_WEEKLY[ageBracket]} per week" → `earning_below_nmw`
3. "Not working" → `not_working`

Note: `earning_above_apprentice_nmw` exists in `WORKING_STATUSES` for data compatibility (schema migration from v5) but is never offered as a radio option in the current form.

### Study questions — About you

These questions appear after the work questions within the same step, for each parent.

| #   | Label                                                                                            | Type  | Options                                                                                             | Condition                                                                      |
| --- | ------------------------------------------------------------------------------------------------ | ----- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| S1  | Are you currently studying? / Excluding your apprenticeship, are you studying for anything else? | Radio | "Yes", "No"                                                                                         | Default label always shown; apprenticeship-aware variant shown when W1 = "Yes" |
| S2  | What level are you studying at?                                                                  | Radio | "School or sixth form", "Further education (e.g. NVQ, BTEC, PGCE)", "Higher education (university)" | Shown if S1 = "Yes"                                                            |
| S3  | Is your course publicly funded?                                                                  | Radio | "Yes", "No"                                                                                         | Shown if S2 = "School or sixth form" or "Further education"                    |
| S4  | Are you studying full-time (120 or more credits per year)?                                       | Radio | "Yes", "No"                                                                                         | Shown if S2 = "Higher education"                                               |
| S5  | Are you eligible for student finance?                                                            | Radio | "Yes", "No"                                                                                         | Shown if S2 = "Higher education"                                               |

These questions determine eligibility for three information-only study childcare schemes: Care to Learn, Learner Support, and Childcare Grant. No cost calculations are performed for these schemes.

### Questions — About your partner

All questions repeat with partner wording:

| #   | Label                                                             |
| --- | ----------------------------------------------------------------- |
| 4   | Is your partner on an apprenticeship?                             |
| 4a  | Is your partner in their first year?                              |
| 4b  | Is your partner self-employed?                                    |
| 5   | Your partner's age bracket                                        |
| 6   | Your partner's working and expected income situation              |
| 6a  | Does your partner receive any of the following allowances: ...    |
| 6b  | Has your partner's business been trading for less than 12 months? |

Same options and conditions as the user questions.

### Study questions — About your partner

| #   | Label                                                              |
| --- | ------------------------------------------------------------------ |
| S6  | Is your partner currently studying?                                |
| S7  | What level is your partner studying at?                            |
| S8  | Is your partner's course publicly funded?                          |
| S9  | Is your partner studying full-time (120 or more credits per year)? |
| S10 | Is your partner eligible for student finance?                      |

Same options and conditions as the user study questions.

### Validation

All questions use the same error message:

| Error message                             | Trigger                                          |
| ----------------------------------------- | ------------------------------------------------ |
| "Please answer this question to continue" | Any unanswered question when Continue is clicked |

### Modal: "Why do you need to know about my work and income?"

**Title:** Why do you need to know about my work and income?

**Body:**

> Key childcare schemes like **30 Hours Childcare** and **Tax-Free Childcare** have minimum earnings requirements. You (and your partner, if you have one) must each expect to earn at least the equivalent of 16 hours per week at the National Minimum Wage.
>
> The exact threshold depends on your age, which is why we ask for your age bracket. There is also a maximum: your expected adjusted net income must not exceed **£100,000 per year**.
>
> **Universal Credit childcare** has different rules — there is no minimum earnings requirement, but you must be in paid work.
>
> If you are not working, you may still qualify if you receive certain benefits such as Carer's Allowance or Incapacity Benefit, and your partner is working.

**Links:**

- [30 Hours eligibility on Best Start in Life](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/)
- [Tax-Free Childcare eligibility on Best Start in Life](https://beststartinlife.gov.uk/childcare-early-years-education/tax-free-childcare/eligibility/)

### Modal: "What if I'm on leave from work?"

**Title:** What if I'm on leave from work?

**Body:**

> For childcare schemes like **30 Hours Childcare** and **Tax-Free Childcare**, you are usually treated as being in paid work even if you are currently on certain types of leave. This includes:
>
> - Maternity leave
> - Paternity leave
> - Shared parental leave
> - Adoption leave
> - Neonatal care leave
> - Bereaved partner paternity leave
> - Sick leave
> - Annual leave
>
> If you are on one of these types of leave and are applying on behalf of a different child than the one you are on leave for, you still count as working and can apply for or continue receiving funded childcare. You do not need to have returned to work first.
>
> However, if you are starting or returning to work after parental leave, there are specific rules about when you can first access your entitlement, based on which term your return date falls in.

**Links:**

- [30 Hours Childcare on GOV.UK](https://www.gov.uk/30-hours-free-childcare)
- [Full eligibility details on Best Start in Life](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/)

### Modal: "What's the income threshold as a monthly, quarterly, or annual figure?"

**Title:** What's the income threshold as a monthly, quarterly, or annual figure?

**Body:**

> The government sets the minimum earnings threshold as a 3-month figure, based on working 16 hours per week at the National Minimum Wage. Here are the thresholds shown weekly, monthly, over 3 months, and annually:

Values are rendered dynamically using `nmwForPeriod(bracket)` from `nmwThresholds.ts`. All three age brackets are shown.

> | Age                               | Weekly  | Monthly | 3 months  | Annually   |
> | --------------------------------- | ------- | ------- | --------- | ---------- |
> | 21+                               | £203.36 | £881.23 | £2,643.68 | £10,574.72 |
> | 18 to 20                          | £173.60 | £752.27 | £2,256.80 | £9,027.20  |
> | Under 18 or first year apprentice | £128.00 | £554.67 | £1,664.00 | £6,656.00  |
>
> These are **before tax** figures. You must expect to earn at least this much over the next 3 months to qualify for 30 Hours Childcare and Tax-Free Childcare.
>
> There is also a maximum: your adjusted net income must not exceed **£100,000 per year**.
>
> If you are **self-employed** and your business has been trading for less than 12 months, you can earn less than these thresholds and still be eligible.

**Link:** [Full eligibility details on Best Start in Life](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/)

### Modal: "What do these income thresholds mean?"

**Title:** What do these income thresholds mean?

**Body:**

Values in this table are rendered from `NMW_WEEKLY` in `nmwThresholds.ts`:

> To qualify for 30 Hours Childcare and Tax-Free Childcare, you must earn at least the National Minimum Wage for 16 hours per week. The thresholds are:
>
> | Age                    | Weekly minimum |
> | ---------------------- | -------------- |
> | 21 and over            | £203.36        |
> | 18 to 20               | £173.60        |
> | Under 18 or apprentice | £128.00        |
>
> If you are **self-employed** and your business has been trading for less than 12 months, you can earn less than these thresholds and still be eligible. You can use an average of your expected earnings over the current tax year.
>
> **Income that does not count** toward the minimum: dividends, interest, property income, and pension payments.
>
> If you have **multiple jobs**, your total earnings from all employment and self-employment count together.

**Link:** [Full eligibility details on Best Start in Life](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/)

### Modal: "What does "adjusted net income" mean?"

**Title:** What does "adjusted net income" mean?

**Body:**

> Adjusted net income (ANI) is the figure HMRC uses to decide whether you exceed the **£100,000 per year** cap for 30 Hours Childcare and Tax-Free Childcare.
>
> **How it is calculated**
>
> Start with your expected total taxable income (salary, self-employment profits, pensions, rental income, savings interest, dividends, etc.), then subtract:
>
> - Pension contributions paid gross (e.g. to a personal pension)
> - Gift Aid donations (grossed up by the basic rate of tax)
> - Trading losses and certain other tax reliefs
>
> The result is your adjusted net income. If it is over £100,000 in a tax year, you are not eligible for 30 Hours Childcare or Tax-Free Childcare for that period.
>
> Foreign and worldwide income is included in the calculation, regardless of where you are tax-resident.
>
> **Why it matters**
>
> If your gross salary is over £100,000, you may still be under the cap once pension contributions and Gift Aid are deducted. It is worth checking your adjusted figure before assuming you are ineligible.

**Links:**

- [Adjusted net income on GOV.UK](https://www.gov.uk/guidance/adjusted-net-income)
- [30 Hours eligibility on Best Start in Life](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/)

### Modal: "What is Carer's Allowance?"

**Condition:** Only shown when the qualifying allowance question is visible (i.e. user or partner selected "Not working").

**Title:** What is Carer's Allowance?

**Body:**

> Carer's Allowance is a benefit for people who spend at least 35 hours a week caring for someone with substantial caring needs. It is currently £86.45 per week.
>
> **Why it matters for childcare support**
>
> If you are not working but receive Carer's Allowance (or certain other benefits like Incapacity Benefit or Severe Disablement Allowance), your working partner (if they live with you) can still qualify the household for:
>
> - 30 Hours Childcare
> - Tax-Free Childcare
>
> This means a household where one person cares full-time and the other works can still access these schemes. However, if you are a single parent receiving Carer's Allowance (or other certain benefits) you will also need to be working and meet the income requirements to be eligible for 30 Hours Childcare.

**Link:** [Carer's Allowance on GOV.UK](https://www.gov.uk/carers-allowance)

### Modal: "Why are you asking about studying?"

**Condition:** Always shown (the studying question is always visible).

**Title:** Why we ask about studying

**Body:**

> Some childcare support schemes are specifically for parents who are studying. We ask about your study situation so we can check whether you might qualify for any of these.
>
> **Care to Learn**
>
> Helps young parents (under 20 at the start of their course) who are on a publicly funded course at school or further education level. It can pay up to £180 per child per week (or £195 in London) toward childcare costs while you study.
>
> **Learner Support**
>
> Discretionary funding from further education learning providers for students aged 19 or over. The amount and availability depend on your provider — they decide how to allocate their hardship funds, which can include help with childcare.
>
> **Childcare Grant**
>
> For full-time higher education students who are eligible for student finance. It provides up to £199.62 per week for one child, or £342.24 per week for two or more children. You do not have to pay it back.

**Links:**

- [Care to Learn on GOV.UK](https://www.gov.uk/care-to-learn)
- [Learner Support on GOV.UK](https://www.gov.uk/learner-support)
- [Childcare Grant on GOV.UK](https://www.gov.uk/childcare-grant)

### Modal: "What counts as a publicly funded course?"

**Condition:** Only shown when any person is studying at school/sixth form or further education level.

**Title:** What counts as a publicly funded course?

**Body:**

> A publicly funded course is one where the tuition fees are paid by the government rather than by you. This matters for **Care to Learn** eligibility.
>
> **Usually publicly funded**
>
> - Courses at state schools and sixth form colleges
> - Most courses at further education colleges (GCSEs, A-levels, T-levels, BTECs, NVQs, and other qualifications funded by the Education and Skills Funding Agency)
> - Apprenticeships (though Care to Learn does not apply to apprenticeships)
>
> **Usually not publicly funded**
>
> - Courses at private or independent schools
> - Courses where you pay the fees yourself
> - Some short commercial or leisure courses at FE colleges
>
> If you are unsure, ask your school or college — they can tell you whether your course is publicly funded.

**Link:** [Care to Learn on GOV.UK](https://www.gov.uk/care-to-learn)

### Modal: "What does 'eligible for student finance' mean?"

**Condition:** Only shown when any person is studying at higher education level.

**Title:** What does "eligible for student finance" mean?

**Body:**

> Student finance from Student Finance England provides tuition fee loans, maintenance loans, and grants to help with the cost of higher education. The **Childcare Grant** is only available to students who are eligible for student finance — even if you choose not to take out a loan.
>
> **You are usually eligible if**
>
> - You are studying your first higher education qualification (undergraduate degree, HND, foundation degree, etc.)
> - Your course is at a university or college in England
> - You meet the residency requirements (usually you must have been living in the UK for at least 3 years)
>
> **You may not be eligible if**
>
> - You already hold an equivalent or higher qualification (for example, studying a second degree)
> - Your course is not designated for student support
> - You do not meet the residency criteria
>
> If you are unsure, you can check with your university or apply to Student Finance England to find out — there is no obligation to accept funding if you are approved.

**Links:**

- [Student finance on GOV.UK](https://www.gov.uk/student-finance)
- [Childcare Grant on GOV.UK](https://www.gov.uk/childcare-grant)

---

## Step 5 — Benefits

### Questions

| #   | Label                                                                                           | Type     | Options     | Condition                                                                                             |
| --- | ----------------------------------------------------------------------------------------------- | -------- | ----------- | ----------------------------------------------------------------------------------------------------- |
| 1   | Do you get any of the following? / Do you or your partner get any of the following?             | Checkbox | See below   | Always shown. Label varies by whether partner exists.                                                 |
| 1a  | Will you be starting a job in the next month?                                                   | Radio    | "Yes", "No" | Shown if UC selected AND user is not working AND user does not receive qualifying allowance           |
| 1b  | Will your partner be starting a job in the next month?                                          | Radio    | "Yes", "No" | Shown if UC selected AND partner is not working AND partner does not receive qualifying allowance     |
| 1c  | Do you have a disability which results in a limited capacity for work (LCW / LCWRA)?            | Radio    | "Yes", "No" | Shown if UC selected AND user is not working AND Q1a = "No" AND partner IS working (or starting soon) |
| 1d  | Does your partner have a disability which results in a limited capacity for work (LCW / LCWRA)? | Radio    | "Yes", "No" | Shown if UC selected AND partner is not working AND Q1b = "No" AND user IS working (or starting soon) |

**Q1 checkbox options:**

1. "Universal Credit"
2. "The guaranteed element of Pension Credit"
3. "Income-related Employment and Support Allowance (ESA)"
4. "None of the above"

"None of the above" is mutually exclusive with all other options. Selecting it deselects all others; selecting any other deselects "None".

### Validation

| Error message                                                                                                                                                                | Trigger                                                                  |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| "Please answer this question to continue"                                                                                                                                    | Q1 is unanswered (null)                                                  |
| "Families where no parent has access to public funds, aren't eligible for these benefits. Please select 'None of the above', or go back and update your immigration status." | All parents have NRPF status AND a benefit other than "none" is selected |
| "Please answer this question to continue"                                                                                                                                    | Any conditional question (1a–1d) is visible but unanswered               |

### Modal: "How do benefits affect my childcare support?"

**Condition:** Always shown.

**Title:** How do benefits affect my childcare support?

**Body:**

> The benefits you receive affect which childcare support schemes are available to you.
>
> **Early Learning for 2-year-olds**
>
> If you receive income-related ESA, or Pension Credit, your 2-year-old may qualify for **15 funded hours per week over 38 weeks of the year.** Families on Universal Credit may also qualify if household income is £15,400 or less after tax.
>
> **Universal Credit childcare**
>
> If you are on Universal Credit and in paid work, you can claim back up to **85% of your childcare costs**, up to:
>
> - £1,071.09 per month for one child
> - £1,836.16 per month for two or more children
>
> **Tax-Free Childcare is not available with UC**
>
> Universal Credit and Tax-Free Childcare **cannot be used together**. If you receive Universal Credit, Tax-Free Childcare will not be included in your results.

**Links:**

- [UC Childcare eligibility on Best Start in Life](https://beststartinlife.gov.uk/childcare-early-years-education/universal-credit-childcare/eligibility-for-universal-credit-childcare/)
- [Which schemes can be combined](https://beststartinlife.gov.uk/childcare-early-years-education/combining-schemes/)

### Modal: "Why does starting work matter?"

**Condition:** Shown when UC is selected AND (user or partner) is not working.

**Title:** Why does starting work matter?

**Body:**

> Universal Credit childcare normally requires you to be in paid work. However, there is an exception: if you have a **confirmed job starting within the next month**, you can still qualify.
>
> This means you can arrange childcare before your start date, rather than waiting until you've started.
>
> **What counts as "starting work"?**
>
> You should have a confirmed offer with a start date in the next month. Simply looking for work or applying for jobs does not count.
>
> If you answer "Yes", we'll include UC Childcare in your results so you can see what support would be available once you start.

_Additional paragraph shown only when user has a partner:_

> If your partner is working and you are not, answering "No" does not necessarily rule out UC Childcare — we'll also check whether you have limited capacity for work, which can waive the work requirement.

### Modal: "What is limited capacity for work?"

**Condition:** Shown when user LCW question or partner LCW question is visible.

**Title:** What is limited capacity for work?

**Body:**

> **Limited capability for work (LCW)** and **limited capability for work-related activity (LCWRA)** are official assessments by the Department for Work and Pensions.
>
> If you have a health condition or disability that limits what work you can do, you may have been assessed as having LCW or LCWRA as part of your Universal Credit claim.
>
> **How would I know?**
>
> You would know if this applies to you — it is recorded in your Universal Credit journal and affects the amount of Universal Credit you receive. LCWRA adds an extra amount to your payment. If you're unsure, check your Universal Credit journal or speak to your work coach.
>
> **Why it matters for childcare**
>
> Normally, Universal Credit childcare requires the parent (and partner if you live with one) to be working. But if you or your partner has LCW or LCWRA, the **work requirement is waived** for that person. This means a couple where one parent works and the other has LCW or LCWRA can still claim Universal Credit childcare.

---

## Step 6 — Your children

### Intro text

> Tell us about your children so we can find the right support for each of them.

Each child is shown in its own card section labelled "Child 1", "Child 2", etc. Users can add children with an "Add a child +" button. A "Remove" button appears per child when there are 2 or more children.

### Questions — per child

| #   | Label                                                                                           | Type          | Options                                        | Condition           |
| --- | ----------------------------------------------------------------------------------------------- | ------------- | ---------------------------------------------- | ------------------- |
| 1   | First name (optional)                                                                           | Text input    | Free text, placeholder "Child {N}"             | Always shown        |
| 2   | Birth month / Birth year                                                                        | Two dropdowns | Months: January–December; Years: dynamic range | Always shown        |
| 3   | Does this child have a disability or special educational needs?                                 | Radio         | "No", "Yes"                                    | Always shown        |
| 3a  | Select any of the following:                                                                    | Checkbox      | See below                                      | Shown if Q3 = "Yes" |
| 4   | Are you a foster carer to this child?                                                           | Radio         | "No", "Yes"                                    | Always shown        |
| 4a  | Does this child have an education, health and care plan (EHCP)?                                 | Radio         | "No", "Yes"                                    | See condition below |
| 4b  | Has this child left care (in England or Wales) under an adoption order or special guardianship? | Radio         | "No", "Yes"                                    | See condition below |

**Q3a checkbox options:**

1. "This child gets Disability Living Allowance (DLA)"
2. "This child gets a Personal Independence Payment (PIP)"
3. "This child is registered blind"
4. "This child gets none of the above support"

"None of the above support" is mutually exclusive with the other options.

**Q4a/Q4b conditions (`shouldShowEhcpQuestions`):**

- Location is in England (LAD code starts with `E`)
- Child's birth month and year are set
- Child is term-eligible as a 2-year-old (`isTermEligible2YO`)
- Child is not fostered (`isFostered !== true`)
- Fostering question has been answered (`isFostered !== null`)
- Disability path is resolved: either `hasSEND` is false, or `hasSEND` is true and `sendDetails` is set
- Child does not already receive DLA (`sendDetails?.receivesDLA` is not true)

### Questions — household income (conditional section after all children)

| #   | Label                                                                                              | Type  | Options     | Condition                        |
| --- | -------------------------------------------------------------------------------------------------- | ----- | ----------- | -------------------------------- |
| 5   | Is your household income less than £15,400 per year, after tax and not including benefit payments? | Radio | "No", "Yes" | See UC income condition below    |
| 6   | Is your household income less than £{threshold} per year, after tax?                               | Radio | "No", "Yes" | See NRPF income condition below  |
| 7   | Do you have less than £16,000 in savings or investments?                                           | Radio | "No", "Yes" | See NRPF savings condition below |

**Q5 condition (`shouldShowUcIncomeQuestion`):**

- Qualifying benefits include "universal_credit"
- Location is in England
- At least one child passes all of:
  - Birth date set, term-eligible 2yo, not fostered, no DLA, `hasEHCP` = false, `hasLeftCareForAdoptionOrSpecialGuardianship` = false
  - All prerequisite questions answered (fostering, disability path, EHCP, care leaver)

**Q6/Q7 condition (`shouldShowNrpfQuestions`):**

- User has `residencyStatus` = "no_recourse_to_public_funds"
- Partner (if present) also has "no_recourse_to_public_funds"
- Location is in England
- At least one child passes the same prerequisite checks as Q5

**Q6 threshold values (`getNrpfThreshold`):**

| Area                                | 1 child | 2+ children |
| ----------------------------------- | ------- | ----------- |
| London (LAD code starts with `E09`) | £34,500 | £38,600     |
| Rest of England                     | £26,500 | £30,600     |

### Validation

| Error message                             | Trigger                                                |
| ----------------------------------------- | ------------------------------------------------------ |
| "Please select the child's date of birth" | Birth month or birth year not selected                 |
| "Please answer this question to continue" | Any unanswered radio/checkbox question that is visible |

Empty child names are auto-filled to "Child 1", "Child 2", etc. on Continue.

### Modal: "Why have you asked my child's name?"

**Condition:** Always shown.

**Title:** Why have you asked my child's name?

**Body:**

> Your child's name is only used to make later screens easier to follow. When you have more than one child, it helps you see which results and cost estimates belong to which child.
>
> This field is optional. If you leave it blank, we'll use "Child 1", "Child 2" and so on automatically.
>
> **Your privacy**
>
> The name stays entirely within your browser. It is never sent to a server, stored in a database, or shared with anyone.

### Modal: "What if I am expecting, or still planning my family?"

**Condition:** Always shown.

**Title:** What if I am expecting, or still planning my family?

**Body:**

> You can still use this tool to get an idea of what childcare might cost and which government support you could be eligible for. Simply enter a birth year in the past to see what support would be available for a child of that age today. You can also edit your responses to see how that support changes as they get older.
>
> **A few things to keep in mind**
>
> **Eligibility depends on age at the time** — funded hours and other schemes start at specific ages (from 9 months for working families, age 2 for some benefits-based support, and age 3 for universal hours). The estimate will reflect what would be available once your child reaches those ages.
>
> **Costs may change** — provider fees, government funding rates, and scheme rules can change between now and when your child starts childcare. Treat the figures as a guide based on today's rates.
>
> **Your circumstances may change too** — your working status, income, and household situation at the time you actually apply will determine your real eligibility, not what you enter today.
>
> **Parental leave** — if you or your partner will be on maternity, paternity, or shared parental leave, you are still treated as being in paid work for scheme eligibility purposes.
>
> This tool is designed to help you plan ahead. You can come back and run it again at any time as your circumstances become clearer.

### Modal: "Why does my child's age matter?"

**Condition:** Always shown.

**Title:** Why does my child's age matter?

**Body:**

> Different childcare schemes become available at different ages. Your child's date of birth determines which support they can access:
>
> | Age           | Available support                                                 |
> | ------------- | ----------------------------------------------------------------- |
> | From 9 months | 30 Hours Childcare (if parents are working)                       |
> | Age 2         | Early Learning for 2 year olds (if on certain benefits)           |
> | Age 3         | 15 Hours universal (all 3 and 4 year old children, no conditions) |
> | School age    | Free breakfast clubs, wraparound childcare                        |
> | Up to 11      | Tax-Free Childcare                                                |
> | Up to 16      | Universal Credit childcare                                        |
>
> Funded hours entitlements start from **the term after** your child reaches the qualifying age. For example, if your child turns 3 in February, they can access 15 hours from the following April.

**Link:** [Full age eligibility details on Best Start in Life](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/)

### Modal: "How does a disability affect childcare support?"

**Condition:** Always shown.

**Title:** How does a disability affect childcare support?

**Body:**

> Children with disabilities or long-term health conditions may qualify for additional childcare support:
>
> **15 Hours Early Learning for 2-year-olds** — a child receiving Disability Living Allowance or with an Education, Health and Care (EHC) plan automatically qualifies, regardless of family income.
>
> **Tax-Free Childcare** — the government top-up doubles to **£4,000 per year** (instead of £2,000) and extends until the child turns **16** (instead of 11). Payments can also cover specialist equipment.
>
> **Universal Credit childcare** — support extends until the 31st August after the child's 16th birthday.

**Link:** [Early Learning for 2-year-olds eligibility](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/additional-support/eligibility/)

### Modal: "What if I'm a foster carer?"

**Condition:** Always shown.

**Title:** What if I'm a foster carer?

**Body:**

> Foster children are not eligible for certain government childcare schemes. This is because local authorities are expected to cover childcare costs for looked-after children through foster care allowances.
>
> The following schemes are affected:
>
> **Tax-Free Childcare** — you cannot use a Tax-Free Childcare account to pay for childcare for a foster child.
>
> **Universal Credit childcare** — childcare costs for foster children cannot be claimed through Universal Credit.
>
> Funded hours entitlements (15 and 30 hours) are not affected by fostering status and remain available where the child meets the age and other eligibility criteria.
>
> If you are fostering and need help with childcare costs, contact your local authority fostering team to discuss what support is available through your foster care allowance.

### Modal: "What is an EHCP?"

**Condition:** Shown when any child passes `shouldShowEhcpQuestions` (see Q4a/Q4b conditions above).

**Title:** What is an education, health and care plan (EHCP)?

**Body:**

> An EHCP is a legal document for children and young people aged 0–25 with special educational needs or disabilities. It describes their needs and the extra support they should receive.
>
> EHCPs are issued by the local authority after a formal assessment known as an **EHC needs assessment**. Not all children with additional needs will have one — many receive informal "SEN support" at their setting instead.
>
> **Why it matters for childcare**
>
> If your child has an EHCP, they **automatically qualify** for 15 funded hours per week of early learning from age 2, regardless of family income or benefits. This is the same automatic entitlement as children receiving Disability Living Allowance.
>
> **SEN support is different from an EHCP**
>
> If your child receives SEN support but does not have a formal EHCP, they do not automatically qualify through this route. However, they may still qualify through other routes such as benefits or income.
>
> If you think your child may need an EHCP, you can request an assessment from your local authority.

**Link:** [EHC plans on GOV.UK](https://www.gov.uk/children-with-special-educational-needs/extra-SEN-help)

### Modal: "What does 'left care' mean here?"

**Condition:** Shown when any child passes `shouldShowEhcpQuestions` (same condition as EHCP modal).

**Title:** What does 'left care' mean here?

**Body:**

> This question applies to children who were previously **looked after by a local authority in England or Wales** (for example, in foster care or residential care) and have since left care through one of these legal routes:
>
> **An adoption order** — the child has been legally adopted.
>
> **A special guardianship order (SGO)** — a court order giving a non-parent (often a relative or former foster carer) parental responsibility.
>
> **A child arrangements order** — a court order specifying who the child lives with.
>
> **Why it matters for childcare**
>
> If your child left care under one of these routes, they **automatically qualify** for 15 funded hours per week of early learning from age 2, regardless of family income or benefits. This is the same automatic entitlement as children receiving Disability Living Allowance or with an EHCP.
>
> If your child was adopted privately (not from local authority care) or has always lived with you, this question does not apply — select "No".

### Modal: "What counts as household income?"

**Condition:** Shown when `shouldShowUcIncomeQuestion(formData)` OR `shouldShowNrpfQuestions(formData)` is true.

**Title:** What counts as household income?

**Body:**

> "Household income" means the combined income of you and your partner (if you have one), after tax.
>
> **What to include**
>
> - Employment income (wages, salary)
> - Self-employment profit
> - Pension income
>
> **What NOT to include**
>
> - Universal Credit or other benefit payments
> - Child Benefit
> - Housing Benefit or housing element of UC
>
> **Why it matters**
>
> This determines whether your 2-year-old qualifies for **15 funded hours per week (over 38 weeks of the year)** of early learning.

_Additional paragraph shown when UC income question is visible:_

> For families on Universal Credit, the threshold is **£15,400 per year** after tax, not including benefit payments.

_Additional content shown when NRPF questions are visible:_

> For families with no recourse to public funds, household income includes earned income and unearned income, such as payments received from charities, local authorities, or from friends and family. Parents should complete a self-declaration form of their income as part of their application and it is up to the local authority to determine if the income threshold has been met.
>
> For families with no recourse to public funds, the threshold also depends on where you live and how many children you have:
>
> | Area            | 1 child | 2+ children |
> | --------------- | ------- | ----------- |
> | London          | £34,500 | £38,600     |
> | Rest of England | £26,500 | £30,600     |

**Link:** [15 Hours Early Learning eligibility on Best Start in Life](https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/additional-support/eligibility/)

### Modal: "What counts as savings and investments?"

**Condition:** Shown when `shouldShowNrpfQuestions(formData)` is true.

**Title:** What counts as savings and investments?

**Body:**

> The £16,000 savings limit is your combined savings with your partner (if you have one).
>
> **What to include**
>
> - Bank and building society accounts
> - Cash ISAs
> - Stocks, shares, and other investments
> - Property you own but do not live in
>
> **What NOT to include**
>
> - The home you live in
> - Personal possessions
> - Business assets (if you are self-employed)
>
> **Why it matters**
>
> Families with no recourse to public funds must meet **both** the income threshold and the savings limit to qualify for 15 funded hours per week of early learning for their 2-year-old.

---

## Summary screen

Shown when the user has previously completed steps and returns, or after completing all steps. Displays a review of all answers before showing results.

### Title and subtitles

**Title:** Your answers so far

**Subtitle (varies by state):**

| State                                  | Subtitle                                                                                         |
| -------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Some answers are invalid after changes | "Some answers need updating after your changes. Update them below, then continue."               |
| Some steps not yet completed           | "We've kept your previous answers. Review them below, then continue to the remaining questions." |
| All steps completed                    | "You've answered all the questions. Review your answers below, or continue to see your results." |

### Per-step summary labels

Each completed step is shown with its label, a summary of the answers, and an "Edit" button (or "Update" if invalid).

| Step label         | Summary format                                                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| Where you live     | Normalised postcode (e.g. "SW1A 1AA")                                                                                           |
| Living situation   | "Lives with a partner" or "Single parent"                                                                                       |
| Immigration status | "You: British or Irish citizen, Has NI number" / "Partner: ..."                                                                 |
| Working situation  | "You: Earning £{threshold} or more per week" / "Partner: Self-employed, Earning less than £{threshold} per week"                |
| Benefits           | Benefit names joined by comma. Plus "Starting work within a month" and "Limited capacity for work (LCW/LCWRA)" if applicable.   |
| Your children      | Child names with birth dates and tags (e.g. "DLA", "fostered", "EHCP", "care leaver"). Plus UC/NRPF income and savings answers. |

### Invalid step message

> Needs updating — your earlier changes affected this step

### All-big-kids message (when all children are 5+)

> Unfortunately, we can't provide a cost estimate for older children at the moment. We don't currently have reliable average cost data for children aged 5 and over. You should contact childcare providers directly to see how much they charge.

### Buttons

| Button                             | Condition                                      |
| ---------------------------------- | ---------------------------------------------- |
| "Continue"                         | Shown when uncompleted or invalid steps remain |
| "Show results"                     | Shown when all steps are completed and valid   |
| "See your support options →"       | Shown when all children are 5+                 |
| "Search for childcare providers →" | Shown when all children are 5+                 |
| "← Start again from the beginning" | Always shown (resets all progress)             |

### Summary answer display values

**Working status labels:**

| Value             | Display                                                                                         |
| ----------------- | ----------------------------------------------------------------------------------------------- |
| earning_above_nmw | "Earning £{threshold} or more per week" (threshold from `NMW_WEEKLY[ageBracket]` or apprentice) |
| earning_below_nmw | "Earning less than £{threshold} per week"                                                       |
| not_working       | "Not working"                                                                                   |
| income_over_100k  | "Adjusted net income over £100,000" (non-apprentice only)                                       |

Note: `earning_above_apprentice_nmw` exists in the type system for data compatibility but is never shown as a radio option or summary label.

**Residency status labels:**

| Value                             | Display                                                                         |
| --------------------------------- | ------------------------------------------------------------------------------- |
| british_irish_citizen             | British or Irish citizen                                                        |
| settled_status                    | I am a citizen of an EU or EEA country, or Switzerland, with settled status     |
| pre_settled_status                | I am a citizen of an EU or EEA country, or Switzerland, with pre-settled status |
| permission_to_access_public_funds | Permission to access public funds                                               |
| no_recourse_to_public_funds       | No recourse to public funds                                                     |
| other                             | Other or unsure                                                                 |

**Benefit labels:**

| Value            | Display                             |
| ---------------- | ----------------------------------- |
| universal_credit | Universal Credit                    |
| pension_credit   | Pension Credit (guaranteed element) |
| esa              | Income-related ESA                  |
| none             | None                                |

**Care type labels:**

| Value                | Display                                     |
| -------------------- | ------------------------------------------- |
| private_nursery      | Nursery (Private, Voluntary or Independent) |
| school_based_nursery | School-based nursery                        |
| childminder          | Childminder                                 |
| breakfast_club       | Breakfast club                              |
| free_breakfast_club  | Free breakfast club                         |
| after_school_club    | After school club                           |
| holiday_club         | Holiday club                                |

---

# Cost Estimator — Questionnaire Text for Policy Sign-Off

All user-facing text from the multi-step "How much is childcare going to cost?" form. This page shares steps 1–6 with the support form above, adding a 7th step for childcare arrangements.

**Page title:** How much is childcare going to cost?

**Page subtitle:** Get a personalised estimate of your annual childcare costs and the government support available.

**Page date line:** Last updated: February 2026

---

## Step order

| #   | Step label             | Component              | Step title shown to user    |
| --- | ---------------------- | ---------------------- | --------------------------- |
| 1   | Where you live         | PostcodeStep           | Where do you live?          |
| 2   | Living situation       | PartnerStep            | Do you live with a partner? |
| 3   | Immigration status     | ImmigrationStep        | Immigration status          |
| 4   | Working situation      | WorkingStep            | Your working situation      |
| 5   | Benefits               | UniversalCreditStep    | Benefits                    |
| 6   | Your children          | ChildrenStep           | Your children               |
| 7   | Childcare arrangements | ChildcareSelectionStep | Childcare arrangements      |

Steps 1–6 are identical to the support form documented above. Only step 7 is new.

After all steps are completed, the user is taken to a **Cost Results** page.

---

## Step 7 — Childcare arrangements

### Intro text

> For each child, select the types of childcare they use and configure the hours or sessions.

If all children are aged 5 or over ("big kids"), the intro text changes:

> Although we can't create a cost estimate for your children, you may still be eligible for government benefits and you can still check our database of childcare providers.

**Continue button label:** Show your cost estimate

**Continue button disabled** when all children are big kids.

---

### Per-child card

Each child is shown in a card with the heading:

> **{firstName} ({age} old)**

Age is formatted as e.g. "2 years, 3 months old" or "8 months old".

---

### Care type availability by child age

| Age range    | Available care types                                                                                                                                 |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0–23 months  | Nursery (Private, Voluntary or Independent), Childminder                                                                                             |
| 24–47 months | Nursery (Private, Voluntary or Independent), School-based nursery, Childminder                                                                       |
| 48–59 months | Nursery (Private, Voluntary or Independent), School-based nursery, Childminder, Breakfast club, Free breakfast club, After school club, Holiday club |
| 60+ months   | No cost estimate (see "Big kid handling" below)                                                                                                      |

---

### Adding and removing selections

Each child starts with no childcare selections. The user adds selections with:

> **[Add childcare type +]** (button)

Each selection shows:

- A heading row with **"Type of care"** label and a **"Remove"** button on the same line
- A **care type radio group** (filtered to the types available for the child's age)
- **Usage inputs** (see below)
- **Weeks per year** radio group (nursery types only; see below)
- A **provider selection dropdown** (optional; see below)

---

### Usage inputs by care type

#### Nursery (Private, Voluntary or Independent) / School-based nursery

| Field                   | Type   | Range | Placeholder    |
| ----------------------- | ------ | ----- | -------------- |
| Morning sessions/week   | number | 0–7   | Enter a number |
| Afternoon sessions/week | number | 0–7   | Enter a number |

**Weeks per year** (radio group, shown for nursery types only):

| Option                 | Label                                          |
| ---------------------- | ---------------------------------------------- |
| Default (PVI)          | "For 50 weeks per year (year-round)"           |
| Default (school-based) | "For 38 weeks per year (term-time only)"       |
| Custom                 | "Custom" — reveals a number input (range 1–52) |

The default radio option depends on the nursery type. When "Custom" is selected, a text input appears allowing the user to enter a specific number of weeks. The value is stored as `selection.weeksPerYear`.

#### Childminder

| Field          | Type   | Range | Placeholder    |
| -------------- | ------ | ----- | -------------- |
| Hours per week | number | 0–168 | Enter a number |
| Weeks per year | number | 0–52  | Default: 44    |

#### Holiday club

| Field         | Type   | Range | Placeholder    |
| ------------- | ------ | ----- | -------------- |
| Days per year | number | 0–365 | Enter a number |

#### Breakfast club / Free breakfast club / After school club

| Field         | Type   | Range | Placeholder    |
| ------------- | ------ | ----- | -------------- |
| Days per week | number | 0–7   | Enter a number |

---

### Provider selection

Below the care type dropdown, a provider selection dropdown is shown:

- **Default option:** "Use average costs for {postcode}"
- **Shortlisted providers** that offer the selected care type
- **Link option:** "Shortlist childcare providers →" (navigates to the provider search page)

If the selected provider's age range does not match the child's age, a warning is shown:

> ⚠ Child's age is outside this provider's range ({minAge} to {maxAge})

Other provider warnings:

- "This provider does not list this care type"
- "No eligibility requirements specified — check with provider"

---

### Validation

**On submit, if no childcare types have been added for any estimatable child:**

> Add at least one childcare type to get a cost estimate

**On submit, if any usage field is empty or out of range:**

> Enter a number between {min} and {max}

**If a usage field has a value of zero:**

> This has zero usage — it won't affect your estimate

---

### Big kid handling (children aged 5+)

Children aged 60 months or over do not get cost inputs. Instead, their card shows:

> We can't estimate childcare costs for **{childName}** yet. We don't currently have reliable average cost data for children aged 5 and over. You'll need to get costs directly from your childcare providers.

If the child is eligible for any government schemes, the card also shows:

> However, **{childName}** may still be eligible for a range of government support:

Followed by a bulleted list of eligible scheme names and descriptions.

When all children are big kids, secondary action buttons are shown:

> **[See your support options →]** (navigates to support results)
>
> **[Search for childcare providers →]** (navigates to provider search)

---

### Footer

Below the step content, a footer link is shown:

> ℹ How are cost estimates calculated?

Clicking this opens a modal.

---

### Modal: "Can I choose the number of weeks per year?"

**Title:** Can I choose the number of weeks per year?

**Body:**

> Not all childcare providers operate for the same number of weeks per year. The default we show depends on the type of provider:
>
> - **Private, voluntary or independent (PVI) nurseries** — typically open year-round, around 50 weeks per year. Some may require you to pay for all 50 weeks even if your child attends fewer. Check with your provider whether a shorter arrangement is available.
> - **School-based nurseries** — usually operate during term time only (38 weeks per year). This is generally fixed and cannot be changed.
> - **Childminders** — vary widely. Many work around 44–50 weeks per year, but this depends on your individual arrangement with them.
>
> If your provider offers a different number of weeks (for example 44 or 48), select "Custom" and enter the number of weeks they require you to pay for.
>
> If you're unsure how many weeks your provider operates, check with them directly.

### Modal: "How are cost estimates calculated?"

**Title:** How are cost estimates calculated?

**Body:**

> We estimate what you would pay for childcare after government support has been applied. Here is how it works:

_When provider estimates are enabled (`VITE_FEATURE_NO_ADDITIONAL_CHARGES` is not set):_

> - **Shortlisted provider** — if you have selected a specific provider from your shortlist, we use their actual published fees.
> - **Average costs** — if no provider is selected, we use the average childcare costs for your postcode area, based on data from local providers.

_When provider estimates are disabled (`VITE_FEATURE_NO_ADDITIONAL_CHARGES` is set):_

> - **Average costs** — we use average childcare costs from the DfE Early Years Childcare Provider Survey (2025) to estimate what you might pay in your area.
> - **Cost range** — we show you a range of estimates to give you an idea of how much your actual childcare costs might vary from our estimate.
> - **Older children** — at the moment we only have average costs for early years childcare.

_Always shown:_

> - **Funded hours** — any government-funded hours your child is eligible for (15 or 30 hours per week for 38 weeks of the year) are deducted automatically, reducing the total cost.
> - **Tax-Free Childcare** — if eligible, the government's 20% top-up is applied (for every £8 you pay, the government adds £2, up to £2,000 per child per year).
> - **Universal Credit childcare** — if eligible, we show the 85% reimbursement that would be included in your Universal Credit payment.
>
> The estimate is a guide based on the information you have provided. Actual costs may vary depending on your provider and exact circumstances.

**Links:**

- [How Tax-Free Childcare works](https://beststartinlife.gov.uk/childcare-early-years-education/tax-free-childcare/how-it-works/)
- [How Universal Credit childcare works](https://beststartinlife.gov.uk/childcare-early-years-education/universal-credit-childcare/how-universal-credit-childcare-works/)

---

## Cost Results page — Explainers

These modals appear conditionally on the cost results page.

### Modal: "Why have you calculated a cost range?"

**Condition:** Shown when `showRange` is true (i.e. cost range data is available).

**Title:** Why have you calculated a cost range?

**Body:**

> Childcare costs and services vary between providers.
>
> To give you the best idea, we use average childcare costs from the DfE Early Years Childcare Provider Survey (2025) to estimate what you might pay in your area.
>
> Where we can, we calculate an estimate of the likely cost range for your local authority.
>
> Where there are insufficient responses, we use regional or national calculations.
>
> Because the way some of your government entitlements are applied depend on the actual childcare costs, we then calculate a full estimate for these lower and upper bounds.

### Modal: "How were my {careType} costs calculated?"

**Condition:** Shown per care type when `feeSource.rateDetails` has entries (i.e. survey-derived rates were used).

**Title:** How were my {careType} costs calculated?

**Body:**

> These figures are based on data from the DfE Early Years Childcare Provider Survey (2025), which collects cost information from childcare providers across England.
>
> _{Dynamic area explanation based on feeSource scope (LA, region, or national)}_
>
> The table below shows the range of rates used in our calculations. The **lower** and **upper** represent a likely range of costs. They aren't the absolute highest and lowest costs in your area. The **average** is a weighted mean rate, which gives you a best estimate.
>
> You should always check with local providers directly to get the best possible estimate of your costs.

_(Dynamic table of rate details: Rate | Lower | Average | Upper)_

_(If session hours are available, an additional table shows typical session durations: Morning, Afternoon, Full day with their hours)_

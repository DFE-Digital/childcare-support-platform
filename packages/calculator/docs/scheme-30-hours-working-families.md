# 30 hours childcare for eligible working families in England

Available for children aged 9 months to 4 years.

## Frontend text (from schemes.json)

| Field                   | Value                                                                                                                            |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Name                    | 30 hours childcare for eligible working families in England                                                                      |
| Description             | 30 hours per week (over 38 weeks of the year) of funded early education for children of working parents aged 9 months to 4 years |
| All schemes description | Available for children aged 9 months to 4 years.                                                                                 |
| Financial type          | `funded_hours`                                                                                                                   |

### Links

| Label        | URL                                                                                                                   |
| ------------ | --------------------------------------------------------------------------------------------------------------------- |
| Eligibility  | https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/eligibility/  |
| How it works | https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/working-families/how-it-works/ |

### Caveats shown to all users

1. (!) Providers may charge separately for meals, nappies, additional hours, and trips.
2. Charges for extras must not be mandatory or a condition of a funded place.
3. Cannot be used with nannies, home carers, or relatives.
4. If you are on maternity, paternity, adoption, or shared parental leave for this child, the date of return to work affects which term access begins.
5. (!) You must reconfirm your eligibility every 3 months.
6. (!) Parents must apply for 30 hours childcare the term before they want to use a 30 hours place. This means parents must apply by 31st March/August/December before they want their child to start a place.
7. If eligible, you can use this scheme until your child starts school, usually when they begin Reception.

### Conditional caveats (from calculator)

| Code                                 | Message                                                                                                            | Condition                                                                                 |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| `partner_carers_allowance_exemption` | "Your partner's Carer's Allowance exempts them from the work requirement."                                         | Couple only: partner not working but receives a qualifying allowance (other parent works) |
| `user_carers_allowance_exemption`    | "Your Carer's Allowance exempts you from the work requirement."                                                    | Couple only: user not working but receives a qualifying allowance (partner works)         |
| `user_self_employed_startup`         | "You may qualify under the self-employed start-up exception even if earning below the minimum threshold."          | User is self-employed < 12 months and below earnings threshold                            |
| `partner_self_employed_startup`      | "Your partner may qualify under the self-employed start-up exception even if earning below the minimum threshold." | Partner is self-employed < 12 months and below earnings threshold                         |
| `apply_with_public_funds_parent`     | "The parent who applies for this benefit must be the one who has access to public funds."                          | One parent has public funds access, the other does not                                    |

## Eligibility

**Rule: ALL conditions must be met.** Each child is evaluated independently. A single ❌ means that child is **ineligible** for this scheme.

### Child conditions

| #   | Condition              | Met | Not met | Code reference                                                    | Notes                                                                                         |
| --- | ---------------------- | :-: | :-----: | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 1   | Child is 9+ months old | ✅  |   ❌    | `getChildAgeInMonths(child) >= 9`                                 | Uses `child.birthMonth`, `child.birthYear`                                                    |
| 2   | Child is pre-school    | ✅  |   ❌    | `isPreSchool(child)` → uses `child.birthMonth`, `child.birthYear` | Starts Reception in September after turning 4 (born Jan-Aug) or following year (born Sep-Dec) |

### Parent work requirement (both must work, or exceptions apply)

**Single parent:**

| #   | Condition         | Met | Not met | Code reference                                                                     | Notes |
| --- | ----------------- | :-: | :-----: | ---------------------------------------------------------------------------------- | ----- |
| 3   | Parent is working | ✅  |   ❌    | `isParentWorking(user)` → checks `user.workingStatus` is any earning/income status |       |

**Couple:**

| #   | Scenario                                                 | Result | Code reference                                                           | Notes                                                                                                                                                   |
| --- | -------------------------------------------------------- | :----: | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 3a  | Both working                                             |   ✅   | `isParentWorking(user) && isParentWorking(partner)`                      |                                                                                                                                                         |
| 3b  | Neither working                                          |   ❌   | `!isParentWorking(user) && !isParentWorking(partner)`                    |                                                                                                                                                         |
| 3c  | One works, other receives a qualifying allowance         |   ✅   | `hasNonWorkingPartnerException()` → `person.receivesQualifyingAllowance` | Qualifying allowances: Carer's Allowance, Carer Support Payment (Scotland), Incapacity Benefit, Severe Disablement Allowance, or contribution-based ESA |
| 3d  | One works, other does not receive a qualifying allowance |   ❌   | `!hasNonWorkingPartnerException()`                                       |                                                                                                                                                         |

### Earnings threshold (only checked if work requirement passes)

The working parent (and partner if they live with one) must be expecting to earn at or above the minimum threshold for their age bracket, over the next three months from when they apply. Threshold values derive from `NMW_WEEKLY` in `packages/calculator/src/nmwThresholds.ts`.

| #   | Age bracket | Minimum weekly earnings | First-year apprentice override | Code reference                          |
| --- | ----------- | ----------------------- | ------------------------------ | --------------------------------------- |
| 4a  | 16-17       | £128.00/week            | £128.00/week (same)            | `workingStatus === "earning_above_nmw"` |
| 4b  | 18-20       | £173.60/week            | £128.00/week                   | `workingStatus === "earning_above_nmw"` |
| 4c  | 21+         | £203.36/week            | £128.00/week                   | `workingStatus === "earning_above_nmw"` |

The form shows the age-appropriate threshold (or apprentice threshold for first-year apprentices). In all cases, the user selects `earning_above_nmw` to indicate they meet the threshold shown. First-year apprentices see £128 because the form uses `NMW_WEEKLY[APPRENTICE_BRACKET]` when `firstYearApprentice === true`.

**`isParentMeetingEarningsThreshold(person)` logic:**

```
income_over_100k → true
earning_above_nmw → true
earning_above_apprentice_nmw AND isApprentice AND firstYearApprentice → true (data compatibility only)
otherwise → false
```

| #   | Scenario                                          | Result | Code reference                                                                                           | Notes                                                      |
| --- | ------------------------------------------------- | :----: | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| 4d  | Both parent and partner meet threshold            |   ✅   | `isParentMeetingEarningsThreshold(user) && isParentMeetingEarningsThreshold(partner)`                    | Also passes if `workingStatus === "income_over_100k"`      |
| 4e  | Parent below threshold, self-employed < 12 months |   ⚠️   | `hasSelfEmployedStartupException()` → `person.isSelfEmployed && person.selfEmployedLessThanTwelveMonths` | Caveat: may qualify under self-employed start-up exception |
| 4f  | Parent below threshold, not self-employed startup |   ❌   | `!isParentMeetingEarningsThreshold() && !hasSelfEmployedStartupException()`                              |                                                            |

### Income cap

| #   | Condition                                                | Met | Not met | Code reference                                 | Notes                                       |
| --- | -------------------------------------------------------- | :-: | :-----: | ---------------------------------------------- | ------------------------------------------- |
| 5   | User's adjusted net income ≤ £100,000                    | ✅  |   ❌    | `user.workingStatus !== "income_over_100k"`    | Checked independently of earnings threshold |
| 6   | Partner's adjusted net income ≤ £100,000 (if applicable) | ✅  |   ❌    | `partner.workingStatus !== "income_over_100k"` |                                             |

### England location

| #   | Condition               | Met | Not met | Code reference                                  | Notes                                                       |
| --- | ----------------------- | :-: | :-----: | ----------------------------------------------- | ----------------------------------------------------------- |
| 7   | Parent lives in England | ✅  |   ❌    | `isEnglandLocation(data)` → LAD code prefix `E` | Derived from postcode at entry time; stored in `ladCodes[]` |

### Public funds access

| #   | Condition                                      | Met | Not met | Code reference                                                  | Notes                                                      |
| --- | ---------------------------------------------- | :-: | :-----: | --------------------------------------------------------------- | ---------------------------------------------------------- |
| 8   | At least one parent has access to public funds | ✅  |   ❌    | `hasEligibleResidency(user) \|\| hasEligibleResidency(partner)` | Same statuses as TFC, but only one parent needs to qualify |

### NI number

| #   | Condition                                               | Met | Not met | Code reference                            | Notes |
| --- | ------------------------------------------------------- | :-: | :-----: | ----------------------------------------- | ----- |
| 9   | User has a National Insurance number                    | ✅  |   ❌    | `data.user.hasNationalInsuranceNumber`    |       |
| 10  | Partner has a National Insurance number (if applicable) | ✅  |   ❌    | `data.partner.hasNationalInsuranceNumber` |       |

### Summary

**Eligible** = conditions 1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10 all pass (logical AND).

Any single failure produces an ineligibility reason. Multiple failures are all reported to the user.

---

## Funded hours calculation

When a child is eligible for this scheme, funded hours reduce the parent's childcare costs. The hours are treated as **free at point of use** — no shortfall is charged to the parent.

### Formula

```
actual funded hours = min(funded hours remaining in pool, weekly hours of the selection)

saving per hour = effective hourly rate (full rate, not capped at government funding rate)

applicable weeks = min(38, selection weeks per year)

saving to parent = actual funded hours × saving per hour × applicable weeks
```

The government funding rate must be positive for the reduction to apply, but the saving amount is based on the effective hourly rate — not the government rate.

### Stacking with 15 Hours 2-Year-Olds

From September 2025, the full 30 hours is available for all eligible ages (9 months to school age). For age-2 children eligible for both this scheme and the 15 Hours 2-Year-Olds (disadvantage) entitlement:

- The 15 Hours 2YO entitlement is applied **first** (15 hours/week)
- The 30 Hours WF allocation is then reduced so the total does not exceed 30 hours (i.e. 15 hours from this scheme)
- Total funded pool: **30 hours/week**

The disadvantage entitlement is listed first because it is not contingent on work status — if the parent stops working, the 15 Hours 2YO entitlement remains.

# Tax-Free Childcare

Get up to £2,000 per year towards childcare costs. The government tops up every £8 you pay with an extra £2.

## Frontend text (from schemes.json)

| Field                       | Value                                                                                                              |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Name                        | Tax-Free Childcare                                                                                                 |
| Description                 | Get up to £{annualCap} per year towards childcare costs. The government tops up every £8 you pay with an extra £2. |
| All schemes description     | If you're a working parent or carer, you can get a £2 top-up for every £8 that you pay towards childcare.          |
| Description template        | `{annualCap}`: default "2,000"; "4,000" for disabled children                                                      |
| Financial type              | `top_up`                                                                                                           |
| Top-up rate                 | 25% (government adds £2 for every £8 paid)                                                                         |
| Max government contribution | £2,000/year per child (£4,000 if disabled)                                                                         |

### Links

| Label        | URL                                                                                             |
| ------------ | ----------------------------------------------------------------------------------------------- |
| Eligibility  | https://beststartinlife.gov.uk/childcare-early-years-education/tax-free-childcare/eligibility/  |
| How it works | https://beststartinlife.gov.uk/childcare-early-years-education/tax-free-childcare/how-it-works/ |

### Caveats shown to all users

1. (!) You must reconfirm your eligibility every 3 months.
2. (!) Cannot be used alongside Universal Credit
3. You will need to apply through the childcare service.
4. The government top-up is per child, not per family.

### Conditional caveats (from calculator)

| Code                                 | Message                                                                                                            | Condition                                                         |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| `partner_carers_allowance_exemption` | "Your partner's Carer's Allowance exempts them from the work requirement."                                         | Partner not working but receives a qualifying allowance           |
| `user_carers_allowance_exemption`    | "Your Carer's Allowance exempts you from the work requirement."                                                    | User not working but receives a qualifying allowance              |
| `user_self_employed_startup`         | "You may qualify under the self-employed start-up exception even if earning below the minimum threshold."          | User is self-employed < 12 months and below earnings threshold    |
| `partner_self_employed_startup`      | "Your partner may qualify under the self-employed start-up exception even if earning below the minimum threshold." | Partner is self-employed < 12 months and below earnings threshold |
| `apply_with_public_funds_parent`     | "The parent who applies for this benefit must be the one who has access to public funds."                          | One parent has public funds access, the other does not            |
| `tfc_bursary_ineligible`             | "You are not eligible if you receive a childcare bursary or grant, or childcare vouchers."                         | Always shown                                                      |
| _(inline)_                           | "Your disabled child qualifies for a higher cap of £4,000/year government contribution."                           | Child has disability and all eligibility conditions pass          |

## Eligibility

**Rule: ALL conditions must be met.** Each child is evaluated independently. A single ❌ means that child is **ineligible** for this scheme.

### Child conditions

| #   | Condition                 | Met | Not met | Code reference                                           | Notes                         |
| --- | ------------------------- | :-: | :-----: | -------------------------------------------------------- | ----------------------------- |
| 1   | Child is within age limit | ✅  |   ❌    | `getChildAgeInYears(child) <= (child.hasSEND ? 16 : 11)` | Max age 11, or 16 if disabled |
| 2   | Child is not fostered     | ✅  |   ❌    | `!child.isFostered`                                      |                               |

### Parent work requirement

Same logic as 30 Hours Working Families.

**Single parent:**

| #   | Condition         | Met | Not met | Code reference                                        | Notes |
| --- | ----------------- | :-: | :-----: | ----------------------------------------------------- | ----- |
| 3   | Parent is working | ✅  |   ❌    | `isParentWorking(user)` → checks `user.workingStatus` |       |

**Couple:**

| #   | Scenario                                                 | Result | Code reference                                                           | Notes                                                                                                                                                   |
| --- | -------------------------------------------------------- | :----: | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 3a  | Both working                                             |   ✅   | `isParentWorking(user) && isParentWorking(partner)`                      |                                                                                                                                                         |
| 3b  | Neither working                                          |   ❌   | `!isParentWorking(user) && !isParentWorking(partner)`                    |                                                                                                                                                         |
| 3c  | One works, other receives a qualifying allowance         |   ✅   | `hasNonWorkingPartnerException()` → `person.receivesQualifyingAllowance` | Qualifying allowances: Carer's Allowance, Carer Support Payment (Scotland), Incapacity Benefit, Severe Disablement Allowance, or contribution-based ESA |
| 3d  | One works, other does not receive a qualifying allowance |   ❌   | `!hasNonWorkingPartnerException()`                                       |                                                                                                                                                         |

### Earnings threshold (only checked if work requirement passes)

Same thresholds and logic as 30 Hours Working Families. Values derive from `NMW_WEEKLY` in `packages/calculator/src/nmwThresholds.ts`.

| #   | Age bracket | Minimum weekly earnings | First-year apprentice override | Code reference                          |
| --- | ----------- | ----------------------- | ------------------------------ | --------------------------------------- |
| 4a  | 16-17       | £128.00/week            | £128.00/week (same)            | `workingStatus === "earning_above_nmw"` |
| 4b  | 18-20       | £173.60/week            | £128.00/week                   | `workingStatus === "earning_above_nmw"` |
| 4c  | 21+         | £203.36/week            | £128.00/week                   | `workingStatus === "earning_above_nmw"` |

See scheme-30-hours-working-families.md for full `isParentMeetingEarningsThreshold()` logic.

| #   | Scenario                                          | Result | Code reference                                                                                           | Notes                                                      |
| --- | ------------------------------------------------- | :----: | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| 4d  | Both parents meet threshold                       |   ✅   | `isParentMeetingEarningsThreshold(user) && isParentMeetingEarningsThreshold(partner)`                    | Also passes if `workingStatus === "income_over_100k"`      |
| 4e  | Parent below threshold, self-employed < 12 months |   ⚠️   | `hasSelfEmployedStartupException()` → `person.isSelfEmployed && person.selfEmployedLessThanTwelveMonths` | Caveat: may qualify under self-employed start-up exception |
| 4f  | Parent below threshold, not self-employed startup |   ❌   | `!isParentMeetingEarningsThreshold() && !hasSelfEmployedStartupException()`                              |                                                            |

### Income cap

| #   | Condition                                                | Met | Not met | Code reference                                 | Notes |
| --- | -------------------------------------------------------- | :-: | :-----: | ---------------------------------------------- | ----- |
| 5   | User's adjusted net income ≤ £100,000                    | ✅  |   ❌    | `user.workingStatus !== "income_over_100k"`    |       |
| 6   | Partner's adjusted net income ≤ £100,000 (if applicable) | ✅  |   ❌    | `partner.workingStatus !== "income_over_100k"` |       |

### Universal Credit exclusion

| #   | Condition                            | Met | Not met | Code reference                                          | Notes                                       |
| --- | ------------------------------------ | :-: | :-----: | ------------------------------------------------------- | ------------------------------------------- |
| 7   | Household is NOT on Universal Credit | ✅  |   ❌    | `!data.qualifyingBenefits.includes("universal_credit")` | TFC and UC childcare are mutually exclusive |

### UK residency

| #   | Condition              | Met | Not met | Code reference                                 | Notes                                                       |
| --- | ---------------------- | :-: | :-----: | ---------------------------------------------- | ----------------------------------------------------------- |
| 8   | Parent lives in the UK | ✅  |   ❌    | `isUkLocation(data)` → LAD code prefix E/W/S/N | Derived from postcode at entry time; stored in `ladCodes[]` |

### Public funds access

| #   | Condition                                      | Met | Not met | Code reference                                                  | Notes                                                           |
| --- | ---------------------------------------------- | :-: | :-----: | --------------------------------------------------------------- | --------------------------------------------------------------- |
| 9   | At least one parent has access to public funds | ✅  |   ❌    | `hasEligibleResidency(user) \|\| hasEligibleResidency(partner)` | Same statuses as 30 Hours, but only one parent needs to qualify |

### NI number

| #   | Condition                                               | Met | Not met | Code reference                            | Notes |
| --- | ------------------------------------------------------- | :-: | :-----: | ----------------------------------------- | ----- |
| 10  | User has a National Insurance number                    | ✅  |   ❌    | `data.user.hasNationalInsuranceNumber`    |       |
| 11  | Partner has a National Insurance number (if applicable) | ✅  |   ❌    | `data.partner.hasNationalInsuranceNumber` |       |

### Disability bonus (caveat only, not an eligibility condition)

| Scenario                                             | Result | Code reference                          | Notes                                                       |
| ---------------------------------------------------- | :----: | --------------------------------------- | ----------------------------------------------------------- |
| Child has a disability and all other conditions pass |   ⚠️   | `child.hasSEND && reasons.length === 0` | Caveat: "higher cap of £4,000/year government contribution" |

### Summary

**Eligible** = conditions 1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10 + 11 all pass (logical AND).

#### Differences from 30 Hours Working Families

| Check              | 30 Hours                                         | Tax-Free Childcare                               |
| ------------------ | ------------------------------------------------ | ------------------------------------------------ |
| Child age range    | 9 months to pre-school                           | 0–11 (0–16 if disabled)                          |
| Foster exclusion   | No                                               | Yes                                              |
| NI number required | Yes                                              | Yes                                              |
| Location check     | England only                                     | UK-wide                                          |
| Public funds       | Yes (at least one parent must have public funds) | Yes (at least one parent must have public funds) |
| UC exclusion       | No                                               | Yes                                              |

---

## Interaction with funded hours

The TFC top-up is calculated on the **net cost after funded hours have been deducted**:

```
eligible costs = gross childcare fees − funded hours saving
```

The £2,000/year cap (£4,000 for disabled children) applies per child to the **government's contribution**, not to the parent's payment. The parent pays 80% of eligible costs up to the cap; the government tops up the remaining 20%.

With additional charges excluded (via `VITE_FEATURE_NO_ADDITIONAL_CHARGES` feature flag), TFC applies to childcare fees minus funded hours only.

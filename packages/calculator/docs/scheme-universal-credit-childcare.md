# Universal Credit childcare

Get up to 85% of your childcare costs paid back, up to £1,071.09 per month for one child.

## Frontend text (from schemes.json)

| Field                   | Value                                                                                     |
| ----------------------- | ----------------------------------------------------------------------------------------- |
| Name                    | Universal Credit childcare                                                                |
| Description             | Get up to 85% of your childcare costs paid back, up to £1,071.09 per month for one child. |
| All schemes description | For working families claiming Universal Credit.                                           |
| Financial type          | `reimbursement`                                                                           |
| Reimbursement rate      | 85%                                                                                       |
| Monthly caps            | £1,071.09 (one child), £1,836.16 (two or more children)                                   |

### Links

| Label        | URL                                                                                                                                   |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| Eligibility  | https://beststartinlife.gov.uk/childcare-early-years-education/universal-credit-childcare/eligibility-for-universal-credit-childcare/ |
| How it works | https://beststartinlife.gov.uk/childcare-early-years-education/universal-credit-childcare/how-universal-credit-childcare-works/       |

### Caveats shown to all users

1. You must pay for childcare yourself first, then claim reimbursement.
2. Cannot be used alongside Tax-Free Childcare.
3. Childcare must be with an Ofsted-registered provider (in England).
4. No minimum hours requirement, but childcare hours must relate to hours worked.
5. You may be eligible for an initial upfront childcare cost payment to help with costs before your first reimbursement.

### Conditional caveats (from calculator)

| Code                             | Message                                                                                   | Condition                                              |
| -------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `apply_with_public_funds_parent` | "The parent who applies for this benefit must be the one who has access to public funds." | One parent has public funds access, the other does not |

## Eligibility

**Rule: ALL conditions must be met.** Each child is evaluated independently. A single ❌ means that child is **ineligible** for this scheme.

### Child conditions

| #   | Condition                                      | Met | Not met | Code reference                                                                                                           | Notes                                                            |
| --- | ---------------------------------------------- | :-: | :-----: | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| 1   | Before 1 September after child's 16th birthday | ✅  |   ❌    | `referenceDate < cutoffDate` where cutoff = 1 Sep of year child turns 16 (born Jan-Aug) or following year (born Sep-Dec) | Same September-boundary logic as school start, applied at age 16 |
| 2   | Child is not fostered                          | ✅  |   ❌    | `!child.isFostered`                                                                                                      | Foster children are not eligible for UC Childcare                |

### Universal Credit

| #   | Condition                        | Met | Not met | Code reference                                         | Notes |
| --- | -------------------------------- | :-: | :-----: | ------------------------------------------------------ | ----- |
| 3   | Household is on Universal Credit | ✅  |   ❌    | `data.qualifyingBenefits.includes("universal_credit")` |       |

### UK location

| #   | Condition              | Met | Not met | Code reference                                   | Notes                                                       |
| --- | ---------------------- | :-: | :-----: | ------------------------------------------------ | ----------------------------------------------------------- |
| 4   | Parent lives in the UK | ✅  |   ❌    | `isUkLocation(data)` → LAD code prefix `E/W/S/N` | Derived from postcode at entry time; stored in `ladCodes[]` |

### Work requirement

This scheme's work check is **more lenient** than 30 Hours / TFC. "Working" includes being in paid work **or starting paid work in the next month** (`isWorkingOrStartingSoon()`).

**Single parent:**

| #   | Condition                                            | Met | Not met | Code reference                                                                       | Notes                                                    |
| --- | ---------------------------------------------------- | :-: | :-----: | ------------------------------------------------------------------------------------ | -------------------------------------------------------- |
| 5   | Parent is working or starting work in the next month | ✅  |   ❌    | `isWorkingOrStartingSoon(user)` → `isParentWorking(user) \|\| startingWorkNextMonth` | Starting paid work counts the same as being in paid work |

**Couple:**

| #   | Scenario                                                   | Result | Code reference                                                           | Notes                                                                                                                                                   |
| --- | ---------------------------------------------------------- | :----: | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 5a  | Both working (or starting soon)                            |   ✅   | `isWorkingOrStartingSoon(user) && isWorkingOrStartingSoon(partner)`      |                                                                                                                                                         |
| 5b  | Neither working (and neither starting soon)                |   ❌   | `!isWorkingOrStartingSoon(user) && !isWorkingOrStartingSoon(partner)`    |                                                                                                                                                         |
| 5c  | One works, other receives a qualifying allowance           |   ✅   | `hasNonWorkingPartnerException()` → `person.receivesQualifyingAllowance` | Qualifying allowances: Carer's Allowance, Carer Support Payment (Scotland), Incapacity Benefit, Severe Disablement Allowance, or contribution-based ESA |
| 5d  | One works, other has limited capacity for work (LCW/LCWRA) |   ✅   | `person.hasLimitedCapacityForWork === true`                              | Asked in the UC form step when the non-working parent has no qualifying allowance and is not starting work soon                                         |
| 5e  | One works, other has no qualifying allowance or LCW        |   ❌   | `!hasNonWorkingPartnerException() && !person.hasLimitedCapacityForWork`  | Non-working parent is ineligible                                                                                                                        |

### Public funds access

| #   | Condition                                      | Met | Not met | Code reference                                                  | Notes                                                      |
| --- | ---------------------------------------------- | :-: | :-----: | --------------------------------------------------------------- | ---------------------------------------------------------- |
| 6   | At least one parent has access to public funds | ✅  |   ❌    | `hasEligibleResidency(user) \|\| hasEligibleResidency(partner)` | Same statuses as TFC, but only one parent needs to qualify |

### Summary

**Eligible** = conditions 1 + 2 + 3 + 4 + 5 + 6 all pass (logical AND).

#### Key difference from 30 Hours / TFC work check

| Scenario                                        | 30 Hours / TFC |               UC Childcare               |
| ----------------------------------------------- | :------------: | :--------------------------------------: |
| One parent not working, no qualifying allowance |       ❌       | Depends on LCW/LCWRA (form-driven check) |

UC Childcare asks whether the non-working parent has limited capacity for work (LCW/LCWRA). If yes, they are treated as having an exception to the work requirement. If no, they are ineligible.

---

## Interaction with funded hours

UC reimbursement is calculated on the **net cost after funded hours have been deducted**:

```
eligible costs = gross childcare fees − funded hours saving
```

With additional charges excluded (via `VITE_FEATURE_NO_ADDITIONAL_CHARGES` feature flag), UC applies to childcare fees minus funded hours only — there are no additional charges in the eligible costs figure.

The monthly cap (£1,071.09 for one child, £1,836.16 for two or more) applies to the reimbursement amount after the 85% rate is applied, not to the eligible costs themselves.

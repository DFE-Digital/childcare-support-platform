# Early Learning for 2 year olds

15 hours of early learning each week for families in England who get extra support, like those on Universal Credit or children with an Education, Health, and Care Plan.

## Frontend text (from schemes.json)

| Field                   | Value                                                                                                                                                                                                                           |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Name                    | Early Learning for 2 year olds                                                                                                                                                                                                  |
| Description             | 15 hours of early learning each week (over 38 weeks of the year) for families in England who get extra support, like those on Universal Credit or children with an Education, Health, and Care Plan.                            |
| All schemes description | For children aged 2 years. 15 hours of early learning each week (over 38 weeks of the year) for families in England who get extra support, like those on Universal Credit or children with an Education, Health, and Care Plan. |
| Financial type          | `funded_hours`                                                                                                                                                                                                                  |

### Links

| Label        | URL                                                                                                                     |
| ------------ | ----------------------------------------------------------------------------------------------------------------------- |
| Eligibility  | https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/additional-support/eligibility/  |
| How it works | https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/additional-support/how-it-works/ |

### Caveats shown to all users

1. (!) Providers may charge separately for meals, nappies, additional hours, and trips.
2. Charges for extras must not be mandatory or a condition of a funded place.
3. Cannot be used with nannies, home carers, or relatives.
4. If you are on maternity, paternity, adoption, or shared parental leave for this child, the date of return to work affects which term access begins.
5. (!) Your benefits will not be affected by taking up this offer.
6. (!) You should apply for this entitlement first.
7. (!) If also eligible for the working parent entitlement, you receive 15 hours from each scheme (max 30 hours total).
8. Contact your local council and/or provider to apply.

### Conditional caveats (from calculator)

| Code                          | Message                                                         | Condition                                                                          |
| ----------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `nrpf_income_above_threshold` | "Household income is above the NRPF threshold of £{threshold}." | NRPF family where `nrpfIncomeUnderThreshold` does not match the expected threshold |
| `nrpf_savings_above_limit`    | "Household savings exceed the £16,000 limit."                   | NRPF family where `nrpfSavingsUnderLimit` does not equal 16000                     |

## Eligibility

Eligibility is determined through automatic qualifying conditions or circumstance-based routes.

### Step 1 — Location and age gate (must pass)

| #   | Condition                                   | Met | Not met | Code reference                                       | Notes                                                     |
| --- | ------------------------------------------- | :-: | :-----: | ---------------------------------------------------- | --------------------------------------------------------- |
| 0   | Family lives in England                     | ✅  |   ❌    | `isEnglandLocation(data)` — LAD code starts with `E` | Early return if not in England                            |
| 1   | Child is term-time eligible as a 2-year-old | ✅  |   ❌    | `isEligibleFor15Hours2YO(child, referenceDate)`      | Uses term-based eligibility windows, not simple age check |

### Step 2 — Automatic eligibility (any one grants immediate eligibility, no caveats)

These routes grant definitive eligibility with no further checks. Each is an early return.

| #   | Route         | Condition                                                    | Code reference | Reason shown                                                                                                                                                  |
| --- | ------------- | ------------------------------------------------------------ | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A   | Looked after  | `child.isFostered === true`                                  | Line 471       | "Children looked-after by a local authority in England or Wales, such as children in foster care, are entitled to 15 funded hours from the term after age 2." |
| B   | DLA recipient | `child.sendDetails?.receivesDLA === true`                    | Line 477       | "Children receiving Disability Living Allowance are entitled to 15 funded hours from the term after age 2."                                                   |
| C   | EHCP          | `child.hasEHCP === true`                                     | Line 483       | "Children with an education, health and care plan are entitled to 15 funded hours from the term after age 2."                                                 |
| D   | Care leaver   | `child.hasLeftCareForAdoptionOrSpecialGuardianship === true` | Line 489       | "Children who have left care under an adoption order or special guardianship are entitled to 15 funded hours from the term after age 2."                      |

### Step 3 — Circumstance-based routes (OR logic — any one is sufficient)

If no automatic route matched, the calculator checks benefit and income circumstances. Multiple routes can match simultaneously.

| #   | Route                               | Condition                                                                                                            | Result | Code reference | Reason/caveat shown                                                                                                      |
| --- | ----------------------------------- | -------------------------------------------------------------------------------------------------------------------- | :----: | -------------- | ------------------------------------------------------------------------------------------------------------------------ |
| E   | Universal Credit                    | `benefits.includes("universal_credit") && data.ucIncomeBelowThreshold`                                               |   ✅   | Line 503       | Reason: "Household receives Universal Credit with income below £15,400/year after tax."                                  |
| F   | NRPF (income + savings confirmed)   | `allParentsAreNRPF(data)` AND `nrpfIncomeUnderThreshold === expectedThreshold` AND `nrpfSavingsUnderLimit === 16000` |   ✅   | Line 511       | Reason: "Household income is below £{threshold} and savings are below £16,000 (NRPF route)."                             |
| F'  | NRPF (income/savings not confirmed) | `allParentsAreNRPF(data)` but income or savings check fails                                                          |   ⚠️   | Line 531       | Caveats: "Household income is above the NRPF threshold of £{threshold}." / "Household savings exceed the £16,000 limit." |
| G   | Qualifying benefits                 | `qualifyingBenefits` includes any of: `esa`, `pension_credit`                                                        |   ✅   | Line 543       | Reason: "Receiving {matched benefit names}."                                                                             |

#### NRPF thresholds

`allParentsAreNRPF` requires **every** parent (user and partner if present) to have `residencyStatus === "no_recourse_to_public_funds"`. Mixed-residency couples do not trigger the NRPF route.

| Location                            | 1 child | 2+ children |
| ----------------------------------- | ------: | ----------: |
| Outside London                      | £26,500 |     £30,600 |
| London (LAD code starts with `E09`) | £34,500 |     £38,600 |

The calculator verifies that `data.nrpfIncomeUnderThreshold` matches the **expected** threshold for the family's current location and child count. This prevents stale confirmations (e.g. from before a move) from granting eligibility.

Savings limit is always £16,000, confirmed via `data.nrpfSavingsUnderLimit === 16000`.

#### Form-level validation: NRPF + benefits incompatibility

NRPF families cannot claim means-tested benefits. If all parents have NRPF status and any benefit other than "none" is selected, the Benefits step shows a validation error and blocks progress.

### Step 4 — Final result

| Scenario                                      |                  Result                  |
| --------------------------------------------- | :--------------------------------------: |
| Any automatic route (A–D) matched             |       ✅ (definitive, no caveats)        |
| One or more circumstance routes (E–G) matched | ✅ (with any applicable caveats from F') |
| No routes matched                             |                    ❌                    |

### Data fields used

| Field                                               | Type              | Purpose                                                                                                                          |
| --------------------------------------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `child.isFostered`                                  | `boolean`         | Auto-eligibility route A                                                                                                         |
| `child.sendDetails.receivesDLA`                     | `boolean`         | Auto-eligibility route B                                                                                                         |
| `child.hasEHCP`                                     | `boolean`         | Auto-eligibility route C                                                                                                         |
| `child.hasLeftCareForAdoptionOrSpecialGuardianship` | `boolean`         | Auto-eligibility route D                                                                                                         |
| `data.qualifyingBenefits`                           | `string[]`        | Routes E and G — checked for `"universal_credit"`, `"esa"`, `"pension_credit"` (Income Support and JSA removed — migrated to UC) |
| `data.ucIncomeBelowThreshold`                       | `boolean`         | Route E — user confirmed UC income ≤ £15,400                                                                                     |
| `data.nrpfIncomeUnderThreshold`                     | `number`          | Route F — stores the threshold the user confirmed against (e.g. `26500`), or `0` if above                                        |
| `data.nrpfSavingsUnderLimit`                        | `number`          | Route F — stores `16000` if confirmed under limit, or `0` if above                                                               |
| `user.residencyStatus` / `partner.residencyStatus`  | `ResidencyStatus` | NRPF detection via `allParentsAreNRPF()`                                                                                         |
| `data.location.ladCodes`                            | `string[]`        | England gate (`E` prefix) and London detection (`E09` prefix)                                                                    |

---

## Funded hours calculation

When a child is eligible for this scheme, 15 funded hours per week reduce the parent's childcare costs. The hours are treated as **free at point of use** — no shortfall is charged to the parent.

### Formula

```
actual funded hours = min(funded hours remaining in pool, weekly hours of the selection)

saving per hour = effective hourly rate (full rate, not capped at government funding rate)

applicable weeks = min(38, selection weeks per year)

saving to parent = actual funded hours × saving per hour × applicable weeks
```

### Stacking with 30 Hours Working Families

When a child is eligible for both this scheme and 30 Hours Working Families:

- The 15 hours from this scheme are applied **first**
- The 30 Hours WF allocation is reduced so the total does not exceed 30 hours (i.e. 15 hours from each scheme)
- Total funded pool: **30 hours/week**

This scheme takes priority because the disadvantage entitlement is not contingent on work status — it is preserved if the parent stops working.

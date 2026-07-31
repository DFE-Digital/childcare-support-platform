# Childcare Grant

Up to 85% of childcare costs for full-time higher education students. This is an **information-only** scheme — the calculator determines eligibility but does not calculate costs (income thresholds are not collected).

## Frontend text (from schemes.json)

| Field                   | Value                                                                                                                                           |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Name                    | Childcare Grant                                                                                                                                 |
| Description             | Up to 85% of childcare costs for eligible full-time higher education students, capped at £199.62 per week (one child) or £342.24 (two or more). |
| All schemes description | For full-time higher education students with children under 15 (or 17 if SEND).                                                                 |
| Financial type          | `awareness`                                                                                                                                     |

### Links

| Label | URL                                |
| ----- | ---------------------------------- |
| Info  | https://www.gov.uk/childcare-grant |

### Caveats shown to all users

1. Cannot be used alongside Tax-Free Childcare, Universal Credit childcare, or Working Tax Credit childcare element.
2. Cannot be used towards the 15 or 30 hours free childcare entitlement, or upfront costs like deposits.
3. You must reconfirm eligibility each academic year.
4. From the 2026-27 academic year, nanny-provided childcare is no longer eligible.

### Conditional caveats (from calculator)

| Code                            | Text                                                                           | When shown    |
| ------------------------------- | ------------------------------------------------------------------------------ | ------------- |
| `childcare_grant_income_caveat` | Eligibility depends on household income — check gov.uk for current thresholds. | When eligible |

## Eligibility

**Rule: ALL conditions must be met.**

| #   | Condition                           | Met | Not met | Code reference                                           | Notes                                            |
| --- | ----------------------------------- | :-: | :-----: | -------------------------------------------------------- | ------------------------------------------------ |
| 1   | Parent is studying HE               | ✅  |   ❌    | `person.isStudying && studyLevel === "higher_education"` | Checks both user and partner                     |
| 2   | Parent is full-time (120+ credits)  | ✅  |   ❌    | `person.isFullTimeStudent === true`                      |                                                  |
| 3   | Parent eligible for student finance | ✅  |   ❌    | `person.eligibleForStudentFinance === true`              |                                                  |
| 4   | Child under 15 (or 17 if SEND)      | ✅  |   ❌    | `getChildAgeInYears(child) < (child.hasSEND ? 17 : 15)`  |                                                  |
| 5   | England location                    | ✅  |   ❌    | `isEnglandLocation(data)`                                |                                                  |
| 6   | Income below threshold              |  —  |    —    | **Not checked** — always caveat                          | ⚠️ Caveat: "Check gov.uk for current thresholds" |

### Per-parent logic

Either parent can be the qualifying student. The evaluator checks both `data.user` and `data.partner` — the qualifying parent must satisfy conditions 1–3 simultaneously.

### Summary

**Eligible** = conditions 1–5 all pass (logical AND) for at least one parent. Income is not verified — flagged as caveat. No cost calculation is performed.

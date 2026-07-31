# Learner Support

Help with childcare costs for adults studying further education courses. This is an **information-only** scheme — the calculator determines eligibility but does not calculate costs. The scheme is inherently discretionary; amounts are decided by the learning provider.

## Frontend text (from schemes.json)

| Field                   | Value                                                                    |
| ----------------------- | ------------------------------------------------------------------------ |
| Name                    | Learner Support                                                          |
| Description             | Help with childcare costs for adults studying further education courses. |
| All schemes description | For parents aged 19+ on further education courses at level 3 or below.   |
| Financial type          | `awareness`                                                              |

### Links

| Label | URL                                |
| ----- | ---------------------------------- |
| Info  | https://www.gov.uk/learner-support |

### Caveats shown to all users

1. The amount you receive is at your learning provider's discretion — there is no fixed entitlement.
2. You cannot claim if you are receiving student finance for higher education.
3. Your learning provider may ask for proof of low income.

### Conditional caveats (from calculator)

| Code                         | Text                                                                               | When shown    |
| ---------------------------- | ---------------------------------------------------------------------------------- | ------------- |
| `learner_support_age_caveat` | You must be 19 or over to get funding for childcare costs through Learner Support. | When eligible |

## Eligibility

**Rule: ALL conditions must be met.**

| #   | Condition                          | Met | Not met | Code reference                                     | Notes                                                                     |
| --- | ---------------------------------- | :-: | :-----: | -------------------------------------------------- | ------------------------------------------------------------------------- |
| 1   | Parent age bracket is 18-20 or 21+ | ✅  |   ❌    | `ageBracket === "18-20" \|\| ageBracket === "21+"` | Age bracket "18-20" includes under-20s — caveat directs user to check age |
| 2   | Parent is studying                 | ✅  |   ❌    | `person.isStudying === true`                       | Checks both user and partner                                              |
| 3   | Study level is FE                  | ✅  |   ❌    | `studyLevel === "further_education"`               |                                                                           |

No location, residency, or income checks — the scheme is discretionary and provider-assessed.

### Per-parent logic

Either parent can be the qualifying student. The evaluator checks both `data.user` and `data.partner`.

### Summary

**Eligible** = conditions 1–3 all pass (logical AND) for at least one parent. This is the weakest eligibility check — the scheme is discretionary. No cost calculation is performed.

# Care to Learn

Childcare support for parents under 20 studying a publicly-funded course in England. This is an **information-only** scheme — the calculator determines eligibility but does not calculate costs.

## Frontend text (from schemes.json)

| Field                   | Value                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Name                    | Care to Learn                                                                                                             |
| Description             | Childcare support of up to £180 per child per week (£195 in London) while you study (and additional travel costs).        |
| All schemes description | Childcare support for parents studying on a publicly-funded course in England, who were under 20 when their course began. |
| Financial type          | `awareness`                                                                                                               |

### Links

| Label | URL                              |
| ----- | -------------------------------- |
| Info  | https://www.gov.uk/care-to-learn |

### Caveats shown to all users

1. Your education provider pays the childcare provider directly — you do not receive the money yourself.
2. Payments stop if you stop attending your course or your child stops attending childcare.
3. Claiming Care to Learn will not affect your family's benefits or allowances.
4. Apprentices receiving a salary are not eligible.

### Conditional caveats (from calculator)

| Code                       | Text                                                             | When shown    |
| -------------------------- | ---------------------------------------------------------------- | ------------- |
| `care_to_learn_age_caveat` | You must be under 20 at the start of your course to be eligible. | When eligible |

## Eligibility

**Rule: ALL conditions must be met.**

| #   | Condition                              | Met | Not met | Code reference                                                               | Notes                                                                              |
| --- | -------------------------------------- | :-: | :-----: | ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| 1   | Parent is under 20                     | ✅  |   ❌    | `ageBracket === "16-17" \|\| ageBracket === "18-20"`                         | Age bracket "18-20" includes 20-year-olds — caveat directs user to check exact age |
| 2   | Parent is studying                     | ✅  |   ❌    | `person.isStudying === true`                                                 | Checks both user and partner                                                       |
| 3   | Study level is school/sixth form or FE | ✅  |   ❌    | `studyLevel === "school_sixth_form" \|\| studyLevel === "further_education"` |                                                                                    |
| 4   | Course is publicly funded              | ✅  |   ❌    | `person.courseIsPubliclyFunded === true`                                     |                                                                                    |
| 5   | Parent is not an apprentice            | ✅  |   ❌    | `!person.isApprentice`                                                       | Apprentices receiving a salary are not eligible                                    |
| 6   | England location                       | ✅  |   ❌    | `isEnglandLocation(data)`                                                    |                                                                                    |
| 7   | Eligible residency                     | ✅  |   ❌    | `hasEligibleResidency(qualifyingParent)`                                     |                                                                                    |

### Per-parent logic

Either parent can be the qualifying student. The evaluator checks both `data.user` and `data.partner` — the qualifying parent must satisfy conditions 1–5 simultaneously.

### Summary

**Eligible** = conditions 1–7 all pass (logical AND) for at least one parent. No cost calculation is performed.

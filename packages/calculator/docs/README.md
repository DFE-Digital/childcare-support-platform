# Calculator Documentation

Policy-facing documentation for `@bsil/calculator`. These documents are intended for the policy team to review and sign off the rules, calculations, and user-facing text implemented in the calculator.

## Documents

### 1. Scheme eligibility rules

One file per scheme, describing the conditions a family must meet for each government childcare scheme.

| Scheme                     | File                                                                         |
| -------------------------- | ---------------------------------------------------------------------------- |
| 30 Hours Working Families  | [scheme-30-hours-working-families.md](scheme-30-hours-working-families.md)   |
| 15 Hours Universal (3-4yo) | [scheme-15-hours-universal.md](scheme-15-hours-universal.md)                 |
| 15 Hours for 2-Year-Olds   | [scheme-15-hours-2-year-olds.md](scheme-15-hours-2-year-olds.md)             |
| Tax-Free Childcare         | [scheme-tax-free-childcare.md](scheme-tax-free-childcare.md)                 |
| UC Childcare               | [scheme-universal-credit-childcare.md](scheme-universal-credit-childcare.md) |
| Wraparound Childcare       | [scheme-wraparound-childcare.md](scheme-wraparound-childcare.md)             |
| Free Breakfast Clubs       | [scheme-free-breakfast-clubs.md](scheme-free-breakfast-clubs.md)             |
| Care to Learn              | [scheme-care-to-learn.md](scheme-care-to-learn.md)                           |
| Learner Support            | [scheme-learner-support.md](scheme-learner-support.md)                       |
| Childcare Grant            | [scheme-childcare-grant.md](scheme-childcare-grant.md)                       |

Each scheme file uses a table of conditions with ✅/❌/⚠️ icons and code references back to `packages/calculator/src/entitlement/calculate.ts`. See any scheme file for the full column definitions.

### 2. Cost calculation logic

**[cost-calculation.md](cost-calculation.md)** — describes the pipeline that estimates annual childcare costs: fee lookup, gross cost annualisation, funded hours reduction, additional charges, and government support (Tax-Free Childcare / UC Childcare). Code references point to `packages/calculator/src/costs/`.

### 3. Questionnaire text

**[questionnaire-text.md](questionnaire-text.md)** — all user-facing text from both questionnaire forms, extracted for policy sign-off. Covers:

- **Support form** ("What support am I entitled to?") — 6 steps
- **Cost estimator** ("How much is childcare going to cost?") — the same 6 steps plus step 7 (Childcare arrangements)

Includes every question, option label, help text, validation message, and modal.

## Keeping these up to date

If the eligibility logic, cost calculation pipeline, or questionnaire wording changes, the corresponding document should be updated to match. Code reference columns in the scheme and cost files make it straightforward to verify each row against the current implementation.

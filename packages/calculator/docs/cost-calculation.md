# Cost Calculation Logic

This document describes how the cost calculator estimates annual childcare costs and government support for a family. It is intended for the policy team to review and sign off the calculation logic.

The calculator takes each child's childcare selections (e.g. 3 full days at a private nursery, 2 mornings with a childminder), resolves the fees, applies government-funded hours, adds any additional charges, and then calculates Tax-Free Childcare or Universal Credit childcare support at the family level.

All code references point to files in `packages/calculator/src/costs/`.

---

## Overview — the calculation pipeline

For **each child**, for **each childcare selection**:

| Step | What happens                                                                                       | Code                    |
| ---- | -------------------------------------------------------------------------------------------------- | ----------------------- |
| 1    | **Resolve fees** — look up provider-specific fees or fall back to area average costs               | `fee-lookup.ts`         |
| 2    | **Calculate gross annual cost** — annualise the fees based on care type                            | `gross-cost.ts`         |
| 3    | **Apply funded hours reduction** — subtract the value of any funded hours the child is entitled to | `funded-hours.ts`       |
| 4    | **Add additional charges** — meals, registration fees, consumables etc.                            | `additional-charges.ts` |

Then across the **whole family**:

| Step | What happens                                                                               | Code                    |
| ---- | ------------------------------------------------------------------------------------------ | ----------------------- |
| 5    | **Calculate government support** — Tax-Free Childcare or UC Childcare (mutually exclusive) | `government-support.ts` |
| 6    | **Compute net cost to family** — total cost minus total support                            | `calculate.ts`          |

---

## Inputs

| Input                    | Description                                                            | Source                            |
| ------------------------ | ---------------------------------------------------------------------- | --------------------------------- |
| Child data               | Birth month/year, disability status, childcare selections              | User form answers                 |
| Childcare selections     | Per child: care type, provider (optional), sessions/hours/days         | User form answers                 |
| Provider fees            | Fee schedules by age band, session hours, additional charges           | Provider database                 |
| Area average costs       | Average fees by care type and age band, with lower/mean/upper range    | Postcode-based area cost data     |
| Entitlement results      | Which schemes each child is eligible for (from entitlement calculator) | `entitlement/calculate.ts` output |
| Scheme config            | TFC top-up rate, UC reimbursement rate, caps                           | `schemes.json`                    |
| Government funding rates | Per-hour funding rate by age band and local authority                  | Area cost data                    |

---

## Age bands

The child's age in months determines which fee band and government funding rate applies.

| Age band  | Age in months | Label   |
| --------- | ------------- | ------- |
| `under2`  | 0–23          | Under 2 |
| `age2`    | 24–35         | Age 2   |
| `age3to4` | 36+           | Age 3–4 |

Code: `age-band.ts` → `getAgeBand(child, referenceDate)`

---

## Care type reference

| Care type                                   | Fee unit                                     | Term-time or year-round | Default weeks/year           | Funded hours eligible |
| ------------------------------------------- | -------------------------------------------- | ----------------------- | ---------------------------- | --------------------- |
| Nursery (Private, Voluntary or Independent) | Per session (morning / afternoon / full day) | Year-round              | ~50 (from data); overridable | Yes                   |
| School-based nursery                        | Per session (morning / afternoon / full day) | Term-time               | 38; overridable              | Yes                   |
| Childminder                                 | Per hour                                     | Year-round              | 50                           | Yes                   |
| Breakfast club                              | Per session                                  | Term-time               | 38                           | No                    |
| Free breakfast club                         | Free (£0)                                    | Term-time               | 38                           | No                    |
| After-school club                           | Per session                                  | Term-time               | 38                           | No                    |
| Holiday club                                | Per day                                      | Year-round              | — (uses days/year)           | No                    |

For nursery types, the user can override the default weeks per year via the form (radio choice of standard defaults or a custom value between 1–52). The override is stored as `selection.weeksPerYear`.

---

## Step 1 — Fee resolution

**Priority:** provider-specific fees first; if no provider is selected, fall back to area average costs.

Code: `fee-lookup.ts` → `resolveFeesForSelection()`

### Provider fees

Fees are looked up from the provider's fee schedule for the child's age band. If the provider has an `age2plus` band but no separate `age2` or `age3to4` band, `age2plus` is used as a fallback.

For clubs and holiday club, fees may be flat (not nested under age bands) — the resolver checks for a flat `perSession` or `perDay` field first, then falls back to the age-banded structure.

### Area average fees

When no provider is selected, area average costs are used. These are stored as hourly rates per age band and converted to the fee unit for each care type:

| Care type                            | Conversion                                                              |
| ------------------------------------ | ----------------------------------------------------------------------- |
| Nursery (PVI) / school-based nursery | hourly rate × session hours (morning: 5h, afternoon: 5h, full day: 10h) |
| Childminder                          | hourly rate used directly                                               |
| Breakfast / after-school club        | hourly rate × session duration (from data, default 1h)                  |
| Holiday club                         | hourly rate × day duration (from data, default 7h)                      |

Session hour defaults (if not specified in area data): morning = 5h, afternoon = 5h, full day = 10h.

### Fee variants

Area average costs come in three variants:

| Variant | Meaning                      |
| ------- | ---------------------------- |
| `lower` | Lower quartile of area costs |
| `mean`  | Mean of area costs           |
| `upper` | Upper quartile of area costs |

Provider-specific fees are fixed (no variants). The cost range feature (see end of document) runs the full pipeline three times with each variant.

### Cost area fallback

Area average data may be sourced at different geographic levels. The `costArea` field records where the data came from (local authority, region, or nation).

---

## Step 2 — Gross annual childcare cost

Each care type has its own annualisation formula. All amounts are annual.

Code: `gross-cost.ts` → `calculateChildcareFees()`

### Nursery (Private, Voluntary or Independent) / school-based nursery

```
weekly fee = (morning days × morning session fee)
           + (afternoon days × afternoon session fee)
           + (full day days × full day fee)

weeks = selection.weeksPerYear ?? fees.operatingWeeksPerYear

annual cost = weekly fee × weeks
```

The user can override the default weeks per year via the form. If no override is set, the provider or area average operating weeks apply (typically 50 for PVI, 38 for school-based).

**Effective hourly rate** (used in Step 3):

```
weekly hours = (morning days × morning hours)
             + (afternoon days × afternoon hours)
             + (full day days × full day hours)

effective hourly rate = weekly fee ÷ weekly hours
```

Session hour defaults: morning = 5h, afternoon = 5h, full day = 10h.

### Childminder

```
annual cost = hours per week × rate per hour × weeks per year
```

Weeks per year: user-specified, or provider/area default (typically 50).

Effective hourly rate = the per-hour rate directly.

### Breakfast club / after-school club

```
annual cost = days per week × session fee × 38 weeks
```

Always 38 weeks (term-time only).

### Free breakfast club

```
annual cost = £0
```

### Holiday club

```
annual cost = days per year × day rate
```

No weekly cycle — the user specifies total days per year directly.

---

## Step 3 — Funded hours reduction

Funded hours reduce the parent's cost by offsetting some of the childcare fees with government funding. This step only applies to **eligible care types**: private nursery, school-based nursery, and childminder. Clubs and holiday club are not eligible.

Code: `funded-hours.ts` → `determineFundedHoursPerWeek()`, `calculateFundedHoursReduction()`

### Funded hours pool

The child's funded hours per week are determined from their entitlement results. Multiple schemes can contribute to the pool — in particular, the 15 Hours 2-Year-Olds (disadvantage) entitlement and the working parent entitlement are **stackable** for age-2 children.

Allocations are built in this order:

| Order | Scheme                    | Age band | Hours/week | Notes                                                           |
| ----- | ------------------------- | -------- | ---------- | --------------------------------------------------------------- |
| 1     | 15 Hours 2-Year-Olds      | age 2    | 15         | Disadvantage entitlement — applied first                        |
| 2     | 30 Hours Working Families | any      | 30\*       | Full 30 hours (from Sep 2025); reduced when stacking with row 1 |
| 3     | 15 Hours Universal        | age 3–4  | 15         | Only if not eligible for 30 Hours WF                            |

\* When stacking with the 15 Hours 2YO entitlement (row 1), the working parent allocation is reduced to 15 so the total does not exceed 30 hours.

The resulting pool per scenario:

| Age band | Eligible schemes        | Total funded hours/week |
| -------- | ----------------------- | ----------------------- |
| under 2  | 30 Hours WF only        | 30                      |
| age 2    | 15 Hours 2YO only       | 15                      |
| age 2    | 30 Hours WF only        | 30                      |
| age 2    | **Both** (stacked)      | **30** (15 + 15)        |
| age 3–4  | 30 Hours WF             | 30                      |
| age 3–4  | 15 Hours Universal only | 15                      |
| any      | None eligible           | 0                       |

The 15 Hours 2YO entitlement is applied first because it is not contingent on work status — if the parent subsequently stops working, the disadvantage entitlement remains. The working parent hours fill the remainder up to 30. The total funded pool is always capped at 30 hours/week.

### How the reduction is calculated

Funded hours are treated as **free at point of use** — the full cost of each funded hour is deducted from the parent's bill. There is no shortfall charged to the parent.

For each eligible childcare selection, in order:

```
actual funded hours = min(funded hours remaining in pool, weekly hours of this selection)

saving per hour = effective hourly rate

applicable weeks = min(38, selection weeks per year)

saving to parent = actual funded hours × saving per hour × applicable weeks

shortfall per hour = 0
```

The funded hours pool is **shared across selections** — the first selection consumes hours from the pool, and subsequent selections use whatever remains.

The saving is calculated over a maximum of **38 weeks** (the government funding entitlement period), but capped at the child's actual attendance weeks for that selection. This prevents the funded hours saving from exceeding the actual childcare fees when a child attends fewer than 38 weeks.

**Rationale for no shortfall:** When area average costs are used, the hourly rate is a statistical average rather than an actual provider rate. Calculating a shortfall between an average rate and the government funding rate would produce a misleading figure. Since the calculator cannot know what a specific provider charges above the funded rate, no shortfall is applied.

### Government funding rates

The per-hour government funding rate varies by age band and local authority. Rates are sourced from the area cost data:

| Age band | Rate source                                        |
| -------- | -------------------------------------------------- |
| Under 2  | `areaCosts.governmentFundingRates.under2.perHour`  |
| Age 2    | `areaCosts.governmentFundingRates.age2.perHour`    |
| Age 3–4  | `areaCosts.governmentFundingRates.age3to4.perHour` |

If no rate data is available, the reduction is zero (no funded hours saving applied). The government funding rate is still required to be positive for the reduction to apply, even though the saving amount is based on the effective hourly rate (not the government rate).

---

## Step 4 — Additional charges

Providers may have additional charges beyond their core session/hourly fees — for example, meals, consumables, or registration fees. These are annualised and added to the cost.

**Feature flag:** This step is gated behind the `includeAdditionalCharges` option in `CostCalculatorInput`. When disabled (the default in production via `VITE_FEATURE_NO_ADDITIONAL_CHARGES`), additional charges are excluded entirely: `additional = { total: 0, estimated: false }`. This means the cost estimate reflects core session fees only.

Code: `additional-charges.ts` → `calculateAdditionalCharges()`

### Annualisation by unit

| Charge unit | Annual amount                     |
| ----------- | --------------------------------- |
| Per day     | charge × attendance days per year |
| Per week    | charge × operating weeks per year |
| Per session | charge × sessions per year        |

### Attendance days calculation

How "attendance days per year" is determined depends on the care type:

| Care type                    | Attendance days per year                                             |
| ---------------------------- | -------------------------------------------------------------------- |
| Holiday club                 | `daysPerYear` (user-specified)                                       |
| Childminder (days known)     | `daysPerWeek × weeksPerYear`                                         |
| Childminder (days not known) | `min(5, ceil(hoursPerWeek ÷ 6)) × weeksPerYear` — **estimated**      |
| Nursery (session-based)      | `max(morning days, afternoon days, full day days) × operating weeks` |
| Clubs                        | `daysPerWeek × operating weeks`                                      |

When childminder attendance days must be estimated from weekly hours, the result is flagged as `estimated: true` so the UI can indicate the figure is approximate.

### Sessions per year

For "per session" charges:

| Care type                     | Sessions per year                                                   |
| ----------------------------- | ------------------------------------------------------------------- |
| Breakfast / after-school club | `daysPerWeek × 38`                                                  |
| Nursery                       | `(morning days + afternoon days + full day days) × operating weeks` |

### Operating weeks

| Care type                                      | Weeks                                                                               |
| ---------------------------------------------- | ----------------------------------------------------------------------------------- |
| Breakfast / free breakfast / after-school club | 38 (term-time, hardcoded)                                                           |
| Childminder                                    | User-specified (`selection.weeksPerYear`), or provider/area default                 |
| Nursery                                        | User-specified (`selection.weeksPerYear`), or provider/area `operatingWeeksPerYear` |

---

## Step 5 — Government support

Two government support schemes can reduce the family's costs. They are **mutually exclusive** — a family on Universal Credit gets UC Childcare; all other families get Tax-Free Childcare. UC takes priority.

Code: `government-support.ts` → `calculateGovernmentSupport()`

### Tax-Free Childcare

Calculated **per child**. Only children eligible for the TFC scheme (from entitlement results) are included.

| Parameter             | Value               | Source                                                      |
| --------------------- | ------------------- | ----------------------------------------------------------- |
| Top-up rate           | 25%                 | `schemes.json` → `topUpRate`                                |
| Effective rate        | 20% (= 0.25 ÷ 1.25) | Derived                                                     |
| Annual cap (standard) | £2,000 per child    | `schemes.json` → `maxGovernmentContributionPerYear`         |
| Annual cap (disabled) | £4,000 per child    | `schemes.json` → `maxGovernmentContributionPerYearDisabled` |

**Formula:**

```
eligible costs = gross childcare fees − funded hours saving

uncapped saving = eligible costs × 0.20

saving to parent = min(uncapped saving, annual cap)
```

The "effective rate" of 20% comes from the TFC account mechanics: for every £8 a parent pays in, the government adds £2, making £10 total. The government's £2 is 25% of the parent's £8 but 20% of the total £10. Since `eligible costs` represents the total cost, we use the 20% effective rate.

If the uncapped saving exceeds the cap, a note is generated showing the capped amount.

### UC Childcare

Calculated at the **family level**, then allocated proportionally to each child.

| Parameter                          | Value     | Source                                  |
| ---------------------------------- | --------- | --------------------------------------- |
| Reimbursement rate                 | 85%       | `schemes.json` → `reimbursementRate`    |
| Monthly cap (1 eligible child)     | £1,071.09 | `schemes.json` → `maxPerMonthOneChild`  |
| Monthly cap (2+ eligible children) | £1,836.16 | `schemes.json` → `maxPerMonthTwoOrMore` |

Only children eligible for the UC Childcare scheme (from entitlement results) are included.

**Formula:**

```
total eligible costs = Σ (gross childcare fees − funded hours saving) for each eligible child

monthly eligible = total eligible costs ÷ 12

monthly reimbursement = min(monthly eligible × 0.85, monthly cap)

annual saving = monthly reimbursement × 12
```

The monthly cap depends on the number of eligible children (1 vs 2+).

**Per-child allocation:**

The annual saving is split across children proportionally to their eligible costs:

```
child allocation = annual saving × (child eligible costs ÷ total eligible costs)
```

The last child receives the remainder (to ensure allocations sum exactly to the total, avoiding rounding drift).

If the reimbursement is capped, a note is generated showing the cap amount.

---

## Step 6 — Family totals

Code: `calculate.ts` → `calculateCosts()`

```
total childcare fees     = Σ (gross fees) across all children and selections
total additional charges = Σ (additional charges) across all children and selections
total cost of childcare  = total childcare fees + total additional charges

total government support = funded hours saving + TFC saving + UC saving

estimated annual cost to family = total cost of childcare − total government support
```

### Per-child totals

Each child also gets an individual breakdown:

```
child gross cost   = Σ (gross fees + additional charges) for that child's selections
child support      = funded hours + TFC allocation + UC allocation
child cost to family = child gross cost − child support
```

### Selection grouping

If a child has a mix of term-time care (nursery, clubs) and year-round care (childminder, holiday club), the selections are grouped into:

- **Term-time care** (38 weeks): school-based nursery, breakfast club, free breakfast club, after-school club
- **Year-round care**: private nursery, childminder, holiday club

This grouping is for display purposes only — it does not affect the calculation.

---

## Cost range

The calculator can produce a cost range by running the full pipeline three times with different fee variants.

Code: `calculate.ts` → `calculateCostRange()`

| Run | Fee variant | Effect                                 |
| --- | ----------- | -------------------------------------- |
| 1   | `lower`     | Uses lower quartile area average costs |
| 2   | `mean`      | Uses mean area average costs           |
| 3   | `upper`     | Uses upper quartile area average costs |

Provider-specific fees do not vary — only area average costs have lower/mean/upper variants. The range output includes the full family result for each variant, plus a summary `{ lower, upper }` of the estimated annual cost to family.

---

## Rounding

Code: `rounding.ts`

Two rounding modes are available:

| Mode        | Behaviour                                 |
| ----------- | ----------------------------------------- |
| `precise`   | Round to 2 decimal places (nearest penny) |
| `nearest10` | Round to nearest £10                      |

The default mode is `precise`. Rounding is applied to: gross fees per selection, additional charges per selection, funded hours saving per selection, and government support amounts.

---

## Code reference

| Section                                         | Source file                   |
| ----------------------------------------------- | ----------------------------- |
| Pipeline orchestration, family totals, grouping | `costs/calculate.ts`          |
| Fee resolution (provider and area average)      | `costs/fee-lookup.ts`         |
| Gross cost annualisation formulas               | `costs/gross-cost.ts`         |
| Funded hours pool and reduction                 | `costs/funded-hours.ts`       |
| Additional charges annualisation                | `costs/additional-charges.ts` |
| Government support (TFC and UC)                 | `costs/government-support.ts` |
| Age band determination                          | `costs/age-band.ts`           |
| Rounding modes                                  | `costs/rounding.ts`           |

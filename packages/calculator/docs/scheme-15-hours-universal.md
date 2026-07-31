# 15 hours childcare for all families in England

15 hours per week of funded early education for all 3 and 4-year-olds.

## Frontend text (from schemes.json)

| Field                   | Value                                                                                              |
| ----------------------- | -------------------------------------------------------------------------------------------------- |
| Name                    | 15 hours childcare for all families in England                                                     |
| Description             | 15 hours per week (over 38 weeks of the year) of funded early education for all 3 and 4-year-olds. |
| All schemes description | For all children aged 3-4 years.                                                                   |
| Financial type          | `funded_hours`                                                                                     |

### Links

| Label        | URL                                                                                                                  |
| ------------ | -------------------------------------------------------------------------------------------------------------------- |
| Eligibility  | https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/universal-offer/eligibility/  |
| How it works | https://beststartinlife.gov.uk/childcare-early-years-education/15-and-30-hours-support/universal-offer/how-it-works/ |

### Caveats shown to all users

1. (!) Providers may charge separately for meals, nappies, additional hours, and trips.
2. Charges for extras must not be mandatory or a condition of a funded place.
3. Cannot be used with nannies, home carers, or relatives.
4. If you are on maternity, paternity, adoption, or shared parental leave for this child, the date of return to work affects which term access begins.
5. If eligible, you can use this scheme until your child starts school, usually when they begin Reception.
6. (!) If also eligible for the working families entitlement, you receive 15 hours from each scheme (max 30 hours total).

### Conditional caveats (from calculator)

None.

## Eligibility

**Rule: ALL conditions must be met.**

| #   | Condition               | Met | Not met | Code reference                                                                | Notes                                                                                         |
| --- | ----------------------- | :-: | :-----: | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 1   | Child is 3+ years old   | ✅  |   ❌    | `getChildAgeInYears(child) >= 3` → uses `child.birthMonth`, `child.birthYear` |                                                                                               |
| 2   | Child is pre-school     | ✅  |   ❌    | `isPreSchool(child)` → uses `child.birthMonth`, `child.birthYear`             | Starts Reception in September after turning 4 (born Jan-Aug) or following year (born Sep-Dec) |
| 3   | Parent lives in England | ✅  |   ❌    | `isEnglandLocation(data)` → LAD code prefix `E`                               | Derived from postcode at entry time; stored in `ladCodes[]`                                   |

### Summary

**Eligible** = conditions 1 + 2 + 3 all pass (logical AND).

No caveats are generated.

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

### Interaction with 30 Hours Working Families

This scheme is only used in the calculator when the child is **not** eligible for 30 Hours Working Families. The two are mutually exclusive in the funded hours allocation logic — a child eligible for 30 Hours WF receives all 30 hours through that scheme (or stacked with 15 Hours 2YO), and the 15 Hours Universal scheme is not applied.

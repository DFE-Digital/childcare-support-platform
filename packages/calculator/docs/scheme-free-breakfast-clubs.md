# Free breakfast clubs

Free 30-minute breakfast sessions before primary school, saving families up to £450 per year.

## Frontend text (from schemes.json)

| Field                   | Value                                                                                         |
| ----------------------- | --------------------------------------------------------------------------------------------- |
| Name                    | Free breakfast clubs                                                                          |
| Description             | Free 30-minute breakfast sessions before primary school, saving families up to £450 per year. |
| All schemes description | Free 30-minute breakfast sessions before primary school, saving families up to £450 per year. |
| Financial type          | `free_service`                                                                                |

### Links

| Label | URL                                                                                                |
| ----- | -------------------------------------------------------------------------------------------------- |
| Info  | https://educationhub.blog.gov.uk/2026/02/free-breakfast-club-roll-out-everything-you-need-to-know/ |

### Caveats shown to all users

1. Not yet available in all schools — being phased in across England.
2. Available to all children in participating schools, not means-tested.
3. Disadvantaged schools (highest proportion of free school meal pupils) have been prioritised.

### Conditional caveats (from calculator)

None.

## Eligibility

**Rule: ALL conditions must be met.**

| #   | Condition             | Met | Not met | Code reference                                                                | Notes |
| --- | --------------------- | :-: | :-----: | ----------------------------------------------------------------------------- | ----- |
| 1   | Child is 4+ years old | ✅  |   ❌    | `getChildAgeInYears(child) >= 4` → uses `child.birthMonth`, `child.birthYear` |       |
| 2   | Child is 11 or under  | ✅  |   ❌    | `getChildAgeInYears(child) <= 11`                                             |       |

No parent conditions apply. No caveats are generated.

### Summary

**Eligible** = conditions 1 + 2 both pass (logical AND).

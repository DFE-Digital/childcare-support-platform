# Data quality validation checks and SQL audit: BSIL (Beta)

## 1. Scope

This initial audit focuses on profiling the data quality and identifying critical fixes for our three beta regions: **Bristol**, **Bath and North East Somerset**, and **South Gloucestershire**.

We have a two pronged validation strategy which combines row level programmatic validation checks with macro level relational audits.

## 2. Two-Pronged Validation Strategy

- **Micro-Validation (Python Pipeline):** Evaluates each provider in isolation, ensuring strict schema adherence, type safety, and logical field bounds (e.g., checking if opening hours are valid times, or ensuring max age > min age). Entries which don't meet validation could be discarded, but not necessarily the full provider entry. This is TBD on a per-check basis.
- **Macro-Validation (SQL Audit):** Evaluates the dataset holistically to catch business logic errors, systemic data entry defaults, and cross relational anomalies that a row-by-row script would naturally miss.

## 3. Findings & Anomalies (via SQL Audit, v7 and v8)

> Now tracked on this [Google sheet](https://docs.google.com/spreadsheets/d/1MRwGjZVGs4WEJMPoQRc0XtgJZs5QCOu6uza9OdNRrDc/edit?gid=1386834576#gid=1386834576)

By applying SQL based semantic and aggregation checks across the Parquet files v7 and v8 several systemic issues that have been flagged for resolution:

| Issue                                               | Example / Detail                                                                                                                                                           | Recommendation                                                                                                                                                                                |
| :-------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Systemic Default Values (URLs)**                  | 194 providers in South Gloucestershire default to the same generic local authority directory link (`life.southglos.gov.uk...`) rather than a specific provider website.    | **Blacklist generic URLs:** Add a check in the pipeline to reject URLs containing known directory paths (e.g., `/directory/service.page`).                                                    |
| **Semantic Anomalies (Non-Formal Childcare)**       | Providers like "IKEA" are listed under the `private_nursery` care type.                                                                                                    | **Filter retail crèches:** IKEA can be searched for and discarded, but we must identify logic to broadly filter out retail crèches, gyms, and leisure centers.                                |
| **Chain Overlap (Identical Names)**                 | Found 7 distinct records with the same name "Mama Bear's Day Nursery".                                                                                                     | **Low concern / Revisit later:** Likely from a chain. Optionally suffix matching names with a locational identifier to avoid confusion. Revisit when the front-end site is live.              |
| **Chain Overlap (Shared Phones)**                   | Cross-provider data bleeding, such as a Head Office phone number being applied uniformly to multiple distinct nurseries in the same group.                                 | **Accepted in v7.**                                                                                                                                                                           |
| **Address Data Bleed**                              | Spot checks using regex (`\d`) revealed 3 instances where the full street address and postcode were erroneously merged into the `city` field.                              | **Low priority: Cleanse data:** Add a regex check for digits in the city field and apply data cleansing to unpack merged fields.                                                              |
| **Stale Source Data**                               | Several providers with Ofsted inspection dates older than 7 years (dating back to 2015–2017). This suggests closed provisions or failure to link updated URNs.             | **Expand validation:** Update the `ofsted_inspection_date` check to flag dates older than 7 years as a warning.                                                                               |
| **IKEA childcare centres**                          | IKEA childcare is Ofsted inspected but has been flagged as a private_nursery in this set                                                                                   | **Check with policy:** Confirmed they should not be included, and we should search of other similar providers to exclude.                                                                     |
| **Entries dropped between v7 and v8**               | 7 providers were dropped between v7 and v8                                                                                                                                 | **Investigated & Accepted:** These moved from school URNs to ofsted URNs - they all gained after school clubs. So they should still all exist but under a different URN (ofsted not school).. |
| **Mismatch between institution type and care type** | 30 schools private nurseries instead of school based nurseries or after school clubs, following a more general reconciliation on institution type vs care type (see below) | **To investigate:** csv with all 30 entries sent to Teneeka.                                                                                                                                  |
| **Entries changing institution type**               | 7 schools changed institution type                                                                                                                                         | **Investigated & Accepted:** This is down to improved matching.                                                                                                                               |

## 3b. Findings & Anomalies (via SQL Audit, v9)

> Now tracked on this [Google sheet](https://docs.google.com/spreadsheets/d/1MRwGjZVGs4WEJMPoQRc0XtgJZs5QCOu6uza9OdNRrDc/edit?gid=1386834576#gid=1386834576)

By applying SQL based semantic and aggregation checks across the Parquet files v7 and v8 several systemic issues that have been flagged for resolution:
| Issue | Example / Detail | Recommendation |
| :--- | :--- | :--- |
| **Chain Overlap (Shared Phones)** | Cross-provider data bleeding, such as a Head Office phone number being applied uniformly to multiple distinct nurseries in the same group. | **To investigate:** 66 entries have phone number 01454868008 which is South Glos council. |
| **Chain Overlap (Shared Emails)** | Cross-provider data bleeding, such as a Head Office email being applied uniformly to multiple distinct nurseries in the same group. | **To investigate:** 60 entries have email cis@southglos.gov.uk |
| **Leisure centre / gym / creche checks (like IKEA)** | 3 providers with IKEA, gym, leisure, creche or fitness in title. One is IKEA. One from this group is a provider of care in school holidays only https://www.lets-play.org.uk/sessions/, the other is a mobile creche centre Carolines Crèches | **To investigate:** confirm policy |
| **0 registered places**| 6 schools have 0 registered places | **To investigate:** confirm policy |
| **Over 250 registered places**| Knowle Park After School Care has 550 places and Filton Avenue Nursery School 262 **To investigate:** confirm policy |

## 4. Deep Dive: Institution type vs Care type (v7)

| institution_type   | care_type            | count_star() |
| :----------------- | :------------------- | -----------: |
| childminder        | childminder          |          609 |
| childminder        | private_nursery      |            1 |
| nursery            | after_school_club    |            5 |
| nursery            | breakfast_club       |            2 |
| nursery            | holiday_club         |            5 |
| nursery            | private_nursery      |          344 |
| out_of_school_club | after_school_club    |          172 |
| out_of_school_club | breakfast_club       |            2 |
| out_of_school_club | holiday_club         |            4 |
| out_of_school_club | school_based_nursery |            2 |
| school_independent | after_school_club    |            3 |
| school_independent | private_nursery      |            1 |
| school_independent | school_based_nursery |           12 |
| school_nursery     | private_nursery      |            6 |
| school_nursery     | school_based_nursery |           12 |
| school_primary     | after_school_club    |           56 |
| school_primary     | breakfast_club       |           52 |
| school_primary     | free_breakfast_club  |           17 |
| school_primary     | holiday_club         |            6 |
| school_primary     | private_nursery      |           23 |
| school_primary     | school_based_nursery |           86 |
| school_secondary   | after_school_club    |            2 |
| school_secondary   | holiday_club         |            2 |
| school_secondary   | school_based_nursery |            2 |
| school_special     | school_based_nursery |            9 |

And in v9:

<img width="383" height="452" alt="image" src="https://github.com/user-attachments/assets/c7dda0b2-3368-46c0-a2e9-4640f7e9c9df" />
 
## 5. Deep Dive: No contact details (v9)
It is not only childminders and Bristol driving blank entries... 
| lad25cd | COALESCE(institution_type, '--TOTAL--') | count_star() |
| :--- | :--- | ---: |
| E06000022 | childminder | 47 |
| E06000022 | nursery | 8 |
| E06000022 | out_of_school_club | 15 |
| E06000022 | school_primary | 2 |
| E06000022 | --TOTAL-- | 72 |
| E06000023 | childminder | 274 |
| E06000023 | nursery | 69 |
| E06000023 | out_of_school_club | 95 |
| E06000023 | school_nursery | 1 |
| E06000023 | school_primary | 4 |
| E06000023 | --TOTAL-- | 443 |
| E06000025 | childminder | 56 |
| E06000025 | nursery | 49 |
| E06000025 | out_of_school_club | 24 |
| E06000025 | school_primary | 3 |
| E06000025 | --TOTAL-- | 132 |
| NULL | --TOTAL-- | 647 |

## 6. How 'grouped' is our data geographically? (v9)

Depending on mapping rules (inc lat long truncation), it could be a max of 4 providers at any one point for regional beta
<img width="943" height="168" alt="image" src="https://github.com/user-attachments/assets/d6d62107-d04e-4728-863d-ce402985233a" />

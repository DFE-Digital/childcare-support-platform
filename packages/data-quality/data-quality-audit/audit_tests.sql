-------------------------------------------------------------------------------
-- 0. SETUP: CREATE THE BASE VIEW
-- Filters to 3 beta regions so we don't have to repeat the WHERE clause.
-- Runs natively in duckdb
-- >brew install duckdb
-- >cd to-folder/with-parquets/
-- >duckdb
-------------------------------------------------------------------------------
CREATE OR REPLACE VIEW q9 AS 
SELECT *
FROM 'providers.parquet'
WHERE lad25cd IN ('E06000023', 'E06000022', 'E06000025');

-------------------------------------------------------------------------------
-- 1. COMPLETENESS & DEFAULT VALUES
-- Looking for missing data or lazy placeholder values.
-------------------------------------------------------------------------------

-- 1A: Count of providers completely missing a name
SELECT COUNT(*) AS missing_names 
FROM q9 
WHERE (name IS NULL OR TRIM(name) = '') and institution_type != 'childminder';

-- 1B: Providers missing ALL contact information (Ghost records)
SELECT lad25cd, ifnull(institution_type,'--TOTAL--'), count(*)
FROM q9 
WHERE phone IS NULL 
AND email IS NULL 
AND website IS NULL 
GROUP by ROLLUP (lad25cd, institution_type) order by lad25cd, institution_type;

-- 1C: Default or highly repeated websites (Catches the South Glos anomaly)
SELECT website, count(*) as freq 
FROM q9 
WHERE website IS NOT NULL 
GROUP BY website 
HAVING count(*) > 5 
ORDER BY freq DESC;

-- 1C_a: Default or highly repeated fis_urls (Catches the South Glos anomaly)
SELECT fis_url, count(*) as freq 
         FROM q9 
         WHERE fis_url IS NOT NULL 
         GROUP BY fis_url 
         HAVING count(*) > 5 
         ORDER BY freq DESC;

-- 1D: Default or placeholder names (e.g., "TBC", "Test")
SELECT name, count(*) as freq 
FROM q9 
WHERE name IS NOT NULL 
GROUP BY name 
HAVING count(*) > 3 
ORDER BY freq DESC;

-- eyeballing to check the duplicates are really distinct:
SELECT * FROM q9 WHERE name LIKE 'Mama Bear%';

-- 1E: Catches standard 'lazy' data entry numbers
SELECT id, name, phone FROM q9 
WHERE phone LIKE '%0000000%' 
OR phone LIKE '%1111111%' 
OR phone LIKE '%1234567%' 
OR phone LIKE '%9999999%';

-- 1F: Checks for weekend-only providers 
SELECT count(*) FROM 'opening_hours.parquet' 
WHERE monday IS false 
AND tuesday IS false 
AND wednesday IS false 
AND thursday IS false 
AND friday IS false;

-- 1G: Eyeball for unusual times, note Joe's script already has logic to actually validate these
SELECT * FROM 'opening_hours.parquet'
WHERE open NOT LIKE '%:00:00' 
AND open NOT LIKE '%:15:00' 
AND open NOT LIKE '%:30:00' 
AND open NOT LIKE '%:45:00' ;

-- 1H: How do phone area codes group?
SELECT left(phone, 4), count(*) FROM q9 
WHERE left(phone,2) != '07' 
GROUP BY left(phone,4);

-------------------------------------------------------------------------------
-- 2. UNIQUENESS & DEDUPLICATION
-- Finding Head Offices, chain data entry, or actual duplicate records.
-------------------------------------------------------------------------------

-- 2A: Shared Phone Numbers (Catches Head Office numbers applied to many nurseries)
SELECT phone, count(*) as shared_count, list(name) as provider_names
FROM q9 
WHERE phone IS NOT NULL 
GROUP BY phone 
HAVING count(*) > 2 
ORDER BY shared_count DESC;

-- 2B: Shared Emails (Often catches local authority group emails or chains)
SELECT email, count(*) as shared_count, list(name) as provider_names
FROM q9 
WHERE email IS NOT NULL 
GROUP BY email 
HAVING count(*) > 2 
ORDER BY shared_count DESC;

-- 2C: Geolocation stacking (Multiple providers at the exact same Lat/Long)
-- Could indicate a shared building, or a default bounding-box centroid
SELECT latitude, longitude, count(*) as stacked_count, list(name) as provider_names
FROM q9 
WHERE latitude IS NOT NULL 
GROUP BY latitude, longitude 
HAVING count(*) > 2 
ORDER BY stacked_count DESC;

-------------------------------------------------------------------------------
-- 3. SEMANTIC ANOMALIES & BUSINESS LOGIC
-- Finding data that is formatted correctly but makes no real-world sense.
-------------------------------------------------------------------------------

-- 3A: Address bleed into the City field (Checking for numbers in the city)
SELECT id, name, city, address_line1 
FROM q9 
WHERE regexp_matches(city, '\d');

-- 3B: "Fake" childcare or short-term crèches (IKEA, Gyms, Leisure Centres)
-- These often shouldn't be in a formal childcare search for parents.
SELECT id, name, institution_type 
FROM q9 
WHERE name ILIKE '%ikea%' 
   OR name ILIKE '%gym%' 
   OR name ILIKE '%leisure%' 
   OR name ILIKE '%creche%'
   OR name ILIKE '%fitness%';

-- 3C: Stale Ofsted Data (Inspections older than 7 years)
SELECT id, name, ofsted_inspection_date, ofsted_legacy_rating 
FROM q9 
WHERE ofsted_inspection_date < '2019-01-01' 
ORDER BY ofsted_inspection_date ASC;

-- 3D: Suspicious Registered Places (Nurseries with tiny capacity or massive capacity)
SELECT id, name, institution_type, registered_places 
FROM q9 
WHERE registered_places < 3 
   OR registered_places > 250
ORDER BY registered_places DESC;

-- 3E: Unexpected locations
SELECT id, name, postcode, latitude, longitude 
FROM q9
WHERE latitude < 51.0 OR latitude > 52.0 
OR longitude < -3.0 OR longitude > -2.0;

-------------------------------------------------------------------------------
-- 4. CROSS-TABLE RELATIONAL INTEGRITY
-- Ensuring a provider's characteristics match across files.
-------------------------------------------------------------------------------

-- 4A: Childminders with an illegal number of places (> 6 is usually a red flag in the UK)
-- Already checked in Joe's script
SELECT id, name, registered_places 
FROM q9 
WHERE institution_type = 'childminder' 
  AND registered_places > 6;

-- 4B: Providers that exist in the main table but have NO care types listed
-- (Requires joining to the care_types file)
-- Already checked in Joe's script
SELECT tr.id, tr.name, tr.institution_type
FROM q9 tr
LEFT JOIN 'care_types.parquet' ct ON tr.id = ct.provider_id
WHERE ct.provider_id IS NULL;

-- 4C: Mismatched Institution vs. Care Type (e.g. a Childminder running a School Nursery)
SELECT tr.institution_type, ct.care_type, count(*) as freq
FROM q9 tr
JOIN 'care_types.parquet' ct ON tr.id = ct.provider_id
GROUP BY tr.institution_type, ct.care_type
ORDER BY tr.institution_type, ct.care_type;

-- 4D: unrealistic age bounds for provision
SELECT tr.id, tr.name, ct.care_type, ct.eligible_min_years, ct.eligible_max_years
FROM q9 tr
JOIN 'care_types.parquet' ct ON tr.id = ct.provider_id
WHERE ct.eligible_max_years > 18;

-- 4E: No care types
SELECT * FROM q9 LEFT JOIN 'care_types.parquet' ct 
ON q9.id = ct.provider_id WHERE ct.provider_id is null;

-- which institution type are providers with no care type ?
SELECT institution_type, count(*) FROM q9 
LEFT JOIN 'care_types.parquet' ct ON q9.id = ct.provider_id WHERE ct.provider_id is null 
GROUP BY institution_type;

-- 4F: Conflicting care types
SELECT q9.id, q9.name, q9.institution_type, group_concat(care_type) as care_types 
FROM q9 LEFT JOIN 'care_types.parquet' ct ON q9.id = ct.provider_id 
GROUP BY q9.id, q9.name, q9.institution_type  
HAVING care_types ILIKE '%school_based%' AND care_types ILIKE '%private_nursery%'; 


SELECT * FROM q9 LEFT JOIN 'care_types.parquet' ct 
ON q9.id = ct.provider_id WHERE  eligible_min_years = eligible_max_years;
-- 16 rows
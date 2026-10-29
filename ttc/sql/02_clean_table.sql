-- 02_clean_table.sql
-- Builds ttc.bus_delays_clean from the raw upload ttc.bus_delays_raw.
--
-- Load the raw file first: download "TTC Bus Delay Data since 2025.csv" from
-- https://open.toronto.ca/dataset/ttc-bus-delay-data/ and upload it in the BigQuery
-- console (Create table > Upload > CSV > auto-detect schema) as ttc.bus_delays_raw.
--
-- One row per unique incident. What this does, step by step:
--   1. dedup     drop exact repeats (same date, time, line, location, code, minutes, vehicle)
--   2. base      parse time, derive weekday from the date (the source Day column is wrong
--                on some dates), turn vehicle 0 into NULL, keep only valid directions
--   3. names     one standard name per route number (most common spelling)
--   4. codes     unique reason labels: codes that share a description (four are "OTHER")
--                get their group appended, e.g. "OTHER (EQUIPMENT)"
--   5. flags     zero-minute, long (>180 min), suspect placeholder (999), undocumented code,
--                truncated location, garage location
--
-- Missing routes are NOT filled in. likely_route_no holds a reference-only guess (the route
-- the same bus ran that day); a spot check showed these rows are garage pull-outs, so the
-- guess is unreliable and is never used as route_no.
--
-- Replace YOUR_PROJECT with your Google Cloud project id.

CREATE OR REPLACE TABLE `YOUR_PROJECT.ttc.bus_delays_clean`
OPTIONS (description = 'Cleaned TTC bus delays (Jan 2025 onward). One row per unique incident. See ttc/README.md for the cleaning rules.') AS
WITH base AS (
  SELECT
    r._id AS incident_id,
    DATE(r.Date) AS delay_date,
    PARSE_TIME('%H:%M', r.Time) AS delay_time,
    NULLIF(TRIM(r.Line), '') AS line_raw,
    SAFE_CAST(REGEXP_EXTRACT(r.Line, r'^(\d+)') AS INT64) AS route_no,
    r.Station AS location_raw,
    UPPER(TRIM(r.Code)) AS code,
    r.`Min Delay` AS delay_min,
    r.`Min Gap` AS gap_min,
    r.Bound AS bound_raw,
    NULLIF(r.Vehicle, 0) AS vehicle,
    ROW_NUMBER() OVER (
      PARTITION BY r.Date, r.Time, r.Line, r.Station, r.Code, r.`Min Delay`, r.Vehicle
      ORDER BY r._id) AS dup_rank
  FROM `YOUR_PROJECT.ttc.bus_delays_raw` r
),
dedup AS (
  SELECT * EXCEPT (dup_rank) FROM base WHERE dup_rank = 1
),
bus_day AS (
  -- reference only: the single route a bus reported that day
  SELECT delay_date, vehicle, ANY_VALUE(route_no) AS known_route_no
  FROM dedup
  WHERE route_no IS NOT NULL AND vehicle IS NOT NULL
  GROUP BY delay_date, vehicle
  HAVING COUNT(DISTINCT route_no) = 1
),
names AS (
  SELECT route_no, line_raw AS route_name
  FROM (
    SELECT route_no, line_raw,
           ROW_NUMBER() OVER (PARTITION BY route_no ORDER BY COUNT(*) DESC, line_raw) AS rk
    FROM dedup WHERE route_no IS NOT NULL
    GROUP BY route_no, line_raw)
  WHERE rk = 1
),
codes AS (
  SELECT code, description, COUNT(*) OVER (PARTITION BY description) AS same_desc
  FROM `YOUR_PROJECT.ttc.delay_codes`
)
SELECT
  d.incident_id,
  d.delay_date,
  d.delay_time,
  DATETIME(d.delay_date, d.delay_time) AS delay_datetime,
  DATE_TRUNC(d.delay_date, MONTH) AS delay_month,
  FORMAT_DATE('%A', d.delay_date) AS weekday,
  EXTRACT(DAYOFWEEK FROM d.delay_date) IN (1, 7) AS is_weekend,
  EXTRACT(HOUR FROM d.delay_time) AS hour_of_day,
  d.route_no,
  n.route_name,
  d.route_no IS NOT NULL AS is_regular_route,
  CASE WHEN d.route_no IS NOT NULL THEN 'reported'
       WHEN d.line_raw IS NULL THEN 'missing'
       ELSE 'not a route' END AS route_source,
  CASE
    WHEN d.route_no IS NOT NULL THEN 'Regular route'
    WHEN d.line_raw IS NULL THEN 'Missing'
    WHEN REGEXP_CONTAINS(UPPER(d.line_raw), r'SHUT|SHUTLE') THEN 'Subway shuttle'
    WHEN REGEXP_CONTAINS(UPPER(d.line_raw), r'TRAIN|OTC|FAMILIARIZ|ROAD TEST') THEN 'Training'
    WHEN REGEXP_CONTAINS(UPPER(d.line_raw), r'CHARTER|SPECIAL EVENT|CNE|FIFA') THEN 'Charter / special event'
    ELSE 'Non-revenue / other' END AS line_type,
  d.line_raw,
  NULLIF(TRIM(REGEXP_REPLACE(REGEXP_REPLACE(REGEXP_REPLACE(REGEXP_REPLACE(
      UPPER(TRIM(d.location_raw)), r'\s*&\s*', ' AND '), r'\bSTN\b', 'STATION'), r'[.,;]+', ''), r'\s+', ' ')), '') AS location,
  LENGTH(d.location_raw) >= 22 AS is_location_truncated,
  d.location_raw,
  d.code,
  CASE
    WHEN c.code IS NULL THEN CONCAT('UNDOCUMENTED CODE ', d.code)
    WHEN c.same_desc > 1 THEN CONCAT(c.description, ' (', CASE SUBSTR(d.code, 1, 1)
      WHEN 'E' THEN 'EQUIPMENT' WHEN 'M' THEN 'MISCELLANEOUS' WHEN 'P' THEN 'PLANT'
      WHEN 'S' THEN 'SECURITY' WHEN 'T' THEN 'TRANSPORTATION' ELSE 'UNKNOWN' END, ')')
    ELSE c.description END AS reason,
  c.code IS NULL AS is_undocumented_code,
  CASE SUBSTR(d.code, 1, 1)
    WHEN 'E' THEN 'Equipment' WHEN 'M' THEN 'Miscellaneous' WHEN 'P' THEN 'Plant'
    WHEN 'S' THEN 'Security' WHEN 'T' THEN 'Transportation' ELSE 'Unknown' END AS reason_group,
  d.delay_min,
  d.gap_min,
  CASE
    WHEN d.delay_min = 0 THEN 'Zero minutes'
    WHEN d.delay_min = 999 THEN 'Suspect placeholder (999)'
    WHEN d.delay_min > 180 THEN 'Long event (>180 min)'
    ELSE 'Normal' END AS delay_class,
  d.delay_min = 0 AS is_zero_delay,
  d.delay_min > 180 AS is_long_event,
  CASE WHEN d.bound_raw IN ('N', 'S', 'E', 'W') THEN d.bound_raw
       WHEN d.bound_raw = 'B' THEN 'Both' ELSE NULL END AS direction,
  CASE d.bound_raw WHEN 'N' THEN 'Northbound' WHEN 'S' THEN 'Southbound' WHEN 'E' THEN 'Eastbound'
       WHEN 'W' THEN 'Westbound' WHEN 'B' THEN 'Both directions' ELSE 'Unknown' END AS direction_label,
  d.vehicle,
  IF(d.line_raw IS NULL, bd.known_route_no, NULL) AS likely_route_no,
  REGEXP_CONTAINS(UPPER(d.location_raw), r'GARAGE|DIVISION|YARD') AS is_garage_location
FROM dedup d
LEFT JOIN bus_day bd ON bd.delay_date = d.delay_date AND bd.vehicle = d.vehicle
LEFT JOIN names n ON n.route_no = d.route_no
LEFT JOIN codes c ON c.code = d.code;

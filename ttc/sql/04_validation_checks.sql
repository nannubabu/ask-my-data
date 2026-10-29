-- 04_validation_checks.sql
-- Proves the clean table still adds up to the raw upload. Every row should say PASS.
--
-- Replace YOUR_PROJECT with your Google Cloud project id.

WITH c AS (SELECT * FROM `YOUR_PROJECT.ttc.bus_delays_clean`),
r AS (SELECT * FROM `YOUR_PROJECT.ttc.bus_delays_raw`),
rd AS (SELECT DISTINCT Date, Time, Line, Station, Code, `Min Delay` AS m, Vehicle FROM r)
SELECT check_name, expected, actual, IF(expected = actual, 'PASS', 'FAIL') AS result
FROM UNNEST([
  STRUCT('01 Rows = raw rows minus exact duplicates' AS check_name,
         (SELECT COUNT(*) FROM rd) AS expected, (SELECT COUNT(*) FROM c) AS actual),
  STRUCT('02 incident_id is unique',
         (SELECT COUNT(*) FROM c), (SELECT COUNT(DISTINCT incident_id) FROM c)),
  STRUCT('03 Every clean row traces back to a raw row',
         (SELECT COUNT(*) FROM c), (SELECT COUNT(*) FROM c JOIN r ON r._id = c.incident_id)),
  STRUCT('04 Delay minutes match the de-duplicated raw data',
         (SELECT SUM(m) FROM rd), (SELECT SUM(delay_min) FROM c)),
  STRUCT('05 No blanks in date, time, code, delay or gap',
         0, (SELECT COUNTIF(delay_date IS NULL OR delay_time IS NULL OR code IS NULL OR delay_min IS NULL OR gap_min IS NULL) FROM c)),
  STRUCT('06 Every row has a reason label',
         0, (SELECT COUNTIF(reason IS NULL) FROM c)),
  STRUCT('07 One unique reason label per code',
         (SELECT COUNT(DISTINCT code) FROM c), (SELECT COUNT(DISTINCT reason) FROM c)),
  STRUCT('08 Weekday always matches the date',
         0, (SELECT COUNTIF(weekday != FORMAT_DATE('%A', delay_date)) FROM c)),
  STRUCT('09 Direction is only N, S, E, W, Both or blank',
         0, (SELECT COUNTIF(direction IS NOT NULL AND direction NOT IN ('N', 'S', 'E', 'W', 'Both')) FROM c)),
  STRUCT('10 No vehicle recorded as 0',
         0, (SELECT COUNTIF(vehicle = 0) FROM c)),
  STRUCT('11 One route name per route number',
         (SELECT COUNT(DISTINCT route_no) FROM c),
         (SELECT COUNT(DISTINCT CONCAT(CAST(route_no AS STRING), route_name)) FROM c WHERE route_no IS NOT NULL)),
  STRUCT('12 Every route has a name',
         0, (SELECT COUNTIF(route_no IS NOT NULL AND route_name IS NULL) FROM c)),
  STRUCT('13 Same days covered as the raw data',
         (SELECT COUNT(DISTINCT DATE(Date)) FROM r), (SELECT COUNT(DISTINCT delay_date) FROM c)),
  STRUCT('14 Same months covered as the raw data',
         (SELECT COUNT(DISTINCT DATE_TRUNC(DATE(Date), MONTH)) FROM r), (SELECT COUNT(DISTINCT delay_month) FROM c)),
  STRUCT('15 Every row has a line_type and delay_class',
         0, (SELECT COUNTIF(line_type IS NULL OR delay_class IS NULL) FROM c)),
  STRUCT('16 Routes only where the source reported one',
         (SELECT COUNT(*) FROM c WHERE REGEXP_CONTAINS(line_raw, r'^\d')), (SELECT COUNT(*) FROM c WHERE route_no IS NOT NULL)),
  STRUCT('17 Missing-route rows = blank source line',
         (SELECT COUNT(*) FROM c WHERE line_raw IS NULL), (SELECT COUNTIF(line_type = 'Missing') FROM c)),
  STRUCT('18 likely_route_no never overrides a real route',
         0, (SELECT COUNTIF(likely_route_no IS NOT NULL AND route_no IS NOT NULL) FROM c))
])
ORDER BY check_name;

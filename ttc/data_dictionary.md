# Data dictionary: `ttc.bus_delays_clean`

One row per unique bus delay incident reported to the TTC, Jan 2025 onward. Built by [`sql/02_clean_table.sql`](sql/02_clean_table.sql) from the City of Toronto's *TTC Bus Delay Data*. The agent reads it through the view `ttc.bus_delays` ([`sql/03_agent_view.sql`](sql/03_agent_view.sql)), which adds `is_duplicate` (always FALSE).

## Columns

| Column | Type | Meaning |
|---|---|---|
| `incident_id` | INT | Row id from the source file |
| `delay_date` | DATE | Local Toronto date of the incident |
| `delay_time` | TIME | Local time the incident started |
| `delay_datetime` | DATETIME | Date and time together |
| `delay_month` | DATE | First day of the month |
| `weekday` | STRING | Day name, derived from the date (the source's own Day column is wrong on some dates) |
| `is_weekend` | BOOL | Saturday or Sunday |
| `hour_of_day` | INT | 0 to 23 |
| `route_no` | INT | Route number, e.g. 52. Blank for non-route lines and missing routes |
| `route_name` | STRING | One standard name per route number (its most common spelling), e.g. "52 LAWRENCE WEST" |
| `is_regular_route` | BOOL | `route_no` is not blank |
| `route_source` | STRING | `reported`, `missing` (blank in source) or `not a route` (shuttle, fleet, training) |
| `line_type` | STRING | Regular route, Missing, Subway shuttle, Training, Charter / special event, Non-revenue / other |
| `line_raw` | STRING | Route text exactly as reported |
| `location` | STRING | Location with formatting standardized (uppercase, `&` to `AND`, `STN` to `STATION`, no punctuation or extra spaces) |
| `is_location_truncated` | BOOL | Source text hit the 22-character limit, so the location may be cut off |
| `location_raw` | STRING | Location exactly as reported |
| `code` | STRING | Delay code, e.g. EFO, TFCNO |
| `reason` | STRING | Unique readable label for the code, e.g. "NO OPERATOR AVAILABLE", "OTHER (EQUIPMENT)", "UNDOCUMENTED CODE MFGD" |
| `is_undocumented_code` | BOOL | Code not in the city's code list |
| `reason_group` | STRING | Equipment, Miscellaneous, Plant, Security, Transportation (from the code's first letter; inferred) |
| `delay_min` | INT | Minutes of delay reported |
| `gap_min` | INT | Minutes between this bus and the one ahead |
| `delay_class` | STRING | Normal, Zero minutes, Long event (>180 min), Suspect placeholder (999) |
| `is_zero_delay` | BOOL | `delay_min = 0` |
| `is_long_event` | BOOL | `delay_min > 180` (mostly diversions) |
| `direction` | STRING | N, S, E, W, Both, or blank |
| `direction_label` | STRING | Northbound, Southbound, Eastbound, Westbound, Both directions, Unknown |
| `vehicle` | INT | Bus number; blank when unknown (source used 0) |
| `likely_route_no` | INT | Reference only: the one route the same bus reported that day, on rows with no route. Unreliable (these are garage pull-outs); never used as `route_no` |
| `is_garage_location` | BOOL | Location mentions a garage, division or yard |

## Metric definitions

| Metric | Definition |
|---|---|
| Delay incidents (default "delays") | Rows with `NOT is_zero_delay` |
| All reports | All rows (duplicates are already removed) |
| Delay minutes | `SUM(delay_min)` on delay incidents excluding `is_long_event`; long events reported separately |
| Typical delay | Median `delay_min`; the mean is skewed by long events |
| Incidents per day | Delay incidents divided by distinct `delay_date` in the window |
| Route rankings | Group by `route_no`, show `route_name`, filter `is_regular_route` |

## Traps

1. Group routes by `route_no`, never by `line_raw` (591 spellings for 274 routes).
2. Group reasons by `reason` or `code`, never by the code-table description (four codes share "OTHER").
3. "OTHER (EQUIPMENT)" is the largest single reason; it means the cause wasn't recorded specifically.
4. 6.5% of reports use undocumented codes; keep them and say so if they rank highly.
5. Exclude zero-minute reports from delay counts by default.
6. Exclude long events (>180 min) from delay-minute totals by default; they hold about 27% of all minutes.
7. Use `weekday` from the date, never the source's Day column.
8. Exclude non-route lines from route rankings; include them in system totals.
9. Location answers are approximate (text truncated at 22 characters).
10. The latest month may be partial; compare equal windows or per-day rates.
11. No schedules, trip counts or ridership: "how often does the bus run" and "what share of trips were late" can't be answered from this data.

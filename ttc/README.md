# TTC bus delays: cleaning and validating a real public dataset

A second dataset for the Ask My Data agent: **every TTC bus delay reported in Toronto from January 2025 to September 2026** (107,349 reports), from the City of Toronto's open data portal.

Unlike the TheLook demo data, this is real operational data, typed in by people. It has duplicates, misspellings, placeholder values and a text column cut off mid-word. This folder documents how it was loaded into BigQuery, what was wrong with it, how it was cleaned, and the checks that prove the cleaned table still adds up to the original.

| | |
|---|---|
| Source | [City of Toronto Open Data: TTC Bus Delay Data](https://open.toronto.ca/dataset/ttc-bus-delay-data/), file *TTC Bus Delay Data since 2025* (refreshed monthly) |
| Period | Jan 1, 2025 to Sep 30, 2026 (638 days, 21 months) |
| Raw rows | 107,349 reports, 11 columns |
| Clean rows | 106,920 unique incidents |
| Validation | 18 of 18 checks pass ([`sql/04_validation_checks.sql`](sql/04_validation_checks.sql)) |

## Files

| File | What it does |
|---|---|
| [`sql/01_delay_codes.sql`](sql/01_delay_codes.sql) | Creates the `ttc` dataset and the 46-row delay-code lookup table |
| [`sql/02_clean_table.sql`](sql/02_clean_table.sql) | Builds `ttc.bus_delays_clean` from the raw upload |
| [`sql/03_agent_view.sql`](sql/03_agent_view.sql) | The view the agent queries |
| [`sql/04_validation_checks.sql`](sql/04_validation_checks.sql) | 18 checks; every row should say PASS |
| [`data_dictionary.md`](data_dictionary.md) | Every column of the clean table, metric definitions and traps |
| [`agent_prompt.md`](agent_prompt.md) | The instructions the analyst agent follows for this dataset |

## 1. Profiling: what was wrong

Profiling every column before writing any analysis found these problems.

**Missing values**

| Column | Missing | Share |
|---|---|---|
| `Bound` (direction) | 22,906 blank, plus 26 junk values such as `` ` ``, `Q`, `7` | 21.3% |
| `Vehicle` | 5,410 recorded as `0` rather than blank, so a null check misses them | 5.0% |
| `Line` (route) | 1,314 blank | 1.2% |
| Date, time, day, location, code, delay, gap | none | 0% |

**Other problems**

| Problem | Size | Why it matters |
|---|---|---|
| Exact duplicate reports | 429 rows | Double-counts incidents |
| One route, many names | 274 route numbers written 591 ways (route 52 alone: "52 LAWRENCE WEST", "52B LAWRENCE WEST", "52 BURNHAMTHORPE", ...) | Route rankings split one route into several |
| Codes sharing a description | 4 codes are all "OTHER"; 2 are "TTC COLLISION - PROPERTY DAMAGE" | Grouping by description invents a fake top reason |
| Wrong weekday | 130 rows (e.g. Apr 26, 2026 labelled Saturday; it was a Sunday) | Weekday/weekend comparisons drift |
| Undocumented codes | 35 codes, 6.5% of rows, not in the city's code list | No readable reason |
| Zero-minute reports | 12.8% of rows | Not delays in the usual sense |
| Very long events | 1,627 reports over 3 hours, mostly diversions, holding 27% of all delay minutes | Skew totals and averages |
| Placeholder value | 1 report of exactly 999 minutes | Likely "unknown" |
| Non-route lines | 439 rows: subway shuttles, training buses, fleet vehicles | Not bus routes |
| Locations truncated | Every location is cut at 22 characters (24% of rows hit the limit, e.g. "QUEENS QUAY AND SHERBO"); about 17,000 spellings | Location answers can only be approximate |

## 2. Cleaning rules

Each fix is either applied, or flagged and left for the analyst to decide. Nothing is guessed.

| Problem | Rule | Rows |
|---|---|---|
| Exact duplicates | Removed (kept the first by id) | 429 |
| Route-name variants | Grouped by route number; one standard name each (the most common spelling) | all route rows |
| Shared code descriptions | Unique labels, e.g. "OTHER (EQUIPMENT)", "OTHER (SECURITY)" | 4 codes |
| Wrong weekday | Recomputed from the date | 130 |
| Junk / blank direction | Set to blank, labelled "Unknown" | 22,859 |
| Vehicle `0` | Set to blank | 5,391 |
| Undocumented codes | Kept, labelled "UNDOCUMENTED CODE xxx", flagged | 6,908 |
| Zero-minute, >180 min, 999 | Kept, classified in `delay_class` and flagged | 15,392 |
| Non-route lines | Classified: subway shuttle, training, charter, non-revenue | 439 |
| Location formatting | Uppercased; `&` to `AND`; `STN` to `STATION`; punctuation and extra spaces removed (17,018 to 16,826 spellings). Truncated rows flagged | all rows |
| Missing route | **Left missing** (see below) | 1,314 |

Counts after de-duplication.

### A fix that was tried and reversed

43 reports with no route came from a bus that reported exactly one route that same day, so it was tempting to fill the route in. A spot check showed **every one of those reports was at a bus garage** (e.g. Eglinton Garage at 12:55 a.m.), hours away from that route's service. The bus was most likely pulling out of or into the garage, not in service. The rows stay "missing"; the guess is kept only in `likely_route_no`, for reference.

## 3. Validation

[`sql/04_validation_checks.sql`](sql/04_validation_checks.sql) compares the clean table with the raw upload. Results on the October 2026 load:

| # | Check | Expected | Actual | |
|---|---|---|---|---|
| 01 | Rows = raw rows minus exact duplicates | 106,920 | 106,920 | ✅ |
| 02 | incident_id is unique | 106,920 | 106,920 | ✅ |
| 03 | Every clean row traces back to a raw row | 106,920 | 106,920 | ✅ |
| 04 | Delay minutes match the de-duplicated raw data | 2,302,605 | 2,302,605 | ✅ |
| 05 | No blanks in date, time, code, delay or gap | 0 | 0 | ✅ |
| 06 | Every row has a reason label | 0 | 0 | ✅ |
| 07 | One unique reason label per code | 75 | 75 | ✅ |
| 08 | Weekday always matches the date | 0 | 0 | ✅ |
| 09 | Direction is only N, S, E, W, Both or blank | 0 | 0 | ✅ |
| 10 | No vehicle recorded as 0 | 0 | 0 | ✅ |
| 11 | One route name per route number | 274 | 274 | ✅ |
| 12 | Every route has a name | 0 | 0 | ✅ |
| 13 | Same days covered as the raw data | 638 | 638 | ✅ |
| 14 | Same months covered as the raw data | 21 | 21 | ✅ |
| 15 | Every row has a line_type and delay_class | 0 | 0 | ✅ |
| 16 | Routes only where the source reported one | 105,167 | 105,167 | ✅ |
| 17 | Missing-route rows = blank source line | 1,314 | 1,314 | ✅ |
| 18 | likely_route_no never overrides a real route | 0 | 0 | ✅ |

The published `02_clean_table.sql` was also run into a separate table and compared row for row with the live clean table: 106,920 rows each, 0 differences in either direction.

## 4. Testing the agent

Five questions were answered by the agent from the view and checked against queries written separately on the raw table (different de-duplication and route logic). The first run scored 4/5: ranking reasons by description merged four "OTHER" codes into one (20,548 incidents instead of 17,890). After the unique-label fix, 5/5 matched exactly.

| Question | Answer (delay incidents, Jan 2025 to Sep 2026 unless noted) |
|---|---|
| Most-delayed routes, 2025 | 32 Eglinton West 1,485; 52 Lawrence West 1,435; 102 Markham Road 1,136 |
| Top reasons | Other (equipment) 17,890; No operator available 8,907; Used as shuttle bus 7,680 |
| Worst hour | 5 p.m. (6,268), then 3 p.m. (6,150) |
| Weekday vs weekend | 156 incidents per weekday, 121 per weekend day |
| Jan to Sep, 2026 vs 2025 | 38,347 vs 40,312 (4.9% fewer) |

"Delay incidents" means de-duplicated reports with more than 0 minutes of delay.

## 5. Limitations

- **Locations** are truncated at 22 characters in the source, so they can't be fully standardized. Location answers are approximate.
- **Routes** are missing on 1.2% of reports, and **direction** on 21%. These are left blank, not guessed.
- **Reason groups** (Equipment, Miscellaneous, Plant, Security, Transportation) come from the first letter of the code. That pattern is inferred, not documented by the city.
- **No schedules or ridership.** The data records delays only, so it can't answer "how often does the bus run" or "what share of trips were late."

## Reproducing it

1. Download *TTC Bus Delay Data since 2025.csv* from the [dataset page](https://open.toronto.ca/dataset/ttc-bus-delay-data/).
2. In each SQL file, replace `YOUR_PROJECT` with your Google Cloud project id.
3. Run [`sql/01_delay_codes.sql`](sql/01_delay_codes.sql) in the BigQuery console.
4. Upload the CSV in the console: open the `ttc` dataset, **Create table**, *Upload*, *CSV*, table name `bus_delays_raw`, **Auto detect** schema.
5. Run `02_clean_table.sql`, then `03_agent_view.sql`, then `04_validation_checks.sql` and confirm every row says PASS.

In the free BigQuery sandbox, tables expire after 60 days; rerun these steps to reload.

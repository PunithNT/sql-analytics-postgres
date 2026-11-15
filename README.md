# SQL Analytics with Postgres: NYC 311 Service Requests

A portfolio project that loads NYC 311 style service request data into Postgres and answers 10 business questions using CTEs and window functions. A zero setup SQLite version runs the exact same 10 questions with only the Python standard library, so anyone can reproduce the results without installing a database server.

Author: Punith Nonavinakere Thandavamurthy, M.S. Data Science, Pace University (expected Jan 2027). GitHub: https://github.com/PunithNT, LinkedIn: linkedin.com/in/punith-nt, Email: contactpunithnt@gmail.com

## Overview

City service request data is a good test of practical SQL: messy timestamps, categorical dimensions like borough and agency, skewed resolution times, and questions that need ranking, running totals, and comparisons against group averages. This repo is built around those patterns.

What this project shows:

- Schema design for an operational dataset with indexes on the main filter columns
- Loading a CSV into Postgres and into SQLite from the same source file
- Ten business questions answered with CTEs and window functions, not just GROUP BY
- A deterministic synthetic data generator that mirrors the real NYC 311 schema, so the repo runs offline with no API key
- Automated tests that execute all 10 queries and check their output columns

## Dataset

### Real dataset: NYC Open Data 311 Service Requests

Source: NYC Open Data, "311 Service Requests from 2010 to Present" (dataset id erm2-nwe9 on data.cityofnewyork.us).

How to download the real CSV:

1. Go to https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9
2. Use Export, then Download as CSV. For a manageable file, filter first in the portal UI, for example Created Date in 2024 and a single agency, because the full dataset has tens of millions of rows.
3. Or use the Socrata API: `https://data.cityofnewyork.us/resource/erm2-nwe9.csv?$limit=50000&$where=created_date between '2024-01-01T00:00:00' and '2024-12-31T23:59:59'`
4. Rename the exported headers to the snake_case names used in this repo (see the mapping below) and drop columns you do not need, then load the file as `data/requests_311.csv`.

Columns used in this repo (real header in parentheses):

- `unique_key` (Unique Key): unique id for each request
- `created_date` (Created Date): when the request was opened
- `closed_date` (Closed Date): when it was closed, null if still open
- `agency` (Agency): responsible agency code, for example NYPD, HPD, DOT, DSNY, DEP
- `complaint_type` (Complaint Type): category, for example Noise - Residential, HEAT/HOT WATER, Street Condition
- `descriptor` (Descriptor): sub category detail within a complaint type
- `borough` (Borough): MANHATTAN, BROOKLYN, QUEENS, BRONX, or STATEN ISLAND
- `status` (Status): Closed, Open, or Pending
- `resolution_hours`: derived column, hours between created_date and closed_date. The real export does not include this directly, so compute it on load as the epoch difference divided by 3600.

### Bundled synthetic data

The repo bundles a synthetic generator, it does not bundle real 311 records. `src/generate_data.py` creates `data/requests_311.csv` with 5000 rows, seed 42, covering all of 2024. The schema, agency codes, complaint types, descriptors, and borough values mirror the real dataset listed above. Resolution times are drawn around per complaint base values, so agency comparisons look realistic in shape. All findings in this README and in `reports/answers.md` are demo findings from synthetic data and should not be cited as real NYC results.

## Quickstart

### Path A: Postgres via Docker Compose

Prerequisites: Docker with Compose, and Python 3.10 or newer for the generator step.

```bash
# 1. Generate the synthetic CSV (or place a renamed real CSV at the same path)
python src/generate_data.py

# 2. Start Postgres. This runs sql/01_schema.sql and sql/02_load_notes.sql
#    as init scripts from the mounted sql/ folder.
docker compose up -d

# 3. Wait for the healthcheck, then load the CSV with psql copy
docker compose exec db psql -U analytics -d nyc311 -c "\copy requests_311 (unique_key, created_date, closed_date, agency, complaint_type, descriptor, borough, status, resolution_hours) FROM '/data/requests_311.csv' WITH (FORMAT csv, HEADER true, NULL '')"

# 4. Run all 10 Postgres queries
docker compose exec db psql -U analytics -d nyc311 -f /docker-entrypoint-initdb.d/queries.sql
# Note: queries.sql lives in the mounted sql/ folder. If your Compose
# version maps it under a different name, run it via a local psql instead:
# psql "postgresql://analytics:analytics@localhost:5432/nyc311" -f sql/queries.sql

# 5. Stop the database (add -v to also delete the data volume)
docker compose down
```

Database connection defaults from `docker-compose.yml`: database `nyc311`, user `analytics`, password `analytics`, host port 5432, image `postgres:16`.

Loading note: `sql/02_load_notes.sql` documents why loading is via the Python loader and psql copy rather than a server side COPY inside the schema file. The same CSV path works for Docker, local Postgres, and SQLite.

### Path B: Zero setup SQLite demo (no server, no Docker)

Prerequisites: Python 3.10 or newer only. The loader uses the standard library `sqlite3` and `csv` modules. Pandas is optional and not required for this path.

```bash
python src/generate_data.py
python src/load_and_run.py
python tests/test_queries.py
```

`load_and_run.py` creates `data/requests_311.db`, loads the CSV, runs the 10 questions from `src/queries_sqlite.py`, prints the top rows for each question, and writes the full output to `reports/answers.md`. If pytest is installed, you can also run `pytest tests/test_queries.py -v`.

Dialect differences between the Postgres and SQLite versions:

- Month truncation: Postgres uses `DATE_TRUNC('month', created_date)`, SQLite uses `strftime('%Y-%m', created_date)`.
- Date only: Postgres uses `created_date::date`, SQLite uses `date(created_date)`.
- Numeric rounding: Postgres casts to numeric for `ROUND(AVG(...)::numeric, 2)` in a few queries, SQLite rounds floats directly.
- Everything else, including CTEs, `ROW_NUMBER`, `RANK`, `DENSE_RANK`, `LAG`, `NTILE`, running `SUM() OVER`, and framed moving averages, is identical logic in both dialects. SQLite 3.25 and newer supports all of these window functions.

## The 10 Business Questions

1. Borough volume and share: Which boroughs generate the most requests, and what share of total volume does each represent? Shows a CTE with `RANK()` and `SUM() OVER ()` for share of total.
2. Top 3 complaints per borough: What are the top 3 complaint types within each borough? Shows `ROW_NUMBER() OVER (PARTITION BY borough ORDER BY count DESC)` in a ranked CTE.
3. Monthly trend: How has monthly request volume trended, and what is the month over month change? Shows `LAG() OVER (ORDER BY month)` for prior period comparison.
4. Cumulative total: What is the cumulative running total of requests by month? Shows running `SUM() OVER (ORDER BY month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`.
5. Agency speed leaderboard: Which agencies resolve requests fastest and slowest on average? Shows `RANK()` and `DENSE_RANK()` over an aggregated CTE.
6. Slower than agency average: Which complaint types take longer to resolve than their own agency average? Shows `AVG() OVER (PARTITION BY agency)` compared against complaint level averages.
7. Resolution quartiles: How do resolution times split into quartiles, and what does the slowest quartile look like? Shows `NTILE(4) OVER (ORDER BY resolution_hours)` in a CTE, then a summary by quartile.
8. Daily moving average: What does daily volume look like smoothed with a 7 day moving average? Shows `AVG() OVER` with a `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` frame.
9. Top descriptor per complaint: What is the single most common descriptor for each complaint type? Shows `ROW_NUMBER()` partitioned by complaint type plus `SUM() OVER (PARTITION BY ...)` for totals.
10. Backlog concentration: Where is the open request backlog concentrated by borough and agency? Shows partitioned `SUM() OVER` and `RANK() OVER (PARTITION BY borough ...)` on filtered Open and Pending rows.

Full SQL: Postgres versions in `sql/queries.sql`, SQLite versions in `src/queries_sqlite.py`. Full output tables in `reports/answers.md`.

## Demo Findings from Synthetic Data

These findings come from running the bundled synthetic dataset (5000 rows, seed 42, calendar year 2024). They demonstrate the queries, they are not findings about real NYC operations.

- Borough volume (Q1): Brooklyn generated the most requests with 1589 (31.78 percent of total), followed by Queens with 1364 (27.28 percent), Manhattan with 997 (19.94 percent), Bronx with 763 (15.26 percent), and Staten Island with 287 (5.74 percent).
- Top complaints (Q2): Noise and parking dominate every borough. In Brooklyn the top 3 were Blocked Driveway (93), Noise - Residential (78), and Noise - Street/Sidewalk (73). In the Bronx the order flipped, with Noise - Street/Sidewalk first at 48. The same three complaint families appear in the top 3 of four of the five boroughs.
- Monthly trend (Q3 and Q4): Volume was flat by design in the synthetic data, ranging from 377 in November to 443 in September, with the largest month over month drops in November (minus 12.12 percent) and March (minus 10.27 percent). Cumulative volume crossed 25 percent of the year in March and 50 percent in July.
- Agency speed (Q5 and Q6): NYPD was fastest on average at 11.24 hours across 1019 closed requests, while DOB was slowest at 116.03 hours and DOT was second slowest at 111.53 hours. The largest gap above an agency average was DOT Sidewalk Condition at 195.11 hours, which is 83.59 hours above the DOT average.
- Resolution quartiles (Q7): The fastest quartile averaged 8.85 hours and capped at 15.85 hours, while the slowest quartile averaged 153.06 hours and stretched to 926.46 hours, showing the long tail that a single overall average would hide.
- Backlog (Q10): NYPD held the largest open backlog slice in every borough, for example 62 of 238 open requests in Brooklyn (26.05 percent) and 38 of 114 in the Bronx (33.33 percent).

See `reports/answers.md` for the complete result tables for all 10 questions.

## Project Structure

```
sql-analytics-postgres/
  README.md
  LICENSE
  docker-compose.yml
  requirements.txt
  data/
    requests_311.csv          Generated synthetic data (created by generate_data.py)
  sql/
    01_schema.sql             Postgres table and indexes
    02_load_notes.sql         Why loading is via the Python loader, plus copy command
    queries.sql               All 10 questions, Postgres dialect
  src/
    generate_data.py          Deterministic synthetic 311 style generator, seed 42
    queries_sqlite.py         All 10 questions, SQLite dialect
    load_and_run.py           SQLite loader and runner, writes reports/answers.md
  reports/
    answers.md                Generated output for all 10 questions
  tests/
    test_queries.py           Executes all 10 queries and checks columns and rows
```

## Tests

```bash
python tests/test_queries.py
# or, if pytest is installed:
pytest tests/test_queries.py -v
```

Tests build a small in memory SQLite database from generated data (500 rows, seed 123), run all 10 queries, verify the exact output columns for each question, check that Q1 shares sum to about 100 percent, and check that Q2 returns at most 3 rows per borough.

## Limitations and Next Steps

- The bundled data is synthetic. Real 311 data has strong seasonality, agency specific backlogs, duplicate requests, and location fields (latitude, longitude, facility type, zip) that this schema omits for focus.
- Resolution hours for Open and Pending requests are null by definition, so backlog aging by days open would be a natural Q11.
- A useful extension is a borough by month heatmap query using conditional aggregation, and a percentile query using `PERCENTILE_CONT` in Postgres (which has no direct SQLite equivalent).

## Author

Punith Nonavinakere Thandavamurthy, M.S. Data Science, Pace University (expected Jan 2027)

GitHub: https://github.com/PunithNT, LinkedIn: linkedin.com/in/punith-nt, Email: contactpunithnt@gmail.com

## License

MIT, see LICENSE.

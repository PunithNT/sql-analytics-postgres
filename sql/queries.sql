-- queries.sql
-- All 10 business questions in Postgres dialect.
-- Run after 01_schema.sql and after loading data/requests_311.csv
-- (loading is via the Python loader, see 02_load_notes.sql).
-- SQLite versions of the same logic live in src/queries_sqlite.py.

-- Q1: Which boroughs generate the most requests, and what share of total volume does each represent?
-- Technique: CTE, RANK(), SUM() OVER () for share of total.
WITH borough_counts AS (
    SELECT borough, COUNT(*) AS request_count
    FROM requests_311
    GROUP BY borough
)
SELECT
    borough,
    request_count,
    RANK() OVER (ORDER BY request_count DESC) AS volume_rank,
    ROUND(100.0 * request_count / SUM(request_count) OVER (), 2) AS pct_of_total
FROM borough_counts
ORDER BY request_count DESC;

-- Q2: What are the top 3 complaint types within each borough?
-- Technique: CTE, ROW_NUMBER() OVER (PARTITION BY borough ...).
WITH complaint_counts AS (
    SELECT borough, complaint_type, COUNT(*) AS request_count
    FROM requests_311
    GROUP BY borough, complaint_type
),
ranked AS (
    SELECT
        borough,
        complaint_type,
        request_count,
        ROW_NUMBER() OVER (
            PARTITION BY borough ORDER BY request_count DESC, complaint_type ASC
        ) AS rn
    FROM complaint_counts
)
SELECT borough, complaint_type, request_count, rn AS rank_in_borough
FROM ranked
WHERE rn <= 3
ORDER BY borough, rn;

-- Q3: How has monthly request volume trended, and what is the month over month change?
-- Technique: CTE with DATE_TRUNC, LAG() OVER for prior month comparison.
WITH monthly AS (
    SELECT DATE_TRUNC('month', created_date)::date AS month, COUNT(*) AS request_count
    FROM requests_311
    GROUP BY month
)
SELECT
    month,
    request_count,
    LAG(request_count) OVER (ORDER BY month) AS prev_month_count,
    request_count - LAG(request_count) OVER (ORDER BY month) AS mom_change,
    ROUND(
        100.0 * (request_count - LAG(request_count) OVER (ORDER BY month))
        / NULLIF(LAG(request_count) OVER (ORDER BY month), 0),
        2
    ) AS mom_pct_change
FROM monthly
ORDER BY month;

-- Q4: What is the cumulative running total of requests by month, and when did volume cross key thresholds?
-- Technique: CTE, running SUM() OVER (ORDER BY month ROWS UNBOUNDED PRECEDING).
WITH monthly AS (
    SELECT DATE_TRUNC('month', created_date)::date AS month, COUNT(*) AS request_count
    FROM requests_311
    GROUP BY month
)
SELECT
    month,
    request_count,
    SUM(request_count) OVER (
        ORDER BY month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_requests,
    ROUND(
        100.0 * SUM(request_count) OVER (
            ORDER BY month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) / SUM(request_count) OVER (),
        2
    ) AS cumulative_pct_of_year
FROM monthly
ORDER BY month;

-- Q5: Which agencies resolve requests fastest and slowest on average?
-- Technique: CTE, RANK() and DENSE_RANK() on AVG(resolution_hours).
WITH agency_stats AS (
    SELECT
        agency,
        COUNT(*) AS closed_count,
        ROUND(AVG(resolution_hours)::numeric, 2) AS avg_resolution_hours,
        ROUND(MIN(resolution_hours)::numeric, 2) AS min_resolution_hours,
        ROUND(MAX(resolution_hours)::numeric, 2) AS max_resolution_hours
    FROM requests_311
    WHERE status = 'Closed' AND resolution_hours IS NOT NULL
    GROUP BY agency
)
SELECT
    agency,
    closed_count,
    avg_resolution_hours,
    min_resolution_hours,
    max_resolution_hours,
    RANK() OVER (ORDER BY avg_resolution_hours ASC) AS fastest_rank,
    DENSE_RANK() OVER (ORDER BY avg_resolution_hours DESC) AS slowest_dense_rank
FROM agency_stats
ORDER BY avg_resolution_hours ASC;

-- Q6: Which complaint types take longer to resolve than their own agency average?
-- Technique: AVG() OVER (PARTITION BY agency) window inside a CTE, then filter.
WITH closed AS (
    SELECT agency, complaint_type, resolution_hours
    FROM requests_311
    WHERE status = 'Closed' AND resolution_hours IS NOT NULL
),
with_agency_avg AS (
    SELECT
        agency,
        complaint_type,
        resolution_hours,
        AVG(resolution_hours) OVER (PARTITION BY agency) AS agency_avg_hours
    FROM closed
),
complaint_stats AS (
    SELECT
        agency,
        complaint_type,
        COUNT(*) AS closed_count,
        ROUND(AVG(resolution_hours)::numeric, 2) AS avg_resolution_hours,
        ROUND(MAX(agency_avg_hours)::numeric, 2) AS agency_avg_hours,
        ROUND((AVG(resolution_hours) - MAX(agency_avg_hours))::numeric, 2) AS hours_above_agency_avg
    FROM with_agency_avg
    GROUP BY agency, complaint_type
)
SELECT agency, complaint_type, closed_count, avg_resolution_hours, agency_avg_hours, hours_above_agency_avg
FROM complaint_stats
WHERE avg_resolution_hours > agency_avg_hours
ORDER BY hours_above_agency_avg DESC;

-- Q7: How do resolution times split into quartiles, and what does the slowest quartile look like?
-- Technique: NTILE(4) OVER (ORDER BY resolution_hours) in a CTE, then summarize.
WITH quartiled AS (
    SELECT
        borough,
        agency,
        resolution_hours,
        NTILE(4) OVER (ORDER BY resolution_hours ASC) AS quartile
    FROM requests_311
    WHERE status = 'Closed' AND resolution_hours IS NOT NULL
)
SELECT
    quartile,
    COUNT(*) AS request_count,
    ROUND(MIN(resolution_hours)::numeric, 2) AS min_hours,
    ROUND(AVG(resolution_hours)::numeric, 2) AS avg_hours,
    ROUND(MAX(resolution_hours)::numeric, 2) AS max_hours
FROM quartiled
GROUP BY quartile
ORDER BY quartile;

-- Q8: What does daily volume look like smoothed with a 7 day moving average?
-- Technique: CTE on daily counts, AVG() OVER with ROWS BETWEEN 6 PRECEDING frame.
WITH daily AS (
    SELECT created_date::date AS day, COUNT(*) AS request_count
    FROM requests_311
    GROUP BY day
)
SELECT
    day,
    request_count,
    ROUND(
        AVG(request_count) OVER (
            ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        )::numeric,
        2
    ) AS moving_avg_7d,
    MAX(request_count) OVER (
        ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS max_in_7d_window
FROM daily
ORDER BY day;

-- Q9: What is the single most common descriptor for each complaint type?
-- Technique: CTE, ROW_NUMBER() partitioned by complaint_type, SUM() OVER for totals.
WITH descriptor_counts AS (
    SELECT complaint_type, descriptor, COUNT(*) AS request_count
    FROM requests_311
    GROUP BY complaint_type, descriptor
),
ranked AS (
    SELECT
        complaint_type,
        descriptor,
        request_count,
        ROW_NUMBER() OVER (
            PARTITION BY complaint_type ORDER BY request_count DESC, descriptor ASC
        ) AS rn,
        SUM(request_count) OVER (PARTITION BY complaint_type) AS complaint_total
    FROM descriptor_counts
)
SELECT
    complaint_type,
    descriptor AS top_descriptor,
    request_count AS top_descriptor_count,
    complaint_total,
    ROUND(100.0 * request_count / complaint_total, 2) AS pct_of_complaint_type
FROM ranked
WHERE rn = 1
ORDER BY request_count DESC;

-- Q10: Where is the open request backlog concentrated by borough and agency?
-- Technique: CTE, SUM() OVER (PARTITION BY borough), RANK() partitioned by borough.
WITH backlog AS (
    SELECT
        borough,
        agency,
        COUNT(*) AS open_count
    FROM requests_311
    WHERE status IN ('Open', 'Pending')
    GROUP BY borough, agency
),
with_totals AS (
    SELECT
        borough,
        agency,
        open_count,
        SUM(open_count) OVER (PARTITION BY borough) AS borough_open_total,
        SUM(open_count) OVER () AS total_open
    FROM backlog
)
SELECT
    borough,
    agency,
    open_count,
    borough_open_total,
    ROUND(100.0 * open_count / borough_open_total, 2) AS pct_of_borough_backlog,
    RANK() OVER (PARTITION BY borough ORDER BY open_count DESC) AS rank_in_borough
FROM with_totals
ORDER BY borough, open_count DESC;

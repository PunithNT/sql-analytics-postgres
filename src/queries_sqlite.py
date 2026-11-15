"""The 10 business questions in SQLite dialect.

These mirror sql/queries.sql (Postgres dialect). Dialect differences:
- Month truncation uses strftime('%Y-%m', created_date) instead of
  DATE_TRUNC('month', created_date).
- Date only extraction uses date(created_date) instead of
  created_date::date.
- Window functions, CTEs, RANK, ROW_NUMBER, LAG, NTILE and running
  SUM OVER work the same way in both dialects (SQLite 3.25+).
"""

QUERIES = [
    {
        "id": 1,
        "question": "Which boroughs generate the most requests, and what share of total volume does each represent?",
        "sql": """
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
ORDER BY request_count DESC
""",
    },
    {
        "id": 2,
        "question": "What are the top 3 complaint types within each borough?",
        "sql": """
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
ORDER BY borough, rn
""",
    },
    {
        "id": 3,
        "question": "How has monthly request volume trended, and what is the month over month change?",
        "sql": """
WITH monthly AS (
    SELECT strftime('%Y-%m', created_date) AS month, COUNT(*) AS request_count
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
ORDER BY month
""",
    },
    {
        "id": 4,
        "question": "What is the cumulative running total of requests by month, and when did volume cross key thresholds?",
        "sql": """
WITH monthly AS (
    SELECT strftime('%Y-%m', created_date) AS month, COUNT(*) AS request_count
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
ORDER BY month
""",
    },
    {
        "id": 5,
        "question": "Which agencies resolve requests fastest and slowest on average?",
        "sql": """
WITH agency_stats AS (
    SELECT
        agency,
        COUNT(*) AS closed_count,
        ROUND(AVG(resolution_hours), 2) AS avg_resolution_hours,
        ROUND(MIN(resolution_hours), 2) AS min_resolution_hours,
        ROUND(MAX(resolution_hours), 2) AS max_resolution_hours
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
ORDER BY avg_resolution_hours ASC
""",
    },
    {
        "id": 6,
        "question": "Which complaint types take longer to resolve than their own agency average?",
        "sql": """
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
        ROUND(AVG(resolution_hours), 2) AS avg_resolution_hours,
        ROUND(MAX(agency_avg_hours), 2) AS agency_avg_hours,
        ROUND(AVG(resolution_hours) - MAX(agency_avg_hours), 2) AS hours_above_agency_avg
    FROM with_agency_avg
    GROUP BY agency, complaint_type
)
SELECT agency, complaint_type, closed_count, avg_resolution_hours, agency_avg_hours, hours_above_agency_avg
FROM complaint_stats
WHERE avg_resolution_hours > agency_avg_hours
ORDER BY hours_above_agency_avg DESC
""",
    },
    {
        "id": 7,
        "question": "How do resolution times split into quartiles, and what does the slowest quartile look like?",
        "sql": """
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
    ROUND(MIN(resolution_hours), 2) AS min_hours,
    ROUND(AVG(resolution_hours), 2) AS avg_hours,
    ROUND(MAX(resolution_hours), 2) AS max_hours
FROM quartiled
GROUP BY quartile
ORDER BY quartile
""",
    },
    {
        "id": 8,
        "question": "What does daily volume look like smoothed with a 7 day moving average?",
        "sql": """
WITH daily AS (
    SELECT date(created_date) AS day, COUNT(*) AS request_count
    FROM requests_311
    GROUP BY day
)
SELECT
    day,
    request_count,
    ROUND(
        AVG(request_count) OVER (
            ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ),
        2
    ) AS moving_avg_7d,
    MAX(request_count) OVER (
        ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS max_in_7d_window
FROM daily
ORDER BY day
""",
    },
    {
        "id": 9,
        "question": "What is the single most common descriptor for each complaint type?",
        "sql": """
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
ORDER BY request_count DESC
""",
    },
    {
        "id": 10,
        "question": "Where is the open request backlog concentrated by borough and agency?",
        "sql": """
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
ORDER BY borough, open_count DESC
""",
    },
]

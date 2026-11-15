"""Tests that all 10 SQLite queries execute and return expected columns.

Uses an in-memory/temp SQLite database with a small generated dataset.
Runs under pytest, and also as a plain script:
    python tests/test_queries.py
"""

import csv
import sqlite3
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from generate_data import generate_rows  # noqa: E402
from queries_sqlite import QUERIES  # noqa: E402

SCHEMA_SQL = """
CREATE TABLE requests_311 (
    unique_key INTEGER PRIMARY KEY,
    created_date TEXT NOT NULL,
    closed_date TEXT,
    agency TEXT NOT NULL,
    complaint_type TEXT NOT NULL,
    descriptor TEXT,
    borough TEXT NOT NULL,
    status TEXT NOT NULL,
    resolution_hours REAL
);
"""

EXPECTED_COLUMNS = {
    1: ["borough", "request_count", "volume_rank", "pct_of_total"],
    2: ["borough", "complaint_type", "request_count", "rank_in_borough"],
    3: ["month", "request_count", "prev_month_count", "mom_change", "mom_pct_change"],
    4: ["month", "request_count", "cumulative_requests", "cumulative_pct_of_year"],
    5: ["agency", "closed_count", "avg_resolution_hours", "min_resolution_hours", "max_resolution_hours", "fastest_rank", "slowest_dense_rank"],
    6: ["agency", "complaint_type", "closed_count", "avg_resolution_hours", "agency_avg_hours", "hours_above_agency_avg"],
    7: ["quartile", "request_count", "min_hours", "avg_hours", "max_hours"],
    8: ["day", "request_count", "moving_avg_7d", "max_in_7d_window"],
    9: ["complaint_type", "top_descriptor", "top_descriptor_count", "complaint_total", "pct_of_complaint_type"],
    10: ["borough", "agency", "open_count", "borough_open_total", "pct_of_borough_backlog", "rank_in_borough"],
}


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    rows = generate_rows(n_rows=500, seed=123)
    conn.executemany(
        """
        INSERT INTO requests_311
            (unique_key, created_date, closed_date, agency, complaint_type,
             descriptor, borough, status, resolution_hours)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["unique_key"],
                r["created_date"],
                r["closed_date"] or None,
                r["agency"],
                r["complaint_type"],
                r["descriptor"],
                r["borough"],
                r["status"],
                float(r["resolution_hours"]) if r["resolution_hours"] != "" else None,
            )
            for r in rows
        ],
    )
    conn.commit()
    return conn


def test_all_queries_execute_and_return_rows():
    conn = make_conn()
    try:
        assert len(QUERIES) == 10
        for q in QUERIES:
            cur = conn.execute(q["sql"])
            headers = [d[0] for d in cur.description]
            rows = cur.fetchall()
            assert headers == EXPECTED_COLUMNS[q["id"]], (
                f"Q{q['id']} columns {headers} != expected {EXPECTED_COLUMNS[q['id']]}"
            )
            assert len(rows) > 0, f"Q{q['id']} returned no rows"
    finally:
        conn.close()


def test_q1_shares_sum_to_approx_100():
    conn = make_conn()
    try:
        q1 = next(q for q in QUERIES if q["id"] == 1)
        rows = conn.execute(q1["sql"]).fetchall()
        total_pct = sum(r[3] for r in rows)
        assert 99.0 <= total_pct <= 101.0, f"Q1 pct sum was {total_pct}"
    finally:
        conn.close()


def test_q2_at_most_3_per_borough():
    conn = make_conn()
    try:
        q2 = next(q for q in QUERIES if q["id"] == 2)
        rows = conn.execute(q2["sql"]).fetchall()
        from collections import Counter

        counts = Counter(r[0] for r in rows)
        for borough, c in counts.items():
            assert c <= 3, f"{borough} had {c} rows in Q2"
    finally:
        conn.close()


def test_csv_roundtrip(tmp_path=None):
    # Verify the generator writes a readable CSV with the right header
    target_dir = Path(tmp_path) if tmp_path else Path(tempfile.mkdtemp())
    csv_path = target_dir / "test.csv"
    rows = generate_rows(n_rows=50, seed=7)
    fieldnames = [
        "unique_key", "created_date", "closed_date", "agency",
        "complaint_type", "descriptor", "borough", "status", "resolution_hours",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == fieldnames
        loaded = list(reader)
        assert len(loaded) == 50


if __name__ == "__main__":
    test_all_queries_execute_and_return_rows()
    print("test_all_queries_execute_and_return_rows PASSED")
    test_q1_shares_sum_to_approx_100()
    print("test_q1_shares_sum_to_approx_100 PASSED")
    test_q2_at_most_3_per_borough()
    print("test_q2_at_most_3_per_borough PASSED")
    test_csv_roundtrip()
    print("test_csv_roundtrip PASSED")
    print("All tests passed.")

-- 01_schema.sql
-- Schema for NYC Open Data 311 style service requests.
-- Postgres 16 dialect. Mirrors the columns used by the bundled
-- synthetic generator in src/generate_data.py.
--
-- Loading note: this file only creates the table. Data loading is
-- handled by the Python loader and by sql/02_load_notes.sql, not by
-- a raw COPY in this file, so the same CSV works for local files
-- and for the Docker init flow.

DROP TABLE IF EXISTS requests_311;

CREATE TABLE requests_311 (
    unique_key       BIGINT PRIMARY KEY,
    created_date     TIMESTAMP NOT NULL,
    closed_date      TIMESTAMP,
    agency           TEXT NOT NULL,
    complaint_type   TEXT NOT NULL,
    descriptor       TEXT,
    borough          TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('Closed', 'Open', 'Pending')),
    resolution_hours DOUBLE PRECISION
);

CREATE INDEX idx_requests_311_borough ON requests_311 (borough);
CREATE INDEX idx_requests_311_agency ON requests_311 (agency);
CREATE INDEX idx_requests_311_created_date ON requests_311 (created_date);
CREATE INDEX idx_requests_311_complaint_type ON requests_311 (complaint_type);
CREATE INDEX idx_requests_311_status ON requests_311 (status);

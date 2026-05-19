-- Parquet Artifacts
-- Tracks the parquet files uploaded to object storage (Cloudflare R2 or any
-- S3-compatible backend). One row per table_name; UPSERT replaces the prior
-- artifact entry when a new run uploads.
--
-- This is the metadata-in-Postgres half of the "files in R2, metadata in
-- Neon" pattern. Hasura tracks it like any other table; viz apps query for
-- the latest object_key + sha256 to know what to fetch and verify.
DROP TABLE IF EXISTS parquet_artifacts CASCADE;

CREATE TABLE parquet_artifacts (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(64) NOT NULL UNIQUE,
    object_key VARCHAR(512) NOT NULL,
    bucket VARCHAR(128) NOT NULL,
    endpoint VARCHAR(256) NOT NULL,
    sha256 CHAR(64) NOT NULL,
    etag VARCHAR(128),
    size_bytes BIGINT NOT NULL,
    row_count BIGINT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_parquet_artifacts_table ON parquet_artifacts(table_name);
CREATE INDEX idx_parquet_artifacts_uploaded ON parquet_artifacts(uploaded_at DESC);

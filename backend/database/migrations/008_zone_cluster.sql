-- 008_zone_cluster.sql
-- K-Means soil fertility zone clustering and expert validation tables.
-- Idempotent: safe to run repeatedly.

-- =====================================================================
-- 1. Tabel klaster zona kesuburan tanah (hasil model K-Means)
-- =====================================================================
CREATE TABLE IF NOT EXISTS hara_zone_cluster (
    area_id INTEGER PRIMARY KEY REFERENCES hara_bogor(id) ON DELETE CASCADE,
    cluster_id INTEGER NOT NULL,
    zone_key VARCHAR(32) NOT NULL,
    zone_label VARCHAR(64) NOT NULL,
    dist_to_centroid DOUBLE PRECISION,
    dist_to_second DOUBLE PRECISION,
    model_version VARCHAR(32) NOT NULL,
    trained_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_hara_zone_cluster_zone_key ON hara_zone_cluster (zone_key);
CREATE INDEX IF NOT EXISTS ix_hara_zone_cluster_model_version ON hara_zone_cluster (model_version);

COMMENT ON TABLE hara_zone_cluster IS
    'Soil fertility zone classification produced by K-Means model.';

-- =====================================================================
-- 2. Tabel override zona oleh pakar (audit trail koreksi label)
-- =====================================================================
CREATE TABLE IF NOT EXISTS hara_zone_label_override (
    id SERIAL PRIMARY KEY,
    area_id INTEGER NOT NULL REFERENCES hara_bogor(id) ON DELETE CASCADE,
    zone_key VARCHAR(32) NOT NULL,
    expert_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_hara_zone_label_override_area_id ON hara_zone_label_override (area_id);
CREATE INDEX IF NOT EXISTS ix_hara_zone_label_override_expert_id ON hara_zone_label_override (expert_id);

COMMENT ON TABLE hara_zone_label_override IS
    'Expert manual corrections to algorithmic soil fertility zone classifications.';

-- =====================================================================
-- 3. Tabel log review analisis AI oleh pakar
-- =====================================================================
CREATE TABLE IF NOT EXISTS analysis_review (
    id SERIAL PRIMARY KEY,
    area_id INTEGER NOT NULL REFERENCES hara_bogor(id) ON DELETE CASCADE,
    expert_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    decision VARCHAR(32) NOT NULL, -- 'validated' | 'overridden'
    zone_key VARCHAR(32),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_analysis_review_area_id ON analysis_review (area_id);
CREATE INDEX IF NOT EXISTS ix_analysis_review_expert_id ON analysis_review (expert_id);

COMMENT ON TABLE analysis_review IS
    'Expert validation and override reviews for AI recommendations and zone classifications.';

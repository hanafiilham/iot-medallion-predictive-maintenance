CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 1. BRONZE: Data mentah dari sensor
CREATE TABLE bronze_sensor_raw (
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    device_id VARCHAR(50),
    raw_payload JSONB
);
SELECT create_hypertable('bronze_sensor_raw', 'ingested_at', if_not_exists => true);

-- 2. SILVER: Data bersih & penanda anomali
CREATE TABLE silver_sensor_clean (
    event_time TIMESTAMPTZ NOT NULL,
    device_id VARCHAR(50) NOT NULL,
    temperature_c DOUBLE PRECISION,
    vibration_mms DOUBLE PRECISION,
    power_watt DOUBLE PRECISION,
    is_anomaly BOOLEAN DEFAULT FALSE
);
SELECT create_hypertable('silver_sensor_clean', 'event_time', if_not_exists => true);

-- 3. GOLD: Agregasi per 1 menit (siap latih model Deep Learning)
CREATE TABLE gold_sensor_features_1m (
    bucket_time TIMESTAMPTZ NOT NULL,
    device_id VARCHAR(50) NOT NULL,
    avg_temp_c DOUBLE PRECISION,
    max_vibration_mms DOUBLE PRECISION,
    std_vibration_mms DOUBLE PRECISION,
    avg_power_watt DOUBLE PRECISION,
    sample_count INT,
    PRIMARY KEY (bucket_time, device_id)
);
SELECT create_hypertable('gold_sensor_features_1m', 'bucket_time', if_not_exists => true);

-- ==========================================
-- ENTERPRISE DATA MANAGEMENT & GOVERNANCE
-- ==========================================

-- 1. Kebijakan Retensi pada Lapisan Bronze (hapus otomatis log JSON mentah > 7 hari)
SELECT add_retention_policy('bronze_sensor_raw', INTERVAL '7 days', if_not_exists => true);

-- 2. Kompresi Otomatis pada Lapisan Silver (> 1 hari)
ALTER TABLE silver_sensor_clean SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'device_id'
);
SELECT add_compression_policy('silver_sensor_clean', INTERVAL '1 day', if_not_exists => true);

-- 3. Tabel Audit Kualitas Data (Data Quality Logs)
CREATE TABLE IF NOT EXISTS data_quality_logs (
  audit_time TIMESTAMPTZ DEFAULT NOW(),
  check_name VARCHAR(100),
  metric_value DOUBLE PRECISION,
  status VARCHAR(20),
  details TEXT
);
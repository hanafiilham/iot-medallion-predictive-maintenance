import os
import psycopg2
from datetime import datetime, timezone

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "iot_telemetry")
DB_USER = os.getenv("DB_USER", "de_user")
DB_PASS = os.getenv("DB_PASS", "de_password")

def run_data_quality_audit():
    conn = psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )
    cur = conn.cursor()

    checks = []

    # 1. Completeness & Drop Rate Check (Bronze vs Silver dalam 15 menit terakhir)
    cur.execute("""
        SELECT
            (SELECT COUNT(*) FROM bronze_sensor_raw WHERE ingested_at >= NOW() - INTERVAL '15 minutes') AS bronze_cnt,
            (SELECT COUNT(*) FROM silver_sensor_clean WHERE event_time >= NOW() - INTERVAL '15 minutes') AS silver_cnt;
    """)
    bronze_cnt, silver_cnt = cur.fetchone()
    if bronze_cnt > 0:
        drop_rate = ((bronze_cnt - silver_cnt) / bronze_cnt) * 100
        status = "PASS" if drop_rate <= 15.0 else "WARN"
        checks.append((
            "bronze_to_silver_drop_rate_pct",
            round(drop_rate, 2),
            status,
            f"Bronze: {bronze_cnt} rows, Silver: {silver_cnt} rows"
        ))

    # 2. Validity Check: Memastikan tidak ada nilai daya/getaran negatif di Silver
    cur.execute("""
        SELECT COUNT(*) FROM silver_sensor_clean
        WHERE event_time >= NOW() - INTERVAL '15 minutes'
          AND (power_watt < 0 OR vibration_mms < 0 OR temperature_c < -50);
    """)
    invalid_rows = cur.fetchone()[0]
    checks.append((
        "silver_physical_bounds_check",
        float(invalid_rows),
        "PASS" if invalid_rows == 0 else "FAIL",
        f"Invalid physical sensor rows found: {invalid_rows}"
    ))

    # 3. Freshness / Latency Check: Pastikan data Gold ter-update maksimal 2 menit terakhir
    cur.execute("""
        SELECT EXTRACT(EPOCH FROM (NOW() - MAX(bucket_time))) FROM gold_sensor_features_1m;
    """)
    lag_seconds = cur.fetchone()[0]
    if lag_seconds is not None:
        checks.append((
            "gold_layer_freshness_lag_sec",
            round(float(lag_seconds), 1),
            "PASS" if lag_seconds <= 120 else "WARN",
            f"Latest Gold bucket lag: {round(float(lag_seconds), 1)}s"
        ))

    # Simpan & cetak hasil audit
    print(f"\n=== DATA QUALITY AUDIT REPORT ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}) ===")
    for name, val, status, detail in checks:
        cur.execute(
            "INSERT INTO data_quality_logs (check_name, metric_value, status, details) VALUES (%s, %s, %s, %s);",
            (name, val, status, detail)
        )
        print(f"[{status}] {name}: {val} -> {detail}")

    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    run_data_quality_audit()
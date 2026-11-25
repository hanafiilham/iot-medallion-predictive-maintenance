import json
import os
from collections import defaultdict
from datetime import datetime
import statistics
import paho.mqtt.client as mqtt
import psycopg2

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
TOPIC = "factory/machines/+/telemetry"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "iot_telemetry"),
    "user": os.getenv("DB_USER", "de_user"),
    "password": os.getenv("DB_PASSWORD", "de_password"),
}

minute_buffers = defaultdict(list)
current_minute_key = {}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def flush_to_gold(conn, device_id: str, bucket_str: str, records: list):
    if not records:
        return
    temps = [r["temperature_c"] for r in records if r["temperature_c"] is not None]
    vibs = [r["vibration_mms"] for r in records]
    powers = [r["power_watt"] for r in records]

    avg_temp = round(sum(temps) / len(temps), 2) if temps else None
    max_vib = round(max(vibs), 3)
    std_vib = round(statistics.stdev(vibs), 3) if len(vibs) > 1 else 0.0
    avg_power = round(sum(powers) / len(powers), 2)

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO gold_sensor_features_1m 
            (bucket_time, device_id, avg_temp_c, max_vibration_mms, std_vibration_mms, avg_power_watt, sample_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (bucket_time, device_id) DO UPDATE SET
                avg_temp_c = EXCLUDED.avg_temp_c,
                max_vibration_mms = EXCLUDED.max_vibration_mms,
                std_vibration_mms = EXCLUDED.std_vibration_mms,
                avg_power_watt = EXCLUDED.avg_power_watt,
                sample_count = EXCLUDED.sample_count;
        """, (bucket_str, device_id, avg_temp, max_vib, std_vib, avg_power, len(records)))
    conn.commit()
    print(f"[GOLD] Agregasi 1m disimpan untuk {device_id} @ {bucket_str}")

def process_message(conn, raw_str: str):
    data = json.loads(raw_str)
    device_id = data.get("device_id", "UNKNOWN")

    # 1. INSERT KE BRONZE
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO bronze_sensor_raw (device_id, raw_payload) VALUES (%s, %s)",
            (device_id, json.dumps(data))
        )

    # 2. VALIDASI & INSERT KE SILVER
    temp = data.get("temperature_c")
    vib = data.get("vibration_mms")
    power = data.get("power_watt")
    event_time = datetime.fromisoformat(data["timestamp"])

    if temp is None or vib is None:
        conn.commit()
        print(f"[SILVER SKIP] Data null dibuang dari {device_id}")
        return

    is_anomaly = (temp > 90.0) or (vib > 5.0)

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO silver_sensor_clean 
            (event_time, device_id, temperature_c, vibration_mms, power_watt, is_anomaly)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (event_time, device_id, temp, vib, power, is_anomaly))
    conn.commit()

    # 3. WINDOWING 1 MENIT UNTUK GOLD
    bucket_dt = event_time.replace(second=0, microsecond=0)
    bucket_str = bucket_dt.isoformat()

    if device_id in current_minute_key and current_minute_key[device_id] != bucket_str:
        old_bucket = current_minute_key[device_id]
        flush_to_gold(conn, device_id, old_bucket, minute_buffers[(device_id, old_bucket)])
        del minute_buffers[(device_id, old_bucket)]

    current_minute_key[device_id] = bucket_str
    minute_buffers[(device_id, bucket_str)].append(data)

def main():
    conn = get_db_connection()

    def on_connect(client, userdata, flags, reason_code, properties):
        print("Processor terhubung ke MQTT Broker, mendengarkan data...")
        client.subscribe(TOPIC)

    def on_message(client, userdata, msg):
        try:
            process_message(conn, msg.payload.decode("utf-8"))
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Gagal memproses pesan: {e}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="medallion_processor")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()

if __name__ == "__main__":
    main()
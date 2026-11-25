import json
import math
import os
import random
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

BROKER_HOST = os.getenv("MQTT_HOST", "localhost")
BROKER_PORT = int(os.getenv("MQTT_PORT", 1883))
TOPIC_PREFIX = "factory/machines"

DEVICES = ["MOTOR-01", "MOTOR-02", "MOTOR-03"]

def generate_telemetry(device_id: str, step: int) -> dict:
    base_temp = 65.0 + 5.0 * math.sin(step / 10.0) + random.uniform(-0.8, 0.8)
    base_vib = 2.1 + 0.4 * math.cos(step / 8.0) + random.uniform(-0.15, 0.15)
    base_power = 1200.0 + 50.0 * math.sin(step / 12.0) + random.uniform(-10, 10)

    if random.random() < 0.05:
        base_temp += random.uniform(35.0, 60.0)
        base_vib += random.uniform(4.0, 8.0)

    temp_val = None if random.random() < 0.02 else round(base_temp, 2)

    return {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": temp_val,
        "vibration_mms": round(base_vib, 3),
        "power_watt": round(base_power, 2)
    }

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="iot_simulator")
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    print(f"Terhubung ke MQTT Broker di {BROKER_HOST}:{BROKER_PORT}")
    step = 0
    try:
        while True:
            for device in DEVICES:
                payload = generate_telemetry(device, step)
                topic = f"{TOPIC_PREFIX}/{device}/telemetry"
                client.publish(topic, json.dumps(payload), qos=1)
                print(f"[SENT] {topic} -> {payload}")
            step += 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("Simulator dihentikan.")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
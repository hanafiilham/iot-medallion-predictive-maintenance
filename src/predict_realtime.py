import time
import os
import psycopg2
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "iot_telemetry"),
    "user": os.getenv("DB_USER", "de_user"),
    "password": os.getenv("DB_PASSWORD", "de_password")
}
MODEL_PATH = "models/lstm_autoencoder.pth"
POLL_INTERVAL_SEC = 30  # Jalankan inference setiap 30 detik


class LSTMAutoencoder(nn.Module):
    def __init__(self, n_features, hidden_dim=16):
        super().__init__()
        self.encoder = nn.LSTM(n_features, hidden_dim, batch_first=True)
        self.decoder = nn.LSTM(hidden_dim, n_features, batch_first=True)

    def forward(self, x):
        _, (hidden, _) = self.encoder(x)
        repeated = hidden.squeeze(0).unsqueeze(1).repeat(1, x.size(1), 1)
        reconstructed, _ = self.decoder(repeated)
        return reconstructed


def load_model_bundle():
    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    features = checkpoint["features"]
    seq_len = checkpoint["seq_len"]
    threshold = float(checkpoint["threshold"])
    mean = checkpoint["scaler_mean"]
    scale = checkpoint["scaler_scale"]

    model = LSTMAutoencoder(n_features=len(features), hidden_dim=16)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, features, seq_len, threshold, mean, scale


def run_inference_cycle(model, features, seq_len, threshold, mean, scale):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Ambil 5 bucket terakhir per device_id dari lapisan Gold
    query = """
        WITH ranked AS (
            SELECT bucket_time, device_id, avg_temp_c, max_vibration_mms,
                   COALESCE(std_vibration_mms, 0) AS std_vibration_mms, avg_power_watt,
                   ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY bucket_time DESC) AS rn
            FROM gold_sensor_features_1m
        )
        SELECT bucket_time, device_id, avg_temp_c, max_vibration_mms, std_vibration_mms, avg_power_watt
        FROM ranked
        WHERE rn <= %s
        ORDER BY device_id, bucket_time ASC;
    """
    df = pd.read_sql(query, conn, params=(seq_len,))

    scored_count = 0
    for device_id, group in df.groupby("device_id"):
        if len(group) < seq_len:
            continue

        latest_bucket = group["bucket_time"].max()
        raw_vals = group[features].values
        scaled_vals = (raw_vals - mean) / scale
        tensor_x = torch.tensor(scaled_vals, dtype=torch.float32).unsqueeze(0)

        with torch.no_grad():
            recon = model(tensor_x).numpy()
            mse_score = float(np.mean((scaled_vals - recon[0]) ** 2))

        is_anomaly = mse_score > threshold

        cur.execute(
            """
            INSERT INTO gold_predictive_alerts (scored_at, device_id, anomaly_score, threshold, is_predicted_anomaly)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (scored_at, device_id) DO UPDATE
            SET anomaly_score = EXCLUDED.anomaly_score,
                threshold = EXCLUDED.threshold,
                is_predicted_anomaly = EXCLUDED.is_predicted_anomaly;
            """,
            (latest_bucket, device_id, mse_score, threshold, is_anomaly)
        )
        scored_count += 1
        status_tag = "ALERT!" if is_anomaly else "NORMAL"
        print(f"[{status_tag}] {device_id} | Bucket: {latest_bucket} | MSE Score: {mse_score:.4f} (Threshold: {threshold:.4f})")

    conn.commit()
    cur.close()
    conn.close()
    return scored_count


def main():
    print("Memuat artefak model LSTM Autoencoder...")
    model, features, seq_len, threshold, mean, scale = load_model_bundle()
    print(f"Model siap! Window={seq_len}m | Threshold={threshold:.4f} | Interval={POLL_INTERVAL_SEC}s\n")

    while True:
        try:
            run_inference_cycle(model, features, seq_len, threshold, mean, scale)
        except Exception as e:
            print(f"[ERROR] Inference cycle gagal: {e}")
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
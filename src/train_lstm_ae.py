import os
import psycopg2
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler

# 1. Konfigurasi Database & Hyperparameters
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "iot_telemetry",
    "user": "de_user",
    "password": "de_password"
}
FEATURES = ["avg_temp_c", "max_vibration_mms", "std_vibration_mms", "avg_power_watt"]
SEQ_LEN = 5          # Jendela waktu 5 menit berturut-turut
HIDDEN_DIM = 16
EPOCHS = 40
BATCH_SIZE = 8
MODEL_PATH = "models/lstm_autoencoder.pth"


# 2. Ekstraksi Fitur dari Gold Layer (TimescaleDB)
def load_gold_features():
    conn = psycopg2.connect(**DB_CONFIG)
    query = """
        SELECT bucket_time, device_id, avg_temp_c, max_vibration_mms,
               COALESCE(std_vibration_mms, 0) AS std_vibration_mms, avg_power_watt
        FROM gold_sensor_features_1m
        ORDER BY device_id, bucket_time ASC;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


# 3. Pembentukan Sliding Window Sequence per Mesin
def create_sequences(df, scaler, seq_len=SEQ_LEN):
    sequences = []
    meta = []
    for device_id, group in df.groupby("device_id"):
        group = group.sort_values("bucket_time").reset_index(drop=True)
        if len(group) < seq_len:
            continue
        scaled_vals = scaler.transform(group[FEATURES].values)
        for i in range(len(scaled_vals) - seq_len + 1):
            sequences.append(scaled_vals[i : i + seq_len])
            meta.append((device_id, group.loc[i + seq_len - 1, "bucket_time"]))
    return np.array(sequences, dtype=np.float32), meta


# 4. Arsitektur LSTM Autoencoder (PyTorch)
class LSTMAutoencoder(nn.Module):
    def __init__(self, n_features, hidden_dim):
        super().__init__()
        self.encoder = nn.LSTM(n_features, hidden_dim, batch_first=True)
        self.decoder = nn.LSTM(hidden_dim, n_features, batch_first=True)

    def forward(self, x):
        _, (hidden, _) = self.encoder(x)
        # Ulangi vektor bottleneck sepanjang seq_len untuk direkonstruksi
        repeated = hidden.squeeze(0).unsqueeze(1).repeat(1, x.size(1), 1)
        reconstructed, _ = self.decoder(repeated)
        return reconstructed


def main():
    print("Mengambil dataset deret waktu dari Gold Layer...")
    df = load_gold_features()
    print(f"Total baris Gold Layer ditemukan: {len(df)} baris ({df['device_id'].nunique()} mesin)")

    if len(df) < SEQ_LEN * 2:
        print(f"Data Gold Layer masih sedikit ({len(df)} baris). Tunggu 3-5 menit lagi agar agregasi 1-menitan terkumpul.")
        return

    # Normalisasi fitur
    scaler = StandardScaler()
    scaler.fit(df[FEATURES].values)

    X, meta = create_sequences(df, scaler, SEQ_LEN)
    print(f"Total sequence terbentuk (window={SEQ_LEN} menit): {X.shape}")

    dataset = TensorDataset(torch.tensor(X))
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    # Inisialisasi Model, Loss, dan Optimizer
    model = LSTMAutoencoder(n_features=len(FEATURES), hidden_dim=HIDDEN_DIM)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    # Training Loop
    model.train()
    for epoch in range(1, EPOCHS + 1):
        total_loss = 0.0
        for (batch_x,) in loader:
            optimizer.zero_grad()
            output = model(batch_x)
            loss = criterion(output, batch_x)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * batch_x.size(0)
        if epoch % 10 == 0 or epoch == 1:
            print(f"Epoch [{epoch:02d}/{EPOCHS}] - Reconstruction MSE Loss: {total_loss / len(X):.6f}")

    # Evaluasi Reconstruction Error & Deteksi Anomali
    model.eval()
    with torch.no_grad():
        preds = model(torch.tensor(X)).numpy()
        mse_per_seq = np.mean((X - preds) ** 2, axis=(1, 2))

    threshold = np.mean(mse_per_seq) + 2.5 * np.std(mse_per_seq)
    anomalies = [(meta[i][0], meta[i][1], mse_per_seq[i]) for i in range(len(mse_per_seq)) if mse_per_seq[i] > threshold]

    print("\n=== HASIL EVALUASI PREDICTIVE MAINTENANCE ===")
    print(f"Mean Reconstruction Error : {np.mean(mse_per_seq):.6f}")
    print(f"Dynamic Anomaly Threshold : {threshold:.6f}")
    print(f"Total Window Anomali      : {len(anomalies)} dari {len(X)} window")

    for dev, ts, score in anomalies[:5]:
        print(f"  [ALERT] Mesin: {dev} | Waktu: {ts} | Anomaly Score (MSE): {score:.6f}")

    # Simpan artefak model & parameter scaler
    os.makedirs("models", exist_ok=True)
    torch.save({
        "model_state_dict": model.state_dict(),
        "scaler_mean": scaler.mean_,
        "scaler_scale": scaler.scale_,
        "threshold": threshold,
        "seq_len": SEQ_LEN,
        "features": FEATURES
    }, MODEL_PATH)
    print(f"\nModel berhasil disimpan ke: {MODEL_PATH}")


if __name__ == "__main__":
    main()
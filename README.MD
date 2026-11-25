# End-to-End IoT Medallion Data Pipeline & Predictive Maintenance

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-LSTM_Autoencoder-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![TimescaleDB](https://img.shields.io/badge/TimescaleDB-Medallion_Lakehouse-FDB515?style=for-the-badge&logo=timescale&logoColor=black)
![MQTT](https://img.shields.io/badge/MQTT-Eclipse_Mosquitto-3C5280?style=for-the-badge&logo=eclipsemosquitto&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-Real--Time_Observability-F46800?style=for-the-badge&logo=grafana&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)

Sistem pemantauan telemetri sensor motor industri secara *real-time* yang menggabungkan **IoT Data Engineering (Medallion Architecture)**, **Enterprise Data Management (EDM)**, dan **Deep Learning Anomaly Detection (LSTM Autoencoder)** untuk mendeteksi gejala degradasi mesin sebelum terjadi kegagalan total (*unplanned downtime*).

![Grafana Dashboard Preview](docs/dashboard_preview.png)

---

## Arsitektur Sistem

```text
[IoT Virtual Sensors (Python)] 
        │ (MQTT / JSON)
        ▼
[Eclipse Mosquitto Broker]
        │
        ▼
[Stream ETL Processor (Python)]
   ├──► Bronze Layer : Raw JSON payload ingestion (Audit & Replay, 7-Day Retention)
   ├──► Silver Layer : Null filtering, schema validation & columnar compression
   └──► Gold Layer   : 1-minute tumbling window aggregations (ML/DL Feature Store)
        │
        ▼
[TimescaleDB (PostgreSQL)] ──► [PyTorch LSTM Autoencoder] ──► [Grafana Live Monitoring Dashboard]
                                 (Real-Time MSE Scoring)         (Threshold Alerting: 2.3225)
```

---

## Fitur Utama

* **Real-Time IoT Ingestion:** Simulasi 3 unit motor industri (`MOTOR-01`, `MOTOR-02`, `MOTOR-03`) yang mengirimkan metrik suhu (*temperature*), getaran (*vibration*), arus listrik (*current*), dan kecepatan putaran (*RPM*) setiap detik melalui protokol MQTT.
* **Medallion Architecture & Enterprise Data Management (EDM):**
  * **Bronze Layer:** Menyimpan seluruh log telemetri mentah untuk kebutuhan audit dan *replay* dengan kebijakan retensi data otomatis (*7-day retention policy*).
  * **Silver Layer:** Pembersihan nilai *null*, validasi rentang sensor, serta kompresi kolom otomatis (*columnstore compression*) untuk efisiensi penyimpanan *time-series*.
  * **Gold Layer:** Agregasi fitur per menit (`gold_motor_features_1m`) sebagai *feature store* dan tabel peringatan prediktif (`gold_predictive_alerts`), dilengkapi skrip audit kualitas data (`src/dq_audit.py`).
* **Deep Learning Predictive Maintenance:** Model **LSTM Autoencoder** berbasis PyTorch yang dilatih untuk merekonstruksi pola operasi normal dan menghitung skor anomali (*Reconstruction Error / MSE*) secara *real-time* setiap 30 detik dengan *Dynamic Threshold* sebesar **`2.3225`**.
* **Observability & Containerization:** Seluruh komponen diorkestrasi menggunakan Docker Compose dan dipantau melalui dashboard interaktif Grafana OSS (`grafana/iot_medallion_dashboard.json`).

---

## Struktur Direktori Proyek

```text
iot-medallion-predictive-maintenance/
├── docs/
│   ├── architecture_diagram.png      # Diagram arsitektur sistem
│   └── dashboard_preview.png         # Tangkapan layar dashboard Grafana
├── grafana/
│   └── iot_medallion_dashboard.json  # Konfigurasi ekspor dashboard Grafana (5 panel)
├── models/
│   └── lstm_autoencoder.pth          # Bobot model terlatih PyTorch LSTM Autoencoder
├── src/
│   ├── simulator.py                  # Generator data sensor motor virtual (MQTT Publisher)
│   ├── stream_processor.py           # ETL pipeline dari MQTT ke Bronze/Silver/Gold
│   ├── train_lstm.py                 # Skrip pelatihan model LSTM Autoencoder
│   ├── predict_realtime.py           # Layanan inferensi skor anomali real-time
│   └── dq_audit.py                   # Skrip audit kualitas & tata kelola data (EDM)
├── .env.example                      # Contoh variabel konfigurasi environment
├── .gitignore                        # Pengecualian file lokal (.venv, cache, logs)
├── docker-compose.yml                # Orkestrasi multi-container Docker
├── requirements.txt                  # Daftar dependensi Python
└── README.md                         # Dokumentasi proyek
```

---

## Tech Stack

| Komponen | Teknologi | Peran dalam Pipeline |
| :--- | :--- | :--- |
| **Message Broker** | Eclipse Mosquitto (MQTT) | Perantara pengiriman data telemetri *lightweight* dari sensor IoT |
| **Stream Processing** | Python (`paho-mqtt`, `psycopg2`) | Konsumsi data *real-time* dan transformasi antar lapisan Medallion |
| **Time-Series Lakehouse** | TimescaleDB (PostgreSQL) | Penyimpanan hypertable Bronze, Silver, dan Gold beserta kebijakan retensi & kompresi |
| **Deep Learning** | PyTorch, NumPy, Pandas, Scikit-Learn | Pelatihan dan inferensi model *LSTM Autoencoder* untuk deteksi anomali |
| **Observability** | Grafana OSS | Visualisasi metrik sensor dan *threshold alerting* (`2.3225`) secara *real-time* |
| **Infrastructure** | Docker & Docker Compose | Kontainerisasi dan orkestrasi seluruh layanan *end-to-end* |

---

## Prasyarat & Setup Environment

Sebelum menjalankan proyek, pastikan perangkat Anda telah terpasang:
* **Docker Desktop** (Docker Engine & Docker Compose v2+)
* **Python 3.10+** *(opsional, hanya diperlukan jika ingin menjalankan skrip pelatihan ulang model AI atau audit kualitas data secara lokal di luar container)*
* **Git**

### 1. Clone Repositori
```bash
git clone https://github.com/hanafiilham/iot-medallion-predictive-maintenance.git
cd iot-medallion-predictive-maintenance
```

### 2. Konfigurasi Environment Variables
Salin konfigurasi berikut ke dalam file `.env` di direktori utama proyek (atau gunakan kredensial bawaan pada `docker-compose.yml` untuk pengujian lokal):
```env
POSTGRES_USER=de_user
POSTGRES_PASSWORD=de_password
POSTGRES_DB=iot_telemetry
MQTT_BROKER_HOST=mosquitto
MQTT_BROKER_PORT=1883
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin
```

### 3. Menjalankan Seluruh Pipeline via Docker (Direkomendasikan)
Jalankan seluruh layanan (*Mosquitto Broker*, *TimescaleDB*, *IoT Simulator*, *Stream Processor*, *Real-Time AI Predictor*, dan *Grafana*) dalam satu perintah:
```bash
docker compose up -d --build
```
Pastikan seluruh kontainer berstatus `Up` / `Running`:
```bash
docker compose ps
```

### 4. Setup Python Virtual Environment *(Opsional — untuk Training & Audit Lokal)*
Jika Anda ingin melatih ulang model **LSTM Autoencoder** atau menjalankan **Data Quality Audit** secara manual di terminal lokal:
```powershell
# Buat dan aktifkan virtual environment (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install seluruh dependensi Python
pip install -r requirements.txt

# Jalankan audit kualitas data Medallion Layer
python src/dq_audit.py
```

### 5. Akses & Konfigurasi Dashboard Grafana
1. Buka browser dan akses **`http://localhost:3000`** (login default: `admin` / `admin`).
2. Tambahkan Data Source **PostgreSQL** dengan detail koneksi berikut:
   * **Host:** `timescaledb:5432`
   * **Database:** `iot_telemetry`
   * **User / Password:** `de_user` / `de_password`
   * **TLS/SSL Mode:** `disable`
3. Buka menu **Dashboards** → **New** → **Import**, lalu unggah file **`grafana/iot_medallion_dashboard.json`**.

---

## Detail Model AI & Threshold Anomali

* **Arsitektur Model:** *Sequence-to-Sequence LSTM Autoencoder* dilatih menggunakan data operasional normal dari tabel `gold_motor_features_1m`.
* **Metrik Evaluasi:** *Mean Squared Error (MSE)* antara urutan fitur masukan dan hasil rekonstruksi model (`anomaly_score`).
* **Dynamic Anomaly Threshold:** **`2.3225`** — apabila `anomaly_score` suatu motor melampaui nilai ini, kolom `is_predicted_anomaly` pada tabel `gold_predictive_alerts` otomatis bernilai `TRUE` dan memicu garis peringatan merah pada panel *Real-Time AI Anomaly Score* di Grafana.
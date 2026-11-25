# Real-Time IoT Telemetry & Medallion Data Pipeline

End-to-end streaming data engineering pipeline yang mensimulasikan telemetri sensor industri secara real-time, memproses kualitas data menggunakan arsitektur **Medallion (Bronze, Silver, Gold)**, dan menyajikan fitur deret waktu siap pakai untuk analitik maupun pelatihan model *Deep Learning / Predictive Maintenance*.

## Arsitektur Sistem
```text
[IoT Virtual Sensors (Python)] 
        │ (MQTT / JSON)
        ▼
[Eclipse Mosquitto Broker]
        │
        ▼
[Stream ETL Processor (Python)]
   ├──► Bronze Layer : Raw JSON payload ingestion (Audit & Replay)
   ├──► Silver Layer : Null filtering & anomaly detection flagging
   └──► Gold Layer   : 1-minute tumbling window aggregations (ML/DL Features)
        │
        ▼
[TimescaleDB (PostgreSQL)] ──► [Grafana Live Monitoring Dashboard]

## Prasyarat & Setup Environment

Sebelum menjalankan proyek, pastikan perangkat Anda telah terpasang:
* **Docker Desktop** (Docker Engine & Docker Compose v2+)
* **Python 3.10+** (opsional, hanya diperlukan jika ingin menjalankan skrip pelatihan ulang model AI atau audit kualitas data secara lokal di luar container)
* **Git**

### 1. Clone Repositori
```bash
git clone [https://github.com/hanafiilham/iot-medallion-predictive-maintenance.git](https://github.com/hanafiilham/iot-medallion-predictive-maintenance.git)
cd iot-medallion-predictive-maintenance

### KonFirugrasi Environment Variables
POSTGRES_USER=de_user
POSTGRES_PASSWORD=de_password
POSTGRES_DB=iot_telemetry
MQTT_BROKER_HOST=mosquitto
MQTT_BROKER_PORT=1883
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin

# Menjalankan seluruh pipeline via docker
docker compose up -d --build
docker compose ps

# Buat dan aktifkan virtual environment (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install seluruh dependensi Python
pip install -r requirements.txt

# Jalankan audit kualitas data Medallion Layer
python src/dq_audit.py

### Akses & Konfigurasi Dashboard Grafana
Buka browser dan akses http://localhost:3000 (login default: admin / admin).

Tambahkan Data Source PostgreSQL dengan detail koneksi:

Host: timescaledb:5432

Database: iot_telemetry

User / Password: de_user / de_password

TLS/SSL Mode: disable

Buka menu Dashboards → New → Import, lalu unggah file grafana/iot_medallion_dashboard.json.
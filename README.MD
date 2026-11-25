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
import time
import os
import numpy as np
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text

# Get database connection URL
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

PLANT_MILLS = ["Mill 1", "Mill 2", "Mill 4", "Mill 5", "Mill 6"]
EQUIPMENT_LIST = ["Dynamic Separator", "E5 & E8 Cement Pumps", "Separator Filter Fan", "Mill Main Control", "Main Filter Fan"]

def init_remote_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS plc_telemetry (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                mill VARCHAR(50) NOT NULL,
                equipment VARCHAR(50) NOT NULL,
                vibration_mm_s REAL NOT NULL,
                temperature_c REAL NOT NULL
            );
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mill_ts ON plc_telemetry(mill, timestamp);"))

def poll_and_ingest():
    now = datetime.now()
    rows = []
    for mill in PLANT_MILLS:
        for eq in EQUIPMENT_LIST:
            vib_base = 4.0 if eq == "Mill Main Control" else 2.5
            temp_base = 62.0 if eq == "E5 & E8 Cement Pumps" else 55.0
            
            vib = round(max(0, np.random.normal(vib_base, 0.4)), 2)
            temp = round(np.random.normal(temp_base, 1.2), 1)
            
            rows.append({
                "timestamp": now,
                "mill": mill,
                "equipment": eq,
                "vibration_mm_s": vib,
                "temperature_c": temp
            })
    
    df = pd.DataFrame(rows)
    df.to_sql("plc_telemetry", engine, if_exists="append", index=False)
    print(f"[{now.strftime('%H:%M:%S')}] 💾 Ingested {len(df)} telemetry tags to Cloud PostgreSQL.")

if __name__ == "__main__":
    init_remote_db()
    print("🚀 Central Cloud Telemetry Daemon Running...")
    while True:
        try:
            poll_and_ingest()
        except Exception as e:
            print(f"⚠️ Ingestion Warning: {e}")
        time.sleep(3)
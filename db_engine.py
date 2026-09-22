import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# Fallback to local SQLite if DATABASE_URL is not set
DATABASE_URL = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///plant_telemetry.db"))

@st.cache_resource
def get_db_engine():
    """Returns a cached SQLAlchemy database connection engine."""
    return create_engine(DATABASE_URL, pool_pre_ping=True)

def init_db():
    """Initializes table schema across SQLite or PostgreSQL."""
    engine = get_db_engine()
    
    id_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if "sqlite" in str(engine.url) else "SERIAL PRIMARY KEY"
    
    query = f"""
    CREATE TABLE IF NOT EXISTS plc_telemetry (
        id {id_type},
        timestamp TIMESTAMP NOT NULL,
        mill VARCHAR(50) NOT NULL,
        equipment VARCHAR(50) NOT NULL,
        vibration_mm_s REAL NOT NULL,
        temperature_c REAL NOT NULL
    );
    """
    with engine.begin() as conn:
        conn.execute(text(query))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mill_ts ON plc_telemetry(mill, timestamp);"))

def fetch_telemetry_history(mill_name, limit_records=1000):
    """Fetches telemetry history for plotting."""
    engine = get_db_engine()
    query = text("""
        SELECT timestamp, mill, equipment, vibration_mm_s, temperature_c 
        FROM plc_telemetry 
        WHERE mill = :mill 
        ORDER BY timestamp DESC 
        LIMIT :limit
    """)
    try:
        df = pd.read_sql_query(query, engine, params={"mill": mill_name, "limit": limit_records})
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df.sort_values("timestamp")
    except Exception as e:
        print(f"Database Query Error: {e}")
    return pd.DataFrame(columns=["timestamp", "mill", "equipment", "vibration_mm_s", "temperature_c"])
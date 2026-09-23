# db_engine.py
import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

DATABASE_URL = st.secrets.get(
    "DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://postgres.avzcqgwerokdyzdpflnz:Just72506537%40@aws-1-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require")
)

@st.cache_resource
def get_db_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)

def init_alert_db_table():
    """Ensures the central plc_alerts table exists in Supabase."""
    engine = get_db_engine()
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS plc_alerts (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        mill VARCHAR(50),
        equipment VARCHAR(100),
        severity VARCHAR(20),
        issue TEXT,
        status VARCHAR(50),
        operator_notes TEXT,
        vibration_snapshot FLOAT,
        temperature_snapshot FLOAT
    );
    """
    with engine.begin() as conn:
        conn.execute(text(create_table_sql))

def fetch_all_alerts():
    """Fetches all logged alerts from Supabase PostgreSQL."""
    engine = get_db_engine()
    query = "SELECT * FROM plc_alerts ORDER BY timestamp DESC;"
    try:
        return pd.read_sql(query, con=engine).to_dict(orient="records")
    except Exception:
        return []

def log_alert_to_db(mill: str, equipment: str, severity: str, issue: str, vib: float, temp: float):
    """Inserts a new critical alert into central PostgreSQL storage."""
    engine = get_db_engine()
    query = """
    INSERT INTO plc_alerts (timestamp, mill, equipment, severity, issue, status, operator_notes, vibration_snapshot, temperature_snapshot)
    VALUES (NOW(), :mill, :equipment, :severity, :issue, 'ACTIVE / REQUIRES ACTION', 'Automated ML Alert — Pending Sign-off', :vib, :temp);
    """
    with engine.begin() as conn:
        conn.execute(text(query), {
            "mill": mill,
            "equipment": equipment,
            "severity": severity,
            "issue": issue,
            "vib": vib,
            "temp": temp
        })
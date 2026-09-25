# reset_db.py
import os
import streamlit as st
from sqlalchemy import create_engine, text

# Force direct PostgreSQL port 5432 for local network compatibility
DEFAULT_DB_URL = "postgresql://postgres.avzcqgwerokdyzdpflnz:Just72506537%40@aws-1-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require"

DATABASE_URL = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL", DEFAULT_DB_URL))
if ":6543" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace(":6543", ":5432")

def clear_tables():
    print("🔌 Connecting to Supabase PostgreSQL via Port 5432...")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE plc_alerts RESTART IDENTITY;"))
        conn.execute(text("TRUNCATE TABLE plc_telemetry RESTART IDENTITY;"))
        
    print("🧹 Supabase database tables (`plc_alerts` and `plc_telemetry`) successfully wiped clean!")

if __name__ == "__main__":
    try:
        clear_tables()
    except Exception as e:
        print(f"❌ Failed to reset database: {e}")
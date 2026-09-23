# inject_critical_data.py
import os
import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from ml_engine import analyze_telemetry_diagnostics
from mock_data import get_shared_plant_engine

DATABASE_URL = st.secrets.get(
    "DATABASE_URL", 
    os.getenv("DATABASE_URL", "postgresql://postgres.avzcqgwerokdyzdpflnz:Just72506537%40@aws-1-eu-west-1.pooler.supabase.com:6543/postgres")
)

def inject_and_evaluate_critical_event():
    print("🚀 Injecting CRITICAL telemetry event...")
    
    mill_name = "Mill 6"
    equipment_name = "Dynamic Separator"
    critical_vib = 8.2      # mm/s
    critical_temp = 92.5    # °C
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Run ML Diagnostics and Dispatch Email Alert
    print("🧠 Running ML Anomaly Diagnostic Engine...")
    result = analyze_telemetry_diagnostics(
        mill=mill_name,
        equipment=equipment_name,
        vib=critical_vib,
        temp=critical_temp
    )
    
    # 2. Write Sensor Data to Supabase PostgreSQL (for Live Trend Charts)
    engine = create_engine(DATABASE_URL)
    payload = {
        "timestamp": datetime.now(),
        "mill_name": mill_name,
        "equipment_name": equipment_name,
        "vibration": critical_vib,
        "temperature": critical_temp,
        "status": result["severity"]
    }
    pd.DataFrame([payload]).to_sql("plc_telemetry", con=engine, if_exists="append", index=False)
    
    # 3. Add Entry to In-Memory Alert Log (for Servicing Desk UI Table)
    plant_engine = get_shared_plant_engine()
    new_alert_id = len(plant_engine.alerts_log) + 101
    
    alert_record = {
        "id": new_alert_id,
        "timestamp": timestamp_str,
        "mill": mill_name,
        "equipment": equipment_name,
        "severity": result["severity"],
        "issue": f"ML Anomaly ({result['anomaly_prob']}% Risk): Concurrent heat & vibration rise",
        "status": "ACTIVE / REQUIRES ACTION",
        "operator_notes": "Automated ML Alert — Pending Technician Sign-off",
        "vibration_snapshot": critical_vib,
        "temperature_snapshot": critical_temp,
        "individual_comments": result["individual_comments"]
    }
    
    plant_engine.alerts_log.append(alert_record)
    
    print(f"✅ Success! Critical alert #{new_alert_id} injected into database AND Servicing Desk table for '{mill_name} - {equipment_name}'.")

if __name__ == "__main__":
    inject_and_evaluate_critical_event()
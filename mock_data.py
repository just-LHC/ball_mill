import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import threading
import streamlit as st
from ml_engine import analyze_telemetry_diagnostics

PLANT_MILLS = ["Mill 1", "Mill 2", "Mill 4", "Mill 5", "Mill 6"]

EQUIPMENT_LIST = [
    "Dynamic Separator",
    "E5 & E8 Cement Pumps",
    "Separator Filter Fan",
    "Mill Main Control",
    "Main Filter Fan"
]

# -------------------------------------------------------------------
# CONTINUOUS 24/7 BACKGROUND TELEMETRY INGESTION ENGINE
# -------------------------------------------------------------------
class PlantDataEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self.df = self._generate_initial_telemetry(60)
        self.alerts_log = []
        self._bg_thread_started = False
        self.start_background_ingestion()

    def _generate_initial_telemetry(self, num_records=60):
        now = datetime.now()
        data = []
        for mill in PLANT_MILLS:
            for eq in EQUIPMENT_LIST:
                for i in range(num_records):
                    timestamp = now - timedelta(minutes=(num_records - i))
                    vib_base = 4.0 if eq == "Mill Main Control" else 2.5
                    temp_base = 62.0 if eq == "E5 & E8 Cement Pumps" else 55.0
                    
                    vib = np.random.normal(vib_base, 0.3)
                    temp = np.random.normal(temp_base, 1.0)
                    
                    data.append({
                        "timestamp": timestamp,
                        "mill": mill,
                        "equipment": eq,
                        "vibration_mm_s": round(max(0, vib), 2),
                        "temperature_c": round(temp, 1)
                    })
        return pd.DataFrame(data)

    def tick_live_telemetry(self):
        """Worker task that pulls/generates SCADA packets regardless of active browser sessions."""
        now = datetime.now()
        new_rows = []
        
        # 🎲 2% chance per background cycle to simulate a critical hardware anomaly on a random unit
        trigger_simulated_critical = (np.random.rand() < 0.02)
        critical_mill_target = np.random.choice(PLANT_MILLS) if trigger_simulated_critical else None
        critical_eq_target = np.random.choice(EQUIPMENT_LIST) if trigger_simulated_critical else None

        for mill in PLANT_MILLS:
            for eq in EQUIPMENT_LIST:
                # Standard operational baselines
                vib_base = 4.0 if eq == "Mill Main Control" else 2.5
                temp_base = 62.0 if eq == "E5 & E8 Cement Pumps" else 55.0
                
                # Check if this specific subsystem is selected for a CRITICAL anomaly spike
                if trigger_simulated_critical and mill == critical_mill_target and eq == critical_eq_target:
                    # High vibration breach (ISO Zone D: > 7.0 mm/s) & High thermal breach (> 90 °C)
                    vib = np.random.uniform(7.2, 9.0)
                    temp = np.random.uniform(91.0, 98.0)
                else:
                    vib = np.random.normal(vib_base, 0.4)
                    temp = np.random.normal(temp_base, 1.2)
                
                row = {
                    "timestamp": now,
                    "mill": mill,
                    "equipment": eq,
                    "vibration_mm_s": round(max(0, vib), 2),
                    "temperature_c": round(temp, 1)
                }
                new_rows.append(row)
                self._evaluate_and_log_alert(row)
                
        new_df = pd.DataFrame(new_rows)
        
        with self._lock:
            self.df = pd.concat([self.df, new_df], ignore_index=True).tail(3000)

    def _evaluate_and_log_alert(self, latest_reading):
        mill = latest_reading["mill"]
        eq = latest_reading["equipment"]
        timestamp = latest_reading["timestamp"]
        vib = latest_reading["vibration_mm_s"]
        temp = latest_reading["temperature_c"]
        
        diag = analyze_telemetry_diagnostics(mill, eq, vib, temp)
        
        if diag["severity"] != "NORMAL":
            # 1. Update local shared thread memory
            with self._lock:
                active_alerts = [
                    a for a in self.alerts_log 
                    if a["mill"] == mill and a["equipment"] == eq and "ACTIVE" in a["status"]
                ]
                
                if not active_alerts:
                    self.alerts_log.insert(0, {
                        "id": len(self.alerts_log) + 1,
                        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "mill": mill,
                        "equipment": eq,
                        "severity": diag["severity"],
                        "issue": diag["diagnostic_comments"],
                        "individual_comments": diag["individual_comments"],
                        "status": f"ACTIVE - {diag['severity']}",
                        "vibration_snapshot": vib,
                        "temperature_snapshot": temp,
                        "operator_notes": "Pending Maintenance"
                    })

            # 2. Persist to central Supabase PostgreSQL database for cross-device & cloud visibility
            try:
                from db_engine import log_alert_to_db
                log_alert_to_db(
                    mill=mill,
                    equipment=eq,
                    severity=diag["severity"],
                    issue=diag["diagnostic_comments"],
                    vib=vib,
                    temp=temp
                )
            except Exception:
                pass

    def start_background_ingestion(self):
        """Launches an asynchronous daemon thread that keeps collecting telemetry every 3 seconds."""
        if not self._bg_thread_started:
            self._bg_thread_started = True
            def _loop():
                while True:
                    try:
                        self.tick_live_telemetry()
                    except Exception as e:
                        print(f"[BACKGROUND TELEMETRY WORKER ERROR] {e}")
                    time.sleep(3) # 3-second SCADA ingestion interval

            thread = threading.Thread(target=_loop, daemon=True)
            thread.start()

# SINGLETON SHARED ENGINE ACROSS ALL USERS AND BACKGROUND WORKERS
@st.cache_resource
def get_shared_plant_engine():
    return PlantDataEngine()

def simple_health_score(vib, temp):
    score = 100
    if vib > 4.5: score -= 30
    if vib > 7.0: score -= 40
    if temp > 75.0: score -= 20
    if temp > 90.0: score -= 100
    return max(0, score)
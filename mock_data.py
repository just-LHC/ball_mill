import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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
# SHARED MULTI-USER STATE ENGINE (Accessible across ALL devices)
# -------------------------------------------------------------------
class PlantDataEngine:
    def __init__(self):
        self.df = self._generate_initial_telemetry(30)
        self.alerts_log = []

    def _generate_initial_telemetry(self, num_records=30):
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
        """Fetches 1 reading for all mills and updates shared memory for ALL devices."""
        now = datetime.now()
        new_rows = []
        for mill in PLANT_MILLS:
            for eq in EQUIPMENT_LIST:
                vib_base = 4.0 if eq == "Mill Main Control" else 2.5
                temp_base = 62.0 if eq == "E5 & E8 Cement Pumps" else 55.0
                
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
        self.df = pd.concat([self.df, new_df], ignore_index=True).tail(2500)

    def _evaluate_and_log_alert(self, latest_reading):
        mill = latest_reading["mill"]
        eq = latest_reading["equipment"]
        timestamp = latest_reading["timestamp"]
        vib = latest_reading["vibration_mm_s"]
        temp = latest_reading["temperature_c"]
        
        diag = analyze_telemetry_diagnostics(mill, eq, vib, temp)
        
        active_alerts = [
            a for a in self.alerts_log 
            if a["mill"] == mill and a["equipment"] == eq and "ACTIVE" in a["status"]
        ]
        
        if not active_alerts and diag["severity"] != "NORMAL":
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

# SINGLETON SHARED INSTANCE ACROSS ALL CONNECTED BROWSERS/DEVICES
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



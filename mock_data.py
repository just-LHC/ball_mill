import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import threading
import streamlit as st
from ml_engine import analyze_telemetry_diagnostics

PLANT_MILLS = ["Mill 1 (White Cement)", "Mill 4", "Mill 5", "Mill 6"]

MILL_EQUIPMENT_MAP = {
    "Mill 6": [
        "Dynamic Separator",
        "Separator Filter Fan",
        "Mill Main Control",
        "Main Filter Fan"
    ],
    "Mill 5": [
        "Dynamic Separator",
        "Separator Filter Fan",
        "Mill Main Control"
    ],
    "Mill 4": [
        "Mill Main Control"
    ],
    "Mill 1 (White Cement)": [
        "Mill Main Control"
    ]
}

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
        for mill, eq_list in MILL_EQUIPMENT_MAP.items():
            for eq in eq_list:
                for i in range(num_records):
                    timestamp = now - timedelta(minutes=(num_records - i))
                    
                    # Channels for Mill 6 & Mill 5 Multi-Sensor Setup
                    vib1 = np.random.normal(2.4, 0.3)
                    vib2 = np.random.normal(2.6, 0.3)
                    temp1 = np.random.normal(58.0, 1.0)
                    temp2 = np.random.normal(60.0, 1.0)
                    oil_press = np.random.normal(4.2, 0.15)
                    m5_curr = np.random.normal(145.0, 3.0)

                    data.append({
                        "timestamp": timestamp,
                        "mill": mill,
                        "equipment": eq,
                        "vibration_mm_s": round(max(0, vib1), 2),
                        "vibration_2_mm_s": round(max(0, vib2), 2),
                        "temperature_c": round(temp1, 1),
                        "temperature_2_c": round(temp2, 1),
                        "oil_pressure_bar": round(max(0, oil_press), 2),
                        "motor_current_a": round(max(0, m5_curr), 1)
                    })
        return pd.DataFrame(data)

    def tick_live_telemetry(self):
        now = datetime.now()
        new_rows = []
        
        trigger_warning = (np.random.rand() < 0.03)
        trigger_critical = (np.random.rand() < 0.002) if not trigger_warning else False
        
        target_mill = np.random.choice(PLANT_MILLS) if (trigger_warning or trigger_critical) else None
        target_eq = np.random.choice(MILL_EQUIPMENT_MAP[target_mill]) if target_mill and target_mill in MILL_EQUIPMENT_MAP else None

        for mill, eq_list in MILL_EQUIPMENT_MAP.items():
            for eq in eq_list:
                is_target = (trigger_warning or trigger_critical) and mill == target_mill and eq == target_eq
                
                v1_base, v2_base = (7.8, 8.1) if is_target and trigger_critical else ((5.2, 5.5) if is_target else (2.4, 2.6))
                t1_base, t2_base = (93.0, 95.0) if is_target and trigger_critical else ((78.0, 81.0) if is_target else (58.0, 60.0))
                
                vib1 = np.random.normal(v1_base, 0.3)
                vib2 = np.random.normal(v2_base, 0.3)
                temp1 = np.random.normal(t1_base, 1.0)
                temp2 = np.random.normal(t2_base, 1.0)

                oil_press = np.random.normal(2.1, 0.1) if is_target and trigger_critical else np.random.normal(4.2, 0.15)
                m5_curr = np.random.normal(210.0, 5.0) if is_target and trigger_critical else np.random.normal(145.0, 3.0)

                row = {
                    "timestamp": now,
                    "mill": mill,
                    "equipment": eq,
                    "vibration_mm_s": round(max(0, vib1), 2),
                    "vibration_2_mm_s": round(max(0, vib2), 2),
                    "temperature_c": round(temp1, 1),
                    "temperature_2_c": round(temp2, 1),
                    "oil_pressure_bar": round(max(0, oil_press), 2),
                    "motor_current_a": round(max(0, m5_curr), 1)
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
        vib = max(latest_reading["vibration_mm_s"], latest_reading["vibration_2_mm_s"])
        temp = max(latest_reading["temperature_c"], latest_reading["temperature_2_c"])
        
        diag = analyze_telemetry_diagnostics(mill, eq, vib, temp)
        
        if diag["severity"] != "NORMAL":
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

            try:
                from db_engine import log_alert_to_db
                log_alert_to_db(mill=mill, equipment=eq, severity=diag["severity"], issue=diag["diagnostic_comments"], vib=vib, temp=temp)
            except Exception:
                pass

    def start_background_ingestion(self):
        if not self._bg_thread_started:
            self._bg_thread_started = True
            def _loop():
                while True:
                    try:
                        self.tick_live_telemetry()
                    except Exception as e:
                        print(f"[BACKGROUND WORKER ERROR] {e}")
                    time.sleep(3)

            thread = threading.Thread(target=_loop, daemon=True)
            thread.start()

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
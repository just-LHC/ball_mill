import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import threading
import streamlit as st
from ml_engine import analyze_telemetry_diagnostics

# Updated Mill Hierarchy & Specialized Configurations
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

MILL_SENSOR_PROFILES = {
    "Mill 6": {
        "Dynamic Separator": {"vibration_sensors": 2, "temperature_sensors": 2, "notes": "2 Vibration & 2 Temperature sensors"},
        "Separator Filter Fan": {"vibration_sensors": 2, "temperature_sensors": 2, "notes": "2 Vibration & 2 Temperature sensors"},
        "Mill Main Control": {
            "gearbox_ocp_vib": 10, "gearbox_hlc_vib": 2, "gearbox_temp": 12,
            "motor_hlc_vib": 2, "motor_temp": 2,
            "vibration_sensors": 14, "temperature_sensors": 14,
            "notes": "Gearbox: 10 OCP Vib, 2 HLC Vib, 12 Temp | Motor: 2 HLC Vib, 2 Temp"
        },
        "Main Filter Fan": {"vibration_sensors": 2, "temperature_sensors": 0, "notes": "2 Vibration sensors"}
    },
    "Mill 5": {
        "Mill Main Control": {
            "gearbox_ocp_vib": 10, "gearbox_ocp_temp": 10,
            "vibration_sensors": 10, "temperature_sensors": 10,
            "notes": "Gearbox: 10 OCP Vibration & 10 OCP Temperature sensors"
        },
        "Dynamic Separator": {
            "oil_pressure_sensors": 1, "motor_current_sensors": 1, "temperature_sensors": 1,
            "vibration_sensors": 0,
            "notes": "1 Oil Pressure, Motor Current & 1 Temperature sensor"
        },
        "Separator Filter Fan": {
            "vibration_sensors": 2, "motor_current_sensors": 1, "temperature_sensors": 2,
            "notes": "2 Vibration, Motor Current & 2 Temperature sensors"
        }
    },
    "Mill 4": {
        "Mill Main Control": {"vibration_sensors": 6, "temperature_sensors": 6, "notes": "6 Vibration & 6 Temperature sensors (Gearbox & Motor)"}
    },
    "Mill 1 (White Cement)": {
        "Mill Main Control": {"vibration_sensors": 6, "temperature_sensors": 6, "notes": "6 Vibration & 6 Temperature sensors (Gearbox & Motor)"}
    }
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
                    vib_base = 4.0 if eq == "Mill Main Control" else 2.5
                    temp_base = 62.0 if eq == "Dynamic Separator" else 55.0
                    
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
        now = datetime.now()
        new_rows = []
        
        trigger_warning = (np.random.rand() < 0.03)
        trigger_critical = (np.random.rand() < 0.002) if not trigger_warning else False
        
        target_mill = np.random.choice(PLANT_MILLS) if (trigger_warning or trigger_critical) else None
        
        if target_mill and target_mill in MILL_EQUIPMENT_MAP:
            target_eq = np.random.choice(MILL_EQUIPMENT_MAP[target_mill])
        else:
            target_eq = None

        for mill, eq_list in MILL_EQUIPMENT_MAP.items():
            for eq in eq_list:
                vib_base = 4.0 if eq == "Mill Main Control" else 2.5
                temp_base = 62.0 if eq == "Dynamic Separator" else 55.0
                
                if trigger_critical and mill == target_mill and eq == target_eq:
                    vib = np.random.uniform(7.2, 8.8)
                    temp = np.random.uniform(91.0, 96.0)
                elif trigger_warning and mill == target_mill and eq == target_eq:
                    vib = np.random.uniform(4.8, 6.5)
                    temp = np.random.uniform(76.0, 88.0)
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
        if not self._bg_thread_started:
            self._bg_thread_started = True
            def _loop():
                while True:
                    try:
                        self.tick_live_telemetry()
                    except Exception as e:
                        print(f"[BACKGROUND TELEMETRY WORKER ERROR] {e}")
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
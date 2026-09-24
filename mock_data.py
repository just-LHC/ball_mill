import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import threading
import streamlit as st
from ml_engine import analyze_telemetry_diagnostics

PLANT_MILLS = ["Mill 1 (White Cement)", "Mill 4", "Mill 5", "Mill 6"]

MILL_EQUIPMENT_MAP = {
    "Mill 6": ["Dynamic Separator", "Separator Filter Fan", "Mill Main Control", "Main Filter Fan"],
    "Mill 5": ["Dynamic Separator", "Separator Filter Fan", "Mill Main Control"],
    "Mill 4": ["Mill Main Control"],
    "Mill 1 (White Cement)": ["Mill Main Control"]
}

# Detailed Sensor Breakdown per Subsystem
MILL_SENSOR_CONFIG = {
    "Mill 6": {
        "Dynamic Separator": {
            "vibration": ["Vib Sensor 1 (Upper Bearing)", "Vib Sensor 2 (Rotor Housing)"],
            "temperature": ["Temp Sensor 1 (Upper Bearing)", "Temp Sensor 2 (Grease Sump)"]
        },
        "Separator Filter Fan": {
            "vibration": ["Vib Sensor 1 (DE Pillow Block)", "Vib Sensor 2 (NDE Pillow Block)"],
            "temperature": ["Temp Sensor 1 (DE Bearing)", "Temp Sensor 2 (NDE Bearing)"]
        },
        "Mill Main Control": {
            "vibration": [f"Gearbox OCP Vib {i+1}" for i in range(10)] + ["Gearbox HLC Vib 1", "Gearbox HLC Vib 2", "Motor HLC Vib 1", "Motor HLC Vib 2"],
            "temperature": [f"Gearbox Temp {i+1}" for i in range(12)] + ["Motor Temp 1", "Motor Temp 2"]
        },
        "Main Filter Fan": {
            "vibration": ["Vib Sensor 1 (DE Endbell)", "Vib Sensor 2 (NDE Endbell)"],
            "temperature": []
        }
    },
    "Mill 5": {
        "Mill Main Control": {
            "vibration": [f"Gearbox OCP Vib {i+1}" for i in range(10)],
            "temperature": [f"Gearbox OCP Temp {i+1}" for i in range(10)]
        },
        "Dynamic Separator": {
            "vibration": [],
            "temperature": ["Temp Sensor 1 (Bearing Housing)"],
            "oil_pressure": ["Oil Pressure Sensor 1"],
            "current": ["Motor Current Sensor 1"]
        },
        "Separator Filter Fan": {
            "vibration": ["Vib Sensor 1 (Drive End)", "Vib Sensor 2 (Non-Drive End)"],
            "temperature": ["Temp Sensor 1 (Bearing DE)", "Temp Sensor 2 (Bearing NDE)"],
            "current": ["Motor Current Sensor 1"]
        }
    },
    "Mill 4": {
        "Mill Main Control": {
            "vibration": [f"Gearbox Vib {i+1}" for i in range(4)] + ["Motor Vib 1", "Motor Vib 2"],
            "temperature": [f"Gearbox Temp {i+1}" for i in range(4)] + ["Motor Temp 1", "Motor Temp 2"]
        }
    },
    "Mill 1 (White Cement)": {
        "Mill Main Control": {
            "vibration": [f"Gearbox Vib {i+1}" for i in range(4)] + ["Motor Vib 1", "Motor Vib 2"],
            "temperature": [f"Gearbox Temp {i+1}" for i in range(4)] + ["Motor Temp 1", "Motor Temp 2"]
        }
    }
}

class PlantDataEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self.df = self._generate_initial_telemetry(40)
        self.alerts_log = []
        self._bg_thread_started = False
        self.start_background_ingestion()

    def _generate_initial_telemetry(self, num_records=40):
        now = datetime.now()
        data = []
        for mill, eq_list in MILL_EQUIPMENT_MAP.items():
            for eq in eq_list:
                cfg = MILL_SENSOR_CONFIG.get(mill, {}).get(eq, {})
                vib_sensors = cfg.get("vibration", [])
                temp_sensors = cfg.get("temperature", [])
                
                for i in range(num_records):
                    timestamp = now - timedelta(minutes=(num_records - i))
                    
                    vib_readings = {s: round(max(0, np.random.normal(2.8 if "Motor" in s else 3.5, 0.4)), 2) for s in vib_sensors}
                    temp_readings = {s: round(np.random.normal(58.0 if "Motor" in s else 64.0, 1.2), 1) for s in temp_sensors}
                    
                    row = {
                        "timestamp": timestamp,
                        "mill": mill,
                        "equipment": eq,
                        "vib_sensors": vib_readings,
                        "temp_sensors": temp_readings,
                        "max_vibration": max(vib_readings.values()) if vib_readings else 0.0,
                        "max_temperature": max(temp_readings.values()) if temp_readings else 0.0
                    }
                    
                    # Add specialized sensors if configured
                    if "oil_pressure" in cfg:
                        row["oil_pressure"] = round(np.random.normal(4.2, 0.2), 2)
                    if "current" in cfg:
                        row["motor_current"] = round(np.random.normal(145.0, 5.0), 1)

                    data.append(row)
        return pd.DataFrame(data)

    def tick_live_telemetry(self):
        now = datetime.now()
        new_rows = []
        
        trigger_warning = (np.random.rand() < 0.03)
        trigger_critical = (np.random.rand() < 0.002) if not trigger_warning else False
        
        target_mill = np.random.choice(PLANT_MILLS) if (trigger_warning or trigger_critical) else None
        target_eq = np.random.choice(MILL_EQUIPMENT_MAP[target_mill]) if target_mill else None

        for mill, eq_list in MILL_EQUIPMENT_MAP.items():
            for eq in eq_list:
                cfg = MILL_SENSOR_CONFIG.get(mill, {}).get(eq, {})
                vib_sensors = cfg.get("vibration", [])
                temp_sensors = cfg.get("temperature", [])
                
                is_anomaly_target = (mill == target_mill and eq == target_eq)
                
                vib_readings = {}
                for s in vib_sensors:
                    base = 3.5
                    if is_anomaly_target and np.random.rand() < 0.3:
                        val = np.random.uniform(7.2, 8.8) if trigger_critical else np.random.uniform(4.8, 6.5)
                    else:
                        val = np.random.normal(base, 0.4)
                    vib_readings[s] = round(max(0, val), 2)
                    
                temp_readings = {}
                for s in temp_sensors:
                    base = 62.0
                    if is_anomaly_target and np.random.rand() < 0.3:
                        val = np.random.uniform(91.0, 96.0) if trigger_critical else np.random.uniform(76.0, 88.0)
                    else:
                        val = np.random.normal(base, 1.2)
                    temp_readings[s] = round(val, 1)

                row = {
                    "timestamp": now,
                    "mill": mill,
                    "equipment": eq,
                    "vib_sensors": vib_readings,
                    "temp_sensors": temp_readings,
                    "max_vibration": max(vib_readings.values()) if vib_readings else 0.0,
                    "max_temperature": max(temp_readings.values()) if temp_readings else 0.0
                }
                
                if "oil_pressure" in cfg:
                    row["oil_pressure"] = round(np.random.normal(4.2, 0.2), 2)
                if "current" in cfg:
                    row["motor_current"] = round(np.random.normal(145.0, 5.0), 1)

                new_rows.append(row)
                self._evaluate_and_log_alert(row)
                
        new_df = pd.DataFrame(new_rows)
        with self._lock:
            self.df = pd.concat([self.df, new_df], ignore_index=True).tail(2000)

    def _evaluate_and_log_alert(self, latest_reading):
        mill = latest_reading["mill"]
        eq = latest_reading["equipment"]
        timestamp = latest_reading["timestamp"]
        vib = latest_reading["max_vibration"]
        temp = latest_reading["max_temperature"]
        
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
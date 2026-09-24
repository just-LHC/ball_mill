import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import threading
import streamlit as st
from ml_engine import analyze_telemetry_diagnostics

# Attach Streamlit ScriptRunContext to background worker threads
try:
    from streamlit.runtime.scriptrunner import add_script_run_context
except ImportError:
    try:
        from streamlit.scriptrunner import add_script_run_context
    except ImportError:
        add_script_run_context = None

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
                    
                    record = {
                        "timestamp": timestamp,
                        "mill": mill,
                        "equipment": eq,
                        "vibration_mm_s": round(max(0, np.random.normal(2.5, 0.3)), 2),
                        "vibration_2_mm_s": round(max(0, np.random.normal(2.6, 0.3)), 2),
                        "temperature_c": round(np.random.normal(58.0, 1.0), 1),
                        "temperature_2_c": round(np.random.normal(60.0, 1.0), 1),
                        "oil_pressure_bar": round(max(0, np.random.normal(4.2, 0.15)), 2),
                        "motor_current_a": round(max(0, np.random.normal(145.0, 3.0)), 1),
                        "electrical_power_kw": round(max(0, np.random.normal(320.0, 5.0)), 1),
                        "motor_speed_rpm": round(max(0, np.random.normal(980.0, 10.0)), 0),
                        "motor_temp_c": round(max(0, np.random.normal(68.0, 1.2)), 1)
                    }

                    if mill == "Mill 6" and eq == "Mill Main Control":
                        for idx in range(1, 11):
                            record[f"ocp_gb_vib_{idx}"] = round(max(0, np.random.normal(2.8 + idx*0.1, 0.3)), 2)
                        for idx in range(1, 3):
                            record[f"hlc_gb_vib_{idx}"] = round(max(0, np.random.normal(2.4, 0.25)), 2)
                            record[f"ocp_mtr_vib_{idx}"] = round(max(0, np.random.normal(2.1, 0.2)), 2)
                            record[f"hlc_mtr_tmp_{idx}"] = round(np.random.normal(62.0 + idx, 1.1), 1)

                    elif mill == "Mill 5" and eq == "Mill Main Control":
                        for idx in range(1, 11):
                            record[f"m5_ocp_gb1_vib_{idx}"] = round(max(0, np.random.normal(3.0 + idx*0.05, 0.3)), 2)
                            record[f"m5_ocp_gb1_tmp_{idx}"] = round(np.random.normal(65.0 + idx*0.8, 1.0), 1)
                        for idx in range(1, 4):
                            record[f"m5_hlc_gb1_vib_{idx}"] = round(max(0, np.random.normal(2.6, 0.2)), 2)
                        for idx in range(1, 7):
                            record[f"m5_hlc_gb2_tmp_{idx}"] = round(np.random.normal(68.0 + idx*0.5, 1.2), 1)
                        record["m5_hlc_mtr_tmp_1"] = round(np.random.normal(64.5, 1.0), 1)
                        record["m5_hlc_mtr_cur_1"] = round(max(0, np.random.normal(185.0, 4.0)), 1)

                    elif mill == "Mill 4" and eq == "Mill Main Control":
                        for idx in range(1, 3):
                            record[f"m4_gb_vib_{idx}"] = round(max(0, np.random.normal(2.5 + idx*0.1, 0.3)), 2)
                        for idx in range(1, 4):
                            record[f"m4_gb_tmp_{idx}"] = round(np.random.normal(61.0 + idx*0.5, 1.0), 1)
                        for idx in range(1, 6):
                            record[f"m4_mtr_tmp_{idx}"] = round(np.random.normal(63.0 + idx*0.6, 1.1), 1)
                        record["m4_mtr_cur_1"] = round(max(0, np.random.normal(160.0, 3.5)), 1)

                    elif mill == "Mill 1 (White Cement)" and eq == "Mill Main Control":
                        for idx in range(1, 3):
                            record[f"m1_gb_vib_{idx}"] = round(max(0, np.random.normal(2.3 + idx*0.1, 0.25)), 2)
                        for idx in range(1, 4):
                            record[f"m1_gb_tmp_{idx}"] = round(np.random.normal(59.0 + idx*0.5, 0.9), 1)
                        record["m1_mtr_cur_1"] = round(max(0, np.random.normal(140.0, 3.0)), 1)

                    data.append(record)
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
                
                vib1 = np.random.normal(7.8, 0.3) if is_target and trigger_critical else np.random.normal(2.4, 0.3)
                temp1 = np.random.normal(93.0, 1.0) if is_target and trigger_critical else np.random.normal(58.0, 1.0)

                record = {
                    "timestamp": now,
                    "mill": mill,
                    "equipment": eq,
                    "vibration_mm_s": round(max(0, vib1), 2),
                    "vibration_2_mm_s": round(max(0, np.random.normal(2.6, 0.3)), 2),
                    "temperature_c": round(temp1, 1),
                    "temperature_2_c": round(np.random.normal(60.0, 1.0), 1),
                    "oil_pressure_bar": round(max(0, np.random.normal(4.2, 0.15)), 2),
                    "motor_current_a": round(max(0, np.random.normal(145.0, 3.0)), 1),
                    "electrical_power_kw": round(max(0, np.random.normal(320.0, 5.0)), 1),
                    "motor_speed_rpm": round(max(0, np.random.normal(980.0, 10.0)), 0),
                    "motor_temp_c": round(max(0, np.random.normal(68.0, 1.2)), 1)
                }

                mult = 2.5 if is_target and trigger_critical else 1.0

                if mill == "Mill 6" and eq == "Mill Main Control":
                    for idx in range(1, 11):
                        record[f"ocp_gb_vib_{idx}"] = round(max(0, np.random.normal((2.8 + idx*0.1)*mult, 0.3)), 2)
                    for idx in range(1, 3):
                        record[f"hlc_gb_vib_{idx}"] = round(max(0, np.random.normal(2.4*mult, 0.25)), 2)
                        record[f"ocp_mtr_vib_{idx}"] = round(max(0, np.random.normal(2.1*mult, 0.2)), 2)
                        record[f"hlc_mtr_tmp_{idx}"] = round(np.random.normal((62.0 + idx)*mult, 1.1), 1)

                elif mill == "Mill 5" and eq == "Mill Main Control":
                    for idx in range(1, 11):
                        record[f"m5_ocp_gb1_vib_{idx}"] = round(max(0, np.random.normal((3.0 + idx*0.05)*mult, 0.3)), 2)
                        record[f"m5_ocp_gb1_tmp_{idx}"] = round(np.random.normal((65.0 + idx*0.8)*mult, 1.0), 1)
                    for idx in range(1, 4):
                        record[f"m5_hlc_gb1_vib_{idx}"] = round(max(0, np.random.normal(2.6*mult, 0.2)), 2)
                    for idx in range(1, 7):
                        record[f"m5_hlc_gb2_tmp_{idx}"] = round(np.random.normal((68.0 + idx*0.5)*mult, 1.2), 1)
                    record["m5_hlc_mtr_tmp_1"] = round(np.random.normal(64.5*mult, 1.0), 1)
                    record["m5_hlc_mtr_cur_1"] = round(max(0, np.random.normal(185.0*mult, 4.0)), 1)

                elif mill == "Mill 4" and eq == "Mill Main Control":
                    for idx in range(1, 3):
                        record[f"m4_gb_vib_{idx}"] = round(max(0, np.random.normal((2.5 + idx*0.1)*mult, 0.3)), 2)
                    for idx in range(1, 4):
                        record[f"m4_gb_tmp_{idx}"] = round(np.random.normal((61.0 + idx*0.5)*mult, 1.0), 1)
                    for idx in range(1, 6):
                        record[f"m4_mtr_tmp_{idx}"] = round(np.random.normal((63.0 + idx*0.6)*mult, 1.1), 1)
                    record["m4_mtr_cur_1"] = round(max(0, np.random.normal(160.0*mult, 3.5)), 1)

                elif mill == "Mill 1 (White Cement)" and eq == "Mill Main Control":
                    for idx in range(1, 3):
                        record[f"m1_gb_vib_{idx}"] = round(max(0, np.random.normal((2.3 + idx*0.1)*mult, 0.25)), 2)
                    for idx in range(1, 4):
                        record[f"m1_gb_tmp_{idx}"] = round(np.random.normal((59.0 + idx*0.5)*mult, 0.9), 1)
                    record["m1_mtr_cur_1"] = round(max(0, np.random.normal(140.0*mult, 3.0)), 1)

                new_rows.append(record)
                self._evaluate_and_log_alert(record)
                
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
            if add_script_run_context:
                try:
                    add_script_run_context(thread)
                except Exception:
                    pass
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
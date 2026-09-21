import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from ml_engine import analyze_telemetry_diagnostics

PLANT_MILLS = ["Mill 1", "Mill 2", "Mill 4", "Mill 5", "Mill 6"]

EQUIPMENT_LIST = [
    "Dynamic Separator",
    "E5 & E8 Cement Pumps",
    "Separator Filter Fan",
    "Mill Main Control",
    "Main Filter Fan"
]

def generate_multi_mill_telemetry(num_records=30):
    """Generates initial historical telemetry for all plant mills."""
    now = datetime.now()
    data = []
    
    for mill in PLANT_MILLS:
        for eq in EQUIPMENT_LIST:
            for i in range(num_records):
                timestamp = now - timedelta(minutes=(num_records - i))
                vib_base = 2.5 if eq != "Mill Main Control" else 4.0
                temp_base = 55.0 if eq != "E5 & E8 Cement Pumps" else 62.0
                
                vib = np.random.normal(vib_base, 0.3)
                temp = np.random.normal(temp_base, 1.0)
                
                # Simulate an anomaly on Mill 6 (E5 & E8 Pumps) for demonstration
                if mill == "Mill 6" and eq == "E5 & E8 Cement Pumps" and i > 20:
                    vib += (i - 20) * 0.3
                    temp += (i - 20) * 1.2

                data.append({
                    "timestamp": timestamp,
                    "mill": mill,
                    "equipment": eq,
                    "vibration_mm_s": round(max(0, vib), 2),
                    "temperature_c": round(temp, 1)
                })
    return pd.DataFrame(data)

def fetch_multi_mill_live_reading():
    """Fetches a single live packet for all mills."""
    now = datetime.now()
    new_rows = []
    for mill in PLANT_MILLS:
        for eq in EQUIPMENT_LIST:
            vib_base = 2.5 if eq != "Mill Main Control" else 4.0
            temp_base = 55.0 if eq != "E5 & E8 Cement Pumps" else 62.0
            
            vib = np.random.normal(vib_base, 0.4)
            temp = np.random.normal(temp_base, 1.2)
            
            new_rows.append({
                "timestamp": now,
                "mill": mill,
                "equipment": eq,
                "vibration_mm_s": round(max(0, vib), 2),
                "temperature_c": round(temp, 1)
            })
    return pd.DataFrame(new_rows)

def check_sensor_health(last_timestamp, vib_value, temp_value, timeout_seconds=10):
    now = datetime.now()
    time_diff = (now - last_timestamp).total_seconds()
    if time_diff > timeout_seconds:
        return {"status": "OFFLINE", "message": f"No signal received for {int(time_diff)}s"}
    if temp_value < -20 or temp_value > 150 or vib_value < 0:
        return {"status": "SENSOR FAULT", "message": "Out-of-range sensor reading detected"}
    return {"status": "ONLINE", "message": f"Active (Last packet: {last_timestamp.strftime('%H:%M:%S')})"}

def simple_health_score(vib, temp):
    score = 100
    if vib > 4.5: score -= 30
    if vib > 7.0: score -= 40
    if temp > 75.0: score -= 20
    if temp > 90.0: score -= 100
    return max(0, score)

def evaluate_and_log_alerts(latest_reading, alerts_list):
    """Evaluates telemetry and tags alerts with the specific Mill name."""
    mill = latest_reading["mill"]
    eq = latest_reading["equipment"]
    timestamp = latest_reading["timestamp"]
    vib = latest_reading["vibration_mm_s"]
    temp = latest_reading["temperature_c"]
    
    diag = analyze_telemetry_diagnostics(mill, eq, vib, temp)
    
    active_alerts_for_eq = [
        a for a in alerts_list 
        if a["mill"] == mill and a["equipment"] == eq and "ACTIVE" in a["status"]
    ]
    
    if not active_alerts_for_eq and diag["severity"] != "NORMAL":
        alerts_list.insert(0, {
            "id": len(alerts_list) + 1,
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
    return alerts_list
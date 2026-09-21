import pandas as pd
import numpy as np
from datetime import datetime, timedelta
# Import directly from the standalone ML module
from ml_engine import predict_anomaly

EQUIPMENT_LIST = [
    "Dynamic Separator",
    "E5 & E8 Cement Pumps",
    "Separator Filter Fan",
    "Mill Main Control",
    "Main Filter Fan"
]

def generate_telemetry(num_records=50):
    now = datetime.now()
    data = []
    for eq in EQUIPMENT_LIST:
        for i in range(num_records):
            timestamp = now - timedelta(minutes=(num_records - i))
            vib_base = 2.5 if eq != "Mill Main Control" else 4.0
            temp_base = 55.0 if eq != "E5 & E8 Cement Pumps" else 62.0
            
            vib = np.random.normal(vib_base, 0.3)
            temp = np.random.normal(temp_base, 1.0)
            
            # Simulate anomaly on E5 & E8 Pumps to trigger demo alerts
            if eq == "E5 & E8 Cement Pumps" and i > 40:
                vib += (i - 40) * 0.4
                temp += (i - 40) * 1.5

            data.append({
                "timestamp": timestamp,
                "equipment": eq,
                "vibration_mm_s": round(max(0, vib), 2),
                "temperature_c": round(temp, 1)
            })
    return pd.DataFrame(data)

def fetch_single_live_reading():
    now = datetime.now()
    new_rows = []
    for eq in EQUIPMENT_LIST:
        vib_base = 2.5 if eq != "Mill Main Control" else 4.0
        temp_base = 55.0 if eq != "E5 & E8 Cement Pumps" else 62.0
        
        vib = np.random.normal(vib_base, 0.4)
        temp = np.random.normal(temp_base, 1.2)
        
        new_rows.append({
            "timestamp": now,
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
    """Evaluates telemetry using the isolated ML engine and threshold bounds."""
    eq = latest_reading["equipment"]
    timestamp = latest_reading["timestamp"]
    vib = latest_reading["vibration_mm_s"]
    temp = latest_reading["temperature_c"]
    
    # Predict directly via ml_engine
    is_ml_anomaly, anomaly_prob = predict_anomaly(vib, temp)
    
    active_alerts_for_eq = [
        a for a in alerts_list 
        if a["equipment"] == eq and "ACTIVE" in a["status"]
    ]
    
    if not active_alerts_for_eq:
        if is_ml_anomaly or vib > 4.5 or temp > 75.0:
            severity = "CRITICAL" if (vib > 7.0 or temp > 90.0) else "WARNING"
            alerts_list.insert(0, {
                "id": len(alerts_list) + 1,
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "equipment": eq,
                "severity": severity,
                "issue": f"ML Anomaly ({anomaly_prob}% Risk) | Vib: {vib} mm/s, Temp: {temp} °C",
                "status": f"ACTIVE - {severity}",
                "vibration_snapshot": vib,
                "temperature_snapshot": temp,
                "operator_notes": "Pending Maintenance"
            })
    return alerts_list
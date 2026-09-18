import pandas as pd
import numpy as np
from datetime import datetime, timedelta

EQUIPMENT_LIST = [
    "Dynamic Separator",
    "E5 & E8 Cement Pumps",
    "Separator Filter Fan",
    "Mill Main Control",
    "Main Filter Fan"
]

def generate_telemetry(num_records=50):
    """Generates initial historical data."""
    now = datetime.now()
    data = []
    
    for eq in EQUIPMENT_LIST:
        for i in range(num_records):
            timestamp = now - timedelta(minutes=(num_records - i))
            
            vib_base = 2.5 if eq != "Mill Main Control" else 4.0
            temp_base = 55.0 if eq != "E5 & E8 Cement Pumps" else 62.0
            
            vib = np.random.normal(vib_base, 0.3)
            temp = np.random.normal(temp_base, 1.0)
            
            data.append({
                "timestamp": timestamp,
                "equipment": eq,
                "vibration_mm_s": round(max(0, vib), 2),
                "temperature_c": round(temp, 1)
            })
            
    return pd.DataFrame(data)

def fetch_single_live_reading():
    """Simulates receiving a single live sensor packet (e.g., via OPC-UA, Modbus, or MQTT)."""
    now = datetime.now()
    new_rows = []
    
    for eq in EQUIPMENT_LIST:
        vib_base = 2.5 if eq != "Mill Main Control" else 4.0
        temp_base = 55.0 if eq != "E5 & E8 Cement Pumps" else 62.0
        
        # Add slight artificial variance
        vib = np.random.normal(vib_base, 0.4)
        temp = np.random.normal(temp_base, 1.2)
        
        new_rows.append({
            "timestamp": now,
            "equipment": eq,
            "vibration_mm_s": round(max(0, vib), 2),
            "temperature_c": round(temp, 1)
        })
        
    return pd.DataFrame(new_rows)

def simple_health_score(vib, temp):
    score = 100
    if vib > 4.5: score -= 30
    if vib > 7.0: score -= 40
    if temp > 75.0: score -= 20
    if temp > 90.0: score -= 100
    return max(0, score)

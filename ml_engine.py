import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# Model registry storing individual models: {(mill_name, equipment_name): IsolationForest}
_MODEL_REGISTRY = {}
_BUFFER_REGISTRY = {}

def _get_model_key(mill: str, equipment: str) -> tuple:
    return (mill.strip(), equipment.strip())

def init_equipment_model(mill: str, equipment: str):
    """Initializes and pre-trains an isolated ML model for a specific equipment unit."""
    key = _get_model_key(mill, equipment)
    
    if key not in _MODEL_REGISTRY:
        model = IsolationForest(contamination=0.05, random_state=42)
        
        # Define baseline characteristics per equipment type
        vib_base = 4.0 if equipment == "Mill Main Control" else 2.5
        temp_base = 62.0 if equipment == "E5 & E8 Cement Pumps" else 55.0
        
        initial_features = []
        for _ in range(300):
            vib = np.random.normal(vib_base, 0.4)
            temp = np.random.normal(temp_base, 1.5)
            initial_features.append([max(0, vib), temp])
        
        buffer_df = pd.DataFrame(initial_features, columns=["vibration_mm_s", "temperature_c"])
        model.fit(buffer_df)
        
        _MODEL_REGISTRY[key] = model
        _BUFFER_REGISTRY[key] = buffer_df

def analyze_telemetry_diagnostics(mill: str, equipment: str, vib: float, temp: float):
    """
    Evaluates telemetry against the SPECIFIC machine's dedicated ML model 
    and parameter threshold limits.
    """
    key = _get_model_key(mill, equipment)
    if key not in _MODEL_REGISTRY:
        init_equipment_model(mill, equipment)
        
    model = _MODEL_REGISTRY[key]
    comments = []
    severity = "NORMAL"
    
    # ---------------------------------------------------------------
    # 1. PARAMETER DIAGNOSTICS (ISO 10816 & Thermal Limits)
    # ---------------------------------------------------------------
    if vib > 7.0:
        comments.append(f"🔴 VIBRATION HIGH ({vib} mm/s): ISO Zone D breach on {mill} - {equipment}. Check shaft alignment & foundation bolts.")
        severity = "CRITICAL"
    elif vib > 4.5:
        comments.append(f"⚠️ VIBRATION RISING ({vib} mm/s): ISO Zone C warning. Monitor bearing race wear.")
        if severity != "CRITICAL": severity = "WARNING"
    elif vib < 0.5:
        comments.append(f"⚡ VIBRATION TOO LOW ({vib} mm/s): Low signal. Check sensor wiring or uncoupled shaft.")
        if severity != "CRITICAL": severity = "WARNING"
    else:
        comments.append(f"🟢 Vibration Normal ({vib} mm/s).")

    if temp > 90.0:
        comments.append(f"🔴 TEMPERATURE HIGH ({temp} °C): Overheating detected. Inspect lubrication flow immediately.")
        severity = "CRITICAL"
    elif temp > 75.0:
        comments.append(f"⚠️ TEMPERATURE RISING ({temp} °C): Running warm. Check grease levels & cooling fan.")
        if severity != "CRITICAL": severity = "WARNING"
    elif temp < 15.0:
        comments.append(f"⚡ TEMPERATURE TOO LOW ({temp} °C): Check RTD element seating.")
        if severity != "CRITICAL": severity = "WARNING"
    else:
        comments.append(f"🟢 Temperature Normal ({temp} °C).")

    # ---------------------------------------------------------------
    # 2. ISOLATED MACHINE LEARNING PREDICTION
    # ---------------------------------------------------------------
    features = pd.DataFrame([[vib, temp]], columns=["vibration_mm_s", "temperature_c"])
    prediction = model.predict(features)  # -1 = Anomaly, 1 = Normal
    score = model.decision_function(features)
    
    is_ml_anomaly = True if prediction[0] == -1 else False
    anomaly_probability = round(float(max(0, (0.2 - score[0]) * 100)), 1)
    
    if is_ml_anomaly:
        if temp > 65.0 and vib > 3.5:
            ml_comment = f"🔍 SPECIFIC ANOMALY on {mill} {equipment} ({anomaly_probability}% Risk): Concurrent heat & vibration rise. Suggested Action: Inspect bearing coupling."
        elif temp > 65.0 and vib <= 3.5:
            ml_comment = f"🔍 THERMAL PATTERN ({anomaly_probability}% Risk): High heat without matching vibration. Suggested Action: Check cooling fan airflow or grease level."
        elif vib > 3.5 and temp <= 65.0:
            ml_comment = f"🔍 MECHANICAL LOOSENESS ({anomaly_probability}% Risk): Elevated vibration without heat generation. Suggested Action: Check structural mounting bolts."
        else:
            ml_comment = f"🔍 ABNORMAL OPERATION PATTERN ({anomaly_probability}% Risk): Reading deviates from {mill} {equipment}'s baseline."
            
        comments.append(ml_comment)
        if severity == "NORMAL": severity = "WARNING"

    return {
        "severity": severity,
        "is_anomaly": is_ml_anomaly,
        "anomaly_prob": anomaly_probability,
        "diagnostic_comments": " | ".join(comments),
        "individual_comments": comments
    }

def retrain_specific_equipment_model(mill: str, equipment: str, feedback_samples: list, was_true_failure: bool = True):
    """
    Retrains ONLY the model assigned to the specified (mill, equipment) unit,
    preventing cross-contamination with other machines.
    """
    key = _get_model_key(mill, equipment)
    if key not in _MODEL_REGISTRY:
        init_equipment_model(mill, equipment)
        
    model = _MODEL_REGISTRY[key]
    buffer_df = _BUFFER_REGISTRY[key]
    
    new_rows = pd.DataFrame(feedback_samples, columns=["vibration_mm_s", "temperature_c"])
    
    if was_true_failure:
        # Heavily weight confirmed failures for this machine
        updated_buffer = pd.concat([buffer_df, new_rows, new_rows], ignore_index=True)
    else:
        # Add as acceptable baseline variation for this machine
        updated_buffer = pd.concat([buffer_df, new_rows], ignore_index=True)
        
    # Re-fit ONLY this specific model
    model.fit(updated_buffer)
    _MODEL_REGISTRY[key] = model
    _BUFFER_REGISTRY[key] = updated_buffer
    
    print(f"[ML REGISTRY] Retrained isolated model for {mill} -> {equipment}. Buffer size: {len(updated_buffer)} records.")
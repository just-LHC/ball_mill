import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# Global model state
_ml_model = None
_training_data_buffer = None

def init_ml_engine():
    """Initializes and pre-trains the model on baseline operating data."""
    global _ml_model, _training_data_buffer
    
    if _ml_model is None:
        _ml_model = IsolationForest(contamination=0.05, random_state=42)
        
        # Baseline normal dataset
        initial_features = []
        for _ in range(300):
            vib = np.random.normal(2.5, 0.4)
            temp = np.random.normal(58.0, 1.5)
            initial_features.append([vib, temp])
        
        _training_data_buffer = pd.DataFrame(initial_features, columns=["vibration_mm_s", "temperature_c"])
        _ml_model.fit(_training_data_buffer)

# Initialize on module load
init_ml_engine()

def analyze_telemetry_diagnostics(vib: float, temp: float):
    """
    Evaluates vibration and temperature parameters to generate plain-language,
    operator-friendly diagnostic comments and action recommendations.
    """
    comments = []
    severity = "NORMAL"
    
    # ---------------------------------------------------------------
    # 1. VIBRATION DIAGNOSTICS (Operator Terms)
    # ---------------------------------------------------------------
    if vib > 7.0:
        comments.append(f"🔴 VIBRATION HIGH ({vib} mm/s): Excessive mechanical shaking. Check for severe imbalance, loose foundation bolts, or advanced shaft misalignment.")
        severity = "CRITICAL"
    elif vib > 4.5:
        comments.append(f"⚠️ VIBRATION RISING ({vib} mm/s): Shaking above normal. Inspect drive alignment, check for unbalance, or monitor for early bearing race wear.")
        if severity != "CRITICAL": severity = "WARNING"
    elif vib < 0.5:
        comments.append(f"⚡ VIBRATION TOO LOW ({vib} mm/s): Abnormally low signal. Verify if machine is uncoupled, idling, or if sensor cable is damaged.")
        if severity != "CRITICAL": severity = "WARNING"
    else:
        comments.append(f"🟢 Vibration Normal ({vib} mm/s): Running smoothly within safe limit.")

    # ---------------------------------------------------------------
    # 2. TEMPERATURE DIAGNOSTICS (Operator Terms)
    # ---------------------------------------------------------------
    if temp > 90.0:
        comments.append(f"🔴 TEMPERATURE HIGH ({temp} °C): Machinery overheating. Immediate risk of bearing seizure or oil breakdown.")
        severity = "CRITICAL"
    elif temp > 75.0:
        comments.append(f"⚠️ TEMPERATURE RISING ({temp} °C): Bearing/Housing running warm. Inspect cooling fans, check grease/oil level, or check for tight tolerances.")
        if severity != "CRITICAL": severity = "WARNING"
    elif temp < 15.0:
        comments.append(f"⚡ TEMPERATURE TOO LOW ({temp} °C): Cold reading. Verify sensor element seating or check cold start conditions.")
        if severity != "CRITICAL": severity = "WARNING"
    else:
        comments.append(f"🟢 Temperature Normal ({temp} °C): Thermal state stable.")

    # ---------------------------------------------------------------
    # 3. MACHINE LEARNING PATTERN CHECK (Translated for Operators)
    # ---------------------------------------------------------------
    features = pd.DataFrame([[vib, temp]], columns=["vibration_mm_s", "temperature_c"])
    prediction = _ml_model.predict(features)  # -1 = Anomaly, 1 = Normal
    score = _ml_model.decision_function(features)
    
    is_ml_anomaly = True if prediction[0] == -1 else False
    anomaly_probability = round(float(max(0, (0.2 - score[0]) * 100)), 1)
    
    if is_ml_anomaly:
        # Translate the combined (vib + temp) state into clear physical meaning
        if temp > 65.0 and vib > 3.5:
            ml_comment = f"🔍 EARLY WEAR PATTERN DETECTED ({anomaly_probability}% Risk): Both temperature and vibration are creeping up together. Suggested Action: Inspect bearing lubrication and check drive coupling."
        elif temp > 65.0 and vib <= 3.5:
            ml_comment = f"🔍 UNUSUAL THERMAL PATTERN ({anomaly_probability}% Risk): High heat without matching vibration. Suggested Action: Check cooling fan airflow, grease levels, or motor electrical current."
        elif vib > 3.5 and temp <= 65.0:
            ml_comment = f"🔍 UNUSUAL MECHANICAL PATTERN ({anomaly_probability}% Risk): Elevated vibration without heat generation. Suggested Action: Check for mechanical looseness, structural mounting bolts, or belt tension."
        else:
            ml_comment = f"🔍 ABNORMAL OPERATION PATTERN ({anomaly_probability}% Risk): Sensor combination differs from normal running baseline. Suggested Action: Perform routine physical inspection on next round."
            
        comments.append(ml_comment)
        if severity == "NORMAL": severity = "WARNING"

    return {
        "severity": severity,
        "is_anomaly": is_ml_anomaly,
        "anomaly_prob": anomaly_probability,
        "diagnostic_comments": " | ".join(comments),
        "individual_comments": comments
    }

def retrain_with_operator_feedback(feedback_samples: list, was_true_failure: bool = True):
    """Retrains the ML model using ground-truth operator servicing feedback."""
    global _ml_model, _training_data_buffer
    
    new_rows = pd.DataFrame(feedback_samples, columns=["vibration_mm_s", "temperature_c"])
    
    if was_true_failure:
        _training_data_buffer = pd.concat([_training_data_buffer, new_rows, new_rows], ignore_index=True)
    else:
        _training_data_buffer = pd.concat([_training_data_buffer, new_rows], ignore_index=True)
        
    _ml_model.fit(_training_data_buffer)
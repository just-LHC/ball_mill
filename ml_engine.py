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
        
        # Generate initial baseline training dataset (Normal operational baseline)
        initial_features = []
        for _ in range(300):
            vib = np.random.normal(2.5, 0.4)
            temp = np.random.normal(58.0, 1.5)
            initial_features.append([vib, temp])
        
        _training_data_buffer = pd.DataFrame(initial_features, columns=["vibration_mm_s", "temperature_c"])
        _ml_model.fit(_training_data_buffer)
        print("ML Engine Initialized and pre-trained successfully.")

# Ensure model initializes on import
init_ml_engine()

def predict_anomaly(vib: float, temp: float):
    """
    Predicts whether incoming telemetry is an anomaly.
    This function will be called directly by your PLC driver or webhook ingestion layer.
    """
    features = np.array([[vib, temp]])
    prediction = _ml_model.predict(features)  # -1 = Anomaly, 1 = Normal
    score = _ml_model.decision_function(features)  # Lower score = higher risk
    
    is_anomaly = True if prediction[0] == -1 else False
    anomaly_probability = round(float(max(0, (0.2 - score[0]) * 100)), 1)
    
    return is_anomaly, anomaly_probability

def retrain_with_operator_feedback(feedback_samples: list, was_true_failure: bool = True):
    """
    Retrains the Isolation Forest model dynamically based on operator feedback.
    `feedback_samples` should be a list of lists: [[vib, temp]]
    """
    global _ml_model, _training_data_buffer
    
    new_rows = pd.DataFrame(feedback_samples, columns=["vibration_mm_s", "temperature_c"])
    
    if was_true_failure:
        # Weight confirmed failures higher so the model learns the failure profile rapidly
        _training_data_buffer = pd.concat([_training_data_buffer, new_rows, new_rows], ignore_index=True)
    else:
        # If false alarm, register as normal operating baseline
        _training_data_buffer = pd.concat([_training_data_buffer, new_rows], ignore_index=True)
        
    _ml_model.fit(_training_data_buffer)
    print(f"ML Model retrained. Buffer size: {len(_training_data_buffer)} records.")
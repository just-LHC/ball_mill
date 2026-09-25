import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.ensemble import IsolationForest

# Import central database logger functions
try:
    from db_engine import log_alert_to_db, init_alert_db_table
    init_alert_db_table()
except Exception:
    pass

# Retrieve Email Secrets safely
SMTP_SERVER = st.secrets.get("SMTP_SERVER", os.getenv("SMTP_SERVER", "smtp.gmail.com"))
SMTP_PORT = int(st.secrets.get("SMTP_PORT", os.getenv("SMTP_PORT", 465)))
SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", os.getenv("SENDER_EMAIL", ""))
SENDER_PASSWORD = st.secrets.get("SENDER_PASSWORD", os.getenv("SENDER_PASSWORD", ""))
MAINTENANCE_LEADS = st.secrets.get("MAINTENANCE_LEADS", os.getenv("MAINTENANCE_LEADS", ""))

# Model registry storing individual models: {(mill_name, equipment_name): IsolationForest}
_MODEL_REGISTRY = {}
_BUFFER_REGISTRY = {}

def send_critical_alert_email(mill: str, equipment: str, vibration: float = 0.0, temperature: float = 0.0, individual_comments: list = None, sensor_snapshots: dict = None):
    """Sends an automated HTML alert report to Maintenance Leads for CRITICAL ML predictions and sensor breaches."""
    sender_email = st.secrets.get("SENDER_EMAIL", os.getenv("SENDER_EMAIL", SENDER_EMAIL))
    sender_password = st.secrets.get("SENDER_PASSWORD", os.getenv("SENDER_PASSWORD", SENDER_PASSWORD))
    maintenance_leads = st.secrets.get("MAINTENANCE_LEADS", os.getenv("MAINTENANCE_LEADS", MAINTENANCE_LEADS))
    smtp_server = st.secrets.get("SMTP_SERVER", os.getenv("SMTP_SERVER", SMTP_SERVER))
    smtp_port = int(st.secrets.get("SMTP_PORT", os.getenv("SMTP_PORT", SMTP_PORT)))

    if not sender_email or not sender_password or not maintenance_leads:
        return

    recipients = [email.strip() for email in maintenance_leads.split(",") if email.strip()]
    if not recipients:
        return

    subject = f"🚨 [CRITICAL ML ALERT] {mill} - {equipment} Anomaly Detected"
    
    if individual_comments is None:
        individual_comments = []

    comments_html = "".join([f"" for c in individual_comments])
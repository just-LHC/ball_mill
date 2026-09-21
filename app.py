from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from mock_data import (
    generate_telemetry, 
    fetch_single_live_reading, 
    simple_health_score, 
    check_sensor_health, 
    evaluate_and_log_alerts,
    EQUIPMENT_LIST
)
# Direct import from standalone ML module
from ml_engine import retrain_with_operator_feedback

# Page configuration
st.set_page_config(page_title="Mill 6 - Live PdM Dashboard", layout="wide")

# Initialize Session States
if "df" not in st.session_state:
    st.session_state.df = generate_telemetry(50)

if "alerts_log" not in st.session_state:
    st.session_state.alerts_log = []

# Sidebar Navigation
st.sidebar.title("Mill 6 Monitoring")
page = st.sidebar.radio("Navigate View Level", ["Overview (Mill 6)", "Equipment Drill-Down", "Maintenance Alert Log"])

# Live toggle switch
st.sidebar.markdown("---")
streaming_active = st.sidebar.toggle("Live Telemetry Stream", value=True)


# -------------------------------------------------------------------
# LIVE STREAMING FRAGMENT
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_dashboard(selected_page):
    if streaming_active:
        new_packet = fetch_single_live_reading()
        st.session_state.df = pd.concat([st.session_state.df, new_packet], ignore_index=True)
        st.session_state.df = st.session_state.df.tail(1000)
        
        # Check new packet for alerts
        for _, row in new_packet.iterrows():
            st.session_state.alerts_log = evaluate_and_log_alerts(row, st.session_state.alerts_log)

    current_df = st.session_state.df

    # ---------------------------------------------------------------
    # PAGE 1: OVERVIEW VIEW
    # ---------------------------------------------------------------
    if selected_page == "Overview (Mill 6)":
        st.title("Mill 6 - High Level Overview")
        
        active_count = len([a for a in st.session_state.alerts_log if "ACTIVE" in a["status"]])
        if active_count > 0:
            st.error(f"⚠️ **Attention Required:** There are {active_count} active unserviced equipment alerts.")
        else:
            st.success("🟢 All equipment operating within normal parameters. No active alerts.")

        cols = st.columns(len(EQUIPMENT_LIST))
        
        for i, eq in enumerate(EQUIPMENT_LIST):
            eq_df = current_df[current_df["equipment"] == eq]
            latest = eq_df.iloc[-1]
            health = simple_health_score(latest["vibration_mm_s"], latest["temperature_c"])
            
            with cols[i]:
                st.subheader(eq)
                if health > 80:
                    st.success(f"Health: {health}%")
                elif health > 50:
                    st.warning(f"Health: {health}%")
                else:
                    st.error(f"Health: {health}%")
                    
                st.metric("Vibration", f"{latest['vibration_mm_s']} mm/s")
                st.metric("Temperature", f"{latest['temperature_c']} °C")

    # ---------------------------------------------------------------
    # PAGE 2: EQUIPMENT DRILL-DOWN VIEW
    # ---------------------------------------------------------------
    elif selected_page == "Equipment Drill-Down":
        st.title("Equipment Detailed View")
        
        selected_eq = st.selectbox("Select Equipment", EQUIPMENT_LIST)
        eq_data = current_df[current_df["equipment"] == selected_eq]
        latest = eq_data.iloc[-1]
        
        sensor_diagnostic = check_sensor_health(latest["timestamp"], latest["vibration_mm_s"], latest["temperature_c"])
        
        st.markdown("##### 🔌 Field Instrumentation Diagnostics")
        s_col1, s_col2, s_col3 = st.columns([1, 1, 2])
        
        with s_col1:
            if sensor_diagnostic["status"] == "ONLINE":
                st.success("🟢 Vibration Sensor: ONLINE")
            elif sensor_diagnostic["status"] == "SENSOR FAULT":
                st.warning("⚠️ Vibration Sensor: FAULT")
            else:
                st.error("🔴 Vibration Sensor: OFFLINE")
                
        with s_col2:
            if sensor_diagnostic["status"] == "ONLINE":
                st.success("🟢 Temperature Sensor: ONLINE")
            elif sensor_diagnostic["status"] == "SENSOR FAULT":
                st.warning("⚠️ Temperature Sensor: FAULT")
            else:
                st.error("🔴 Temperature Sensor: OFFLINE")
                
        with s_col3:
            st.info(f"⏱️ **Last Telemetry Handshake:** {sensor_diagnostic['message']}")

        st.markdown("---")

        health = simple_health_score(latest["vibration_mm_s"], latest["temperature_c"])
        m1, m2, m3 = st.columns(3)
        m1.metric("Overall Health Index", f"{health}%")
        m2.metric("Latest Vibration", f"{latest['vibration_mm_s']} mm/s")
        m3.metric("Latest Temperature", f"{latest['temperature_c']} °C")
        
        st.markdown("---")
        st.subheader(f"Real-Time Telemetry Trends: {selected_eq}")

        VIB_WARN, VIB_CRIT = 4.5, 7.0
        TEMP_WARN, TEMP_CRIT = 75.0, 90.0
        COLOR_VIB, COLOR_TEMP = "#00D2FF", "#FF8C00"
        COLOR_WARN, COLOR_CRIT, GRID_COLOR = "#F1C40F", "#E74C3C", "#2A2D34"

        # Vibration Graph
        fig_vib = go.Figure()
        fig_vib.add_trace(go.Scatter(x=eq_data["timestamp"], y=eq_data["vibration_mm_s"], name="Vibration (mm/s)", line=dict(color=COLOR_VIB, width=2.5)))
        fig_vib.add_hline(y=VIB_WARN, line_dash="dash", line_color=COLOR_WARN, line_width=1.5, annotation_text="Warning (4.5 mm/s)", annotation_position="top right", annotation_font_color=COLOR_WARN)
        fig_vib.add_hline(y=VIB_CRIT, line_dash="dash", line_color=COLOR_CRIT, line_width=1.5, annotation_text="Critical (7.0 mm/s)", annotation_position="top right", annotation_font_color=COLOR_CRIT)
        fig_vib.update_layout(height=300, template="plotly_dark", xaxis=dict(title="Time", showgrid=True, gridcolor=GRID_COLOR), yaxis=dict(title=dict(text="Vibration (mm/s RMS)", font=dict(color=COLOR_VIB, size=13)), tickfont=dict(color=COLOR_VIB), showgrid=True, gridcolor=GRID_COLOR), margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_vib, use_container_width=True)

        # Temperature Graph
        fig_temp = go.Figure()
        fig_temp.add_trace(go.Scatter(x=eq_data["timestamp"], y=eq_data["temperature_c"], name="Temperature (°C)", line=dict(color=COLOR_TEMP, width=2.5)))
        fig_temp.add_hline(y=TEMP_WARN, line_dash="dash", line_color=COLOR_WARN, line_width=1.5, annotation_text="Warning (75.0 °C)", annotation_position="top right", annotation_font_color=COLOR_WARN)
        fig_temp.add_hline(y=TEMP_CRIT, line_dash="dash", line_color=COLOR_CRIT, line_width=1.5, annotation_text="Critical (90.0 °C)", annotation_position="top right", annotation_font_color=COLOR_CRIT)
        fig_temp.update_layout(height=300, template="plotly_dark", xaxis=dict(title="Time", showgrid=True, gridcolor=GRID_COLOR), yaxis=dict(title=dict(text="Temperature (°C)", font=dict(color=COLOR_TEMP, size=13)), tickfont=dict(color=COLOR_TEMP), showgrid=True, gridcolor=GRID_COLOR), margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_temp, use_container_width=True)

    # ---------------------------------------------------------------
    # PAGE 3: OPERATOR MAINTENANCE ALERT LOG
    # ---------------------------------------------------------------
    elif selected_page == "Maintenance Alert Log":
        st.title("🛠️ Maintenance Alert Log & Active Model Learning")
        st.write("Review active machinery alerts. Servicing an alert automatically feeds diagnostic ground-truth back into the ML model.")
        
        if not st.session_state.alerts_log:
            st.info("No system alerts recorded yet.")
        else:
            alerts_df = pd.DataFrame(st.session_state.alerts_log)
            st.dataframe(
                alerts_df[["id", "timestamp", "equipment", "severity", "issue", "status", "operator_notes"]],
                use_container_width=True,
                hide_index=True
            )
            
            st.markdown("---")
            st.subheader("Update Alert Status & Retrain Model")
            
            active_alerts = [a for a in st.session_state.alerts_log if "ACTIVE" in a["status"]]
            
            if active_alerts:
                alert_options = {f"Alert #{a['id']} - {a['equipment']} ({a['timestamp']})": a['id'] for a in active_alerts}
                selected_alert_str = st.selectbox("Select Alert to Clear:", list(alert_options.keys()))
                selected_id = alert_options[selected_alert_str]
                
                with st.form("service_form"):
                    operator_name = st.text_input("Operator / Maintenance Technician Name:")
                    alert_feedback_type = st.radio(
                        "Diagnostic Feedback for Model Retraining:",
                        ["Genuine Issue (Confirmed Equipment Failure / Wear)", "False Alarm (Normal Operational Spike)"]
                    )
                    action_taken = st.text_area("Maintenance Action Taken (e.g., Replaced bearing, adjusted alignment):")
                    
                    submit = st.form_submit_button("Submit & Retrain Predictive Model")
                    
                    if submit:
                        if operator_name and action_taken:
                            for alert in st.session_state.alerts_log:
                                if alert["id"] == selected_id:
                                    serviced_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    was_true_failure = True if "Genuine Issue" in alert_feedback_type else False
                                    
                                    alert["status"] = "SERVICED / CLOSED"
                                    alert["operator_notes"] = f"Serviced by {operator_name} at {serviced_time}. Action: {action_taken} | Verified: {alert_feedback_type}"
                                    
                                    # Call standalone ML engine for dynamic retraining
                                    feedback_sample = [[alert["vibration_snapshot"], alert["temperature_snapshot"]]]
                                    retrain_with_operator_feedback(feedback_sample, was_true_failure=was_true_failure)
                                    
                            st.success(f"Alert #{selected_id} updated and ML model retrained!")
                            st.rerun()
                        else:
                            st.error("Please provide your name and maintenance action taken.")
            else:
                st.success("🎉 All logged alerts have been serviced and closed.")

# Render Dashboard
render_live_dashboard(page)
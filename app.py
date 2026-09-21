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
from ml_engine import retrain_with_operator_feedback

# Page configuration
st.set_page_config(page_title="Mill 6 - Live PdM Dashboard", layout="wide")

# -------------------------------------------------------------------
# EQUIPMENT DESCRIPTIONS & SENSOR MOUNT LOCATION METADATA
# -------------------------------------------------------------------
EQUIPMENT_PROFILES = {
    "Dynamic Separator": {
        "description": "High-efficiency third-generation air separator that controls cement powder fineness by separating coarse grit from fine product using adjustable rotor speed and air balance.",
        "vibration_sensor_loc": "Mounted horizontally on the top rotor bearing housing (Drive end).",
        "temp_sensor_loc": "Embedded in the main upper bearing grease chamber.",
        "image_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=800&q=80"
    },
    "E5 & E8 Cement Pumps": {
        "description": "Heavy-duty pneumatic screw pumps (E5 and E8 operating as a dual unit) used to transport ground cement powder from Mill 6 discharge directly to storage silos.",
        "vibration_sensor_loc": "Tri-axial accelerometer stud-mounted on the drive-end bearing bracket.",
        "temp_sensor_loc": "PT100 RTD probe inserted into the drive-side bearing oil sump.",
        "image_url": "https://images.unsplash.com/photo-1581092335397-9583fe92d232?auto=format&fit=crop&w=800&q=80"
    },
    "Separator Filter Fan": {
        "description": "High-volume process extraction fan responsible for maintaining negative pressure and conveying fine material through the separator bag filter housing.",
        "vibration_sensor_loc": "Radial vibration pickup installed on the fan shaft pillow block bearing.",
        "temp_sensor_loc": "Contact thermal probe attached directly to the fan bearing casing.",
        "image_url": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=800&q=80"
    },
    "Mill Main Control": {
        "description": "Central drive assembly governing Mill 6 rotation, including the main high-voltage motor, reduction gearbox, main pinion, and high-pressure trunnion lubrication skid.",
        "vibration_sensor_loc": "Dual accelerometers on main gearbox input shaft and pinion housing.",
        "temp_sensor_loc": "Thermo-wells in the main trunnion oil supply line and gearbox sump.",
        "image_url": "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=800&q=80"
    },
    "Main Filter Fan": {
        "description": "Primary plant exhaust fan pulling de-dusted process air through the main baghouse filter to control fugitive emissions and maintain thermal balance inside Mill 6.",
        "vibration_sensor_loc": "Magnetic mount transducer on non-drive end motor bearing.",
        "temp_sensor_loc": "Surface-mounted RTD on the main motor winding housing.",
        "image_url": "https://images.unsplash.com/photo-1581092580497-e0d23cbdf1dc?auto=format&fit=crop&w=800&q=80"
    }
}

# Initialize Session States
if "df" not in st.session_state:
    st.session_state.df = generate_telemetry(50)

if "alerts_log" not in st.session_state:
    st.session_state.alerts_log = []

# Sidebar Navigation
st.sidebar.title("Mill 6 PdM Suite")
page = st.sidebar.radio(
    "Select View Level", 
    ["Overview (Mill 6)", "Equipment Drill-Down", "Maintenance Alert Log"]
)

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
        
        for _, row in new_packet.iterrows():
            st.session_state.alerts_log = evaluate_and_log_alerts(row, st.session_state.alerts_log)

    current_df = st.session_state.df

    # ===============================================================
    # PAGE 1: OVERVIEW VIEW
    # ===============================================================
    if selected_page == "Overview (Mill 6)":
        st.title("🏭 Mill 6 - High Level Plant Overview")
        st.caption("Real-time operational status across all primary units.")
        
        active_critical = len([a for a in st.session_state.alerts_log if "CRITICAL" in a["status"]])
        active_warning = len([a for a in st.session_state.alerts_log if "WARNING" in a["status"]])
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Monitored Equipment", f"{len(EQUIPMENT_LIST)} Units")
        kpi2.metric("Active Critical Alerts", f"{active_critical}", delta_color="inverse")
        kpi3.metric("Active Warnings", f"{active_warning}", delta_color="inverse")
        kpi4.metric("Telemetry Stream Status", "ONLINE 🟢" if streaming_active else "PAUSED ⏸️")
        
        st.markdown("---")
        
        if active_critical > 0 or active_warning > 0:
            st.error(f"⚠️ **Attention Required:** {active_critical} Critical and {active_warning} Warning alerts pending operator maintenance.")
        else:
            st.success("🟢 All Mill 6 equipment operating within normal parameters. No active alerts.")

        st.subheader("Equipment Unit Health Cards")
        cols = st.columns(len(EQUIPMENT_LIST))
        
        for i, eq in enumerate(EQUIPMENT_LIST):
            eq_df = current_df[current_df["equipment"] == eq]
            latest = eq_df.iloc[-1]
            health = simple_health_score(latest["vibration_mm_s"], latest["temperature_c"])
            
            with cols[i]:
                st.markdown(f"### {eq}")
                if health > 80:
                    st.success(f"Health: {health}%")
                elif health > 50:
                    st.warning(f"Health: {health}%")
                else:
                    st.error(f"Health: {health}%")
                    
                st.metric("Vibration", f"{latest['vibration_mm_s']} mm/s")
                st.metric("Temperature", f"{latest['temperature_c']} °C")
                st.caption(f"Last update: {latest['timestamp'].strftime('%H:%M:%S')}")

    # ===============================================================
    # PAGE 2: EQUIPMENT DRILL-DOWN VIEW (WITH PHOTOS & SENSOR POSITIONS)
    # ===============================================================
    elif selected_page == "Equipment Drill-Down":
        st.title("🔬 Equipment Detailed View & Physical Layout")
        
        selected_eq = st.selectbox("Select Equipment to Inspect:", EQUIPMENT_LIST)
        eq_data = current_df[current_df["equipment"] == selected_eq]
        latest = eq_data.iloc[-1]
        profile = EQUIPMENT_PROFILES.get(selected_eq, {})
        
        # -----------------------------------------------------------
        # PHYSICAL EQUIPMENT DESCRIPTION & SENSOR LOCATION MAP
        # -----------------------------------------------------------
        st.markdown("---")
        info_col, img_col = st.columns([3, 2])
        
        with info_col:
            st.subheader(f"⚙️ Subsystem Profile: {selected_eq}")
            st.write(f"**Function & Description:** {profile.get('description', 'N/A')}")
            
            st.markdown("##### 📍 Sensor Mounting Locations:")
            st.write(f"• **Vibration Sensor (RMS):** {profile.get('vibration_sensor_loc', 'N/A')}")
            st.write(f"• **Temperature Sensor (°C):** {profile.get('temp_sensor_loc', 'N/A')}")
            
        with img_col:
            st.image(
                profile.get("image_url"), 
                caption=f"Physical Layout & Sensor Mounting: {selected_eq}", 
                width="stretch"
            )

        st.markdown("---")

        # 1. Field Instrumentation Health
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

        # 2. Key Metrics
        health = simple_health_score(latest["vibration_mm_s"], latest["temperature_c"])
        m1, m2, m3 = st.columns(3)
        m1.metric("Overall Health Index", f"{health}%")
        m2.metric("Latest Vibration", f"{latest['vibration_mm_s']} mm/s")
        m3.metric("Latest Temperature", f"{latest['temperature_c']} °C")
        
        st.markdown("---")
        st.subheader(f"Real-Time Telemetry Trends: {selected_eq}")

        # Industrial Palette & Thresholds
        VIB_WARN, VIB_CRIT = 4.5, 7.0
        TEMP_WARN, TEMP_CRIT = 75.0, 90.0
        COLOR_VIB, COLOR_TEMP = "#00D2FF", "#FF8C00"
        COLOR_WARN, COLOR_CRIT, GRID_COLOR = "#F1C40F", "#E74C3C", "#2A2D34"

        # Vibration Graph
        fig_vib = go.Figure()
        fig_vib.add_trace(go.Scatter(
            x=eq_data["timestamp"], 
            y=eq_data["vibration_mm_s"], 
            name="Vibration (mm/s)", 
            line=dict(color=COLOR_VIB, width=2.5)
        ))
        fig_vib.add_hline(y=VIB_WARN, line_dash="dash", line_color=COLOR_WARN, line_width=1.5, annotation_text="Warning (4.5 mm/s)", annotation_position="top right", annotation_font_color=COLOR_WARN)
        fig_vib.add_hline(y=VIB_CRIT, line_dash="dash", line_color=COLOR_CRIT, line_width=1.5, annotation_text="Critical (7.0 mm/s)", annotation_position="top right", annotation_font_color=COLOR_CRIT)
        fig_vib.update_layout(
            height=300, template="plotly_dark", 
            xaxis=dict(title="Time", showgrid=True, gridcolor=GRID_COLOR), 
            yaxis=dict(title=dict(text="Vibration (mm/s RMS)", font=dict(color=COLOR_VIB, size=13)), tickfont=dict(color=COLOR_VIB), showgrid=True, gridcolor=GRID_COLOR), 
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_vib, width="stretch")

        # Temperature Graph
        fig_temp = go.Figure()
        fig_temp.add_trace(go.Scatter(
            x=eq_data["timestamp"], 
            y=eq_data["temperature_c"], 
            name="Temperature (°C)", 
            line=dict(color=COLOR_TEMP, width=2.5)
        ))
        fig_temp.add_hline(y=TEMP_WARN, line_dash="dash", line_color=COLOR_WARN, line_width=1.5, annotation_text="Warning (75.0 °C)", annotation_position="top right", annotation_font_color=COLOR_WARN)
        fig_temp.add_hline(y=TEMP_CRIT, line_dash="dash", line_color=COLOR_CRIT, line_width=1.5, annotation_text="Critical (90.0 °C)", annotation_position="top right", annotation_font_color=COLOR_CRIT)
        fig_temp.update_layout(
            height=300, template="plotly_dark", 
            xaxis=dict(title="Time", showgrid=True, gridcolor=GRID_COLOR), 
            yaxis=dict(title=dict(text="Temperature (°C)", font=dict(color=COLOR_TEMP, size=13)), tickfont=dict(color=COLOR_TEMP), showgrid=True, gridcolor=GRID_COLOR), 
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_temp, width="stretch")

        # Interactive Fault Injector
        with st.expander("🧪 Test Bench: Inject Simulated Equipment Fault"):
            st.write("Manually inject an artificial anomaly to test the ML detector and alert logging pipeline.")
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                inject_vib = st.slider("Inject Vibration (mm/s)", 0.0, 12.0, 5.5)
            with f_col2:
                inject_temp = st.slider("Inject Temperature (°C)", 20.0, 110.0, 80.0)
            with f_col3:
                st.write("")
                st.write("")
                if st.button("Inject Fault Packet"):
                    fault_packet = pd.DataFrame([{
                        "timestamp": datetime.now(),
                        "equipment": selected_eq,
                        "vibration_mm_s": inject_vib,
                        "temperature_c": inject_temp
                    }])
                    st.session_state.df = pd.concat([st.session_state.df, fault_packet], ignore_index=True)
                    st.session_state.alerts_log = evaluate_and_log_alerts(fault_packet.iloc[0], st.session_state.alerts_log)
                    st.success(f"Injected fault into {selected_eq}! Check the Maintenance Alert Log.")
                    st.rerun()

    # ===============================================================
    # PAGE 3: OPERATOR MAINTENANCE ALERT LOG (With Auto-Clearing Form)
    # ===============================================================
    elif selected_page == "Maintenance Alert Log":
        st.title("🛠️ Maintenance Alert Log & Diagnostic Servicing")
        st.write("Review active machinery alerts with operator guidance. Resolving an issue feeds diagnostic feedback back into the ML model.")
        
        if not st.session_state.alerts_log:
            st.info("No system alerts recorded yet. Machinery operating normally.")
        else:
            alerts_df = pd.DataFrame(st.session_state.alerts_log)
            st.dataframe(
                alerts_df[["id", "timestamp", "equipment", "severity", "issue", "status", "operator_notes"]],
                width="stretch",
                hide_index=True
            )
            
            st.markdown("---")
            st.subheader("Update Alert Status & Retrain Model")
            
            # Filter only active, unserviced alerts
            active_alerts = [a for a in st.session_state.alerts_log if "ACTIVE" in a["status"]]
            
            if active_alerts:
                alert_options = {f"Alert #{a['id']} - {a['equipment']} ({a['timestamp']})": a['id'] for a in active_alerts}
                selected_alert_str = st.selectbox("Select Alert to Resolve:", list(alert_options.keys()))
                selected_id = alert_options[selected_alert_str]
                
                selected_alert_rec = next(a for a in st.session_state.alerts_log if a["id"] == selected_id)
                
                st.markdown("##### 📋 Diagnostic Breakdown for Selected Alert:")
                if "individual_comments" in selected_alert_rec:
                    for comment in selected_alert_rec["individual_comments"]:
                        if "🔴" in comment or "CRITICAL" in comment:
                            st.error(f"• {comment}")
                        elif "⚠️" in comment or "⚡" in comment or "🔍" in comment:
                            st.warning(f"• {comment}")
                        else:
                            st.info(f"• {comment}")

                # UNIQUE FORM KEY: Keyed directly to selected_id to force form reset on change/submit
                with st.form(key=f"service_form_alert_{selected_id}"):
                    operator_name = st.text_input("Operator / Maintenance Technician Name:", key=f"op_name_{selected_id}")
                    alert_feedback_type = st.radio(
                        "Diagnostic Feedback for Model Retraining:",
                        ["Genuine Issue (Confirmed Equipment Failure / Wear)", "False Alarm (Normal Operational Spike)"],
                        key=f"fb_type_{selected_id}"
                    )
                    action_taken = st.text_area("Maintenance Action Taken (e.g., Replaced drive bearing, adjusted alignment):", key=f"act_taken_{selected_id}")
                    
                    submit = st.form_submit_button("Submit & Retrain Predictive Model")
                    
                    if submit:
                        if operator_name.strip() and action_taken.strip():
                            for alert in st.session_state.alerts_log:
                                if alert["id"] == selected_id:
                                    serviced_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    was_true_failure = True if "Genuine Issue" in alert_feedback_type else False
                                    
                                    # 1. Update Alert Record Status
                                    alert["status"] = "SERVICED / CLOSED"
                                    alert["operator_notes"] = f"Serviced by {operator_name} at {serviced_time}. Action: {action_taken} | Verified: {alert_feedback_type}"
                                    
                                    # 2. Retrain Model Once
                                    feedback_sample = [[alert["vibration_snapshot"], alert["temperature_snapshot"]]]
                                    retrain_with_operator_feedback(feedback_sample, was_true_failure=was_true_failure)
                                    
                            st.success(f"Alert #{selected_id} successfully closed and model retrained!")
                            
                            # 3. Force instant UI state reload so closed alert disappears from selection dropdown
                            st.rerun()
                        else:
                            st.error("Please provide both your name and maintenance action taken before submitting.")
            else:
                st.success("🎉 All logged alerts have been serviced and closed.")

# Render Dashboard
render_live_dashboard(page)
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from mock_data import (
    generate_multi_mill_telemetry, 
    fetch_multi_mill_live_reading, 
    simple_health_score, 
    check_sensor_health, 
    evaluate_and_log_alerts,
    PLANT_MILLS,
    EQUIPMENT_LIST
)
# Import isolated equipment-specific retraining function
from ml_engine import retrain_specific_equipment_model

# Page configuration
st.set_page_config(page_title="LafargeHolcim Ivory Coast - Industrial PdM Suite", layout="wide")

# -------------------------------------------------------------------
# GLOBAL BRAND HEADER (Side-by-Side Logo & Text + Top Search Bar)
# -------------------------------------------------------------------
def render_global_header():
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 1.0rem !important;
                padding-bottom: 1.0rem !important;
            }
            div[data-testid="stHorizontalBlock"] {
                align-items: center;
            }
            .brand-caption {
                color: #333333;
                font-size: 1.0rem;
                font-weight: 700;
                line-height: 1.2;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    header_left, header_middle, header_right = st.columns([3.5, 0.5, 2.5])
    
    with header_left:
        logo_col, text_col = st.columns([1, 2.5])
        
        with logo_col:
            try:
                st.image("photo/lafargeholcim_cte_d_ivoire_logo.jfif", width=110)
            except Exception:
                st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Holcim_logo.svg/1200px-Holcim_logo.svg.png", width=110)
            
        with text_col:
            st.markdown(
                """
                <div class="brand-caption">
                    LafargeHolcim Côte d'Ivoire<br>
                    <span style="font-weight: 500; color: #666666; font-size: 0.85rem;">Plant Operations — Engineering & Reliability Suite</span>
                </div>
                """,
                unsafe_allow_html=True
            )
        
    with header_middle:
        st.write("")

    with header_right:
        search_query = st.text_input(
            label="Header Search",
            placeholder="🔍 Search SCADA tag, equipment, or alert ID...",
            label_visibility="collapsed",
            key="global_header_search"
        )
        
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)
    return search_query

# -------------------------------------------------------------------
# ISO 10816 VIBRATION SEVERITY EVALUATOR
# -------------------------------------------------------------------
def get_iso_10816_status(vib):
    if vib <= 2.8:
        return "Zone A (Good / New State)", "#2ECC71"
    elif vib <= 4.5:
        return "Zone B (Acceptable / Continuous Run)", "#27AE60"
    elif vib <= 7.0:
        return "Zone C (Warning / Action Required)", "#F39C12"
    else:
        return "Zone D (Critical / Trip Limit Breach)", "#E74C3C"

# SCADA Instrument & P&ID Metadata
EQUIPMENT_PROFILES = {
    "Dynamic Separator": {
        "tag": "611-SEP-01",
        "vib_tag": "VIB-611-SEP01-R",
        "temp_tag": "TIT-611-SEP01-B1",
        "description": "3rd-generation high-efficiency air separator controlling powder fineness via variable-speed rotor.",
        "vibration_sensor_loc": "P&ID Loc V1: Mounted horizontally on upper rotor main bearing housing.",
        "temp_sensor_loc": "P&ID Loc T1: Pt100 RTD embedded in upper bearing grease reservoir.",
        "image_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=800&q=80"
    },
    "E5 & E8 Cement Pumps": {
        "tag": "611-PMP-E5E8",
        "vib_tag": "VIB-611-PMP05-A",
        "temp_tag": "TIT-611-PMP05-S",
        "description": "Dual pneumatic screw pumping skid for high-pressure powder transport to storage silos.",
        "vibration_sensor_loc": "P&ID Loc V2: Tri-axial accelerometer stud-mounted on drive-end housing.",
        "temp_sensor_loc": "P&ID Loc T2: Thermal probe inserted into main drive bearing oil sump.",
        "image_url": "https://images.unsplash.com/photo-1581092335397-9583fe92d232?auto=format&fit=crop&w=800&q=80"
    },
    "Separator Filter Fan": {
        "description": "Process exhaust fan maintaining controlled negative pressure inside main baghouse filter.",
        "tag": "611-FN-SEP",
        "vib_tag": "VIB-611-FNS-R",
        "temp_tag": "TIT-611-FNS-B",
        "vibration_sensor_loc": "P&ID Loc V1: Pillow block bearing housing radial pickup.",
        "temp_sensor_loc": "P&ID Loc T1: Surface RTD contact probe on fan drive casing.",
        "image_url": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=800&q=80"
    },
    "Mill Main Control": {
        "description": "Primary ball mill drive assembly including HV motor, reduction gearset, and trunnion lubrication skid.",
        "tag": "611-ML-DRV",
        "vib_tag": "VIB-611-MLD-GB",
        "temp_tag": "TIT-611-MLD-TRN",
        "vibration_sensor_loc": "P&ID Loc V1/V2: Dual accelerometers on pinion stand and gearbox input shaft.",
        "temp_sensor_loc": "P&ID Loc T1/T2: Thermowells in main trunnion oil supply feed.",
        "image_url": "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=800&q=80"
    },
    "Main Filter Fan": {
        "description": "Primary plant de-dusting fan discharging process air to main stack.",
        "tag": "611-FN-MAIN",
        "vib_tag": "VIB-611-FNM-DE",
        "temp_tag": "TIT-611-FNM-WNG",
        "vibration_sensor_loc": "P&ID Loc V1: Magnetic accelerometer on NDE motor endbell.",
        "temp_sensor_loc": "P&ID Loc T1: Stator winding embedded RTD channel 1.",
        "image_url": "https://images.unsplash.com/photo-1581092580497-e0d23cbdf1dc?auto=format&fit=crop&w=800&q=80"
    }
}

# Initialize Session States
if "df" not in st.session_state:
    st.session_state.df = generate_multi_mill_telemetry(30)

if "alerts_log" not in st.session_state:
    st.session_state.alerts_log = []

# Sidebar Navigation
st.sidebar.title("🏭 Plant Navigation")
main_view = st.sidebar.radio("Select View Level", ["General Plant Overview", "Individual Mill Monitor"])

selected_mill = "Mill 6"
if main_view == "Individual Mill Monitor":
    selected_mill = st.sidebar.selectbox("Select Mill Unit:", PLANT_MILLS, index=4)
    mill_page = st.sidebar.radio(f"{selected_mill} Pages:", ["Subsystem Overview", "Equipment Drill-Down", "Servicing Desk & Alert Log"])

streaming_active = st.sidebar.toggle("Live Telemetry Stream", value=True)

# -------------------------------------------------------------------
# LIVE DASHBOARD RENDERING FRAGMENT
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_dashboard(main_view):
    search_query = render_global_header()

    if streaming_active:
        new_packet = fetch_multi_mill_live_reading()
        st.session_state.df = pd.concat([st.session_state.df, new_packet], ignore_index=True)
        st.session_state.df = st.session_state.df.tail(2500)
        
        for _, row in new_packet.iterrows():
            st.session_state.alerts_log = evaluate_and_log_alerts(row, st.session_state.alerts_log)

    current_df = st.session_state.df

    alerts_to_display = st.session_state.alerts_log
    if search_query.strip():
        q = search_query.lower()
        alerts_to_display = [
            a for a in st.session_state.alerts_log 
            if q in str(a.get("id")).lower() 
            or q in a.get("mill", "").lower() 
            or q in a.get("equipment", "").lower() 
            or q in a.get("issue", "").lower()
        ]

    # ===============================================================
    # PAGE 1: GENERAL PLANT OVERVIEW
    # ===============================================================
    if main_view == "General Plant Overview":
        st.subheader("🏛️ Plant General Command Overview")
        st.caption("SCADA Central Monitoring: Mill 1, Mill 2, Mill 4, Mill 5, and Mill 6.")
        
        total_active = len([a for a in st.session_state.alerts_log if "ACTIVE" in a["status"]])
        total_crit = len([a for a in st.session_state.alerts_log if "CRITICAL" in a["status"]])
        total_warn = len([a for a in st.session_state.alerts_log if "WARNING" in a["status"]])
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Operating Mills", f"{len(PLANT_MILLS)} Units")
        c2.metric("Total Active Alerts", f"{total_active}", delta_color="inverse")
        c3.metric("Critical Interlock Risks", f"{total_crit}", delta_color="inverse")
        c4.metric("ISO Warning Limits", f"{total_warn}", delta_color="inverse")
        
        st.markdown("---")
        st.subheader("Mill Operational Status Matrix")
        
        cols = st.columns(len(PLANT_MILLS))
        for i, mill_name in enumerate(PLANT_MILLS):
            mill_alerts = [a for a in st.session_state.alerts_log if a["mill"] == mill_name and "ACTIVE" in a["status"]]
            crit_count = len([a for a in mill_alerts if "CRITICAL" in a["status"]])
            warn_count = len([a for a in mill_alerts if "WARNING" in a["status"]])
            
            with cols[i]:
                st.markdown(f"### {mill_name}")
                if crit_count > 0:
                    st.error(f"🔴 CRITICAL ({crit_count} Active)")
                elif warn_count > 0:
                    st.warning(f"⚠️ WARNING ({warn_count} Active)")
                else:
                    st.success("🟢 NORMAL (0 Alerts)")
                    
                st.write(f"**Pending Servicing:** {len(mill_alerts)} item(s)")
                
                main_df = current_df[(current_df["mill"] == mill_name) & (current_df["equipment"] == "Mill Main Control")]
                if not main_df.empty:
                    latest_main = main_df.iloc[-1]
                    st.metric("Drive Vib.", f"{latest_main['vibration_mm_s']} mm/s")
                    st.metric("Drive Temp.", f"{latest_main['temperature_c']} °C")

        active_alerts = [a for a in alerts_to_display if "ACTIVE" in a["status"]]

        # Critical ML Action Banner on Overview Page
        crit_alerts = [a for a in active_alerts if "CRITICAL" in a["severity"]]
        if crit_alerts:
            st.markdown("---")
            st.markdown("##### 🚨 Critical ML Predictive Action Items:")
            for c_alert in crit_alerts[:3]:
                st.error(
                    f"**[{c_alert['mill']} — {c_alert['equipment']}]** "
                    f"*{c_alert['issue']}* — **Action:** Check P&ID instrument tags & perform physical servicing."
                )
                    
        st.markdown("---")
        st.subheader("🚨 Active Plant Alert Log & Operator Recommendations")
        
        if not active_alerts:
            st.success("🎉 All mill systems operating within normal ISO bounds.")
        else:
            formatted_alerts = []
            for a in active_alerts:
                rec_text = "Perform routine physical inspection on next round."
                if "individual_comments" in a and a["individual_comments"]:
                    rec_text = a["individual_comments"][-1]
                
                formatted_alerts.append({
                    "Alert ID": f"#{a['id']}",
                    "Timestamp": a["timestamp"],
                    "Mill": a["mill"],
                    "Equipment Subsystem": a["equipment"],
                    "Severity": a["severity"],
                    "Root Cause Diagnostic": a["issue"],
                    "Recommended Action": rec_text,
                    "Servicing Status": a["status"]
                })
            
            alerts_df = pd.DataFrame(formatted_alerts)
            st.dataframe(
                alerts_df[[
                    "Alert ID", "Timestamp", "Mill", "Equipment Subsystem", 
                    "Severity", "Root Cause Diagnostic", "Recommended Action", "Servicing Status"
                ]],
                width="stretch",
                hide_index=True
            )

    # ===============================================================
    # PAGE 2: INDIVIDUAL MILL MONITOR
    # ===============================================================
    elif main_view == "Individual Mill Monitor":
        mill_df = current_df[current_df["mill"] == selected_mill]
        
        if mill_page == "Subsystem Overview":
            st.subheader(f"⚙️ {selected_mill} - Subsystem Overview")
            
            sub_cols = st.columns(len(EQUIPMENT_LIST))
            for i, eq in enumerate(EQUIPMENT_LIST):
                eq_df = mill_df[mill_df["equipment"] == eq]
                latest = eq_df.iloc[-1]
                health = simple_health_score(latest["vibration_mm_s"], latest["temperature_c"])
                
                with sub_cols[i]:
                    st.markdown(f"#### {eq}")
                    st.caption(f"Tag: {EQUIPMENT_PROFILES.get(eq, {}).get('tag', 'N/A')}")
                    if health > 80: st.success(f"Health: {health}%")
                    elif health > 50: st.warning(f"Health: {health}%")
                    else: st.error(f"Health: {health}%")
                    
                    st.metric("Vibration", f"{latest['vibration_mm_s']} mm/s")
                    st.metric("Temperature", f"{latest['temperature_c']} °C")

        elif mill_page == "Equipment Drill-Down":
            st.subheader(f"🔬 {selected_mill} - Engineering Drill-Down")
            
            selected_eq = st.selectbox(f"Select Subsystem:", EQUIPMENT_LIST)
            eq_data = mill_df[mill_df["equipment"] == selected_eq]
            latest = eq_data.iloc[-1]
            profile = EQUIPMENT_PROFILES.get(selected_eq, {})
            
            # Rate of Change (Thermal Ramp Rate) Calculation
            if len(eq_data) > 1:
                prev_temp = eq_data.iloc[-2]["temperature_c"]
                temp_delta = round((latest["temperature_c"] - prev_temp) / 0.05, 2) # °C per min
            else:
                temp_delta = 0.0

            # ISO 10816 Classification
            iso_status, iso_color = get_iso_10816_status(latest["vibration_mm_s"])

            # 1. SCADA Instrument & P&ID Section
            info_col, img_col = st.columns([3, 2])
            with info_col:
                st.markdown(f"#### SCADA Tag: `{profile.get('tag', 'N/A')}` — {selected_eq}")
                st.write(f"**Process Description:** {profile.get('description', 'N/A')}")
                
                st.markdown("##### 📐 Instrument Mapping (ISA 5.1 Standard):")
                st.write(f"• **Vibration Transmitter (`{profile.get('vib_tag', 'N/A')}`):** {profile.get('vibration_sensor_loc', 'N/A')}")
                st.write(f"• **Temperature Element (`{profile.get('temp_tag', 'N/A')}`):** {profile.get('temp_sensor_loc', 'N/A')}")
                
            with img_col:
                st.image(profile.get("image_url"), caption=f"P&ID Installation Layout: {selected_eq}", width="stretch")

            st.markdown("---")

            # 2. Engineering Key Metrics & Safety Interlocks
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Overall Health Index", f"{simple_health_score(latest['vibration_mm_s'], latest['temperature_c'])}%")
            m2.metric("Vibration RMS", f"{latest['vibration_mm_s']} mm/s")
            m3.metric("Bearing Temperature", f"{latest['temperature_c']} °C", delta=f"{temp_delta} °C/min")
            m4.metric("ISO 10816 State", iso_status)

            st.markdown("##### 🛡️ DCS Interlock & Trip Safety Status")
            t_col1, t_col2 = st.columns(2)
            with t_col1:
                if latest['vibration_mm_s'] > 7.0:
                    st.error("🚨 DRIVE MOTOR HIGH-VIB TRIP INTERLOCK: TRIP ACTIVATED")
                else:
                    st.success("🔒 Vib. Trip Interlock: Normal (Permission to Run)")
            with t_col2:
                if latest['temperature_c'] > 90.0:
                    st.error("🚨 BEARING OVER-TEMPERATURE INTERLOCK: TRIP ACTIVATED")
                else:
                    st.success("🔒 Thermal Interlock: Normal (Permission to Run)")

            st.markdown("---")
            st.subheader(f"Telemetry Trends: {selected_eq}")

            # Trends
            VIB_WARN, VIB_CRIT = 4.5, 7.0
            TEMP_WARN, TEMP_CRIT = 75.0, 90.0
            COLOR_VIB, COLOR_TEMP = "#00D2FF", "#FF8C00"
            COLOR_WARN, COLOR_CRIT, GRID_COLOR = "#F1C40F", "#E74C3C", "#2A2D34"

            fig_vib = go.Figure()
            fig_vib.add_trace(go.Scatter(x=eq_data["timestamp"], y=eq_data["vibration_mm_s"], name="Vibration (mm/s)", line=dict(color=COLOR_VIB, width=2.5)))
            fig_vib.add_hline(y=VIB_WARN, line_dash="dash", line_color=COLOR_WARN, annotation_text="ISO Zone C (4.5 mm/s)")
            fig_vib.add_hline(y=VIB_CRIT, line_dash="dash", line_color=COLOR_CRIT, annotation_text="ISO Zone D Trip (7.0 mm/s)")
            fig_vib.update_layout(height=280, template="plotly_dark", title=f"Vibration Signal — {profile.get('vib_tag', '')}", margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_vib, width="stretch")

            fig_temp = go.Figure()
            fig_temp.add_trace(go.Scatter(x=eq_data["timestamp"], y=eq_data["temperature_c"], name="Temperature (°C)", line=dict(color=COLOR_TEMP, width=2.5)))
            fig_temp.add_hline(y=TEMP_WARN, line_dash="dash", line_color=COLOR_WARN, annotation_text="Warn Threshold (75 °C)")
            fig_temp.add_hline(y=TEMP_CRIT, line_dash="dash", line_color=COLOR_CRIT, annotation_text="Trip Threshold (90 °C)")
            fig_temp.update_layout(height=280, template="plotly_dark", title=f"Thermal Signal — {profile.get('temp_tag', '')}", margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_temp, width="stretch")

        elif mill_page == "Servicing Desk & Alert Log":
            st.subheader(f"🛠️ {selected_mill} - Servicing Desk & Shift Handover")
            
            mill_alerts = [a for a in alerts_to_display if a["mill"] == selected_mill]
            
            if not mill_alerts:
                st.info(f"No alerts recorded for {selected_mill}.")
            else:
                m_df = pd.DataFrame(mill_alerts)
                
                # Shift Handover Export Button
                st.download_button(
                    label="📄 Export Shift Handover Log (CSV)",
                    data=m_df.to_csv(index=False),
                    file_name=f"Shift_Handover_{selected_mill.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
                
                st.dataframe(m_df[["id", "timestamp", "equipment", "severity", "issue", "status", "operator_notes"]], width="stretch", hide_index=True)
                
                st.markdown("---")
                st.subheader(f"Service & Clear Alert ({selected_mill})")
                
                active_mill_alerts = [a for a in mill_alerts if "ACTIVE" in a["status"]]
                
                if active_mill_alerts:
                    alert_options = {f"Alert #{a['id']} - {a['equipment']} ({a['timestamp']})": a['id'] for a in active_mill_alerts}
                    selected_alert_str = st.selectbox("Select Alert to Resolve:", list(alert_options.keys()))
                    selected_id = alert_options[selected_alert_str]
                    selected_rec = next(a for a in mill_alerts if a["id"] == selected_id)
                    
                    st.markdown("##### 📋 Diagnostic Breakdown:")
                    if "individual_comments" in selected_rec:
                        for comment in selected_rec["individual_comments"]:
                            st.warning(f"• {comment}")

                    with st.form(key=f"service_form_{selected_mill}_{selected_id}"):
                        operator_name = st.text_input("Technician Name / Employee ID:", key=f"op_{selected_id}")
                        alert_feedback_type = st.radio(
                            "Feedback for ML Model:",
                            ["Genuine Issue (Confirmed Failure/Wear)", "False Alarm (Operational Spike)"],
                            key=f"fb_{selected_id}"
                        )
                        action_taken = st.text_area("Maintenance Action Taken (e.g., Re-greased bearing, realigned coupling):", key=f"act_{selected_id}")
                        
                        if st.form_submit_button("Submit & Retrain Isolated Equipment Model"):
                            if operator_name.strip() and action_taken.strip():
                                for alert in st.session_state.alerts_log:
                                    if alert["id"] == selected_id:
                                        serviced_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        was_true_failure = True if "Genuine Issue" in alert_feedback_type else False
                                        
                                        alert["status"] = "SERVICED / CLOSED"
                                        alert["operator_notes"] = f"Serviced by {operator_name} at {serviced_time}. Action: {action_taken}"
                                        
                                        # RETRAIN ONLY THIS MACHINE'S ISOLATED MODEL
                                        feedback_sample = [[alert["vibration_snapshot"], alert["temperature_snapshot"]]]
                                        retrain_specific_equipment_model(
                                            mill=alert["mill"],
                                            equipment=alert["equipment"],
                                            feedback_samples=feedback_sample,
                                            was_true_failure=was_true_failure
                                        )
                                        
                                st.success(f"Alert #{selected_id} cleared and isolated model retrained for {selected_rec['mill']} - {selected_rec['equipment']}!")
                                st.rerun()
                            else:
                                st.error("Please enter technician name and action taken.")
                else:
                    st.success(f"🎉 All alerts for {selected_mill} have been serviced.")

# Render Dashboard
render_live_dashboard(main_view)
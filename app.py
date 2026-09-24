import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from mock_data import (
    get_shared_plant_engine,
    simple_health_score, 
    PLANT_MILLS,
    MILL_EQUIPMENT_MAP,
    MILL_SENSOR_CONFIG
)
from db_engine import fetch_all_alerts
from ui_components import (
    render_sidebar_auth, 
    render_global_header, 
    render_servicing_desk
)

st.set_page_config(page_title="LafargeHolcim Ivory Coast - Multi-Sensor PdM Suite", layout="wide")

# Session State Initialization
if "nav_main_view" not in st.session_state:
    st.session_state["nav_main_view"] = "General Plant Overview"
if "nav_selected_mill" not in st.session_state:
    st.session_state["nav_selected_mill"] = "Mill 6"
if "nav_mill_page" not in st.session_state:
    st.session_state["nav_mill_page"] = "Subsystem Overview"
if "nav_selected_eq" not in st.session_state:
    st.session_state["nav_selected_eq"] = "Dynamic Separator"

# Render Global Header & Process Search Navigation FIRST
search_query = render_global_header()

# Render Sidebar Login & Role Management
render_sidebar_auth()

# Connect to shared multi-device data engine singleton
shared_engine = get_shared_plant_engine()

def get_iso_10816_status(vib):
    if vib <= 2.8: return "Zone A (Good / New State)", "#2ECC71"
    elif vib <= 4.5: return "Zone B (Acceptable / Continuous Run)", "#27AE60"
    elif vib <= 7.0: return "Zone C (Warning / Action Required)", "#F39C12"
    else: return "Zone D (Critical / Trip Limit Breach)", "#E74C3C"

EQUIPMENT_PROFILES = {
    "Dynamic Separator": {"tag": "611-SEP-01", "description": "High-efficiency air separator.", "image_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=800&q=80"},
    "Separator Filter Fan": {"tag": "611-FN-SEP", "description": "Process exhaust fan.", "image_url": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=800&q=80"},
    "Mill Main Control": {"tag": "611-ML-DRV", "description": "Ball mill drive assembly.", "image_url": "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=800&q=80"},
    "Main Filter Fan": {"tag": "611-FN-MAIN", "description": "Primary plant de-dusting fan.", "image_url": "https://images.unsplash.com/photo-1581092580497-e0d23cbdf1dc?auto=format&fit=crop&w=800&q=80"}
}

st.sidebar.title("🏭 Plant Navigation")

main_view = st.sidebar.radio(
    "Select View Level", 
    ["General Plant Overview", "Individual Mill Monitor"],
    key="nav_main_view"
)

selected_mill = st.session_state.get("nav_selected_mill", "Mill 6")
if selected_mill not in PLANT_MILLS:
    selected_mill = "Mill 6"

mill_page = st.session_state.get("nav_mill_page", "Subsystem Overview")

if main_view == "Individual Mill Monitor":
    mill_idx = PLANT_MILLS.index(selected_mill) if selected_mill in PLANT_MILLS else 3
    selected_mill = st.sidebar.selectbox("Select Mill Unit:", PLANT_MILLS, index=mill_idx, key="nav_selected_mill")
    mill_page = st.sidebar.radio(f"{selected_mill} Pages:", ["Subsystem Overview", "Equipment Drill-Down", "Servicing Desk & Alert Log"], key="nav_mill_page")

streaming_active = st.sidebar.toggle("Live Telemetry Stream", value=True)

# -------------------------------------------------------------------
# ISOLATED FRAGMENT: GENERAL PLANT OVERVIEW
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_overview_matrix(search_query):
    all_db_alerts = fetch_all_alerts() or shared_engine.alerts_log

    alerts_to_display = all_db_alerts
    if search_query.strip():
        q = search_query.lower()
        alerts_to_display = [
            a for a in all_db_alerts 
            if q in str(a.get("id", "")).lower() 
            or q in str(a.get("mill", "")).lower() 
            or q in str(a.get("equipment", "")).lower() 
            or q in str(a.get("issue", "")).lower()
        ]

    st.subheader("🏛️ Plant General Command Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Operating Mills", f"{len(PLANT_MILLS)} Units")
    c2.metric("Active Alerts", len([a for a in all_db_alerts if "ACTIVE" in str(a.get("status", "")).upper()]), delta_color="inverse")
    c3.metric("Critical Interlocks", len([a for a in all_db_alerts if "CRITICAL" in str(a.get("severity", "")).upper() or "CRITICAL" in str(a.get("status", "")).upper()]), delta_color="inverse")
    c4.metric("ISO Warnings", len([a for a in all_db_alerts if "WARNING" in str(a.get("severity", "")).upper() or "WARNING" in str(a.get("status", "")).upper()]), delta_color="inverse")
    
    st.markdown("---")
    st.subheader("Mill Operational Status Matrix")
    cols = st.columns(len(PLANT_MILLS))
    for i, mill_name in enumerate(PLANT_MILLS):
        mill_alerts = [
            a for a in all_db_alerts 
            if str(a.get("mill", "")).strip().lower() == mill_name.strip().lower() 
            and "ACTIVE" in str(a.get("status", "")).upper()
        ]
        crit = len([a for a in mill_alerts if "CRITICAL" in str(a.get("severity", "")).upper() or "CRITICAL" in str(a.get("status", "")).upper()])
        warn = len([a for a in mill_alerts if "WARNING" in str(a.get("severity", "")).upper() or "WARNING" in str(a.get("status", "")).upper()])
        with cols[i]:
            st.markdown(f"### {mill_name}")
            if crit > 0: st.error(f"🔴 CRITICAL ({crit})")
            elif warn > 0: st.warning(f"⚠️ WARNING ({warn})")
            else: st.success("🟢 NORMAL")
            st.write(f"**Subsystems:** {len(MILL_EQUIPMENT_MAP.get(mill_name, []))}")
            st.write(f"**Pending Alerts:** {len(mill_alerts)}")

    active_alerts = [a for a in alerts_to_display if "ACTIVE" in str(a.get("status", "")).upper()]
    st.markdown("---")
    st.subheader("🚨 Active Plant Alert Log & Recommendations")
    if not active_alerts:
        st.success("🎉 All mill systems operating within normal ISO bounds.")
    else:
        formatted_rows = [{
            "Alert ID": f"#{a.get('id', 'N/A')}",
            "Timestamp": a.get("timestamp", "N/A"),
            "Mill": a.get("mill", "N/A"),
            "Equipment Subsystem": a.get("equipment", "N/A"),
            "Severity": a.get("severity", "N/A"),
            "Root Cause Diagnostic": a.get("issue", "N/A"),
            "Servicing Status": a.get("status", "N/A")
        } for a in active_alerts]
        st.dataframe(pd.DataFrame(formatted_rows), width="stretch", hide_index=True)

# -------------------------------------------------------------------
# ISOLATED FRAGMENT: SUBSYSTEM OVERVIEW (SAFE MULTI-SENSOR FALLBACK)
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_subsystem_cards(selected_mill):
    mill_df = shared_engine.df[shared_engine.df["mill"] == selected_mill]
    available_eq = MILL_EQUIPMENT_MAP.get(selected_mill, [])
    
    st.subheader(f"⚙️ {selected_mill} - Multi-Sensor Subsystem Overview")
    
    for eq in available_eq:
        eq_sub_df = mill_df[mill_df["equipment"] == eq]
        if not eq_sub_df.empty:
            latest = eq_sub_df.iloc[-1]
            
            # Safe extractions with fallback for initial telemetry buffer
            max_v = latest.get("max_vibration", latest.get("vibration_mm_s", 0.0))
            max_t = latest.get("max_temperature", latest.get("temperature_c", 0.0))
            health = simple_health_score(max_v, max_t)
            
            vib_map = latest.get("vib_sensors", {})
            temp_map = latest.get("temp_sensors", {})
            
            with st.expander(f"📌 {eq} — Health: {health}% | Max Vib: {max_v} mm/s | Max Temp: {max_t} °C", expanded=True):
                col_info, col_vib, col_temp = st.columns([1.5, 2, 2])
                
                with col_info:
                    st.markdown(f"### {eq}")
                    if health > 80: st.success(f"Status: Normal ({health}%)")
                    elif health > 50: st.warning(f"Status: Warning ({health}%)")
                    else: st.error(f"Status: Critical ({health}%)")
                    
                    if "oil_pressure" in latest:
                        st.metric("Oil Pressure", f"{latest['oil_pressure']} bar")
                    if "motor_current" in latest:
                        st.metric("Motor Current", f"{latest['motor_current']} A")

                with col_vib:
                    st.markdown(f"**Vibration Sensors ({len(vib_map)} channels):**")
                    if vib_map:
                        vib_df = pd.DataFrame([{"Sensor Channel": k, "Reading (mm/s)": v} for k, v in vib_map.items()])
                        st.dataframe(vib_df, width="stretch", hide_index=True, height=180)
                    else:
                        st.caption("No vibration sensors installed on this unit.")

                with col_temp:
                    st.markdown(f"**Temperature Sensors ({len(temp_map)} channels):**")
                    if temp_map:
                        temp_df = pd.DataFrame([{"Sensor Channel": k, "Reading (°C)": v} for k, v in temp_map.items()])
                        st.dataframe(temp_df, width="stretch", hide_index=True, height=180)
                    else:
                        st.caption("No temperature sensors installed on this unit.")

# -------------------------------------------------------------------
# ISOLATED FRAGMENT: DRILL-DOWN CHARTS (SAFE MULTI-SENSOR FALLBACK)
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_drilldown_charts(selected_mill, selected_eq):
    mill_df = shared_engine.df[shared_engine.df["mill"] == selected_mill]
    eq_data = mill_df[mill_df["equipment"] == selected_eq]
    
    if not eq_data.empty:
        latest = eq_data.iloc[-1]
        max_v = latest.get("max_vibration", latest.get("vibration_mm_s", 0.0))
        max_t = latest.get("max_temperature", latest.get("temperature_c", 0.0))
        
        vib_map = latest.get("vib_sensors", {})
        temp_map = latest.get("temp_sensors", {})
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Subsystem Health", f"{simple_health_score(max_v, max_t)}%")
        m2.metric("Max Vibration RMS", f"{max_v} mm/s")
        m3.metric("Max Bearing Temp", f"{max_t} °C")

        # Multi-Trace Vibration Plot
        if vib_map:
            fig_vib = go.Figure()
            sensor_names = list(vib_map.keys())
            for s_name in sensor_names:
                y_vals = [row.get("vib_sensors", {}).get(s_name, row.get("vibration_mm_s", 0.0)) for _, row in eq_data.iterrows()]
                fig_vib.add_trace(go.Scatter(x=eq_data["timestamp"], y=y_vals, mode="lines", name=s_name))
            
            fig_vib.update_layout(
                height=320, 
                template="plotly_dark", 
                title=f"Multi-Sensor Vibration Traces ({len(sensor_names)} Channels) — {selected_eq}",
                margin=dict(l=20, r=20, t=35, b=20),
                legend=dict(orientation="h", y=-0.2)
            )
            st.plotly_chart(fig_vib, width="stretch")

        # Multi-Trace Temperature Plot
        if temp_map:
            fig_temp = go.Figure()
            sensor_names = list(temp_map.keys())
            for s_name in sensor_names:
                y_vals = [row.get("temp_sensors", {}).get(s_name, row.get("temperature_c", 0.0)) for _, row in eq_data.iterrows()]
                fig_temp.add_trace(go.Scatter(x=eq_data["timestamp"], y=y_vals, mode="lines", name=s_name))
            
            fig_temp.update_layout(
                height=320, 
                template="plotly_dark", 
                title=f"Multi-Sensor Thermal Traces ({len(sensor_names)} Channels) — {selected_eq}",
                margin=dict(l=20, r=20, t=35, b=20),
                legend=dict(orientation="h", y=-0.2)
            )
            st.plotly_chart(fig_temp, width="stretch")

# -------------------------------------------------------------------
# PAGE ROUTING
# -------------------------------------------------------------------
if main_view == "General Plant Overview":
    render_live_overview_matrix(search_query)

elif main_view == "Individual Mill Monitor":
    available_eq = MILL_EQUIPMENT_MAP.get(selected_mill, ["Mill Main Control"])

    if mill_page == "Subsystem Overview":
        render_live_subsystem_cards(selected_mill)

    elif mill_page == "Equipment Drill-Down":
        st.subheader(f"🔬 {selected_mill} - Engineering Drill-Down")
        current_eq = st.session_state.get("nav_selected_eq", available_eq[0])
        eq_idx = available_eq.index(current_eq) if current_eq in available_eq else 0
        selected_eq = st.selectbox("Select Subsystem:", available_eq, index=eq_idx, key="nav_selected_eq")

        profile = EQUIPMENT_PROFILES.get(selected_eq, {})
        info_col, img_col = st.columns([3, 2])
        with info_col:
            st.markdown(f"#### Tag: `{profile.get('tag', 'N/A')}` — {selected_eq}")
            st.write(f"**Description:** {profile.get('description', 'N/A')}")
        with img_col:
            st.image(profile.get("image_url"), caption=f"P&ID Layout: {selected_eq}", width="stretch")

        st.markdown("---")
        render_live_drilldown_charts(selected_mill, selected_eq)

    elif mill_page == "Servicing Desk & Alert Log":
        alerts_to_display = fetch_all_alerts() or shared_engine.alerts_log
        render_servicing_desk(selected_mill, alerts_to_display)
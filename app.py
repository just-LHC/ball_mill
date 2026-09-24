import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from mock_data import (
    get_shared_plant_engine,
    simple_health_score, 
    PLANT_MILLS,
    MILL_EQUIPMENT_MAP,
    MILL_SENSOR_PROFILES
)
from db_engine import fetch_all_alerts
from ui_components import (
    render_sidebar_auth, 
    render_global_header, 
    render_servicing_desk
)

st.set_page_config(page_title="LafargeHolcim Ivory Coast - Industrial PdM Suite", layout="wide")

# Session State Initialization
if "nav_main_view" not in st.session_state:
    st.session_state["nav_main_view"] = "General Plant Overview"
if "nav_selected_mill" not in st.session_state:
    st.session_state["nav_selected_mill"] = "Mill 6"
if "nav_mill_page" not in st.session_state:
    st.session_state["nav_mill_page"] = "Subsystem Overview"
if "nav_selected_eq" not in st.session_state:
    st.session_state["nav_selected_eq"] = "Dynamic Separator"

search_query = render_global_header()
render_sidebar_auth()
shared_engine = get_shared_plant_engine()

def get_iso_10816_status(vib):
    if vib <= 2.8: return "Zone A (Good / New State)", "#2ECC71"
    elif vib <= 4.5: return "Zone B (Acceptable / Continuous Run)", "#27AE60"
    elif vib <= 7.0: return "Zone C (Warning / Action Required)", "#F39C12"
    else: return "Zone D (Critical / Trip Limit Breach)", "#E74C3C"

EQUIPMENT_PROFILES = {
    "Dynamic Separator": {"tag": "611-SEP-01", "vib_tag": "VIB-611-SEP01-R", "temp_tag": "TIT-611-SEP01-B1", "description": "High-efficiency air separator.", "image_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=800&q=80"},
    "Separator Filter Fan": {"tag": "611-FN-SEP", "vib_tag": "VIB-611-FNS-R", "temp_tag": "TIT-611-FNS-B", "description": "Process exhaust fan.", "image_url": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=800&q=80"},
    "Mill Main Control": {"tag": "611-ML-DRV", "vib_tag": "VIB-611-MLD-GB", "temp_tag": "TIT-611-MLD-TRN", "description": "Ball mill drive assembly.", "image_url": "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=800&q=80"},
    "Main Filter Fan": {"tag": "611-FN-MAIN", "vib_tag": "VIB-611-FNM-DE", "temp_tag": "TIT-611-FNM-WNG", "description": "Primary plant de-dusting fan.", "image_url": "https://images.unsplash.com/photo-1581092580497-e0d23cbdf1dc?auto=format&fit=crop&w=800&q=80"}
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
# GENERAL PLANT OVERVIEW
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
    crit_alerts = [a for a in active_alerts if "CRITICAL" in str(a.get("severity", "")).upper() or "CRITICAL" in str(a.get("status", "")).upper()]
    if crit_alerts:
        st.markdown("---")
        st.markdown("##### 🚨 Critical ML Predictive Action Items:")
        for c in crit_alerts[:3]:
            st.error(f"**[{c.get('mill', 'N/A')} — {c.get('equipment', 'N/A')}]** *{c.get('issue', 'Anomaly detected')}* — **Action:** Check P&ID tags & service.")
                
    st.markdown("---")
    st.subheader("🚨 Active Plant Alert Log & Recommendations")
    if not active_alerts:
        st.success("🎉 All mill systems operating within normal ISO bounds.")
    else:
        formatted_rows = []
        for a in active_alerts:
            comments = a.get("individual_comments", [])
            rec_action = comments[-1] if comments and isinstance(comments, list) else "Inspect machine subsystem and verify RTD/vibration sensor seating."
            formatted_rows.append({
                "Alert ID": f"#{a.get('id', 'N/A')}",
                "Timestamp": a.get("timestamp", "N/A"),
                "Mill": a.get("mill", "N/A"),
                "Equipment Subsystem": a.get("equipment", "N/A"),
                "Severity": a.get("severity", "N/A"),
                "Root Cause Diagnostic": a.get("issue", "N/A"),
                "Recommended Action": rec_action,
                "Servicing Status": a.get("status", "N/A")
            })
        alerts_df = pd.DataFrame(formatted_rows)
        st.dataframe(alerts_df, width="stretch", hide_index=True)

# -------------------------------------------------------------------
# SUBSYSTEM OVERVIEW
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_subsystem_cards(selected_mill):
    mill_df = shared_engine.df[shared_engine.df["mill"] == selected_mill]
    available_eq = MILL_EQUIPMENT_MAP.get(selected_mill, [])
    
    st.subheader(f"⚙️ {selected_mill} - Subsystem Overview")
    cols = st.columns(max(1, len(available_eq)))
    
    for i, eq in enumerate(available_eq):
        eq_sub_df = mill_df[mill_df["equipment"] == eq]
        sensor_info = MILL_SENSOR_PROFILES.get(selected_mill, {}).get(eq, {})
        
        if not eq_sub_df.empty:
            latest = eq_sub_df.iloc[-1]
            health = simple_health_score(latest["vibration_mm_s"], latest["temperature_c"])
            with cols[i]:
                st.markdown(f"#### {eq}")
                st.caption(f"🔧 **Sensors:** {sensor_info.get('notes', 'Standard Setup')}")
                if health > 80: st.success(f"Health: {health}%")
                elif health > 50: st.warning(f"Health: {health}%")
                else: st.error(f"Health: {health}%")
                st.metric("Vibration RMS", f"{latest['vibration_mm_s']} mm/s")
                st.metric("Temperature", f"{latest['temperature_c']} °C")

# -------------------------------------------------------------------
# DRILL-DOWN CHARTS
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_drilldown_charts(selected_mill, selected_eq):
    mill_df = shared_engine.df[shared_engine.df["mill"] == selected_mill]
    eq_data = mill_df[mill_df["equipment"] == selected_eq]
    
    if not eq_data.empty:
        latest = eq_data.iloc[-1]
        profile = EQUIPMENT_PROFILES.get(selected_eq, {})
        sensor_info = MILL_SENSOR_PROFILES.get(selected_mill, {}).get(selected_eq, {})
        
        temp_delta = round((latest["temperature_c"] - eq_data.iloc[-2]["temperature_c"]) / 0.05, 2) if len(eq_data) > 1 else 0.0
        iso_status, _ = get_iso_10816_status(latest["vibration_mm_s"])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Health Index", f"{simple_health_score(latest['vibration_mm_s'], latest['temperature_c'])}%")
        m2.metric("Vibration RMS", f"{latest['vibration_mm_s']} mm/s")
        m3.metric("Bearing Temp.", f"{latest['temperature_c']} °C", delta=f"{temp_delta} °C/min")
        m4.metric("ISO 10816 State", iso_status)

        st.info(f"📋 **Instrument Assignment Config ({selected_mill}):** {sensor_info.get('notes', 'Standard Configuration')}")

        fig_vib = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["vibration_mm_s"], name="Vibration", line=dict(color="#00D2FF", width=2.5)))
        fig_vib.update_layout(height=250, template="plotly_dark", title=f"Live Vibration Signal — {profile.get('vib_tag', 'VIB-SCADA')}", margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_vib, width="stretch")

        fig_temp = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["temperature_c"], name="Temperature", line=dict(color="#FF8C00", width=2.5)))
        fig_temp.update_layout(height=250, template="plotly_dark", title=f"Live Thermal Signal — {profile.get('temp_tag', 'TIT-SCADA')}", margin=dict(l=20, r=20, t=30, b=20))
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
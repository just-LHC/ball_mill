import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from mock_data import (
    get_shared_plant_engine,
    simple_health_score, 
    PLANT_MILLS,
    EQUIPMENT_LIST
)
from ui_components import (
    render_sidebar_auth, 
    render_global_header, 
    render_servicing_desk
)

st.set_page_config(page_title="LafargeHolcim Ivory Coast - Industrial PdM Suite", layout="wide")

# Initialize Search-Navigation Keys in Session State
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
    "Dynamic Separator": {"tag": "611-SEP-01", "vib_tag": "VIB-611-SEP01-R", "temp_tag": "TIT-611-SEP01-B1", "description": "3rd-gen high-efficiency air separator.", "vibration_sensor_loc": "P&ID Loc V1: Upper rotor main bearing housing.", "temp_sensor_loc": "P&ID Loc T1: Pt100 RTD in grease reservoir.", "image_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=800&q=80"},
    "E5 & E8 Cement Pumps": {"tag": "611-PMP-E5E8", "vib_tag": "VIB-611-PMP05-A", "temp_tag": "TIT-611-PMP05-S", "description": "Dual pneumatic screw pumping skid.", "vibration_sensor_loc": "P&ID Loc V2: Drive-end housing.", "temp_sensor_loc": "P&ID Loc T2: Drive bearing oil sump.", "image_url": "https://images.unsplash.com/photo-1581092335397-9583fe92d232?auto=format&fit=crop&w=800&q=80"},
    "Separator Filter Fan": {"tag": "611-FN-SEP", "vib_tag": "VIB-611-FNS-R", "temp_tag": "TIT-611-FNS-B", "description": "Process exhaust fan.", "vibration_sensor_loc": "P&ID Loc V1: Pillow block bearing.", "temp_sensor_loc": "P&ID Loc T1: Surface RTD contact probe.", "image_url": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=800&q=80"},
    "Mill Main Control": {"tag": "611-ML-DRV", "vib_tag": "VIB-611-MLD-GB", "temp_tag": "TIT-611-MLD-TRN", "description": "Ball mill drive assembly.", "vibration_sensor_loc": "P&ID Loc V1/V2: Pinion stand & gearbox input.", "temp_sensor_loc": "P&ID Loc T1/T2: Thermowells in trunnion oil line.", "image_url": "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=800&q=80"},
    "Main Filter Fan": {"tag": "611-FN-MAIN", "vib_tag": "VIB-611-FNM-DE", "temp_tag": "TIT-611-FNM-WNG", "description": "Primary plant de-dusting fan.", "vibration_sensor_loc": "P&ID Loc V1: NDE motor endbell.", "temp_sensor_loc": "P&ID Loc T1: Stator winding RTD.", "image_url": "https://images.unsplash.com/photo-1581092580497-e0d23cbdf1dc?auto=format&fit=crop&w=800&q=80"}
}

st.sidebar.title("🏭 Plant Navigation")

main_view = st.sidebar.radio(
    "Select View Level", 
    ["General Plant Overview", "Individual Mill Monitor"],
    key="nav_main_view"
)

selected_mill = st.session_state.get("nav_selected_mill", "Mill 6")
mill_page = st.session_state.get("nav_mill_page", "Subsystem Overview")

if main_view == "Individual Mill Monitor":
    mill_idx = PLANT_MILLS.index(selected_mill) if selected_mill in PLANT_MILLS else 4
    selected_mill = st.sidebar.selectbox("Select Mill Unit:", PLANT_MILLS, index=mill_idx, key="nav_selected_mill")
    mill_page = st.sidebar.radio(f"{selected_mill} Pages:", ["Subsystem Overview", "Equipment Drill-Down", "Servicing Desk & Alert Log"], key="nav_mill_page")

streaming_active = st.sidebar.toggle("Live Telemetry Stream", value=True)

# -------------------------------------------------------------------
# ISOLATED FRAGMENT: GENERAL PLANT OVERVIEW (READ ONLY)
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_overview_matrix(search_query):
    alerts_to_display = shared_engine.alerts_log
    if search_query.strip():
        q = search_query.lower()
        alerts_to_display = [a for a in shared_engine.alerts_log if q in str(a.get("id")).lower() or q in a.get("mill", "").lower() or q in a.get("equipment", "").lower() or q in a.get("issue", "").lower()]

    st.subheader("🏛️ Plant General Command Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Operating Mills", f"{len(PLANT_MILLS)} Units")
    c2.metric("Active Alerts", len([a for a in shared_engine.alerts_log if "ACTIVE" in a["status"]]), delta_color="inverse")
    c3.metric("Critical Interlocks", len([a for a in shared_engine.alerts_log if "CRITICAL" in a["status"]]), delta_color="inverse")
    c4.metric("ISO Warnings", len([a for a in shared_engine.alerts_log if "WARNING" in a["status"]]), delta_color="inverse")
    
    st.markdown("---")
    st.subheader("Mill Operational Status Matrix")
    cols = st.columns(len(PLANT_MILLS))
    for i, mill_name in enumerate(PLANT_MILLS):
        mill_alerts = [a for a in shared_engine.alerts_log if a["mill"] == mill_name and "ACTIVE" in a["status"]]
        crit = len([a for a in mill_alerts if "CRITICAL" in a["status"]])
        warn = len([a for a in mill_alerts if "WARNING" in a["status"]])
        with cols[i]:
            st.markdown(f"### {mill_name}")
            if crit > 0: st.error(f"🔴 CRITICAL ({crit})")
            elif warn > 0: st.warning(f"⚠️ WARNING ({warn})")
            else: st.success("🟢 NORMAL")
            st.write(f"**Pending:** {len(mill_alerts)} item(s)")

    active_alerts = [a for a in alerts_to_display if "ACTIVE" in a["status"]]
    crit_alerts = [a for a in active_alerts if "CRITICAL" in a["severity"]]
    if crit_alerts:
        st.markdown("---")
        st.markdown("##### 🚨 Critical ML Predictive Action Items:")
        for c in crit_alerts[:3]:
            st.error(f"**[{c['mill']} — {c['equipment']}]** *{c['issue']}* — **Action:** Check P&ID tags & service.")
                
    st.markdown("---")
    st.subheader("🚨 Active Plant Alert Log & Recommendations")
    if not active_alerts:
        st.success("🎉 All mill systems operating within normal ISO bounds.")
    else:
        alerts_df = pd.DataFrame([{
            "Alert ID": f"#{a['id']}", "Timestamp": a["timestamp"], "Mill": a["mill"],
            "Equipment Subsystem": a["equipment"], "Severity": a["severity"],
            "Root Cause Diagnostic": a["issue"],
            "Recommended Action": a["individual_comments"][-1] if a.get("individual_comments") else "Inspect machine.",
            "Servicing Status": a["status"]
        } for a in active_alerts])
        st.dataframe(alerts_df, width="stretch", hide_index=True)

# -------------------------------------------------------------------
# ISOLATED FRAGMENT: SUBSYSTEM OVERVIEW (READ ONLY)
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_subsystem_cards(selected_mill):
    mill_df = shared_engine.df[shared_engine.df["mill"] == selected_mill]
    st.subheader(f"⚙️ {selected_mill} - Subsystem Overview")
    cols = st.columns(len(EQUIPMENT_LIST))
    for i, eq in enumerate(EQUIPMENT_LIST):
        eq_sub_df = mill_df[mill_df["equipment"] == eq]
        if not eq_sub_df.empty:
            latest = eq_sub_df.iloc[-1]
            health = simple_health_score(latest["vibration_mm_s"], latest["temperature_c"])
            with cols[i]:
                st.markdown(f"#### {eq}")
                st.caption(f"Tag: {EQUIPMENT_PROFILES.get(eq, {}).get('tag', 'N/A')}")
                if health > 80: st.success(f"Health: {health}%")
                elif health > 50: st.warning(f"Health: {health}%")
                else: st.error(f"Health: {health}%")
                st.metric("Vibration", f"{latest['vibration_mm_s']} mm/s")
                st.metric("Temperature", f"{latest['temperature_c']} °C")

# -------------------------------------------------------------------
# ISOLATED FRAGMENT: DRILL-DOWN CHARTS & METRICS (READ ONLY)
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_drilldown_charts(selected_mill, selected_eq):
    mill_df = shared_engine.df[shared_engine.df["mill"] == selected_mill]
    eq_data = mill_df[mill_df["equipment"] == selected_eq]
    
    if not eq_data.empty:
        latest = eq_data.iloc[-1]
        profile = EQUIPMENT_PROFILES.get(selected_eq, {})
        
        temp_delta = round((latest["temperature_c"] - eq_data.iloc[-2]["temperature_c"]) / 0.05, 2) if len(eq_data) > 1 else 0.0
        iso_status, _ = get_iso_10816_status(latest["vibration_mm_s"])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Health Index", f"{simple_health_score(latest['vibration_mm_s'], latest['temperature_c'])}%")
        m2.metric("Vibration RMS", f"{latest['vibration_mm_s']} mm/s")
        m3.metric("Bearing Temp.", f"{latest['temperature_c']} °C", delta=f"{temp_delta} °C/min")
        m4.metric("ISO 10816 State", iso_status)

        fig_vib = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["vibration_mm_s"], name="Vibration", line=dict(color="#00D2FF", width=2.5)))
        fig_vib.update_layout(height=250, template="plotly_dark", title=f"Live Vibration Signal — {profile.get('vib_tag', '')}", margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_vib, width="stretch")

        fig_temp = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["temperature_c"], name="Temperature", line=dict(color="#FF8C00", width=2.5)))
        fig_temp.update_layout(height=250, template="plotly_dark", title=f"Live Thermal Signal — {profile.get('temp_tag', '')}", margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_temp, width="stretch")

# -------------------------------------------------------------------
# PAGE ROUTING
# -------------------------------------------------------------------
if main_view == "General Plant Overview":
    render_live_overview_matrix(search_query)

elif main_view == "Individual Mill Monitor":
    if mill_page == "Subsystem Overview":
        render_live_subsystem_cards(selected_mill)

    elif mill_page == "Equipment Drill-Down":
        st.subheader(f"🔬 {selected_mill} - Engineering Drill-Down")
        
        eq_idx = EQUIPMENT_LIST.index(st.session_state["nav_selected_eq"]) if st.session_state.get("nav_selected_eq") in EQUIPMENT_LIST else 0
        selected_eq = st.selectbox("Select Subsystem:", EQUIPMENT_LIST, index=eq_idx, key="nav_selected_eq")
        profile = EQUIPMENT_PROFILES.get(selected_eq, {})

        info_col, img_col = st.columns([3, 2])
        with info_col:
            st.markdown(f"#### Tag: `{profile.get('tag', 'N/A')}` — {selected_eq}")
            st.write(f"**Description:** {profile.get('description', 'N/A')}")
            st.write(f"• **Vibration Transmitter (`{profile.get('vib_tag', 'N/A')}`):** {profile.get('vibration_sensor_loc', 'N/A')}")
            st.write(f"• **Temperature Element (`{profile.get('temp_tag', 'N/A')}`):** {profile.get('temp_sensor_loc', 'N/A')}")
        with img_col:
            st.image(profile.get("image_url"), caption=f"P&ID Layout: {selected_eq}", width="stretch")

        st.markdown("---")
        render_live_drilldown_charts(selected_mill, selected_eq)

    elif mill_page == "Servicing Desk & Alert Log":
        alerts_to_display = shared_engine.alerts_log
        render_servicing_desk(selected_mill, alerts_to_display)
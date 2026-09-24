import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from mock_data import (
    get_shared_plant_engine,
    simple_health_score, 
    PLANT_MILLS,
    MILL_EQUIPMENT_MAP,
    SENSOR_CHANNELS
)
from db_engine import fetch_all_alerts
from ui_components import (
    render_sidebar_auth, 
    render_global_header, 
    render_servicing_desk
)

st.set_page_config(page_title="LafargeHolcim Ivory Coast - Industrial PdM Suite", layout="wide")

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
# SUBSYSTEM OVERVIEW: DYNAMIC MULTI-SENSOR READINGS
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_subsystem_cards(selected_mill):
    mill_df = shared_engine.df[shared_engine.df["mill"] == selected_mill]
    available_eq = MILL_EQUIPMENT_MAP.get(selected_mill, [])
    
    st.subheader(f"⚙️ {selected_mill} - Subsystem Overview")
    cols = st.columns(max(1, len(available_eq)))
    
    for i, eq in enumerate(available_eq):
        eq_sub_df = mill_df[mill_df["equipment"] == eq]
        
        if not eq_sub_df.empty:
            latest = eq_sub_df.iloc[-1]
            health = simple_health_score(latest["vibration_mm_s"], latest["temperature_c"])
            
            with cols[i]:
                st.markdown(f"#### {eq}")
                if health > 80: st.success(f"Health: {health}%")
                elif health > 50: st.warning(f"Health: {health}%")
                else: st.error(f"Health: {health}%")
                
                # --- MILL 6 SPECIFIC SENSOR OVERVIEW ---
                if selected_mill == "Mill 6" and eq == "Dynamic Separator":
                    st.metric("Vibration 1 (DE)", f"{latest['vibration_mm_s']} mm/s")
                    st.metric("Vibration 2 (NDE)", f"{latest['vibration_2_mm_s']} mm/s")
                    st.metric("Temp 1 (Upper)", f"{latest['temperature_c']} °C")
                    st.metric("Temp 2 (Lower)", f"{latest['temperature_2_c']} °C")
                    
                # --- MILL 5 SPECIFIC SENSOR OVERVIEW ---
                elif selected_mill == "Mill 5" and eq == "Dynamic Separator":
                    st.metric("Oil Pressure", f"{latest['oil_pressure_bar']} bar")
                    st.metric("Bearing Temp", f"{latest['temperature_c']} °C")
                    st.metric("Motor Current", f"{latest['motor_current_a']} A")
                    
                # --- GENERAL SUBSYSTEM OVERVIEW ---
                else:
                    st.metric("Vibration RMS", f"{latest['vibration_mm_s']} mm/s")
                    st.metric("Bearing Temp", f"{latest['temperature_c']} °C")

# -------------------------------------------------------------------
# DRILL-DOWN: INDIVIDUAL GRAPHS PER ACTIVE SENSOR
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_drilldown_charts(selected_mill, selected_eq):
    mill_df = shared_engine.df[shared_engine.df["mill"] == selected_mill]
    eq_data = mill_df[mill_df["equipment"] == selected_eq]
    
    if not eq_data.empty:
        latest = eq_data.iloc[-1]
        st.markdown(f"### 📊 Live Sensor Signals — {selected_mill} ({selected_eq})")
        
        # --- MILL 6 DYNAMIC SEPARATOR: 4 SEPARATE GRAPHS ---
        if selected_mill == "Mill 6" and selected_eq == "Dynamic Separator":
            c1, c2 = st.columns(2)
            with c1:
                fig1 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["vibration_mm_s"], line=dict(color="#00D2FF", width=2)))
                fig1.update_layout(height=230, template="plotly_dark", title="Vibration Sensor 1 — Drive End (mm/s)")
                st.plotly_chart(fig1, width="stretch")
                
                fig3 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["temperature_c"], line=dict(color="#FF8C00", width=2)))
                fig3.update_layout(height=230, template="plotly_dark", title="Temperature Sensor 1 — Upper Bearing (°C)")
                st.plotly_chart(fig3, width="stretch")
                
            with c2:
                fig2 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["vibration_2_mm_s"], line=dict(color="#33FF57", width=2)))
                fig2.update_layout(height=230, template="plotly_dark", title="Vibration Sensor 2 — Non-Drive End (mm/s)")
                st.plotly_chart(fig2, width="stretch")
                
                fig4 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["temperature_2_c"], line=dict(color="#FF33A8", width=2)))
                fig4.update_layout(height=230, template="plotly_dark", title="Temperature Sensor 2 — Lower Bearing (°C)")
                st.plotly_chart(fig4, width="stretch")

        # --- MILL 5 DYNAMIC SEPARATOR: 3 SEPARATE GRAPHS ---
        elif selected_mill == "Mill 5" and selected_eq == "Dynamic Separator":
            fig_p = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["oil_pressure_bar"], line=dict(color="#00E5FF", width=2)))
            fig_p.update_layout(height=230, template="plotly_dark", title="Oil Pressure Sensor (bar)")
            st.plotly_chart(fig_p, width="stretch")

            fig_t = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["temperature_c"], line=dict(color="#FF9100", width=2)))
            fig_t.update_layout(height=230, template="plotly_dark", title="Bearing Temperature Sensor (°C)")
            st.plotly_chart(fig_t, width="stretch")

            fig_i = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["motor_current_a"], line=dict(color="#D500F9", width=2)))
            fig_i.update_layout(height=230, template="plotly_dark", title="Motor Current Sensor (Amperes)")
            st.plotly_chart(fig_i, width="stretch")

        # --- GENERAL FALLBACK DRILL-DOWN CHARTS ---
        else:
            fig_v = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["vibration_mm_s"], line=dict(color="#00D2FF", width=2)))
            fig_v.update_layout(height=230, template="plotly_dark", title="Vibration Signal RMS (mm/s)")
            st.plotly_chart(fig_v, width="stretch")

            fig_t = go.Figure(go.Scatter(x=eq_data["timestamp"], y=eq_data["temperature_c"], line=dict(color="#FF8C00", width=2)))
            fig_t.update_layout(height=230, template="plotly_dark", title="Thermal Signal (°C)")
            st.plotly_chart(fig_t, width="stretch")

# -------------------------------------------------------------------
# PAGE ROUTING
# -------------------------------------------------------------------
if main_view == "General Plant Overview":
    # General Plant Overview call
    pass

elif main_view == "Individual Mill Monitor":
    available_eq = MILL_EQUIPMENT_MAP.get(selected_mill, ["Mill Main Control"])

    if mill_page == "Subsystem Overview":
        render_live_subsystem_cards(selected_mill)

    elif mill_page == "Equipment Drill-Down":
        st.subheader(f"🔬 {selected_mill} - Engineering Drill-Down")
        current_eq = st.session_state.get("nav_selected_eq", available_eq[0])
        eq_idx = available_eq.index(current_eq) if current_eq in available_eq else 0
        selected_eq = st.selectbox("Select Subsystem:", available_eq, index=eq_idx, key="nav_selected_eq")

        render_live_drilldown_charts(selected_mill, selected_eq)

    elif mill_page == "Servicing Desk & Alert Log":
        alerts_to_display = fetch_all_alerts() or shared_engine.alerts_log
        render_servicing_desk(selected_mill, alerts_to_display)
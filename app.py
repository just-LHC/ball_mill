import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from mock_data import (
    get_shared_plant_engine,
    simple_health_score, 
    PLANT_MILLS,
    MILL_EQUIPMENT_MAP
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
    st.session_state["nav_selected_eq"] = "Mill Main Control"

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
        
        if not eq_sub_df.empty:
            latest = eq_sub_df.iloc[-1]
            health = simple_health_score(latest.get("vibration_mm_s", 2.5), latest.get("temperature_c", 55.0))
            
            with cols[i]:
                st.markdown(f"#### {eq}")
                if health > 80: st.success(f"Health: {health}%")
                elif health > 50: st.warning(f"Health: {health}%")
                else: st.error(f"Health: {health}%")
                
                # Mill 6 Main Control
                if selected_mill == "Mill 6" and eq == "Mill Main Control":
                    st.markdown("**🔹 OCP Company**")
                    for idx in range(1, 11):
                        st.metric(f"OCP GB Vib #{idx}", f"{latest.get(f'ocp_gb_vib_{idx}', 2.8)} mm/s")
                    for idx in range(1, 3):
                        st.metric(f"OCP Mtr Vib #{idx}", f"{latest.get(f'ocp_mtr_vib_{idx}', 2.1)} mm/s")
                    st.markdown("**🔸 HLC Company**")
                    for idx in range(1, 3):
                        st.metric(f"HLC GB Vib #{idx}", f"{latest.get(f'hlc_gb_vib_{idx}', 2.4)} mm/s")
                    for idx in range(1, 3):
                        st.metric(f"HLC Mtr Temp #{idx}", f"{latest.get(f'hlc_mtr_tmp_{idx}', 62.0)} °C")

                # Mill 5 Main Control
                elif selected_mill == "Mill 5" and eq == "Mill Main Control":
                    st.markdown("**🔹 OCP Company**")
                    for idx in range(1, 11):
                        st.metric(f"OCP GB1 Vib #{idx}", f"{latest.get(f'm5_ocp_gb1_vib_{idx}', 3.0)} mm/s")
                    for idx in range(1, 11):
                        st.metric(f"OCP GB1 Temp #{idx}", f"{latest.get(f'm5_ocp_gb1_tmp_{idx}', 65.0)} °C")
                    st.markdown("**🔸 HLC Company**")
                    for idx in range(1, 4):
                        st.metric(f"HLC GB1 Vib #{idx}", f"{latest.get(f'm5_hlc_gb1_vib_{idx}', 2.6)} mm/s")
                    for idx in range(1, 7):
                        st.metric(f"HLC GB2 Temp #{idx}", f"{latest.get(f'm5_hlc_gb2_tmp_{idx}', 68.0)} °C")
                    st.metric("HLC Mtr Temp #1", f"{latest.get('m5_hlc_mtr_tmp_1', 64.5)} °C")
                    st.metric("HLC Mtr Cur #1", f"{latest.get('m5_hlc_mtr_cur_1', 185.0)} A")

                # Mill 4 Main Control
                elif selected_mill == "Mill 4" and eq == "Mill Main Control":
                    st.markdown("**⚙️ Gearbox Sensors**")
                    for idx in range(1, 3):
                        st.metric(f"GB Vibration #{idx}", f"{latest.get(f'm4_gb_vib_{idx}', 2.5)} mm/s")
                    for idx in range(1, 4):
                        st.metric(f"GB Temperature #{idx}", f"{latest.get(f'm4_gb_tmp_{idx}', 61.0)} °C")
                    st.markdown("**⚡ Motor Sensors**")
                    for idx in range(1, 6):
                        st.metric(f"Motor Temp #{idx}", f"{latest.get(f'm4_mtr_tmp_{idx}', 63.0)} °C")
                    st.metric("Motor Current #1", f"{latest.get('m4_mtr_cur_1', 160.0)} A")

                # Mill 1 Main Control
                elif selected_mill == "Mill 1 (White Cement)" and eq == "Mill Main Control":
                    st.markdown("**⚙️ Gearbox Sensors**")
                    for idx in range(1, 3):
                        st.metric(f"GB Vibration #{idx}", f"{latest.get(f'm1_gb_vib_{idx}', 2.3)} mm/s")
                    for idx in range(1, 4):
                        st.metric(f"GB Temperature #{idx}", f"{latest.get(f'm1_gb_tmp_{idx}', 59.0)} °C")
                    st.markdown("**⚡ Motor Sensors**")
                    st.metric("Motor Current #1", f"{latest.get('m1_mtr_cur_1', 140.0)} A")

                # Mill 6 Dynamic Separator
                elif selected_mill == "Mill 6" and eq == "Dynamic Separator":
                    st.metric("Vibration 1 (DE)", f"{latest.get('vibration_mm_s', 2.4)} mm/s")
                    st.metric("Vibration 2 (NDE)", f"{latest.get('vibration_2_mm_s', 2.6)} mm/s")
                    st.metric("Temp 1 (Upper)", f"{latest.get('temperature_c', 58.0)} °C")
                    st.metric("Temp 2 (Lower)", f"{latest.get('temperature_2_c', 60.0)} °C")
                    
                # Mill 5 Dynamic Separator
                elif selected_mill == "Mill 5" and eq == "Dynamic Separator":
                    st.metric("Oil Pressure", f"{latest.get('oil_pressure_bar', 4.2)} bar")
                    st.metric("Bearing Temp", f"{latest.get('temperature_c', 61.5)} °C")
                    st.metric("Motor Current", f"{latest.get('motor_current_a', 145.0)} A")

                # Mill 6 Separator Filter Fan
                elif selected_mill == "Mill 6" and eq == "Separator Filter Fan":
                    st.metric("Vibration 1 (Fan)", f"{latest.get('vibration_mm_s', 2.4)} mm/s")
                    st.metric("Vibration 2 (Motor)", f"{latest.get('vibration_2_mm_s', 2.6)} mm/s")
                    st.metric("Temp 1 (Bearing)", f"{latest.get('temperature_c', 58.0)} °C")
                    st.metric("Temp 2 (Winding)", f"{latest.get('temperature_2_c', 60.0)} °C")

                # Mill 5 Separator Filter Fan
                elif selected_mill == "Mill 5" and eq == "Separator Filter Fan":
                    st.metric("Vibration 1 (Fan)", f"{latest.get('vibration_mm_s', 2.4)} mm/s")
                    st.metric("Vibration 2 (Motor)", f"{latest.get('vibration_2_mm_s', 2.6)} mm/s")
                    st.metric("Temp 1 (Inlet)", f"{latest.get('temperature_c', 58.0)} °C")
                    st.metric("Temp 2 (Outlet)", f"{latest.get('temperature_2_c', 60.0)} °C")
                    st.metric("Motor Current", f"{latest.get('motor_current_a', 145.0)} A")

                # Mill 6 Main Filter Fan
                elif selected_mill == "Mill 6" and eq == "Main Filter Fan":
                    st.metric("Vibration 1 (Inlet)", f"{latest.get('vibration_mm_s', 2.4)} mm/s")
                    st.metric("Vibration 2 (Outlet)", f"{latest.get('vibration_2_mm_s', 2.6)} mm/s")
                    st.metric("Motor Power", f"{latest.get('electrical_power_kw', 320.0)} kW")
                    st.metric("Motor Speed", f"{latest.get('motor_speed_rpm', 980.0)} RPM")
                    st.metric("Motor Temp", f"{latest.get('motor_temp_c', 68.0)} °C")
                    
                # Fallback Subsystems
                else:
                    st.metric("Vibration RMS", f"{latest.get('vibration_mm_s', 2.5)} mm/s")
                    st.metric("Bearing Temp", f"{latest.get('temperature_c', 55.0)} °C")

# -------------------------------------------------------------------
# DRILL-DOWN: INDIVIDUAL GRAPHS PER ACTIVE SENSOR
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_drilldown_charts(selected_mill, selected_eq):
    mill_df = shared_engine.df[shared_engine.df["mill"] == selected_mill]
    eq_data = mill_df[mill_df["equipment"] == selected_eq]
    
    if not eq_data.empty:
        st.markdown(f"### 📊 Live Sensor Signals — {selected_mill} ({selected_eq})")
        
        # 1. MILL 4 MAIN CONTROL (11 GRAPHS)
        if selected_mill == "Mill 4" and selected_eq == "Mill Main Control":
            st.markdown("#### ⚙️ Gearbox Sensors (5 Graphs)")
            c_gb1, c_gb2 = st.columns(2)
            for i in range(1, 3):
                val = eq_data[f"m4_gb_vib_{i}"] if f"m4_gb_vib_{i}" in eq_data.columns else [2.5]*len(eq_data)
                fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#00D2FF", width=2)))
                fig.update_layout(height=200, template="plotly_dark", title=f"Gearbox Vib Sensor #{i} — Tag: M4-GB-VIB-{i:02d} (mm/s)")
                c_gb1.plotly_chart(fig, width="stretch")

            for i in range(1, 4):
                val = eq_data[f"m4_gb_tmp_{i}"] if f"m4_gb_tmp_{i}" in eq_data.columns else [61.0]*len(eq_data)
                fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#FF8C00", width=2)))
                fig.update_layout(height=200, template="plotly_dark", title=f"Gearbox Temp Sensor #{i} — Tag: M4-GB-TMP-{i:02d} (°C)")
                c_gb2.plotly_chart(fig, width="stretch")

            st.markdown("---")
            st.markdown("#### ⚡ Motor Sensors (6 Graphs)")
            c_m1, c_m2 = st.columns(2)
            for i in range(1, 6):
                target = c_m1 if i % 2 != 0 else c_m2
                val = eq_data[f"m4_mtr_tmp_{i}"] if f"m4_mtr_tmp_{i}" in eq_data.columns else [63.0]*len(eq_data)
                fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#FF33A8", width=2)))
                fig.update_layout(height=200, template="plotly_dark", title=f"Motor Temp Sensor #{i} — Tag: M4-MTR-TMP-{i:02d} (°C)")
                target.plotly_chart(fig, width="stretch")

            cur_m4 = eq_data["m4_mtr_cur_1"] if "m4_mtr_cur_1" in eq_data.columns else [160.0]*len(eq_data)
            fig_cur = go.Figure(go.Scatter(x=eq_data["timestamp"], y=cur_m4, line=dict(color="#D500F9", width=2)))
            fig_cur.update_layout(height=200, template="plotly_dark", title="Motor Current Sensor #1 — Tag: M4-MTR-CUR-01 (Amperes)")
            st.plotly_chart(fig_cur, width="stretch")

        # 2. MILL 1 MAIN CONTROL (6 GRAPHS)
        elif selected_mill == "Mill 1 (White Cement)" and selected_eq == "Mill Main Control":
            st.markdown("#### ⚙️ Gearbox Sensors (5 Graphs)")
            c_m1_1, c_m1_2 = st.columns(2)
            for i in range(1, 3):
                val = eq_data[f"m1_gb_vib_{i}"] if f"m1_gb_vib_{i}" in eq_data.columns else [2.3]*len(eq_data)
                fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#00E5FF", width=2)))
                fig.update_layout(height=200, template="plotly_dark", title=f"Gearbox Vib Sensor #{i} — Tag: M1-GB-VIB-{i:02d} (mm/s)")
                c_m1_1.plotly_chart(fig, width="stretch")

            for i in range(1, 4):
                val = eq_data[f"m1_gb_tmp_{i}"] if f"m1_gb_tmp_{i}" in eq_data.columns else [59.0]*len(eq_data)
                fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#FF9100", width=2)))
                fig.update_layout(height=200, template="plotly_dark", title=f"Gearbox Temp Sensor #{i} — Tag: M1-GB-TMP-{i:02d} (°C)")
                c_m1_2.plotly_chart(fig, width="stretch")

            st.markdown("---")
            st.markdown("#### ⚡ Motor Sensors (1 Graph)")
            cur_m1 = eq_data["m1_mtr_cur_1"] if "m1_mtr_cur_1" in eq_data.columns else [140.0]*len(eq_data)
            fig_cur1 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=cur_m1, line=dict(color="#76FF03", width=2)))
            fig_cur1.update_layout(height=220, template="plotly_dark", title="Motor Current Sensor #1 — Tag: M1-MTR-CUR-01 (Amperes)")
            st.plotly_chart(fig_cur1, width="stretch")

        # 3. MILL 6 MAIN CONTROL (16 GRAPHS)
        elif selected_mill == "Mill 6" and selected_eq == "Mill Main Control":
            st.markdown("#### ⚙️ Gearbox Sensors (12 Graphs)")
            st.markdown("##### OCP Company — Gearbox Vibration Sensors (10 Channels)")
            cols_gb1 = st.columns(2)
            for i in range(1, 11):
                target = cols_gb1[0] if i % 2 != 0 else cols_gb1[1]
                val = eq_data[f"ocp_gb_vib_{i}"] if f"ocp_gb_vib_{i}" in eq_data.columns else [2.8]*len(eq_data)
                fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#00D2FF", width=2)))
                fig.update_layout(height=200, template="plotly_dark", title=f"OCP GB Vib #{i} — Tag: OCP-GB-VIB-{i:02d} (mm/s)")
                target.plotly_chart(fig, width="stretch")

            st.markdown("##### HLC Company — Gearbox Vibration Sensors (2 Channels)")
            cols_gb2 = st.columns(2)
            for i in range(1, 3):
                val = eq_data[f"hlc_gb_vib_{i}"] if f"hlc_gb_vib_{i}" in eq_data.columns else [2.4]*len(eq_data)
                fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#33FF57", width=2)))
                fig.update_layout(height=200, template="plotly_dark", title=f"HLC GB Vib #{i} — Tag: HLC-GB-VIB-{i:02d} (mm/s)")
                cols_gb2[i-1].plotly_chart(fig, width="stretch")

            st.markdown("---")
            st.markdown("#### ⚡ Motor Sensors (4 Graphs)")
            cols_mtr = st.columns(2)
            for i in range(1, 3):
                val = eq_data[f"ocp_mtr_vib_{i}"] if f"ocp_mtr_vib_{i}" in eq_data.columns else [2.1]*len(eq_data)
                fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#FFD700", width=2)))
                fig.update_layout(height=200, template="plotly_dark", title=f"OCP Motor Vib #{i} — Tag: OCP-MTR-VIB-{i:02d} (mm/s)")
                cols_mtr[0].plotly_chart(fig, width="stretch")

            for i in range(1, 3):
                val = eq_data[f"hlc_mtr_tmp_{i}"] if f"hlc_mtr_tmp_{i}" in eq_data.columns else [62.0]*len(eq_data)
                fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#FF4500", width=2)))
                fig.update_layout(height=200, template="plotly_dark", title=f"HLC Motor Temp #{i} — Tag: HLC-MTR-TMP-{i:02d} (°C)")
                cols_mtr[1].plotly_chart(fig, width="stretch")

        # 4. MILL 5 MAIN CONTROL (31 GRAPHS)
        elif selected_mill == "Mill 5" and selected_eq == "Mill Main Control":
            with st.expander("⚙️ Gearbox Section One — 23 Channels (10 OCP Vib, 10 OCP Temp, 3 HLC Vib)", expanded=True):
                st.markdown("##### OCP Company — Gearbox 1 Vibration Sensors (10 Channels)")
                c_v1, c_v2 = st.columns(2)
                for i in range(1, 11):
                    target = c_v1 if i % 2 != 0 else c_v2
                    val = eq_data[f"m5_ocp_gb1_vib_{i}"] if f"m5_ocp_gb1_vib_{i}" in eq_data.columns else [3.0]*len(eq_data)
                    fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#00E5FF", width=2)))
                    fig.update_layout(height=190, template="plotly_dark", title=f"OCP GB1 Vib #{i} — Tag: OCP-M5-GB1-VIB-{i:02d} (mm/s)")
                    target.plotly_chart(fig, width="stretch")

                st.markdown("##### OCP Company — Gearbox 1 Temperature Sensors (10 Channels)")
                c_t1, c_t2 = st.columns(2)
                for i in range(1, 11):
                    target = c_t1 if i % 2 != 0 else c_t2
                    val = eq_data[f"m5_ocp_gb1_tmp_{i}"] if f"m5_ocp_gb1_tmp_{i}" in eq_data.columns else [65.0]*len(eq_data)
                    fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#FF9100", width=2)))
                    fig.update_layout(height=190, template="plotly_dark", title=f"OCP GB1 Temp #{i} — Tag: OCP-M5-GB1-TMP-{i:02d} (°C)")
                    target.plotly_chart(fig, width="stretch")

                st.markdown("##### HLC Company — Gearbox 1 Vibration Sensors (3 Channels)")
                c_h1, c_h2, c_h3 = st.columns(3)
                cols_hlc = [c_h1, c_h2, c_h3]
                for i in range(1, 4):
                    val = eq_data[f"m5_hlc_gb1_vib_{i}"] if f"m5_hlc_gb1_vib_{i}" in eq_data.columns else [2.6]*len(eq_data)
                    fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#76FF03", width=2)))
                    fig.update_layout(height=190, template="plotly_dark", title=f"HLC GB1 Vib #{i} — Tag: HLC-M5-GB1-VIB-{i:02d} (mm/s)")
                    cols_hlc[i-1].plotly_chart(fig, width="stretch")

            with st.expander("⚙️ Gearbox Section Two — 6 Channels (HLC Temperature)", expanded=True):
                st.markdown("##### HLC Company — Gearbox 2 Temperature Sensors (6 Channels)")
                cg2_1, cg2_2 = st.columns(2)
                for i in range(1, 7):
                    target = cg2_1 if i % 2 != 0 else cg2_2
                    val = eq_data[f"m5_hlc_gb2_tmp_{i}"] if f"m5_hlc_gb2_tmp_{i}" in eq_data.columns else [68.0]*len(eq_data)
                    fig = go.Figure(go.Scatter(x=eq_data["timestamp"], y=val, line=dict(color="#FF1744", width=2)))
                    fig.update_layout(height=190, template="plotly_dark", title=f"HLC GB2 Temp #{i} — Tag: HLC-M5-GB2-TMP-{i:02d} (°C)")
                    target.plotly_chart(fig, width="stretch")

            with st.expander("⚡ Motor Subsystem — 2 Channels (HLC Temperature & Current)", expanded=True):
                cm1, cm2 = st.columns(2)
                t_m5 = eq_data["m5_hlc_mtr_tmp_1"] if "m5_hlc_mtr_tmp_1" in eq_data.columns else [64.5]*len(eq_data)
                fig_mt = go.Figure(go.Scatter(x=eq_data["timestamp"], y=t_m5, line=dict(color="#D500F9", width=2)))
                fig_mt.update_layout(height=200, template="plotly_dark", title="HLC Motor Temp #1 — Tag: HLC-M5-MTR-TMP-01 (°C)")
                cm1.plotly_chart(fig_mt, width="stretch")

                cur_m5 = eq_data["m5_hlc_mtr_cur_1"] if "m5_hlc_mtr_cur_1" in eq_data.columns else [185.0]*len(eq_data)
                fig_mc = go.Figure(go.Scatter(x=eq_data["timestamp"], y=cur_m5, line=dict(color="#651FFF", width=2)))
                fig_mc.update_layout(height=200, template="plotly_dark", title="HLC Motor Current #1 — Tag: HLC-M5-MTR-CUR-01 (Amperes)")
                cm2.plotly_chart(fig_mc, width="stretch")

        # 5. MILL 6 MAIN FILTER FAN (5 GRAPHS)
        elif selected_mill == "Mill 6" and selected_eq == "Main Filter Fan":
            v1 = eq_data["vibration_mm_s"] if "vibration_mm_s" in eq_data.columns else [2.4]*len(eq_data)
            v2 = eq_data["vibration_2_mm_s"] if "vibration_2_mm_s" in eq_data.columns else [2.6]*len(eq_data)
            power = eq_data["electrical_power_kw"] if "electrical_power_kw" in eq_data.columns else [320.0]*len(eq_data)
            speed = eq_data["motor_speed_rpm"] if "motor_speed_rpm" in eq_data.columns else [980.0]*len(eq_data)
            m_temp = eq_data["motor_temp_c"] if "motor_temp_c" in eq_data.columns else [68.0]*len(eq_data)

            st.markdown("##### 🌀 Mechanical Vibration Transmitters")
            c1, c2 = st.columns(2)
            with c1:
                fig1 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=v1, line=dict(color="#00D2FF", width=2)))
                fig1.update_layout(height=220, template="plotly_dark", title="Vibration Sensor 1 — Inlet Housing (mm/s)")
                st.plotly_chart(fig1, width="stretch")
            with c2:
                fig2 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=v2, line=dict(color="#33FF57", width=2)))
                fig2.update_layout(height=220, template="plotly_dark", title="Vibration Sensor 2 — Outlet Housing (mm/s)")
                st.plotly_chart(fig2, width="stretch")

            st.markdown("##### ⚡ Motor Driver Electrical Telemetry")
            fig3 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=power, line=dict(color="#FFD700", width=2)))
            fig3.update_layout(height=220, template="plotly_dark", title="Motor Driver — Electrical Power (kW)")
            st.plotly_chart(fig3, width="stretch")

            fig4 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=speed, line=dict(color="#FF00FF", width=2)))
            fig4.update_layout(height=220, template="plotly_dark", title="Motor Driver — Motor Speed (RPM)")
            st.plotly_chart(fig4, width="stretch")

            fig5 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=m_temp, line=dict(color="#FF4500", width=2)))
            fig5.update_layout(height=220, template="plotly_dark", title="Motor Driver — Motor Temperature (°C)")
            st.plotly_chart(fig5, width="stretch")

        # 6. MILL 5 SEPARATOR FILTER FAN (5 GRAPHS)
        elif selected_mill == "Mill 5" and selected_eq == "Separator Filter Fan":
            v1 = eq_data["vibration_mm_s"] if "vibration_mm_s" in eq_data.columns else [2.4]*len(eq_data)
            v2 = eq_data["vibration_2_mm_s"] if "vibration_2_mm_s" in eq_data.columns else [2.6]*len(eq_data)
            t1 = eq_data["temperature_c"] if "temperature_c" in eq_data.columns else [58.0]*len(eq_data)
            t2 = eq_data["temperature_2_c"] if "temperature_2_c" in eq_data.columns else [60.0]*len(eq_data)
            curr = eq_data["motor_current_a"] if "motor_current_a" in eq_data.columns else [145.0]*len(eq_data)

            c1, c2 = st.columns(2)
            with c1:
                fig1 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=v1, line=dict(color="#00D2FF", width=2)))
                fig1.update_layout(height=220, template="plotly_dark", title="Vibration Sensor 1 — Fan End (mm/s)")
                st.plotly_chart(fig1, width="stretch")
                fig3 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=t1, line=dict(color="#FF8C00", width=2)))
                fig3.update_layout(height=220, template="plotly_dark", title="Temperature Sensor 1 — Inlet Bearing (°C)")
                st.plotly_chart(fig3, width="stretch")
            with c2:
                fig2 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=v2, line=dict(color="#33FF57", width=2)))
                fig2.update_layout(height=220, template="plotly_dark", title="Vibration Sensor 2 — Motor End (mm/s)")
                st.plotly_chart(fig2, width="stretch")
                fig4 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=t2, line=dict(color="#FF33A8", width=2)))
                fig4.update_layout(height=220, template="plotly_dark", title="Temperature Sensor 2 — Outlet / Housing (°C)")
                st.plotly_chart(fig4, width="stretch")

            fig5 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=curr, line=dict(color="#D500F9", width=2)))
            fig5.update_layout(height=220, template="plotly_dark", title="Motor Current Sensor (Amperes)")
            st.plotly_chart(fig5, width="stretch")

        # 7. MILL 6 SEPARATOR & SEPARATOR FILTER FAN (4 GRAPHS)
        elif selected_mill == "Mill 6" and selected_eq in ["Dynamic Separator", "Separator Filter Fan"]:
            v1 = eq_data["vibration_mm_s"] if "vibration_mm_s" in eq_data.columns else [2.4]*len(eq_data)
            v2 = eq_data["vibration_2_mm_s"] if "vibration_2_mm_s" in eq_data.columns else [2.6]*len(eq_data)
            t1 = eq_data["temperature_c"] if "temperature_c" in eq_data.columns else [58.0]*len(eq_data)
            t2 = eq_data["temperature_2_c"] if "temperature_2_c" in eq_data.columns else [60.0]*len(eq_data)

            c1, c2 = st.columns(2)
            with c1:
                fig1 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=v1, line=dict(color="#00D2FF", width=2)))
                fig1.update_layout(height=225, template="plotly_dark", title="Vibration Sensor 1 — Drive/Fan End (mm/s)")
                st.plotly_chart(fig1, width="stretch")
                fig3 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=t1, line=dict(color="#FF8C00", width=2)))
                fig3.update_layout(height=225, template="plotly_dark", title="Temperature Sensor 1 — Bearing Housing (°C)")
                st.plotly_chart(fig3, width="stretch")
            with c2:
                fig2 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=v2, line=dict(color="#33FF57", width=2)))
                fig2.update_layout(height=225, template="plotly_dark", title="Vibration Sensor 2 — Motor/NDE (mm/s)")
                st.plotly_chart(fig2, width="stretch")
                fig4 = go.Figure(go.Scatter(x=eq_data["timestamp"], y=t2, line=dict(color="#FF33A8", width=2)))
                fig4.update_layout(height=225, template="plotly_dark", title="Temperature Sensor 2 — Motor Winding/Outlet (°C)")
                st.plotly_chart(fig4, width="stretch")

        # 8. MILL 5 DYNAMIC SEPARATOR (3 GRAPHS)
        elif selected_mill == "Mill 5" and selected_eq == "Dynamic Separator":
            p_val = eq_data["oil_pressure_bar"] if "oil_pressure_bar" in eq_data.columns else [4.2]*len(eq_data)
            t_val = eq_data["temperature_c"] if "temperature_c" in eq_data.columns else [61.5]*len(eq_data)
            i_val = eq_data["motor_current_a"] if "motor_current_a" in eq_data.columns else [145.0]*len(eq_data)

            fig_p = go.Figure(go.Scatter(x=eq_data["timestamp"], y=p_val, line=dict(color="#00E5FF", width=2)))
            fig_p.update_layout(height=220, template="plotly_dark", title="Oil Pressure Sensor (bar)")
            st.plotly_chart(fig_p, width="stretch")

            fig_t = go.Figure(go.Scatter(x=eq_data["timestamp"], y=t_val, line=dict(color="#FF9100", width=2)))
            fig_t.update_layout(height=220, template="plotly_dark", title="Bearing Temperature Sensor (°C)")
            st.plotly_chart(fig_t, width="stretch")

            fig_i = go.Figure(go.Scatter(x=eq_data["timestamp"], y=i_val, line=dict(color="#D500F9", width=2)))
            fig_i.update_layout(height=220, template="plotly_dark", title="Motor Current Sensor (Amperes)")
            st.plotly_chart(fig_i, width="stretch")

        # 9. GENERAL FALLBACK DRILL-DOWN
        else:
            v_val = eq_data["vibration_mm_s"] if "vibration_mm_s" in eq_data.columns else [2.5]*len(eq_data)
            t_val = eq_data["temperature_c"] if "temperature_c" in eq_data.columns else [55.0]*len(eq_data)

            fig_v = go.Figure(go.Scatter(x=eq_data["timestamp"], y=v_val, line=dict(color="#00D2FF", width=2)))
            fig_v.update_layout(height=225, template="plotly_dark", title="Vibration Signal RMS (mm/s)")
            st.plotly_chart(fig_v, width="stretch")

            fig_t = go.Figure(go.Scatter(x=eq_data["timestamp"], y=t_val, line=dict(color="#FF8C00", width=2)))
            fig_t.update_layout(height=225, template="plotly_dark", title="Thermal Signal (°C)")
            st.plotly_chart(fig_t, width="stretch")

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

        render_live_drilldown_charts(selected_mill, selected_eq)

    elif mill_page == "Servicing Desk & Alert Log":
        # Servicing Desk is NOT wrapped in a 3s fragment loop so button submits synchronously
        alerts_to_display = fetch_all_alerts() or shared_engine.alerts_log
        render_servicing_desk(selected_mill, alerts_to_display)
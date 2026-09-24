# views.py
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

shared_engine = get_shared_plant_engine()

def inject_silent_stream_css():
    """Injects CSS rules to lock container bounds and eliminate visual layout jitter during live SCADA updates."""
    st.markdown(
        """
        <style>
            /* Stabilize metric cards to prevent height flickering */
            div[data-testid="stMetric"] {
                background-color: #1E222A;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid #2E3440;
                transition: none !important;
            }
            div[data-testid="stMetricValue"] {
                font-size: 1.5rem !important;
                font-weight: 700;
            }
            /* Freeze Plotly wrapper bounds so graph frames don't bounce */
            .stPlotlyChart {
                min-height: 200px;
            }
            /* Smooth transitions for seamless data ticks */
            * {
                transition: background-color 0.2s ease, color 0.2s ease;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

def create_smooth_line_chart(x_data, y_data, title, color="#00D2FF", height=200):
    """Generates a Plotly chart configured with uirevision to prevent visual flickering on telemetry ticks."""
    fig = go.Figure(go.Scatter(
        x=x_data, 
        y=y_data, 
        mode="lines",
        line=dict(color=color, width=2),
        hoverinfo="x+y"
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#ECEFF4")),
        height=height,
        margin=dict(l=30, r=20, t=35, b=25),
        template="plotly_dark",
        uirevision=True,  # Keeps graph position static during live background data appends
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="#2E3440", zeroline=False)
    )
    return fig

# -------------------------------------------------------------------
# 1. GENERAL PLANT OVERVIEW MATRIX
# -------------------------------------------------------------------
@st.fragment(run_every="3s")
def render_live_overview_matrix(search_query):
    inject_silent_stream_css()
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
# 2. SUBSYSTEM OVERVIEW CARDS
# -------------------------------------------------------------------
@st.fragment(run_every="3s")
def render_live_subsystem_cards(selected_mill):
    inject_silent_stream_css()
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

                elif selected_mill == "Mill 1 (White Cement)" and eq == "Mill Main Control":
                    st.markdown("**⚙️ Gearbox Sensors**")
                    for idx in range(1, 3):
                        st.metric(f"GB Vibration #{idx}", f"{latest.get(f'm1_gb_vib_{idx}', 2.3)} mm/s")
                    for idx in range(1, 4):
                        st.metric(f"GB Temperature #{idx}", f"{latest.get(f'm1_gb_tmp_{idx}', 59.0)} °C")
                    st.markdown("**⚡ Motor Sensors**")
                    st.metric("Motor Current #1", f"{latest.get('m1_mtr_cur_1', 140.0)} A")

                elif selected_mill == "Mill 6" and eq == "Dynamic Separator":
                    st.metric("Vibration 1 (DE)", f"{latest.get('vibration_mm_s', 2.4)} mm/s")
                    st.metric("Vibration 2 (NDE)", f"{latest.get('vibration_2_mm_s', 2.6)} mm/s")
                    st.metric("Temp 1 (Upper)", f"{latest.get('temperature_c', 58.0)} °C")
                    st.metric("Temp 2 (Lower)", f"{latest.get('temperature_2_c', 60.0)} °C")
                    
                elif selected_mill == "Mill 5" and eq == "Dynamic Separator":
                    st.metric("Oil Pressure", f"{latest.get('oil_pressure_bar', 4.2)} bar")
                    st.metric("Bearing Temp", f"{latest.get('temperature_c', 61.5)} °C")
                    st.metric("Motor Current", f"{latest.get('motor_current_a', 145.0)} A")

                elif selected_mill == "Mill 6" and eq == "Separator Filter Fan":
                    st.metric("Vibration 1 (Fan)", f"{latest.get('vibration_mm_s', 2.4)} mm/s")
                    st.metric("Vibration 2 (Motor)", f"{latest.get('vibration_2_mm_s', 2.6)} mm/s")
                    st.metric("Temp 1 (Bearing)", f"{latest.get('temperature_c', 58.0)} °C")
                    st.metric("Temp 2 (Winding)", f"{latest.get('temperature_2_c', 60.0)} °C")

                elif selected_mill == "Mill 5" and eq == "Separator Filter Fan":
                    st.metric("Vibration 1 (Fan)", f"{latest.get('vibration_mm_s', 2.4)} mm/s")
                    st.metric("Vibration 2 (Motor)", f"{latest.get('vibration_2_mm_s', 2.6)} mm/s")
                    st.metric("Temp 1 (Inlet)", f"{latest.get('temperature_c', 58.0)} °C")
                    st.metric("Temp 2 (Outlet)", f"{latest.get('temperature_2_c', 60.0)} °C")
                    st.metric("Motor Current", f"{latest.get('motor_current_a', 145.0)} A")

                elif selected_mill == "Mill 6" and eq == "Main Filter Fan":
                    st.metric("Vibration 1 (Inlet)", f"{latest.get('vibration_mm_s', 2.4)} mm/s")
                    st.metric("Vibration 2 (Outlet)", f"{latest.get('vibration_2_mm_s', 2.6)} mm/s")
                    st.metric("Motor Power", f"{latest.get('electrical_power_kw', 320.0)} kW")
                    st.metric("Motor Speed", f"{latest.get('motor_speed_rpm', 980.0)} RPM")
                    st.metric("Motor Temp", f"{latest.get('motor_temp_c', 68.0)} °C")
                    
                else:
                    st.metric("Vibration RMS", f"{latest.get('vibration_mm_s', 2.5)} mm/s")
                    st.metric("Bearing Temp", f"{latest.get('temperature_c', 55.0)} °C")

# -------------------------------------------------------------------
# 3. EQUIPMENT DRILL-DOWN CHARTS (Smooth Background Telemetry Update)
# -------------------------------------------------------------------
@st.fragment(run_every="3s")
def render_live_drilldown_charts(selected_mill, selected_eq):
    inject_silent_stream_css()
    mill_df = shared_engine.df[shared_engine.df["mill"] == selected_mill]
    eq_data = mill_df[mill_df["equipment"] == selected_eq]
    
    if not eq_data.empty:
        st.markdown(f"### 📊 Live Sensor Signals — {selected_mill} ({selected_eq})")
        
        if selected_mill == "Mill 4" and selected_eq == "Mill Main Control":
            st.markdown("#### ⚙️ Gearbox Sensors (5 Graphs)")
            c_gb1, c_gb2 = st.columns(2)
            for i in range(1, 3):
                val = eq_data[f"m4_gb_vib_{i}"] if f"m4_gb_vib_{i}" in eq_data.columns else [2.5]*len(eq_data)
                fig = create_smooth_line_chart(eq_data["timestamp"], val, f"Gearbox Vib Sensor #{i} — Tag: M4-GB-VIB-{i:02d} (mm/s)", "#00D2FF")
                c_gb1.plotly_chart(fig, width="stretch", key=f"p_m4gbv_{i}")

            for i in range(1, 4):
                val = eq_data[f"m4_gb_tmp_{i}"] if f"m4_gb_tmp_{i}" in eq_data.columns else [61.0]*len(eq_data)
                fig = create_smooth_line_chart(eq_data["timestamp"], val, f"Gearbox Temp Sensor #{i} — Tag: M4-GB-TMP-{i:02d} (°C)", "#FF8C00")
                c_gb2.plotly_chart(fig, width="stretch", key=f"p_m4gbt_{i}")

            st.markdown("---")
            st.markdown("#### ⚡ Motor Sensors (6 Graphs)")
            c_m1, c_m2 = st.columns(2)
            for i in range(1, 6):
                target = c_m1 if i % 2 != 0 else c_m2
                val = eq_data[f"m4_mtr_tmp_{i}"] if f"m4_mtr_tmp_{i}" in eq_data.columns else [63.0]*len(eq_data)
                fig = create_smooth_line_chart(eq_data["timestamp"], val, f"Motor Temp Sensor #{i} — Tag: M4-MTR-TMP-{i:02d} (°C)", "#FF33A8")
                target.plotly_chart(fig, width="stretch", key=f"p_m4mt_{i}")

            cur_m4 = eq_data["m4_mtr_cur_1"] if "m4_mtr_cur_1" in eq_data.columns else [160.0]*len(eq_data)
            fig_cur = create_smooth_line_chart(eq_data["timestamp"], cur_m4, "Motor Current Sensor #1 — Tag: M4-MTR-CUR-01 (Amperes)", "#D500F9")
            st.plotly_chart(fig_cur, width="stretch", key="p_m4cur_1")

        elif selected_mill == "Mill 1 (White Cement)" and selected_eq == "Mill Main Control":
            st.markdown("#### ⚙️ Gearbox Sensors (5 Graphs)")
            c_m1_1, c_m1_2 = st.columns(2)
            for i in range(1, 3):
                val = eq_data[f"m1_gb_vib_{i}"] if f"m1_gb_vib_{i}" in eq_data.columns else [2.3]*len(eq_data)
                fig = create_smooth_line_chart(eq_data["timestamp"], val, f"Gearbox Vib Sensor #{i} — Tag: M1-GB-VIB-{i:02d} (mm/s)", "#00E5FF")
                c_m1_1.plotly_chart(fig, width="stretch", key=f"p_m1gbv_{i}")

            for i in range(1, 4):
                val = eq_data[f"m1_gb_tmp_{i}"] if f"m1_gb_tmp_{i}" in eq_data.columns else [59.0]*len(eq_data)
                fig = create_smooth_line_chart(eq_data["timestamp"], val, f"Gearbox Temp Sensor #{i} — Tag: M1-GB-TMP-{i:02d} (°C)", "#FF9100")
                c_m1_2.plotly_chart(fig, width="stretch", key=f"p_m1gbt_{i}")

            st.markdown("---")
            st.markdown("#### ⚡ Motor Sensors (1 Graph)")
            cur_m1 = eq_data["m1_mtr_cur_1"] if "m1_mtr_cur_1" in eq_data.columns else [140.0]*len(eq_data)
            fig_cur1 = create_smooth_line_chart(eq_data["timestamp"], cur_m1, "Motor Current Sensor #1 — Tag: M1-MTR-CUR-01 (Amperes)", "#76FF03")
            st.plotly_chart(fig_cur1, width="stretch", key="p_m1cur_1")

        elif selected_mill == "Mill 6" and selected_eq == "Mill Main Control":
            st.markdown("#### ⚙️ Gearbox Sensors (12 Graphs)")
            st.markdown("##### OCP Company — Gearbox Vibration Sensors (10 Channels)")
            cols_gb1 = st.columns(2)
            for i in range(1, 11):
                target = cols_gb1[0] if i % 2 != 0 else cols_gb1[1]
                val = eq_data[f"ocp_gb_vib_{i}"] if f"ocp_gb_vib_{i}" in eq_data.columns else [2.8]*len(eq_data)
                fig = create_smooth_line_chart(eq_data["timestamp"], val, f"OCP GB Vib #{i} — Tag: OCP-GB-VIB-{i:02d} (mm/s)", "#00D2FF")
                target.plotly_chart(fig, width="stretch", key=f"p_m6ocpv_{i}")

            st.markdown("##### HLC Company — Gearbox Vibration Sensors (2 Channels)")
            cols_gb2 = st.columns(2)
            for i in range(1, 3):
                val = eq_data[f"hlc_gb_vib_{i}"] if f"hlc_gb_vib_{i}" in eq_data.columns else [2.4]*len(eq_data)
                fig = create_smooth_line_chart(eq_data["timestamp"], val, f"HLC GB Vib #{i} — Tag: HLC-GB-VIB-{i:02d} (mm/s)", "#33FF57")
                cols_gb2[i-1].plotly_chart(fig, width="stretch", key=f"p_m6hlcv_{i}")

            st.markdown("---")
            st.markdown("#### ⚡ Motor Sensors (4 Graphs)")
            cols_mtr = st.columns(2)
            for i in range(1, 3):
                val = eq_data[f"ocp_mtr_vib_{i}"] if f"ocp_mtr_vib_{i}" in eq_data.columns else [2.1]*len(eq_data)
                fig = create_smooth_line_chart(eq_data["timestamp"], val, f"OCP Motor Vib #{i} — Tag: OCP-MTR-VIB-{i:02d} (mm/s)", "#FFD700")
                cols_mtr[0].plotly_chart(fig, width="stretch", key=f"p_m6ocpmv_{i}")

            for i in range(1, 3):
                val = eq_data[f"hlc_mtr_tmp_{i}"] if f"hlc_mtr_tmp_{i}" in eq_data.columns else [62.0]*len(eq_data)
                fig = create_smooth_line_chart(eq_data["timestamp"], val, f"HLC Motor Temp #{i} — Tag: HLC-MTR-TMP-{i:02d} (°C)", "#FF4500")
                cols_mtr[1].plotly_chart(fig, width="stretch", key=f"p_m6hlcmt_{i}")

        elif selected_mill == "Mill 5" and selected_eq == "Mill Main Control":
            with st.expander("⚙️ Gearbox Section One — 23 Channels (10 OCP Vib, 10 OCP Temp, 3 HLC Vib)", expanded=True):
                st.markdown("##### OCP Company — Gearbox 1 Vibration Sensors (10 Channels)")
                c_v1, c_v2 = st.columns(2)
                for i in range(1, 11):
                    target = c_v1 if i % 2 != 0 else c_v2
                    val = eq_data[f"m5_ocp_gb1_vib_{i}"] if f"m5_ocp_gb1_vib_{i}" in eq_data.columns else [3.0]*len(eq_data)
                    fig = create_smooth_line_chart(eq_data["timestamp"], val, f"OCP GB1 Vib #{i} — Tag: OCP-M5-GB1-VIB-{i:02d} (mm/s)", "#00E5FF", 190)
                    target.plotly_chart(fig, width="stretch", key=f"p_m5ocpv1_{i}")

                st.markdown("##### OCP Company — Gearbox 1 Temperature Sensors (10 Channels)")
                c_t1, c_t2 = st.columns(2)
                for i in range(1, 11):
                    target = c_t1 if i % 2 != 0 else c_t2
                    val = eq_data[f"m5_ocp_gb1_tmp_{i}"] if f"m5_ocp_gb1_tmp_{i}" in eq_data.columns else [65.0]*len(eq_data)
                    fig = create_smooth_line_chart(eq_data["timestamp"], val, f"OCP GB1 Temp #{i} — Tag: OCP-M5-GB1-TMP-{i:02d} (°C)", "#FF9100", 190)
                    target.plotly_chart(fig, width="stretch", key=f"p_m5ocpt1_{i}")

                st.markdown("##### HLC Company — Gearbox 1 Vibration Sensors (3 Channels)")
                c_h1, c_h2, c_h3 = st.columns(3)
                cols_hlc = [c_h1, c_h2, c_h3]
                for i in range(1, 4):
                    val = eq_data[f"m5_hlc_gb1_vib_{i}"] if f"m5_hlc_gb1_vib_{i}" in eq_data.columns else [2.6]*len(eq_data)
                    fig = create_smooth_line_chart(eq_data["timestamp"], val, f"HLC GB1 Vib #{i} — Tag: HLC-M5-GB1-VIB-{i:02d} (mm/s)", "#76FF03", 190)
                    cols_hlc[i-1].plotly_chart(fig, width="stretch", key=f"p_m5hlcv1_{i}")

            with st.expander("⚙️ Gearbox Section Two — 6 Channels (HLC Temperature)", expanded=True):
                st.markdown("##### HLC Company — Gearbox 2 Temperature Sensors (6 Channels)")
                cg2_1, cg2_2 = st.columns(2)
                for i in range(1, 7):
                    target = cg2_1 if i % 2 != 0 else cg2_2
                    val = eq_data[f"m5_hlc_gb2_tmp_{i}"] if f"m5_hlc_gb2_tmp_{i}" in eq_data.columns else [68.0]*len(eq_data)
                    fig = create_smooth_line_chart(eq_data["timestamp"], val, f"HLC GB2 Temp #{i} — Tag: HLC-M5-GB2-TMP-{i:02d} (°C)", "#FF1744", 190)
                    target.plotly_chart(fig, width="stretch", key=f"p_m5hlct2_{i}")

            with st.expander("⚡ Motor Subsystem — 2 Channels (HLC Temperature & Current)", expanded=True):
                cm1, cm2 = st.columns(2)
                t_m5 = eq_data["m5_hlc_mtr_tmp_1"] if "m5_hlc_mtr_tmp_1" in eq_data.columns else [64.5]*len(eq_data)
                fig_mt = create_smooth_line_chart(eq_data["timestamp"], t_m5, "HLC Motor Temp #1 — Tag: HLC-M5-MTR-TMP-01 (°C)", "#D500F9")
                cm1.plotly_chart(fig_mt, width="stretch", key="p_m5mt_1")

                cur_m5 = eq_data["m5_hlc_mtr_cur_1"] if "m5_hlc_mtr_cur_1" in eq_data.columns else [185.0]*len(eq_data)
                fig_mc = create_smooth_line_chart(eq_data["timestamp"], cur_m5, "HLC Motor Current #1 — Tag: HLC-M5-MTR-CUR-01 (Amperes)", "#651FFF")
                cm2.plotly_chart(fig_mc, width="stretch", key="p_m5mc_1")

        elif selected_mill == "Mill 6" and selected_eq == "Main Filter Fan":
            v1 = eq_data["vibration_mm_s"] if "vibration_mm_s" in eq_data.columns else [2.4]*len(eq_data)
            v2 = eq_data["vibration_2_mm_s"] if "vibration_2_mm_s" in eq_data.columns else [2.6]*len(eq_data)
            power = eq_data["electrical_power_kw"] if "electrical_power_kw" in eq_data.columns else [320.0]*len(eq_data)
            speed = eq_data["motor_speed_rpm"] if "motor_speed_rpm" in eq_data.columns else [980.0]*len(eq_data)
            m_temp = eq_data["motor_temp_c"] if "motor_temp_c" in eq_data.columns else [68.0]*len(eq_data)

            st.markdown("##### 🌀 Mechanical Vibration Transmitters")
            c1, c2 = st.columns(2)
            with c1:
                fig1 = create_smooth_line_chart(eq_data["timestamp"], v1, "Vibration Sensor 1 — Inlet Housing (mm/s)", "#00D2FF", 220)
                st.plotly_chart(fig1, width="stretch", key="p_m6mff_v1")
            with c2:
                fig2 = create_smooth_line_chart(eq_data["timestamp"], v2, "Vibration Sensor 2 — Outlet Housing (mm/s)", "#33FF57", 220)
                st.plotly_chart(fig2, width="stretch", key="p_m6mff_v2")

            st.markdown("##### ⚡ Motor Driver Electrical Telemetry")
            fig3 = create_smooth_line_chart(eq_data["timestamp"], power, "Motor Driver — Electrical Power (kW)", "#FFD700", 220)
            st.plotly_chart(fig3, width="stretch", key="p_m6mff_p")

            fig4 = create_smooth_line_chart(eq_data["timestamp"], speed, "Motor Driver — Motor Speed (RPM)", "#FF00FF", 220)
            st.plotly_chart(fig4, width="stretch", key="p_m6mff_s")

            fig5 = create_smooth_line_chart(eq_data["timestamp"], m_temp, "Motor Driver — Motor Temperature (°C)", "#FF4500", 220)
            st.plotly_chart(fig5, width="stretch", key="p_m6mff_t")

        elif selected_mill == "Mill 5" and selected_eq == "Separator Filter Fan":
            v1 = eq_data["vibration_mm_s"] if "vibration_mm_s" in eq_data.columns else [2.4]*len(eq_data)
            v2 = eq_data["vibration_2_mm_s"] if "vibration_2_mm_s" in eq_data.columns else [2.6]*len(eq_data)
            t1 = eq_data["temperature_c"] if "temperature_c" in eq_data.columns else [58.0]*len(eq_data)
            t2 = eq_data["temperature_2_c"] if "temperature_2_c" in eq_data.columns else [60.0]*len(eq_data)
            curr = eq_data["motor_current_a"] if "motor_current_a" in eq_data.columns else [145.0]*len(eq_data)

            c1, c2 = st.columns(2)
            with c1:
                fig1 = create_smooth_line_chart(eq_data["timestamp"], v1, "Vibration Sensor 1 — Fan End (mm/s)", "#00D2FF", 220)
                st.plotly_chart(fig1, width="stretch", key="p_m5sff_v1")
                fig3 = create_smooth_line_chart(eq_data["timestamp"], t1, "Temperature Sensor 1 — Inlet Bearing (°C)", "#FF8C00", 220)
                st.plotly_chart(fig3, width="stretch", key="p_m5sff_t1")
            with c2:
                fig2 = create_smooth_line_chart(eq_data["timestamp"], v2, "Vibration Sensor 2 — Motor End (mm/s)", "#33FF57", 220)
                st.plotly_chart(fig2, width="stretch", key="p_m5sff_v2")
                fig4 = create_smooth_line_chart(eq_data["timestamp"], t2, "Temperature Sensor 2 — Outlet / Housing (°C)", "#FF33A8", 220)
                st.plotly_chart(fig4, width="stretch", key="p_m5sff_t2")

            fig5 = create_smooth_line_chart(eq_data["timestamp"], curr, "Motor Current Sensor (Amperes)", "#D500F9", 220)
            st.plotly_chart(fig5, width="stretch", key="p_m5sff_c")

        elif selected_mill == "Mill 6" and selected_eq in ["Dynamic Separator", "Separator Filter Fan"]:
            v1 = eq_data["vibration_mm_s"] if "vibration_mm_s" in eq_data.columns else [2.4]*len(eq_data)
            v2 = eq_data["vibration_2_mm_s"] if "vibration_2_mm_s" in eq_data.columns else [2.6]*len(eq_data)
            t1 = eq_data["temperature_c"] if "temperature_c" in eq_data.columns else [58.0]*len(eq_data)
            t2 = eq_data["temperature_2_c"] if "temperature_2_c" in eq_data.columns else [60.0]*len(eq_data)

            c1, c2 = st.columns(2)
            with c1:
                fig1 = create_smooth_line_chart(eq_data["timestamp"], v1, "Vibration Sensor 1 — Drive/Fan End (mm/s)", "#00D2FF", 225)
                st.plotly_chart(fig1, width="stretch", key=f"p_m6s_{selected_eq}_v1")
                fig3 = create_smooth_line_chart(eq_data["timestamp"], t1, "Temperature Sensor 1 — Bearing Housing (°C)", "#FF8C00", 225)
                st.plotly_chart(fig3, width="stretch", key=f"p_m6s_{selected_eq}_t1")
            with c2:
                fig2 = create_smooth_line_chart(eq_data["timestamp"], v2, "Vibration Sensor 2 — Motor/NDE (mm/s)", "#33FF57", 225)
                st.plotly_chart(fig2, width="stretch", key=f"p_m6s_{selected_eq}_v2")
                fig4 = create_smooth_line_chart(eq_data["timestamp"], t2, "Temperature Sensor 2 — Motor Winding/Outlet (°C)", "#FF33A8", 225)
                st.plotly_chart(fig4, width="stretch", key=f"p_m6s_{selected_eq}_t2")

        elif selected_mill == "Mill 5" and selected_eq == "Dynamic Separator":
            p_val = eq_data["oil_pressure_bar"] if "oil_pressure_bar" in eq_data.columns else [4.2]*len(eq_data)
            t_val = eq_data["temperature_c"] if "temperature_c" in eq_data.columns else [61.5]*len(eq_data)
            i_val = eq_data["motor_current_a"] if "motor_current_a" in eq_data.columns else [145.0]*len(eq_data)

            fig_p = create_smooth_line_chart(eq_data["timestamp"], p_val, "Oil Pressure Sensor (bar)", "#00E5FF", 220)
            st.plotly_chart(fig_p, width="stretch", key="p_m5ds_p")

            fig_t = create_smooth_line_chart(eq_data["timestamp"], t_val, "Bearing Temperature Sensor (°C)", "#FF9100", 220)
            st.plotly_chart(fig_t, width="stretch", key="p_m5ds_t")

            fig_i = create_smooth_line_chart(eq_data["timestamp"], i_val, "Motor Current Sensor (Amperes)", "#D500F9", 220)
            st.plotly_chart(fig_i, width="stretch", key="p_m5ds_i")

        else:
            v_val = eq_data["vibration_mm_s"] if "vibration_mm_s" in eq_data.columns else [2.5]*len(eq_data)
            t_val = eq_data["temperature_c"] if "temperature_c" in eq_data.columns else [55.0]*len(eq_data)

            fig_v = create_smooth_line_chart(eq_data["timestamp"], v_val, "Vibration Signal RMS (mm/s)", "#00D2FF", 225)
            st.plotly_chart(fig_v, width="stretch", key="p_gen_v")

            fig_t = create_smooth_line_chart(eq_data["timestamp"], t_val, "Thermal Signal (°C)", "#FF8C00", 225)
            st.plotly_chart(fig_t, width="stretch", key="p_gen_t")
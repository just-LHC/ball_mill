import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from mock_data import generate_telemetry, fetch_single_live_reading, simple_health_score, EQUIPMENT_LIST

# Page configuration
st.set_page_config(page_title="Mill 6 - Live PdM Dashboard", layout="wide")

# Initialize global dataset in Session State
if "df" not in st.session_state:
    st.session_state.df = generate_telemetry(50)

# Sidebar
st.sidebar.title("Mill 6 Monitoring")
page = st.sidebar.radio("Navigate View Level", ["Overview (Mill 6)", "Equipment Drill-Down"])

# Live toggle switch
st.sidebar.markdown("---")
streaming_active = st.sidebar.toggle("Live Telemetry Stream", value=True)


# -------------------------------------------------------------------
# LIVE STREAMING FRAGMENT (Auto-refreshes independently every 3 seconds)
# -------------------------------------------------------------------
@st.fragment(run_every="3s" if streaming_active else None)
def render_live_dashboard(selected_page):
    # 1. Fetch new live sensor data and append to history
    if streaming_active:
        new_packet = fetch_single_live_reading()
        st.session_state.df = pd.concat([st.session_state.df, new_packet], ignore_index=True)
        # Keep buffer to last 1000 records to prevent memory lag
        st.session_state.df = st.session_state.df.tail(1000)

    current_df = st.session_state.df

    # ---------------------------------------------------------------
    # PAGE 1: OVERVIEW VIEW
    # ---------------------------------------------------------------
    if selected_page == "Overview (Mill 6)":
        st.title("Mill 6 - High Level Overview")
        st.caption("Live streaming updates active." if streaming_active else "Stream paused.")
        
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
    # PAGE 2: DRILL-DOWN VIEW (Industrial ISA-101 Color Scheme)
    # ---------------------------------------------------------------
    elif selected_page == "Equipment Drill-Down":
        st.title("Equipment Detailed View")
        
        selected_eq = st.selectbox("Select Equipment", EQUIPMENT_LIST)
        eq_data = current_df[current_df["equipment"] == selected_eq]
        latest = eq_data.iloc[-1]
        
        health = simple_health_score(latest["vibration_mm_s"], latest["temperature_c"])
        
        # Header Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Overall Health Index", f"{health}%")
        m2.metric("Latest Vibration", f"{latest['vibration_mm_s']} mm/s")
        m3.metric("Latest Temperature", f"{latest['temperature_c']} °C")
        
        st.markdown("---")
        st.subheader(f"Real-Time Telemetry Trends: {selected_eq}")

        # Industrial Threshold Values (ISO 10816 Standards)
        VIB_WARN = 4.5
        VIB_CRIT = 7.0
        TEMP_WARN = 75.0
        TEMP_CRIT = 90.0

        # Industrial Theme Palette
        COLOR_VIB = "#00D2FF"     # Cyan (Vibration signal)
        COLOR_TEMP = "#FF8C00"    # Amber/Coral (Temperature signal)
        COLOR_WARN = "#F1C40F"    # Industrial Yellow (Warning zone)
        COLOR_CRIT = "#E74C3C"    # Industrial Red (Critical zone)
        GRID_COLOR = "#2A2D34"    # Subtle dark grid line

        # -----------------------------------------------------------
        # GRAPH 1: VIBRATION TREND (Cyan / Electric Blue)
        # -----------------------------------------------------------
        fig_vib = go.Figure()
        fig_vib.add_trace(go.Scatter(
            x=eq_data["timestamp"], 
            y=eq_data["vibration_mm_s"], 
            name="Vibration (mm/s)", 
            line=dict(color=COLOR_VIB, width=2.5)
        ))
        
        # ISO Warning Line
        fig_vib.add_hline(
            y=VIB_WARN, line_dash="dash", line_color=COLOR_WARN, line_width=1.5,
            annotation_text="Warning (4.5 mm/s)", annotation_position="top right",
            annotation_font_color=COLOR_WARN
        )
        # ISO Critical Line
        fig_vib.add_hline(
            y=VIB_CRIT, line_dash="dash", line_color=COLOR_CRIT, line_width=1.5,
            annotation_text="Critical (7.0 mm/s)", annotation_position="top right",
            annotation_font_color=COLOR_CRIT
        )

        fig_vib.update_layout(
            height=320,
            template="plotly_dark",
            xaxis=dict(title="Time", showgrid=True, gridcolor=GRID_COLOR),
            yaxis=dict(
                title=dict(text="Vibration (mm/s RMS)", font=dict(color=COLOR_VIB, size=13)),
                tickfont=dict(color=COLOR_VIB),
                showgrid=True,
                gridcolor=GRID_COLOR
            ),
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_vib, use_container_width=True)

        # -----------------------------------------------------------
        # GRAPH 2: TEMPERATURE TREND (Amber / Orange)
        # -----------------------------------------------------------
        fig_temp = go.Figure()
        fig_temp.add_trace(go.Scatter(
            x=eq_data["timestamp"], 
            y=eq_data["temperature_c"], 
            name="Temperature (°C)", 
            line=dict(color=COLOR_TEMP, width=2.5)
        ))

        # Thermal Warning Line
        fig_temp.add_hline(
            y=TEMP_WARN, line_dash="dash", line_color=COLOR_WARN, line_width=1.5,
            annotation_text="Warning (75.0 °C)", annotation_position="top right",
            annotation_font_color=COLOR_WARN
        )
        # Thermal Critical Line
        fig_temp.add_hline(
            y=TEMP_CRIT, line_dash="dash", line_color=COLOR_CRIT, line_width=1.5,
            annotation_text="Critical (90.0 °C)", annotation_position="top right",
            annotation_font_color=COLOR_CRIT
        )

        fig_temp.update_layout(
            height=320,
            template="plotly_dark",
            xaxis=dict(title="Time", showgrid=True, gridcolor=GRID_COLOR),
            yaxis=dict(
                title=dict(text="Temperature (°C)", font=dict(color=COLOR_TEMP, size=13)),
                tickfont=dict(color=COLOR_TEMP),
                showgrid=True,
                gridcolor=GRID_COLOR
            ),
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_temp, use_container_width=True)

# Call the fragment function
render_live_dashboard(page)
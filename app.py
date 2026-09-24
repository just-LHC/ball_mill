import streamlit as st

from mock_data import get_shared_plant_engine, PLANT_MILLS, MILL_EQUIPMENT_MAP
from db_engine import fetch_all_alerts
from ui_components import render_sidebar_auth, render_global_header, render_servicing_desk
from views import render_live_overview_matrix, render_live_subsystem_cards, render_live_drilldown_charts

st.set_page_config(page_title="LafargeHolcim Ivory Coast - Industrial PdM Suite", layout="wide")

# Session State Initializations
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
        alerts_to_display = fetch_all_alerts() or shared_engine.alerts_log
        render_servicing_desk(selected_mill, alerts_to_display)
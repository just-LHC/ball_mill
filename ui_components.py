from datetime import datetime
import streamlit as st
import pandas as pd
from sqlalchemy import text
from ml_engine import retrain_specific_equipment_model
from db_engine import fetch_all_alerts, get_db_engine
from mock_data import get_shared_plant_engine

# User Authentication Database
USER_CREDENTIALS = {
    "op_cotedivoire": {"password": "cement_operator", "role": "Operator", "name": "Control Room Operator"},
    "admin_pdm": {"password": "lafarge_admin", "role": "Reliability Engineer", "name": "Lead Reliability Engineer"}
}

def render_sidebar_auth():
    """Renders login controls and user role management in the sidebar."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user_role = None
        st.session_state.user_name = ""

    st.sidebar.markdown("### 🔐 User Authentication")
    if not st.session_state.authenticated:
        username = st.sidebar.text_input("Username", key="login_user")
        password = st.sidebar.text_input("Password", type="password", key="login_pass")
        if st.sidebar.button("Login"):
            if username in USER_CREDENTIALS and USER_CREDENTIALS[username]["password"] == password:
                st.session_state.authenticated = True
                st.session_state.user_role = USER_CREDENTIALS[username]["role"]
                st.session_state.user_name = USER_CREDENTIALS[username]["name"]
                st.sidebar.success(f"Logged in as {st.session_state.user_name}")
                st.rerun()
            else:
                st.sidebar.error("Invalid credentials")
    else:
        st.sidebar.info(f"👤 **User:** {st.session_state.user_name}\n\n🏅 **Role:** {st.session_state.user_role}")
        if st.sidebar.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.user_role = None
            st.session_state.user_name = ""
            st.rerun()

    st.sidebar.markdown("---")

def render_global_header():
    """Renders top corporate banner and active search jump-routing bar."""
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
            placeholder="🔍 Search tag (e.g. 611-SEP-01) or mill (e.g. Mill 6)...",
            label_visibility="collapsed",
            key="global_header_search"
        )

    st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)

    if "last_processed_search" not in st.session_state:
        st.session_state["last_processed_search"] = ""

    current_search = search_query.strip().lower()

    if current_search and current_search != st.session_state["last_processed_search"]:
        st.session_state["last_processed_search"] = current_search
        
        tag_map = {
            "611-sep-01": "Dynamic Separator",
            "vib-611-sep01-r": "Dynamic Separator",
            "tit-611-sep01-b1": "Dynamic Separator",
            "separator": "Dynamic Separator",
            "611-fn-sep": "Separator Filter Fan",
            "vib-611-fns-r": "Separator Filter Fan",
            "611-ml-drv": "Mill Main Control",
            "vib-611-mld-gb": "Mill Main Control",
            "drive": "Mill Main Control",
            "611-fn-main": "Main Filter Fan",
            "vib-611-fnm-de": "Main Filter Fan"
        }

        should_rerun = False

        for mill in ["Mill 1 (White Cement)", "Mill 4", "Mill 5", "Mill 6"]:
            if mill.lower() in current_search:
                st.session_state["nav_main_view"] = "Individual Mill Monitor"
                st.session_state["nav_selected_mill"] = mill
                should_rerun = True
                break

        for tag, eq_name in tag_map.items():
            if tag in current_search:
                st.session_state["nav_main_view"] = "Individual Mill Monitor"
                st.session_state["nav_mill_page"] = "Equipment Drill-Down"
                st.session_state["nav_selected_eq"] = eq_name
                should_rerun = True
                break

        if should_rerun:
            st.rerun()

    elif not current_search:
        st.session_state["last_processed_search"] = ""

    return search_query

def render_servicing_desk(selected_mill: str, alerts_to_display: list):
    """Renders the RBAC-protected servicing desk form and updates both PostgreSQL DB and local memory."""
    st.subheader(f"🛠️ {selected_mill} - Servicing Desk & Shift Handover")
    
    shared_engine = get_shared_plant_engine()

    # 1. Fetch live alerts directly from central Supabase PostgreSQL
    all_db_alerts = fetch_all_alerts()
    if not all_db_alerts:
        all_db_alerts = shared_engine.alerts_log

    # Apply any session_state servicing overrides immediately
    if "serviced_alert_overrides" not in st.session_state:
        st.session_state["serviced_alert_overrides"] = {}

    for alert in all_db_alerts:
        a_id = str(alert.get("id"))
        if a_id in st.session_state["serviced_alert_overrides"]:
            alert["status"] = st.session_state["serviced_alert_overrides"][a_id]["status"]
            alert["operator_notes"] = st.session_state["serviced_alert_overrides"][a_id]["notes"]

    mill_alerts = [
        a for a in all_db_alerts 
        if str(a.get("mill", "")).strip().lower() == selected_mill.strip().lower() 
        or str(a.get("mill_name", "")).strip().lower() == selected_mill.strip().lower()
    ]
    
    if not mill_alerts:
        st.info(f"No active or historical alerts recorded for {selected_mill}.")
        return

    m_df = pd.DataFrame(mill_alerts)
    m_df["datetime_obj"] = pd.to_datetime(m_df["timestamp"])
    now = datetime.now()
    
    st.markdown("##### ⏱️ Shift Log & Export Timeframe Filter")
    f_col1, f_col2 = st.columns([2, 2])
    
    with f_col1:
        time_frame = st.selectbox(
            "Select Export Timeframe:",
            ["All Recorded Alerts", "Today Only", "Last 24 Hours", "Last 7 Days", "Last 30 Days", "Custom Range"],
            key=f"export_tf_{selected_mill}"
        )
    
    filtered_export_df = m_df.copy()
    if time_frame == "Today Only":
        filtered_export_df = m_df[m_df["datetime_obj"].dt.date == now.date()]
    elif time_frame == "Last 24 Hours":
        cutoff = now - pd.Timedelta(hours=24)
        filtered_export_df = m_df[m_df["datetime_obj"] >= cutoff]
    elif time_frame == "Last 7 Days":
        cutoff = now - pd.Timedelta(days=7)
        filtered_export_df = m_df[m_df["datetime_obj"] >= cutoff]
    elif time_frame == "Last 30 Days":
        cutoff = now - pd.Timedelta(days=30)
        filtered_export_df = m_df[m_df["datetime_obj"] >= cutoff]
    elif time_frame == "Custom Range":
        with f_col2:
            date_range = st.date_input(
                "Select Start & End Dates:",
                value=(now.date() - pd.Timedelta(days=7), now.date()),
                key=f"custom_dates_{selected_mill}"
            )
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_date, end_date = date_range
                filtered_export_df = m_df[
                    (m_df["datetime_obj"].dt.date >= start_date) & 
                    (m_df["datetime_obj"].dt.date <= end_date)
                ]

    export_ready_df = filtered_export_df.drop(columns=["datetime_obj"])

    st.download_button(
        label=f"📄 Export Shift Handover Log ({len(export_ready_df)} Records - CSV)",
        data=export_ready_df.to_csv(index=False),
        file_name=f"Shift_Handover_{selected_mill.replace(' ', '_')}_{time_frame.replace(' ', '_')}_{now.strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key=f"download_btn_{selected_mill}"
    )
    
    display_cols = [col for col in ["id", "timestamp", "equipment", "severity", "issue", "status", "operator_notes"] if col in export_ready_df.columns]
    st.dataframe(
        export_ready_df[display_cols],
        width="stretch",
        hide_index=True
    )
    
    st.markdown("---")
    st.subheader(f"Service & Clear Alert ({selected_mill})")
    
    active_mill_alerts = [a for a in mill_alerts if "ACTIVE" in str(a.get("status", "")).upper()]
    
    if active_mill_alerts:
        alert_options = {f"Alert #{a['id']} - {a['equipment']} ({a['timestamp']})": a['id'] for a in active_mill_alerts}
        selected_alert_str = st.selectbox("Select Alert to Resolve:", list(alert_options.keys()))
        selected_id = alert_options[selected_alert_str]
        selected_rec = next(a for a in mill_alerts if str(a["id"]) == str(selected_id))

        is_admin = (st.session_state.get("user_role") == "Reliability Engineer")

        with st.form(key=f"form_service_{selected_mill}_{selected_id}"):
            operator_name = st.text_input(
                "Technician Name / Employee ID:", 
                value=st.session_state.get("user_name", ""),
                key=f"input_op_{selected_mill}_{selected_id}"
            )
            
            alert_feedback_type = st.radio(
                "Feedback for ML Model:",
                ["Genuine Issue (Confirmed Failure/Wear)", "False Alarm (Operational Spike)"],
                disabled=not is_admin,
                help="Only Reliability Engineers can confirm or invalidate ML model baseline feedback.",
                key=f"input_fb_{selected_mill}_{selected_id}"
            )
            
            action_taken = st.text_area("Maintenance Action Taken:", key=f"input_act_{selected_mill}_{selected_id}")
            button_label = "Submit & Retrain ML Model" if is_admin else "Submit Maintenance Note (Pending Engineer Review)"
            
            submitted = st.form_submit_button(button_label)
            
            if submitted:
                if operator_name.strip() and action_taken.strip():
                    serviced_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    new_status = "SERVICED / CLOSED" if is_admin else "ACTIVE / OPERATOR NOTE ADDED"
                    notes = (
                        f"Approved & Serviced by {operator_name} ({st.session_state.user_role}) at {serviced_time}. Action: {action_taken}"
                        if is_admin else 
                        f"Operator Note by {operator_name} at {serviced_time}: {action_taken} (Pending Sign-off)"
                    )
                    
                    # 1. Update session state overrides for instant UI reflection
                    st.session_state["serviced_alert_overrides"][str(selected_id)] = {
                        "status": new_status,
                        "notes": notes
                    }

                    # 2. Update local shared memory in mock_data
                    for in_mem_alert in shared_engine.alerts_log:
                        if str(in_mem_alert.get("id")) == str(selected_id):
                            in_mem_alert["status"] = new_status
                            in_mem_alert["operator_notes"] = notes
                            break

                    # 3. Direct PostgreSQL Update with explicit commit
                    try:
                        engine = get_db_engine()
                        update_sql = text("UPDATE plc_alerts SET status = :status, operator_notes = :notes WHERE CAST(id AS TEXT) = :str_id;")
                        with engine.connect() as conn:
                            conn.execute(update_sql, {"status": new_status, "notes": notes, "str_id": str(selected_id)})
                            conn.commit()
                    except Exception as e:
                        print(f"[DB SERVICING UPDATE ERROR] {e}")

                    # 4. Retrain ML model if closed by Reliability Engineer
                    if is_admin:
                        was_true_failure = True if "Genuine Issue" in alert_feedback_type else False
                        vib_snap = float(selected_rec.get("vibration_snapshot", 5.0))
                        temp_snap = float(selected_rec.get("temperature_snapshot", 70.0))
                        
                        try:
                            retrain_specific_equipment_model(
                                mill=selected_rec.get("mill", selected_mill),
                                equipment=selected_rec.get("equipment", ""),
                                feedback_samples=[[vib_snap, temp_snap]],
                                was_true_failure=was_true_failure
                            )
                        except Exception as e:
                            print(f"[ML RETRAIN ERROR] {e}")

                    st.cache_data.clear()
                    st.success(f"✅ Alert #{selected_id} successfully updated to '{new_status}'!")
                    st.rerun()
                else:
                    st.error("⚠️ Please enter technician name and action taken before submitting.")
    else:
        st.success(f"🎉 All alerts for {selected_mill} have been serviced.")
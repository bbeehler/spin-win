import streamlit as st
import pandas as pd
from supabase import create_client

# Connect to database
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

st.title("Promotion Admin Console")

# Secure Login
with st.sidebar.form("login_form"):
    st.header("Admin Login")
    admin_pass = st.text_input("Password", type="password")
    submit_login = st.form_submit_button("Log In")

expected_pass = st.secrets.get("ADMIN_PASSWORD", "HardRock2026")

if admin_pass != expected_pass:
    st.warning("Please enter the admin password in the sidebar and click 'Log In' to view this page.")
    st.stop()

# Create Tabs for Organization
tab_analytics, tab_setup = st.tabs(["📊 Live Analytics", "⚙️ Setup & Inventory"])

# -----------------------------------------
# TAB 2: SETUP & INVENTORY
# -----------------------------------------
with tab_setup:
    st.header("1. Create a New Promotion Event")
    st.write("Creating a new event will automatically make it the active promotion on the main wheel.")
    
    with st.form("new_event_form"):
        event_name = st.text_input("Event Name (e.g., Summer Concert Promo)")
        submit_event = st.form_submit_button("Create & Activate Event")
        
        if submit_event and event_name:
            supabase.table("events").update({"is_active": False}).neq("name", "placeholder").execute()
            supabase.table("events").insert({"name": event_name, "is_active": True}).execute()
            st.success(f"Event '{event_name}' created successfully!")
            st.rerun() 

    st.divider()

    st.header("2. Add Prizes to Active Event")
    active_events = supabase.table("events").select("*").eq("is_active", True).execute()
    
    if active_events.data:
        current_event = active_events.data[0]
        st.info(f"Currently managing inventory for: **{current_event['name']}**")
        
        with st.form("new_prize_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                prize_name = st.text_input("Prize Name")
            with col2:
                prize_value = st.number_input("Value ($)", min_value=0.0, value=15.0)
            with col3:
                prize_qty = st.number_input("Total Quantity", min_value=1, value=50)
            
            submit_prize = st.form_submit_button("Add Prize to Inventory")
            
            if submit_prize and prize_name:
                supabase.table("prizes").insert({
                    "event_id": current_event['id'],
                    "name": prize_name,
                    "value": prize_value,
                    "total_quantity": prize_qty,
                    "remaining_quantity": prize_qty
                }).execute()
                st.success(f"Added {prize_qty}x {prize_name} to the vault!")
                st.rerun()
                
        st.divider()

        # --- NEW MANAGE PRIZES SECTION ---
        st.header("3. Manage Existing Prizes")
        
        # Fetch prizes for the current active event
        current_prizes = supabase.table("prizes").select("*").eq("event_id", current_event['id']).execute()
        
        if current_prizes.data:
            # Create a dictionary to easily map the selected name back to its full database row
            prize_dict = {p['name']: p for p in current_prizes.data}
            
            selected_prize_name = st.selectbox("Select a prize to edit or delete:", options=["-- Select a Prize --"] + list(prize_dict.keys()))
            
            if selected_prize_name != "-- Select a Prize --":
                selected_prize = prize_dict[selected_prize_name]
                
                with st.expander(f"Editing: {selected_prize['name']}", expanded=True):
                    with st.form(f"edit_form_{selected_prize['id']}"):
                        col1, col2 = st.columns(2)
                        col3, col4 = st.columns(2)
                        
                        with col1:
                            new_name = st.text_input("Name", value=selected_prize['name'])
                        with col2:
                            new_value = st.number_input("Value ($)", min_value=0.0, value=float(selected_prize['value']))
                        with col3:
                            new_total = st.number_input("Total Quantity", min_value=0, value=int(selected_prize['total_quantity']))
                        with col4:
                            new_remaining = st.number_input("Remaining Quantity", min_value=0, value=int(selected_prize['remaining_quantity']))
                            
                        submit_update = st.form_submit_button("Save Changes")
                        
                        if submit_update:
                            supabase.table("prizes").update({
                                "name": new_name,
                                "value": new_value,
                                "total_quantity": new_total,
                                "remaining_quantity": new_remaining
                            }).eq("id", selected_prize['id']).execute()
                            st.success("Prize updated successfully!")
                            st.rerun()
                    
                    # Delete button placed outside the form to prevent accidental submission
                    st.write("---")
                    if st.button("🚨 Delete This Prize", type="primary"):
                        supabase.table("prizes").delete().eq("id", selected_prize['id']).execute()
                        st.success(f"Prize '{selected_prize['name']}' deleted!")
                        st.rerun()
        else:
            st.info("No prizes available to manage for this event.")
            
    else:
        st.warning("Please create an active event above before managing prizes.")

# -----------------------------------------
# TAB 1: LIVE ANALYTICS
# -----------------------------------------
with tab_analytics:
    st.header("Live Event Analytics")

    event_response = supabase.table("events").select("*").eq("is_active", True).execute()

    if event_response.data:
        current_event = event_response.data[0]
        st.subheader(f"Active Event: {current_event['name']}")
        
        st.markdown("### Current Prize Inventory")
        prizes = supabase.table("prizes").select("*").eq("event_id", current_event['id']).execute()
        
        if prizes.data:
            prize_df = pd.DataFrame(prizes.data)
            display_prizes = prize_df[['name', 'value', 'total_quantity', 'remaining_quantity']].rename(
                columns={'name': 'Prize', 'value': 'Value ($)', 'total_quantity': 'Total', 'remaining_quantity': 'Remaining'}
            )
            st.dataframe(display_prizes, hide_index=True, use_container_width=True)
        else:
            st.info("No prizes added yet. Go to the Setup tab to add inventory.")
        
        st.markdown("### PSR Winners List")
        spins = supabase.table("spins").select("first_name, last_name, email, claimed_at, prizes(name)").eq("event_id", current_event['id']).execute()
        
        if spins.data:
            winners = []
            for s in spins.data:
                winners.append({
                    "First Name": s.get("first_name"),
                    "Last Name": s.get("last_name"),
                    "Email": s.get("email"),
                    "Prize Won": s["prizes"]["name"] if s.get("prizes") else "Unknown",
                    "Time Claimed": pd.to_datetime(s.get("claimed_at")).strftime("%Y-%m-%d %I:%M %p") if s.get("claimed_at") else ""
                })
            
            winners_df = pd.DataFrame(winners)
            st.dataframe(winners_df, hide_index=True, use_container_width=True)
            
            st.download_button(
                label="Download Winners List (CSV)",
                data=winners_df.to_csv(index=False).encode('utf-8'),
                file_name="psr_winners_list.csv",
                mime="text/csv"
            )
        else:
            st.info("No winners yet. The list will populate here as guests claim prizes.")
    else:
        st.error("No active events found. Go to the Setup tab to create one.")

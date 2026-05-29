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
            # First, set all existing events to inactive so the wheel doesn't get confused
            supabase.table("events").update({"is_active": False}).neq("name", "placeholder").execute()
            
            # Now, insert the new active event
            supabase.table("events").insert({"name": event_name, "is_active": True}).execute()
            st.success(f"Event '{event_name}' created successfully!")
            st.rerun() # Refresh the page to update the UI instantly

    st.divider()

    st.header("2. Add Prizes to Active Event")
    
    # Check if there is an active event to add prizes to
    active_events = supabase.table("events").select("*").eq("is_active", True).execute()
    
    if active_events.data:
        current_event = active_events.data[0]
        st.info(f"Currently adding inventory to: **{current_event['name']}**")
        
        with st.form("new_prize_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                prize_name = st.text_input("Prize Name (e.g., Unity T-Shirt)")
            with col2:
                prize_value = st.number_input("Value ($)", min_value=0.0, value=15.0)
            with col3:
                prize_qty = st.number_input("Total Quantity", min_value=1, value=50)
            
            submit_prize = st.form_submit_button("Add Prize to Inventory")
            
            if submit_prize and prize_name:
                # Insert the prize and link it to the current event ID
                supabase.table("prizes").insert({
                    "event_id": current_event['id'],
                    "name": prize_name,
                    "value": prize_value,
                    "total_quantity": prize_qty,
                    "remaining_quantity": prize_qty
                }).execute()
                st.success(f"Added {prize_qty}x {prize_name} to the vault!")
                st.rerun()
    else:
        st.warning("Please create an active event above before adding prizes.")

# -----------------------------------------
# TAB 1: LIVE ANALYTICS
# -----------------------------------------
with tab_analytics:
    st.header("Live Event Analytics")

    # Fetch active event
    event_response = supabase.table("events").select("*").eq("is_active", True).execute()

    if event_response.data:
        current_event = event_response.data[0]
        st.subheader(f"Active Event: {current_event['name']}")
        
        # Display prize inventory
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
        
        # Display PSR Winners List
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

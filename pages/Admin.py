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

# Simple security checkpoint
# It will check your advanced settings for an admin password, defaulting to "HardRock2026" if none is set
admin_pass = st.sidebar.text_input("Admin Password", type="password")
expected_pass = st.secrets.get("ADMIN_PASSWORD", "HardRock2026")

if admin_pass != expected_pass:
    st.warning("Please enter the admin password in the sidebar to view this page.")
    st.stop()

st.header("Live Event Analytics")

# 1. Fetch active event
event_response = supabase.table("events").select("*").eq("is_active", True).execute()

if event_response.data:
    current_event = event_response.data[0]
    st.subheader(f"Active Event: {current_event['name']}")
    
    # 2. Fetch and display prize inventory
    st.markdown("### Prize Inventory")
    prizes = supabase.table("prizes").select("*").eq("event_id", current_event['id']).execute()
    
    if prizes.data:
        prize_df = pd.DataFrame(prizes.data)
        # Rename columns for a cleaner display
        display_prizes = prize_df[['name', 'value', 'total_quantity', 'remaining_quantity']].rename(
            columns={'name': 'Prize', 'value': 'Value ($)', 'total_quantity': 'Total', 'remaining_quantity': 'Remaining'}
        )
        st.dataframe(display_prizes, hide_index=True, use_container_width=True)
    
    # 3. Fetch and display PSR Winners List
    st.markdown("### PSR Winners List")
    spins = supabase.table("spins").select("first_name, last_name, email, claimed_at, prizes(name)").eq("event_id", current_event['id']).execute()
    
    if spins.data:
        # Flatten the data structure for the table
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
        
        # Export button for the desk
        st.download_button(
            label="Download Winners List (CSV)",
            data=winners_df.to_csv(index=False).encode('utf-8'),
            file_name="psr_winners_list.csv",
            mime="text/csv"
        )
    else:
        st.info("No winners yet. The list will populate here as guests claim prizes.")
else:
    st.error("No active events found. Add one in the Supabase Table Editor.")

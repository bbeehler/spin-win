import streamlit as st
from supabase import create_client

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

st.title("Unity by Hard Rock: Spin to Win")

# 1. Fetch active or paused event
event_response = supabase.table("events").select("*").in_("status", ["Active", "Paused"]).execute()

if not event_response.data:
    st.error("There are no active promotions at this time. Please check back later!")
    st.stop()

current_event = event_response.data[0]

# Block the wheel if the event is paused
if current_event['status'] == 'Paused':
    st.warning("⏸️ The prize wheel is temporarily paused for restocking. Please check back in a few minutes!")
    st.stop()

# Initialize session state variables
if "won_prize" not in st.session_state:
    st.session_state.won_prize = None

# 2. Spin Logic
if st.button("Spin the Wheel!") and not st.session_state.won_prize:
    # Fetch available prizes for the event
    prizes = supabase.table("prizes").select("*").eq("event_id", current_event['id']).gt("remaining_quantity", 0).execute()
    
    # Insert probability math and database decrement logic here
    # For now, we simulate a win saving to the session state
    st.session_state.won_prize = "Exclusive Unity T-Shirt" 
    st.rerun()
    
# 3. Form Submission
if st.session_state.won_prize and "claimed" not in st.session_state:
    st.success(f"You won: {st.session_state.won_prize}! Enter your details below to reveal your claim pass.")
    
    with st.form("claim_form"):
        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")
        email = st.text_input("Email")
        submit = st.form_submit_button("Reveal Claim Pass")
        
        if submit:
            if first_name and last_name and email:
                # Insert record into the 'spins' table in Supabase here so the PSR can verify it
                
                st.session_state.claimed = True
                st.session_state.first_name = first_name
                st.rerun()
            else:
                st.error("Please fill out all fields to claim your prize.")

# 4. Final Screenshot Screen
if "claimed" in st.session_state:
    st.warning("🚨 TAKE A SCREENSHOT OF THIS PAGE NOW 🚨")
    st.write(f"**Name:** {st.session_state.first_name}")
    st.write(f"**Prize:** {st.session_state.won_prize}")
    st.write("Show this screenshot to a PSR at the Unity Players Club to redeem your prize and complete your membership signup.")

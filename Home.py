import streamlit as st
from supabase import create_client
import random

# Initialize connection
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

st.title("Unity by Hard Rock: Spin to Win")

# 1. Fetch active event and check expiration
event_response = supabase.table("events").select("*").eq("is_active", True).execute()

if not event_response.data:
    st.error("There are no active promotions at this time.")
    st.stop()

current_event = event_response.data[0]

# 2. Spin Logic
if st.button("Spin the Wheel!"):
    # Fetch available prizes for the event
    prizes = supabase.table("prizes").select("*").eq("event_id", current_event['id']).gt("remaining_quantity", 0).execute()
    
    # Probability logic goes here. If a prize is selected:
    # 1. Update the database to decrement remaining_quantity
    # 2. Save the prize state to st.session_state
    
    st.success("You won a prize! Enter your details to claim it at the Players Club.")
    
# 3. Form Submission
if 'won_prize' in st.session_state:
    with st.form("claim_form"):
        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")
        email = st.text_input("Email")
        submit = st.form_submit_button("Claim Prize")
        
        if submit:
            # Insert record into the 'spins' table
            # Trigger the email delivery function
            st.write("Confirmation email sent! Show it to a PSR at the Unity Players Club.")
            del st.session_state['won_prize']

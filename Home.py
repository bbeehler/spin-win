import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
import random
import time
import string
import datetime

# --- MOBILE-FIRST UI CONFIGURATION ---
st.set_page_config(page_title="Unity Spin to Win", page_icon="🎸", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 500px; 
    }
    
    div[data-testid="stButton"] > button {
        height: 65px;
        font-size: 20px;
        font-weight: bold;
        border-radius: 12px;
        background-color: #e11c2a; 
        color: white;
        border: none;
    }
    div[data-testid="stFormSubmitButton"] > button {
        height: 60px;
        font-size: 18px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

def render_wheel(prize_names, winning_index):
    if len(prize_names) == 1:
        prize_names = prize_names * 4
    elif len(prize_names) == 2:
        prize_names = prize_names * 2
        
    actual_winning_index = prize_names.index(prize_names[winning_index]) if winning_index < len(prize_names) else winning_index

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body {{ display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: transparent; font-family: sans-serif; overflow: hidden; touch-action: none; }}
        .wheel-container {{ position: relative; width: 280px; height: 280px; max-width: 90vw; max-height: 90vw; }}
        canvas {{ width: 100%; height: 100%; border-radius: 50%; border: 5px solid #333; transition: transform 4s cubic-bezier(0.25, 0.1, 0.25, 1); }}
        .pointer {{ position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 20px solid transparent; border-right: 20px solid transparent; border-top: 40px solid #e11c2a; z-index: 10; }}
    </style>
    </head>
    <body>
        <div class="wheel-container">
            <div class="pointer"></div>
            <canvas id="wheel" width="280" height="280"></canvas>
        </div>
        <script>
            const canvas = document.getElementById("wheel");
            const ctx = canvas.getContext("2d");
            const prizes = {prize_names};
            const numSlices = prizes.length;
            const sliceAngle = (2 * Math.PI) / numSlices;
            const colors = ["#ffffff", "#f0f0f0", "#e0e0e0", "#d0d0d0", "#c0c0c0", "#b0b0b0"];
            
            for (let i = 0; i < numSlices; i++) {{
                ctx.beginPath();
                ctx.moveTo(140, 140);
                ctx.arc(140, 140, 140, i * sliceAngle, (i + 1) * sliceAngle);
                ctx.fillStyle = colors[i % colors.length];
                ctx.fill();
                ctx.stroke();
                
                ctx.save();
                ctx.translate(140, 140);
                ctx.rotate(i * sliceAngle + sliceAngle / 2);
                ctx.textAlign = "right";
                ctx.fillStyle = "#000";
                ctx.font = "bold 13px Arial";
                ctx.fillText(prizes[i], 130, 5);
                ctx.restore();
            }}

            const winningIndex = {actual_winning_index};
            const targetRotation = (360 * 5) - (winningIndex * (360 / numSlices)) - ((360 / numSlices) / 2) + 270; 
            
            setTimeout(() => {{
                canvas.style.transform = `rotate(${{targetRotation}}deg)`;
            }}, 100);
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=310)

col1, col2, col3 = st.columns([1,2,1])
with col2:
    try:
        st.image("logo.png", use_column_width=True)
    except:
        st.title("Unity by Hard Rock")

# Fetch active or paused events
event_response = supabase.table("events").select("*").in_("status", ["Active", "Paused"]).execute()

if not event_response.data:
    st.error("There are no active promotions at this time. Please check back later!")
    st.stop()

# Initialize session states
if "selected_event" not in st.session_state:
    st.session_state.selected_event = None
if "authorized_email" not in st.session_state:
    st.session_state.authorized_email = None
if "won_prize" not in st.session_state:
    st.session_state.won_prize = None
if "prize_id" not in st.session_state:
    st.session_state.prize_id = None
if "spinning" not in st.session_state:
    st.session_state.spinning = False

# --- STEP 1: EVENT SELECTION ---
if not st.session_state.selected_event:
    st.markdown("### Select Your Event")
    st.write("Please choose the promotion you are currently attending to get started.")
    
    with st.form("event_selection_form"):
        event_dict = {e['name']: e for e in event_response.data}
        selected_name = st.selectbox("Current Event Location", options=["-- Select an Event --"] + list(event_dict.keys()))
        
        submit_event = st.form_submit_button("Continue")
        
        if submit_event:
            if selected_name != "-- Select an Event --":
                st.session_state.selected_event = event_dict[selected_name]
                st.rerun()
            else:
                st.error("Please select an event from the list.")
    st.stop()

current_event = st.session_state.selected_event

if current_event['status'] == 'Paused':
    st.warning("⏸️ The prize wheel for this event is temporarily paused for restocking. Please check back in a few minutes!")
    if st.button("⬅️ Back to Event List", use_container_width=True):
        st.session_state.selected_event = None
        st.rerun()
    st.stop()

# --- STEP 2: THE GATEKEEPER ---
if not st.session_state.authorized_email:
    st.markdown(f"### Welcome to **{current_event['name']}**!")
    st.write("Guests are limited to one prize spin per lifetime across all Hard Rock promotional events. Enter your email to begin.")
    
    with st.form("eligibility_form"):
        email_input = st.text_input("Email Address", type="default").strip().lower()
        submit_check = st.form_submit_button("Check Eligibility")
        
        if submit_check:
            if email_input:
                history_check = supabase.table("spins").select("id").eq("email", email_input).execute()
                if history_check.data:
                    st.error("🚨 It looks like you've already participated in a Spin to Win event! We'll see you on the casino floor.")
                else:
                    st.session_state.authorized_email = email_input
                    st.rerun()
            else:
                st.error("Please enter a valid email address.")
    st.stop()

# --- STEP 3: THE WHEEL ---
prizes_response = supabase.table("prizes").select("*").eq("event_id", current_event['id']).gt("remaining_quantity", 0).execute()

if not prizes_response.data:
    st.error("Wow! We have given away all our prizes for this event. Thank you for coming!")
    st.stop()

if not st.session_state.won_prize and not st.session_state.spinning:
    if st.button("SPIN THE WHEEL", type="primary", use_container_width=True):
        st.session_state.spinning = True
        
        available_prizes = [p for p in prizes_response.data if p['remaining_quantity'] > 0]
        if not available_prizes:
            st.error("All prizes have been claimed!")
            st.stop()
            
        prize_odds = [float(p['win_probability_percent']) for p in available_prizes]
        winning_prize = random.choices(available_prizes, weights=prize_odds, k=1)[0]
                
        new_quantity = winning_prize['remaining_quantity'] - 1
        supabase.table("prizes").update({"remaining_quantity": new_quantity}).eq("id", winning_prize['id']).execute()
        
        st.session_state.won_prize = winning_prize['name']
        st.session_state.prize_id = winning_prize['id']
        st.rerun()

elif st.session_state.spinning and "claimed" not in st.session_state:
    prize_names = [p['name'] for p in prizes_response.data]
    winning_index = next(i for i, p in enumerate(prizes_response.data) if p['id'] == st.session_state.prize_id)
    
    render_wheel(prize_names, winning_index)
    
    with st.spinner("Spinning..."):
        time.sleep(4)
        
    st.session_state.spinning = False
    st.rerun()

# --- STEP 4: CLAIM FORM ---
if st.session_state.won_prize and not st.session_state.spinning and "claimed" not in st.session_state:
    st.success(f"🎉 You won: **{st.session_state.won_prize}**!")
    st.write("Enter your name below to reveal your claim pass.")
    
    with st.form("claim_form"):
        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")
        submit = st.form_submit_button("Reveal Claim Pass")
        
        if submit:
            if first_name and last_name:
                unique_code = "HR-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                
                supabase.table("spins").insert({
                    "event_id": current_event['id'],
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": st.session_state.authorized_email, 
                    "prize_id": st.session_state.prize_id,
                    "claim_code": unique_code
                }).execute()
                
                st.session_state.claimed = True
                st.session_state.first_name = first_name
                st.session_state.last_name = last_name
                st.session_state.claim_code = unique_code
                st.rerun()
            else:
                st.error("Please enter your name to secure your prize.")

# --- STEP 5: FINAL SCREENSHOT ---
if "claimed" in st.session_state:
    st.warning("🚨 **TAKE A SCREENSHOT OF THIS PAGE NOW** 🚨")
    
    fname = st.session_state.get('first_name', 'Guest')
    lname = st.session_state.get('last_name', '')
    won_prize = st.session_state.get('won_prize', 'Unknown Prize')
    claim_code = st.session_state.get('claim_code', 'ERROR-NO-CODE')
    
    try:
        start_str = datetime.datetime.strptime(current_event['redeem_start'], "%Y-%m-%d").strftime("%B %d, %Y")
        expiry_str = datetime.datetime.strptime(current_event['redeem_expiry'], "%Y-%m-%d").strftime("%B %d, %Y")
        validity_text = f"{start_str} to {expiry_str}"
    except:
        validity_text = "See Players Club for details."
    
    st.markdown(f"""
    ### Your Claim Pass
    * **Claim Code:** `{claim_code}`
    * **Name:** {fname} {lname}
    * **Prize Won:** {won_prize}
    * **Event:** {current_event['name']}
    * **Valid For Redemption:** {validity_text}
    """)
    
    st.info("Show this screenshot to a representative at the Unity Players Club during the valid redemption dates to claim your prize. See you on the floor!")
    
    st.write("")
    if st.button("🔄 Admin: Reset for Next Test", use_container_width=True):
        st.session_state.clear()
        st.rerun()

import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
import random
import time
import string

# --- MOBILE-FIRST UI CONFIGURATION ---
st.set_page_config(page_title="Unity Spin to Win", page_icon="🎸", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Hide standard Streamlit top-right menu and footer, but KEEP the header so you can open the sidebar */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Reduce top padding for mobile screens so the logo is at the top */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 500px; 
    }
    
    /* Make buttons huge and thumb-friendly */
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

# Connect to database
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# HTML/JS Code for the Visual Wheel
def render_wheel(prize_names, winning_index):
    if len(prize_names) == 1:
        prize_names = prize_names * 4
    elif len(prize_names) == 2:
        prize_names = prize_names * 2
        
    actual_winning_index = prize_names.index(prize_names[winning_index]) if winning_index < len(prize_names) else winning_index

    # Added viewport meta tag to prevent pinch-to-zoom on mobile
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
            
            // Draw Wheel
            for (let i = 0; i < numSlices; i++) {{
                ctx.beginPath();
                ctx.moveTo(140, 140);
                ctx.arc(140, 140, 140, i * sliceAngle, (i + 1) * sliceAngle);
                ctx.fillStyle = colors[i % colors.length];
                ctx.fill();
                ctx.stroke();
                
                // Add Text
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

# Add Logo 
col1, col2, col3 = st.columns([1,2,1])
with col2:
    try:
        st.image("logo.png", use_column_width=True)
    except:
        st.title("Unity by Hard Rock")

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

# Initialize session states
if "won_prize" not in st.session_state:
    st.session_state.won_prize = None
if "prize_id" not in st.session_state:
    st.session_state.prize_id = None
if "spinning" not in st.session_state:
    st.session_state.spinning = False

# 2. Fetch available prizes
prizes_response = supabase.table("prizes").select("*").eq("event_id", current_event['id']).gt("remaining_quantity", 0).execute()

if not prizes_response.data:
    st.error("Wow! We have given away all our prizes for this event. Thank you for coming!")
    st.stop()

# 3. Spin Logic & The Wheel
if not st.session_state.won_prize and not st.session_state.spinning:
    if st.button("SPIN THE WHEEL", type="primary", use_container_width=True):
        st.session_state.spinning = True
        
        total_remaining = sum(p['remaining_quantity'] for p in prizes_response.data)
        random_val = random.randint(1, total_remaining)
        current_sum = 0
        winning_prize = None
        winning_index = 0
        
        for idx, p in enumerate(prizes_response.data):
            current_sum += p['remaining_quantity']
            if random_val <= current_sum:
                winning_prize = p
                winning_index = idx
                break
                
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

# 4. Form Submission
if st.session_state.won_prize and not st.session_state.spinning and "claimed" not in st.session_state:
    st.success(f"🎉 You won: **{st.session_state.won_prize}**!")
    st.write("Enter your details below to reveal your claim pass.")
    
    with st.form("claim_form"):
        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")
        email = st.text_input("Email", type="default") # Explicitly set to string input for mobile keyboards
        submit = st.form_submit_button("Reveal Claim Pass")
        
        if submit:
            if first_name and last_name and email:
                unique_code = "HR-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                
                supabase.table("spins").insert({
                    "event_id": current_event['id'],
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "prize_id": st.session_state.prize_id,
                    "claim_code": unique_code
                }).execute()
                
                st.session_state.claimed = True
                st.session_state.first_name = first_name
                st.session_state.last_name = last_name
                st.session_state.claim_code = unique_code
                st.rerun()
            else:
                st.error("Please fill out all fields to secure your prize.")

# 5. Final Screenshot Screen
if "claimed" in st.session_state:
    st.warning("🚨 **TAKE A SCREENSHOT OF THIS PAGE NOW** 🚨")
    
    fname = st.session_state.get('first_name', 'Guest')
    lname = st.session_state.get('last_name', '')
    won_prize = st.session_state.get('won_prize', 'Unknown Prize')
    claim_code = st.session_state.get('claim_code', 'ERROR-NO-CODE')
    
    st.markdown(f"""
    ### Your Claim Pass
    * **Claim Code:** `{claim_code}`
    * **Name:** {fname} {lname}
    * **Prize Won:** {won_prize}
    * **Event:** {current_event['name']}
    """)
    
    st.info("Show this screenshot to a representative at the Unity Players Club to redeem your prize and complete your membership signup. See you on the floor!")

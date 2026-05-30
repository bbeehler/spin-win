import streamlit as st
import pandas as pd
from supabase import create_client
import datetime

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()
st.set_page_config(page_title="Admin Console", layout="wide")

# -----------------------------------------
# LOGIN SYSTEM
# -----------------------------------------
if "admin_role" not in st.session_state:
    st.title("Unity Promotion Console")
    st.write("Please log in to access your dashboard.")
    with st.form("login_form"):
        username = st.text_input("Username").strip()
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Log In", type="primary")
        if submit:
            user_check = supabase.table("admin_users").select("*").eq("username", username).eq("password", password).execute()
            if user_check.data:
                user = user_check.data[0]
                st.session_state.admin_role = user['role']
                st.session_state.admin_username = user['username']
                st.rerun()
            else:
                st.error("Invalid username or password.")
    st.stop()

# -----------------------------------------
# SIDEBAR NAVIGATION
# -----------------------------------------
role = st.session_state.admin_role
st.sidebar.success(f"Logged in as: **{st.session_state.admin_username}** ({role})")
if st.sidebar.button("Log Out"):
    st.session_state.clear()
    st.rerun()

st.sidebar.divider()

nav_options = []
if role == 'PSR':
    nav_options = ["✅ Verify & Redeem", "📋 Winners List"]
elif role == 'Manager':
    nav_options = ["✅ Verify & Redeem", "📊 Event Analytics", "⚙️ Setup & Inventory"]
elif role == 'Super Admin':
    nav_options = ["✅ Verify & Redeem", "📊 Event Analytics", "⚙️ Setup & Inventory", "🔐 Manage Staff"]

choice = st.sidebar.radio("Navigation", nav_options)

# -----------------------------------------
# VIEW: VERIFY & REDEEM 
# -----------------------------------------
if choice == "✅ Verify & Redeem":
    st.header("PSR Verification Kiosk")
    verify_code = st.text_input("Enter Claim Code (e.g., HR-XXXXXX)").strip().upper()
    
    if verify_code:
        # Pull the spin, the prize name, AND the event dates in one query
        spin_record = supabase.table("spins").select("*, prizes(name), events(name, redeem_start, redeem_expiry)").eq("claim_code", verify_code).execute()
        
        if spin_record.data:
            record = spin_record.data[0]
            st.markdown("### Database Match Found")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Name:** {record['first_name']} {record['last_name']}")
                st.write(f"**Email:** {record['email']}")
                st.write(f"**Event:** {record['events']['name'] if record.get('events') else 'Unknown'}")
            with col2:
                st.write(f"**Prize:** {record['prizes']['name'] if record['prizes'] else 'Unknown'}")
                st.write(f"**Claim Code:** `{record['claim_code']}`")
                
            st.divider()
            
            # --- REDEMPTION DATE LOGIC ---
            today = datetime.date.today()
            start_date = None
            expiry_date = None
            
            if record.get('events') and record['events'].get('redeem_start') and record['events'].get('redeem_expiry'):
                start_date = datetime.datetime.strptime(record['events']['redeem_start'], "%Y-%m-%d").date()
                expiry_date = datetime.datetime.strptime(record['events']['redeem_expiry'], "%Y-%m-%d").date()

            if record.get('is_redeemed'):
                st.error("🚨 FRAUD ALERT: THIS CODE HAS ALREADY BEEN REDEEMED. 🚨")
            elif start_date and today < start_date:
                st.error(f"⚠️ TOO EARLY: This prize cannot be redeemed until **{start_date.strftime('%B %d, %Y')}**.")
                st.write("Please inform the guest to return during the active redemption window.")
            elif expiry_date and today > expiry_date:
                st.error(f"🚨 EXPIRED: This prize expired on **{expiry_date.strftime('%B %d, %Y')}**.")
                st.write("This claim code is no longer valid.")
            else:
                st.success("✅ Code is valid, unredeemed, and within the active window.")
                st.warning(f"Please verify the guest's physical ID matches the name: **{record['first_name']} {record['last_name']}**")
                if st.button("Mark as Redeemed & Issue Prize", type="primary"):
                    supabase.table("spins").update({"is_redeemed": True}).eq("id", record['id']).execute()
                    st.success("Prize successfully marked as redeemed! The code is now burned.")
                    st.rerun()
        else:
            st.error("❌ Invalid Claim Code. No match found.")

# -----------------------------------------
# VIEW: PSR WINNERS LIST 
# -----------------------------------------
elif choice == "📋 Winners List":
    st.header("Daily Winners List")
    active_events = supabase.table("events").select("*").in_("status", ["Active", "Paused"]).execute()
    if active_events.data:
        current_event = active_events.data[0]
        st.subheader(f"Event: {current_event['name']}")
        spins = supabase.table("spins").select("first_name, last_name, email, claimed_at, claim_code, is_redeemed, prizes(name)").eq("event_id", current_event['id']).execute()
        if spins.data:
            winners = [{"Code": s.get("claim_code"), "Status": "Redeemed" if s.get("is_redeemed") else "Pending", "First Name": s.get("first_name"), "Last Name": s.get("last_name"), "Prize Won": s["prizes"]["name"] if s.get("prizes") else "Unknown"} for s in spins.data]
            st.dataframe(pd.DataFrame(winners), hide_index=True, use_container_width=True)
        else:
            st.info("No winners recorded yet.")
    else:
        st.info("No active events currently running.")

# -----------------------------------------
# VIEW: EVENT ANALYTICS 
# -----------------------------------------
elif choice == "📊 Event Analytics":
    st.header("Event Analytics")
    all_events_response = supabase.table("events").select("*").order("name").execute()
    if all_events_response.data:
        event_dict = {e['name']: e for e in all_events_response.data}
        active_event_name = next((e['name'] for e in all_events_response.data if e.get('status') == 'Active'), None)
        default_index = list(event_dict.keys()).index(active_event_name) if active_event_name in event_dict else 0
        selected_event_name = st.selectbox("Select an Event to View:", options=list(event_dict.keys()), index=default_index)
        selected_event = event_dict[selected_event_name]
        
        st.divider()
        st.markdown("### Prize Inventory & Odds Tracker")
        prizes = supabase.table("prizes").select("*").eq("event_id", selected_event['id']).execute()
        if prizes.data:
            prize_df = pd.DataFrame(prizes.data)
            total_odds = prize_df['win_probability_percent'].sum()
            if total_odds == 100:
                st.success(f"✅ The math is balanced. Total probabilities equal {total_odds}%")
            else:
                st.error(f"⚠️ MATH WARNING: Probabilities total {total_odds}%. Adjust them in Setup so they equal exactly 100%.")

            display_prizes = prize_df[['name', 'value', 'total_quantity', 'remaining_quantity', 'win_probability_percent']].rename(
                columns={'name': 'Prize', 'value': 'Value ($)', 'total_quantity': 'Total', 'remaining_quantity': 'Remaining', 'win_probability_percent': 'Odds (%)'}
            )
            
            # --- CALCULATE AND APPEND TOTALS ROW ---
            totals_row = pd.DataFrame([{
                'Prize': 'TOTALS',
                'Value ($)': display_prizes['Value ($)'].sum(),
                'Total': display_prizes['Total'].sum(),
                'Remaining': display_prizes['Remaining'].sum(),
                'Odds (%)': display_prizes['Odds (%)'].sum()
            }])
            
            display_prizes = pd.concat([display_prizes, totals_row], ignore_index=True)
            
            st.dataframe(display_prizes, hide_index=True, use_container_width=True)
        else:
            st.info("No prizes associated with this event.")
        
        st.markdown("### Full Winners List")
        spins = supabase.table("spins").select("first_name, last_name, email, claimed_at, claim_code, is_redeemed, prizes(name)").eq("event_id", selected_event['id']).execute()
        if spins.data:
            winners = [{"Code": s.get("claim_code"), "First Name": s.get("first_name"), "Last Name": s.get("last_name"), "Prize Won": s["prizes"]["name"] if s.get("prizes") else "Unknown", "Time": pd.to_datetime(s.get("claimed_at")).strftime("%Y-%m-%d %I:%M %p") if s.get("claimed_at") else ""} for s in spins.data]
            winners_df = pd.DataFrame(winners)
            st.dataframe(winners_df, hide_index=True, use_container_width=True)
            st.download_button(label="Download CSV", data=winners_df.to_csv(index=False).encode('utf-8'), file_name="winners.csv", mime="text/csv")

# -----------------------------------------
# VIEW: SETUP & INVENTORY 
# -----------------------------------------
elif choice == "⚙️ Setup & Inventory":
    
    st.header("1. Create a New Promotion Event")
    with st.form("new_event_form"):
        event_name = st.text_input("Event Name (e.g., Summer Concert Promo)")
        
        # New Date Pickers
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("Redemption Start Date", datetime.date.today())
        with col_end:
            expiry_date = st.date_input("Redemption Expiry Date", datetime.date.today() + datetime.timedelta(days=30))
            
        submit_event = st.form_submit_button("Create & Activate Event")
        if submit_event and event_name:
            supabase.table("events").update({"status": "Completed"}).eq("status", "Active").execute()
            supabase.table("events").insert({
                "name": event_name, 
                "status": "Active",
                "redeem_start": str(start_date),
                "redeem_expiry": str(expiry_date)
            }).execute()
            st.success(f"Event '{event_name}' created and activated!")
            st.rerun() 

    st.divider()
    
    st.header("2. Manage Event Status")
    all_events_manage = supabase.table("events").select("*").execute()
    if all_events_manage.data:
        event_dict_manage = {e['name']: e for e in all_events_manage.data}
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_manage_name = st.selectbox("Select an Event to Update:", options=["-- Select an Event --"] + list(event_dict_manage.keys()))
        
        if selected_manage_name != "-- Select an Event --":
            selected_event_manage = event_dict_manage[selected_manage_name]
            current_status = selected_event_manage.get('status', 'Completed')
            
            with col2:
                new_status = st.radio("Set Status:", options=["Active", "Paused", "Completed"], index=["Active", "Paused", "Completed"].index(current_status))
                
            if st.button("Update Event Status", type="primary"):
                if new_status == "Active":
                    supabase.table("events").update({"status": "Paused"}).eq("status", "Active").execute()
                supabase.table("events").update({"status": new_status}).eq("id", selected_event_manage['id']).execute()
                st.success(f"'{selected_manage_name}' is now {new_status}!")
                st.rerun()
    else:
        st.info("No events found.")

    st.divider()

    st.header("3. Add & Manage Prizes")
    active_events = supabase.table("events").select("*").eq("status", "Active").execute()
    if active_events.data:
        current_event = active_events.data[0]
        st.info(f"Adding inventory to: **{current_event['name']}**")
        with st.form("new_prize_form"):
            col1, col2 = st.columns(2)
            col3, col4 = st.columns(2)
            with col1: prize_name = st.text_input("Prize Name")
            with col2: prize_value = st.number_input("Value ($)", min_value=0.0, value=15.0)
            with col3: prize_qty = st.number_input("Total Quantity", min_value=1, value=50)
            with col4: prize_odds = st.number_input("Win Probability (%)", min_value=0.0, max_value=100.0, value=10.0)
            
            if st.form_submit_button("Add Prize"):
                supabase.table("prizes").insert({
                    "event_id": current_event['id'], "name": prize_name, "value": prize_value,
                    "total_quantity": prize_qty, "remaining_quantity": prize_qty, "win_probability_percent": prize_odds
                }).execute()
                st.success("Prize added!")
                st.rerun()
                
        st.divider()
        st.subheader("Manage Existing Prizes")
        current_prizes = supabase.table("prizes").select("*").eq("event_id", current_event['id']).execute()
        if current_prizes.data:
            prize_dict = {p['name']: p for p in current_prizes.data}
            selected_prize_name = st.selectbox("Select a prize to edit:", options=["-- Select a Prize --"] + list(prize_dict.keys()))
            if selected_prize_name != "-- Select a Prize --":
                selected_prize = prize_dict[selected_prize_name]
                with st.expander(f"Editing: {selected_prize['name']}", expanded=True):
                    with st.form(f"edit_form_{selected_prize['id']}"):
                        c1, c2 = st.columns(2)
                        c3, c4 = st.columns(2)
                        with c1: new_name = st.text_input("Name", value=selected_prize['name'])
                        with c2: new_odds = st.number_input("Win Probability (%)", value=float(selected_prize['win_probability_percent']))
                        with c3: new_total = st.number_input("Total Quantity", value=int(selected_prize['total_quantity']))
                        with c4: new_remaining = st.number_input("Remaining Quantity", value=int(selected_prize['remaining_quantity']))
                        
                        if st.form_submit_button("Save Changes"):
                            supabase.table("prizes").update({
                                "name": new_name, "win_probability_percent": new_odds,
                                "total_quantity": new_total, "remaining_quantity": new_remaining
                            }).eq("id", selected_prize['id']).execute()
                            st.success("Prize updated!")
                            st.rerun()
                    if st.button("🚨 Delete Prize", type="primary"):
                        supabase.table("prizes").delete().eq("id", selected_prize['id']).execute()
                        st.rerun()
    else:
        st.warning("⚠️ There are no Active events right now.")

# -----------------------------------------
# VIEW: MANAGE STAFF
# -----------------------------------------
elif choice == "🔐 Manage Staff":
    st.header("Staff Management")
    with st.form("add_user_form"):
        col1, col2, col3 = st.columns(3)
        with col1: new_user = st.text_input("Username")
        with col2: new_pass = st.text_input("Password")
        with col3: new_role = st.selectbox("Role", ["PSR", "Manager"])
        if st.form_submit_button("Create Account"):
            supabase.table("admin_users").insert({"username": new_user, "password": new_pass, "role": new_role}).execute()
            st.rerun()
            
    st.divider()
    st.subheader("Current Staff Accounts")
    
    users_req = supabase.table("admin_users").select("*").order("role").execute()
    if users_req.data:
        for u in users_req.data:
            col1, col2, col3 = st.columns([2, 2, 1])
            col1.write(f"👤 **{u['username']}**")
            col2.write(f"*{u['role']}*")
            if u['role'] != 'Super Admin':
                if col3.button("Remove Access", key=f"del_{u['id']}", type="secondary"):
                    supabase.table("admin_users").delete().eq("id", u['id']).execute()
                    st.rerun()
            else:
                col3.write("*(Master Account)*")

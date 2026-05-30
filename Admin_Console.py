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

# Define navigation based on role
nav_options = []
if role == 'PSR':
    nav_options = ["✅ Verify & Redeem", "📋 Winners List"]
elif role == 'Manager':
    nav_options = ["✅ Verify & Redeem", "📊 Event Analytics", "⚙️ Setup & Inventory"]
elif role == 'Super Admin':
    nav_options = ["✅ Verify & Redeem", "📊 Event Analytics", "⚙️ Setup & Inventory", "🔐 Manage Staff"]

choice = st.sidebar.radio("Navigation", nav_options)

# -----------------------------------------
# VIEW: VERIFY & REDEEM (All Roles)
# -----------------------------------------
if choice == "✅ Verify & Redeem":
    st.header("PSR Verification Kiosk")
    st.write("Enter the claim code from the guest's screenshot to verify their identity and redeem the prize.")
    
    verify_code = st.text_input("Enter Claim Code (e.g., HR-XXXXXX)").strip().upper()
    
    if verify_code:
        spin_record = supabase.table("spins").select("*, prizes(name)").eq("claim_code", verify_code).execute()
        
        if spin_record.data:
            record = spin_record.data[0]
            
            st.markdown("### Database Match Found")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Name:** {record['first_name']} {record['last_name']}")
                st.write(f"**Email:** {record['email']}")
            with col2:
                st.write(f"**Prize:** {record['prizes']['name'] if record['prizes'] else 'Unknown'}")
                st.write(f"**Claim Code:** `{record['claim_code']}`")
                
            st.divider()
            
            if record.get('is_redeemed'):
                st.error("🚨 FRAUD ALERT: THIS CODE HAS ALREADY BEEN REDEEMED. 🚨")
                st.write("Do not issue a prize. This screenshot has already been used.")
            else:
                st.success("✅ Code is valid and unredeemed.")
                st.warning(f"Please verify the guest's physical ID matches the name: **{record['first_name']} {record['last_name']}**")
                
                if st.button("Mark as Redeemed & Issue Prize", type="primary"):
                    supabase.table("spins").update({"is_redeemed": True}).eq("id", record['id']).execute()
                    st.success("Prize successfully marked as redeemed! The code is now burned.")
                    st.rerun()
        else:
            st.error("❌ Invalid Claim Code. No match found in the database. Do not issue prize.")

# -----------------------------------------
# VIEW: PSR WINNERS LIST (PSR Only)
# -----------------------------------------
elif choice == "📋 Winners List":
    st.header("Daily Winners List")
    st.write("Download the verified list of winners for your desk.")
    
    active_events = supabase.table("events").select("*").in_("status", ["Active", "Paused"]).execute()
    if active_events.data:
        current_event = active_events.data[0]
        st.subheader(f"Event: {current_event['name']}")
        
        spins = supabase.table("spins").select("first_name, last_name, email, claimed_at, claim_code, is_redeemed, prizes(name)").eq("event_id", current_event['id']).execute()
        
        if spins.data:
            winners = [{"Code": s.get("claim_code"), "Status": "Redeemed" if s.get("is_redeemed") else "Pending", "First Name": s.get("first_name"), "Last Name": s.get("last_name"), "Prize Won": s["prizes"]["name"] if s.get("prizes") else "Unknown"} for s in spins.data]
            winners_df = pd.DataFrame(winners)
            st.dataframe(winners_df, hide_index=True, use_container_width=True)
            
            st.download_button(
                label="Download Winners (CSV)",
                data=winners_df.to_csv(index=False).encode('utf-8'),
                file_name=f"psr_winners.csv",
                mime="text/csv"
            )
        else:
            st.info("No winners recorded yet.")
    else:
        st.info("No active events currently running.")

# -----------------------------------------
# VIEW: EVENT ANALYTICS (Manager & Super Admin)
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
        
        status = selected_event.get('status', 'Completed')
        if status == 'Active':
            st.success(f"🟢 **{selected_event['name']}** is currently ACTIVE.")
        elif status == 'Paused':
            st.warning(f"⏸️ **{selected_event['name']}** is currently PAUSED.")
        else:
            st.info(f"⚪ **{selected_event['name']}** is COMPLETED.")

        st.divider()
        
        st.markdown("### Prize Inventory")
        prizes = supabase.table("prizes").select("*").eq("event_id", selected_event['id']).execute()
        
        if prizes.data:
            prize_df = pd.DataFrame(prizes.data)
            display_prizes = prize_df[['name', 'value', 'total_quantity', 'remaining_quantity']].rename(
                columns={'name': 'Prize', 'value': 'Value ($)', 'total_quantity': 'Total', 'remaining_quantity': 'Remaining'}
            )
            st.dataframe(display_prizes, hide_index=True, use_container_width=True)
        else:
            st.info("No prizes associated with this event.")
        
        st.markdown("### Full Winners List")
        spins = supabase.table("spins").select("first_name, last_name, email, claimed_at, claim_code, is_redeemed, prizes(name)").eq("event_id", selected_event['id']).execute()
        
        if spins.data:
            winners = [{"Code": s.get("claim_code"), "Status": "Redeemed" if s.get("is_redeemed") else "Pending", "First Name": s.get("first_name"), "Last Name": s.get("last_name"), "Email": s.get("email"), "Prize Won": s["prizes"]["name"] if s.get("prizes") else "Unknown", "Time": pd.to_datetime(s.get("claimed_at")).strftime("%Y-%m-%d %I:%M %p") if s.get("claimed_at") else ""} for s in spins.data]
            winners_df = pd.DataFrame(winners)
            st.dataframe(winners_df, hide_index=True, use_container_width=True)
            
            st.download_button(
                label=f"Download {selected_event_name} Winners (CSV)",
                data=winners_df.to_csv(index=False).encode('utf-8'),
                file_name=f"{selected_event_name.replace(' ', '_').lower()}_winners.csv",
                mime="text/csv"
            )
        else:
            st.info("No winners recorded for this event yet.")
    else:
        st.error("No events found in the database.")

# -----------------------------------------
# VIEW: SETUP & INVENTORY (Manager & Super Admin)
# -----------------------------------------
elif choice == "⚙️ Setup & Inventory":
    st.header("1. Create a New Promotion Event")
    with st.form("new_event_form"):
        event_name = st.text_input("Event Name (e.g., Summer Concert Promo)")
        submit_event = st.form_submit_button("Create & Activate Event")
        
        if submit_event and event_name:
            supabase.table("events").update({"status": "Completed"}).eq("status", "Active").execute()
            supabase.table("events").insert({"name": event_name, "status": "Active"}).execute()
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

    st.divider()

    st.header("3. Add Prizes to Active Event")
    active_events = supabase.table("events").select("*").eq("status", "Active").execute()
    
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
                    "name": prize_name, "value": prize_value,
                    "total_quantity": prize_qty, "remaining_quantity": prize_qty
                }).execute()
                st.success(f"Added {prize_qty}x {prize_name} to the vault!")
                st.rerun()
                
        st.divider()

        st.header("4. Manage Existing Prizes")
        current_prizes = supabase.table("prizes").select("*").eq("event_id", current_event['id']).execute()
        
        if current_prizes.data:
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
                                "name": new_name, "value": new_value,
                                "total_quantity": new_total, "remaining_quantity": new_remaining
                            }).eq("id", selected_prize['id']).execute()
                            st.success("Prize updated successfully!")
                            st.rerun()
                    
                    if st.button("🚨 Delete This Prize", type="primary"):
                        supabase.table("prizes").delete().eq("id", selected_prize['id']).execute()
                        st.success("Prize deleted!")
                        st.rerun()
        else:
            st.info("No prizes available for this event.")
    else:
        st.warning("Please ensure an event is 'Active' before managing prizes.")

# -----------------------------------------
# VIEW: MANAGE STAFF (Super Admin Only)
# -----------------------------------------
elif choice == "🔐 Manage Staff":
    st.header("Staff Management")
    st.write("Create and remove access accounts for your team.")
    
    with st.form("add_user_form"):
        st.subheader("Add New Staff Member")
        col1, col2, col3 = st.columns(3)
        with col1:
            new_user = st.text_input("Username")
        with col2:
            new_pass = st.text_input("Password")
        with col3:
            new_role = st.selectbox("Role", ["PSR", "Manager"])
            
        if st.form_submit_button("Create Account"):
            if new_user and new_pass:
                # Check if username exists
                check = supabase.table("admin_users").select("id").eq("username", new_user).execute()
                if check.data:
                    st.error("Username already exists. Choose another.")
                else:
                    supabase.table("admin_users").insert({
                        "username": new_user,
                        "password": new_pass,
                        "role": new_role
                    }).execute()
                    st.success(f"Account for {new_user} created successfully!")
                    st.rerun()
            else:
                st.error("Please fill out all fields.")
                
    st.divider()
    st.subheader("Current Staff Accounts")
    
    users_req = supabase.table("admin_users").select("*").order("role").execute()
    if users_req.data:
        for u in users_req.data:
            col1, col2, col3 = st.columns([2, 2, 1])
            col1.write(f"👤 **{u['username']}**")
            col2.write(f"*{u['role']}*")
            
            # Prevent Super Admin from deleting themselves accidentally
            if u['role'] != 'Super Admin':
                if col3.button("Remove Access", key=f"del_{u['id']}", type="secondary"):
                    supabase.table("admin_users").delete().eq("id", u['id']).execute()
                    st.rerun()
            else:
                col3.write("*(Master Account)*")

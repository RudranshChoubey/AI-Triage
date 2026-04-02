import streamlit as st
from database import supabase

st.set_page_config(page_title="Clinic Staff Portal", layout="wide")
st.title("👨‍⚕️ Live Patient Support Hub")

# 1. Fetch all active handoff alerts
res = supabase.table("chat_logs").select("*").eq("needs_intervention", True).execute()
alerts = res.data

if not alerts:
    st.success("All quiet! No patients are currently waiting for a live chat.")
    if st.button("🔄 Refresh"):
        st.rerun()
else:
    # 🌟 THE FIX: Extract UNIQUE session IDs using a Python Set
    unique_sessions = list(set([alert['session_id'] for alert in alerts]))
    
    st.warning(f"🚨 {len(unique_sessions)} Patient(s) requested human assistance.")
    
    # 2. Create exactly ONE tab per unique patient
    tabs = st.tabs([f"Patient {sid[:4]}" for sid in unique_sessions])
    
    # 3. Loop through the UNIQUE sessions, not the individual messages
    for i, session_id in enumerate(unique_sessions):
        with tabs[i]:
            st.subheader(f"Chatting with Patient {session_id[:8]}")
            
            # Fetch the FULL chat history for this specific patient
            history_res = supabase.table("chat_logs").select("*").eq("session_id", session_id).order("timestamp", desc=False).execute()
            history = history_res.data
            
            # Display the chat history inside a proper scrollable container
            chat_container = st.container(height=400, border=True)
            with chat_container:
                for msg in history:
                    role = "user" if msg['sender'] == "USER" else "assistant"
                    avatar = "👨‍⚕️" if msg['sender'] == "STAFF" else None
                    
                    with st.chat_message(role, avatar=avatar):
                        st.markdown(msg['message'])
            
            # The Staff Input Box (Guaranteed unique because the loop is based on unique sessions!)
            staff_reply = st.chat_input("Type your reply...", key=f"staff_input_{session_id}")
            
            if staff_reply:
                try:
                    # Save staff reply to Supabase
                    supabase.table("chat_logs").insert({
                        "session_id": session_id,
                        "sender": "STAFF",
                        "message": staff_reply,
                        "needs_intervention": True # Keeps the tab open
                    }).execute()
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to send message: {e}")
            
            # Button to close the ticket
            st.divider()
            if st.button("✅ Resolve & Close Ticket", key=f"close_{session_id}"):
                # Flips all messages for this session back to False so it leaves the dashboard
                supabase.table("chat_logs").update({"needs_intervention": False}).eq("session_id", session_id).execute()
                st.rerun()
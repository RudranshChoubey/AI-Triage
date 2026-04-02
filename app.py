import streamlit as st
import requests
import uuid
from streamlit_autorefresh import st_autorefresh
from database import supabase

st.set_page_config(page_title="Clinic AI Triage", page_icon="🏥")
st.title("🏥 Clinic Support Triage")

# 1. Initialize Session State
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant", 
            "content": "Hello! Welcome to City Health Partners. 🏥 How can I help you today?", 
            "is_staff": False
        }
    ]
if "waiting_for_staff" not in st.session_state:
    st.session_state.waiting_for_staff = False

# 2. THE LIVE SYNC ENGINE (Only runs if a handoff was triggered)
if st.session_state.waiting_for_staff:
    # 1. Refresh the app every 3 seconds
    st_autorefresh(interval=3000, limit=100, key="chat_sync")
    
    # Show a little visual indicator so you KNOW it's checking
    st.caption("🔄 Listening for staff replies...")
    
    # 2. Fetch ALL staff messages for this session from the database
    db_res = supabase.table("chat_logs").select("*").eq("session_id", st.session_state.session_id).eq("sender", "STAFF").order("timestamp", desc=False).execute()
    db_staff_msgs = db_res.data
    
    # 3. Clean the local memory (Keep only User and AI messages)
    clean_messages = [m for m in st.session_state.messages if not m.get("is_staff")]
    
    # 4. Inject the fresh Staff messages directly from the database
    for m in db_staff_msgs:
        clean_messages.append({
            "role": "assistant", 
            "content": f"** Front Desk:** {m['message']}", 
            "is_staff": True
        })
    
    # 5. If the new list is longer than the old list, update and redraw!
    if len(clean_messages) > len(st.session_state.messages):
        st.session_state.messages = clean_messages
        st.rerun()

# 3. Display the Chat History
for message in st.session_state.messages:
    # We skip showing the AI's technical confirmation if a human is here
    if "A staff member is joining" in message["content"] and st.session_state.waiting_for_staff:
        continue
    # 🌟 AVATAR LOGIC 🌟
    if message.get("is_staff"):
        avatar_icon = "👨‍⚕️"  # Human Staff Icon
    elif message["role"] == "assistant":
        avatar_icon = "🏥"  # AI Clinic Icon (replaces the robot)
    else:
        avatar_icon = "👤"  # Patient Icon
            
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 4. User Input Box
if prompt := st.chat_input("How can I help you today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        # Send message to FastAPI
        response = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"session_id": st.session_state.session_id, "user_message": prompt}
        )
        data = response.json()
        
        bot_reply = data["response_text"]
        action = data.get("action_taken", "") # Grab the digital signal from main.py
        
        # 🌟 THE DIGITAL HANDSHAKE 🌟
        # If the backend signals a chat is active, turn on the sync!
        if action == "LIVE_CHAT_ACTIVE" or action == "HUMAN_CHAT_IN_PROGRESS":
            st.session_state.waiting_for_staff = True
            st.toast("🟢 Live Chat Sync Activated!")

        st.session_state.messages.append({"role": "assistant", "content": bot_reply})
        
        # Only show the bot's reply if we aren't waiting for a human
        if not st.session_state.waiting_for_staff:
            with st.chat_message("assistant"):
                st.markdown(bot_reply)
        else:
            st.rerun() # Force a rerun to start the 3-second loop
            
    except Exception as e:
        st.error(f"Error connecting to server: {e}")
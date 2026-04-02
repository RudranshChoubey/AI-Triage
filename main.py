from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
import os
from dotenv import load_dotenv
from pypdf import PdfReader
from fastapi.middleware.cors import CORSMiddleware

# Your database imports
from database import supabase, check_and_book_appointment, log_chat, trigger_staff_alert, send_staff_sms_alert

load_dotenv()

app = FastAPI(title="Clinic Agentic Triage MVP")

# --- CORS MIDDLEWARE (Restored!) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
      allow_credentials=True,  # In production, specify your frontend URL here
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INITIALIZE THE AI (Restored!) ---
groq_key = os.getenv("GROQ_API_KEY")
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, api_key=groq_key)

# --- HELPER FUNCTIONS (Restored!) ---
async def handle_emergency():
    return "🚨 This sounds like a medical emergency. Please call 911 or go to the nearest emergency room immediately."

async def handle_booking(classification, session_id):
    reply = await check_and_book_appointment(classification.doctor_name, classification.appointment_time, classification.patient_phone, session_id)
    return reply

async def handle_faq(user_message):
    try:
        context = ""
        if os.path.exists("clinic_manual.pdf"):
            reader = PdfReader("clinic_manual.pdf")
            for page in reader.pages:
                context += page.extract_text() + "\n"
        else:
            context = "Clinic hours are 8am to 8pm. We accept most major insurances."

        faq_prompt = PromptTemplate.from_template("""
        You are a helpful clinic assistant answering questions based ONLY on the provided clinic manual context.
        CRITICAL RULES:
        1. If the answer is not in the context, say: "I'm sorry, I don't have that specific information."
        2. DO NOT offer to connect the user to a human.
        3. DO NOT offer "chat" or "callback" options.
        Context: {context}
        Question: {question}
        """)
        faq_chain = faq_prompt | llm
        res = faq_chain.invoke({"context": context, "question": user_message})
        return res.content
    except Exception as e:
        print(f"FAQ Error: {e}")
        return "I'm having trouble reading the clinic manual right now."

async def handle_handoff(session_id, user_message):
    await trigger_staff_alert(session_id, user_message)
    return "I understand. I'm looping in our front desk team now. 🤝\n\nWould you prefer to: 1️⃣ Chat right here on the webpage? 2️⃣ Receive a Callback on your phone?"


# --- PYDANTIC SCHEMAS ---
class ChatRequest(BaseModel):
    session_id: str
    user_message: str

class ChatResponse(BaseModel):
    response_text: str
    action_taken: str

class TriageClassification(BaseModel):
    intent: str = Field(
        description="Must be exactly one of: GREETING, EMERGENCY, BOOKING, FAQ, HANDOFF, HANDOFF_CHAT, HANDOFF_CALL, PROVIDE_PHONE_CALLBACK"
    )
    doctor_type: str | None = Field(default=None, description="The type of visit or specialist (e.g., General, Orthodontist, Surgeon).")
    doctor_name: str | None = Field(default=None, description="The specific doctor requested, if any.")
    appointment_time: str | None = Field(default=None, description="The requested time, if any.")
    patient_phone: str | None = Field(default=None, description="The patient's phone number, if provided.")

# --- THE AGENCY-GRADE SYSTEM PROMPT ---
system_prompt = """
You are the routing brain for Apex Dental clinic.
Analyze the user's latest message IN THE CONTEXT of the recent conversation history. 


Classify the intent into exactly ONE of these categories:
1. GREETING: User says hello, hi, good morning.
2. EMERGENCY: Life-threatening conditions.
3. BOOKING: User wants to schedule a visit.
4. FAQ: User asks about clinic information.
5. HANDOFF: User expresses frustration or generally asks for a human/front desk.
6. HANDOFF_CHAT: The user is confirming they want to chat on the webpage.
7. HANDOFF_CALL: The user is confirming they want a phone call.
8. PROVIDE_PHONE_CALLBACK: The user is providing their phone number specifically because they want a human to call 
them back.
CRITICAL CONTEXT RULES:
1. If the last AI message was "I'd be happy to help schedule that! What is the best phone number...", and the user provides a phone number, you MUST classify the intent as BOOKING and extract the patient_phone.
2. If the last AI message asked for a time and the user provides one, classify as BOOKING and extract appointment_time. You MUST format this time strictly as a standard timestamp (e.g., "2026-04-02 05:00 PM"). Do not use casual words like "tom" or "tomorrow".
3. If the last AI message asked for a doctor type and the user provides one, classify as BOOKING and extract doctor_type.
4. If the last AI message presented a list of doctors, and the user picks one, classify as BOOKING and extract the doctor_name.
5. You are managing a multi-step booking funnel. You MUST read the Recent Conversation History to find previously provided information.
6. STICKY MEMORY: If the user provided their phone number, appointment time, or doctor type at ANY point in the chat history, you MUST extract and include them in your current output. NEVER output null for a field if the data exists in the history!

Recent Conversation History:
{chat_history}

User's Latest Message: {user_message}
"""

triage_prompt = PromptTemplate.from_template(system_prompt)
triage_chain = triage_prompt | llm.with_structured_output(TriageClassification)


# --- THE MAIN ENDPOINT ---
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        user_msg_lower = request.user_message.strip().lower()
        intent = None
        classification = None
        
        
        # 🛑 1. THE MENU BYPASS
        if user_msg_lower == "2" or any(word in user_msg_lower for word in ["call", "callback", "phone", "text me", "sms"]):
            intent = "HANDOFF_CALL"
        elif user_msg_lower == "1" or any(word in user_msg_lower for word in ["chat", "text here", "stay here", "type", "web"]):
            intent = "HANDOFF_CHAT"
        elif user_msg_lower in ["hi", "hey", "hello", "greetings", "good morning"]:
            intent = "GREETING"

        # 🛑 2. THE GATEKEEPER 
        if not intent:
            # Check for the most recent intervention status for THIS session
            check_handoff = supabase.table("chat_logs") \
                .select("needs_intervention") \
                .eq("session_id", request.session_id) \
                .order("timestamp", desc=True) \
                .limit(1) \
                .execute()
            
            if check_handoff.data and check_handoff.data[0]['needs_intervention']:
                await log_chat(request.session_id, "USER", request.user_message)
                return ChatResponse(response_text="Message received. A staff member is looking at this.", action_taken="HUMAN_CHAT_IN_PROGRESS") 

        # 🧠 3. LET GROQ THINK (Priority 3: For complex questions/bookings)
        if not intent:
            # Grab the last 2 messages for memory
            history_res = supabase.table("chat_logs").select("sender, message").eq("session_id", request.session_id).order("timestamp", desc=True).limit(10).execute()
            formatted_history = "".join([f"{'AI' if row['sender'] == 'AI' else 'User'}: {row['message']}\n" for row in reversed(history_res.data)])
            
            classification = triage_chain.invoke({
                "chat_history": formatted_history,
                "user_message": request.user_message
            })
            intent = classification.intent.upper()

        print(f"🧠 FINAL INTENT TO ROUTE: {intent}")

        # 🚀 4. EXECUTE THE ROUTE
        if intent == "GREETING":
            reply = "Hello! I am Apex! You can ask me questions about our services, book an appointment, or ask to speak to our front desk. How can I help?"
            
        elif intent == "EMERGENCY":
            reply = await handle_emergency()
            
        elif intent == "BOOKING":
            # Step 1: Get Phone Number
            if not classification.patient_phone:
                reply = "I'd be happy to help schedule that! What is the best phone number to send your confirmation text to?"
                intent = "ASKING_PHONE"
                
            # Step 2: Get Time & Date
            elif not classification.appointment_time:
                reply = "Got it! What date and time would you like to come in?"
                intent = "ASKING_TIME"
                
            # Step 3: Get Specialty/Type
            elif not classification.doctor_type:
                reply = f"Perfect, {classification.appointment_time} is open. What kind of visit is this? (e.g., General Checkup, Orthodontics, Surgery)"
                intent = "ASKING_TYPE"
                
            # Step 4: Present Doctors & Get Selection
            elif not classification.doctor_name:
                reply = (
                    f"Great! For a {classification.doctor_type} appointment at {classification.appointment_time}, "
                    f"we have the following doctors available:\n\n"
                    f"👨‍⚕️ **Dr. Smith** (Senior {classification.doctor_type})\n"
                    f"👩‍⚕️ **Dr. Patel** (Lead {classification.doctor_type})\n\n"
                    f"Which doctor would you prefer to see?"
                )
                intent = "PRESENTING_DOCTORS"
                
            # Step 5: Execute the Booking!
            else:
                reply = await handle_booking(classification, request.session_id)
            
        elif intent == "FAQ":
            reply = await handle_faq(request.user_message)
            
        elif intent == "HANDOFF":
            reply = await handle_handoff(request.session_id, request.user_message)
            
        elif intent == "HANDOFF_CALL":
            # Just ask for the number. DO NOT fire Twilio yet!
            reply = "Got it. What is the best phone number for our team to call you back?"
            intent = "ASKING_PHONE" 
            
        elif intent == "PROVIDE_PHONE_CALLBACK":
            # NOW we fire the Twilio text, and include their actual message!
            await trigger_staff_alert(request.session_id, f"CALLBACK NUMBER: {request.user_message}")
            await send_staff_sms_alert(f"🚨 URGENT: Patient {request.session_id[:4]} requested a callback! Number provided: {request.user_message}")
            reply = "Perfect. I've sent your number directly to our front desk. They will call you shortly."
            intent = "CALLBACK_SCHEDULED"
            
        elif intent == "HANDOFF_CHAT":
            # Add this line to make it show up in your staff portal!
            await trigger_staff_alert(request.session_id, "User requested live chat.") 
            reply = "Great. Please stay on this page. A staff member is joining the chat now."
            intent = "LIVE_CHAT_ACTIVE"
            
        else:
            # Ultimate safety fallback
            reply = await handle_handoff(request.session_id, request.user_message)
        
        await log_chat(request.session_id, "USER", request.user_message)
        await log_chat(request.session_id, "AI", reply)

        return ChatResponse(response_text=reply, action_taken=intent)

    except Exception as e:
        print(f"❌ Error in chat_endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from twilio.rest import Client 
from datetime import datetime, timedelta

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

async def check_and_book_appointment(doctor_name: str, appointment_time: str, patient_phone: str, session_id: str) -> str:
    try:
        fallback_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT10:00:00Z")
        clean_doc_name = doctor_name if doctor_name else "General Dentist"
        clean_time = appointment_time if appointment_time else fallback_date 
        clean_phone = patient_phone if patient_phone else "0000000000" 
        
        # Simplified insert for the demo
        appt_data = {
            "doctor_name": clean_doc_name,
            "appointment_time": clean_time,
            "status": "scheduled"
        }
        # Only include patient_id if you are SURE it exists in the other table
        supabase.table("appointments").insert(appt_data).execute() 
        
        # Trigger the confirmation SMS!
        await send_patient_sms_confirmation(clean_doc_name, clean_time, clean_phone) 
        
        return f"✅ Success! I have booked your appointment with {clean_doc_name} for {clean_time}. You will receive a confirmation text shortly."
        
    except Exception as e:
        print(f"Booking Logic Error: {e}")
        return "⚠️ The scheduling system rejected that entry. Let me hand you off to a human."

async def log_chat(session_id: str, sender: str, message: str):
    """Logs the conversation history."""
    try:
        data = {"session_id": session_id, "sender": sender, "message": message}
        supabase.table("chat_logs").insert(data).execute()
    except Exception as e:
        print(f"Logging Error: {e}")


async def trigger_staff_alert(session_id: str, last_message: str):
    try:
        data = {
            "session_id": session_id,
            "sender": "USER",
            "message": last_message,
            "needs_intervention": True  # This is the magic key
        }
        # We insert this as a fresh alert row
        res = supabase.table("chat_logs").insert(data).execute()
        print(f"DEBUG: Handoff logged successfully: {res.data}")
        return True
    except Exception as e:
        print(f"DEBUG: Handoff failed: {e}")
        return False
    
async def send_staff_sms_alert(message_body: str):
    try:
        # Grab the keys from the .env file
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
        target_number = os.getenv("MY_CELL_PHONE")

        # Connect to Twilio and send the text
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=message_body,
            from_=twilio_number,
            to=target_number
        )
        print(f"✅ SMS Sent successfully! ID: {message.sid}")
    except Exception as e:
        print(f"❌ SMS Alert Failed: {e}")

async def send_patient_sms_confirmation(doctor_name: str, appointment_time: str, patient_phone: str):
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
        
        # 🌟 THE DEMO MAGIC: We still route it to YOUR phone so it actually sends!
        target_number = os.getenv("MY_CELL_PHONE") 

        message_body = (
            f"🏥 Apex Dental Appointment Confirmed!\n\n"
            f"👨‍⚕️ Doctor: {doctor_name}\n"
            f"📅 Time: {appointment_time}\n"
            f"📞 Number on file: {patient_phone}\n" # Proof that the AI captured it!
            f"📍 Location: 123 Main St, Clinic Wing.\n\n"
            f"Reply to this message to reschedule."
        )

        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=message_body,
            from_=twilio_number,
            to=target_number
        )
        print(f"✅ Patient Confirmation SMS Sent! ID: {message.sid}")
    except Exception as e:
        print(f"❌ Patient SMS Failed: {e}")


# Temporary test block - delete after it works
if __name__ == "__main__":
    import asyncio
    async def test():
        try:
            res = supabase.table("appointments").select("*", count="exact").limit(1).execute()
            print("✅ Connection Successful! Found tables.")
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
    
    asyncio.run(test())
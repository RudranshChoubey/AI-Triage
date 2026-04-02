# 🏥 Apex Dental: AI Triage & Booking Agent

An agency-grade, full-stack AI chatbot designed for medical and dental clinics. This system features an autonomous AI routing brain that handles patient greetings, FAQ answering via RAG (Retrieval-Augmented Generation), automated appointment scheduling, and seamless human-in-the-loop (HITL) handoffs to a live staff portal.

Currently, this repository is configured to operate as a **headless backend** communicating with a lightweight, client-facing HTML/JS webpage widget.

## 🚀 Key Features

* **Agentic Routing (Groq / Llama 3):** Dynamically classifies user intent (Booking, Emergency, FAQ, Handoff) based on conversation history.
* **Decoupled Architecture:** A lightweight Javascript webpage widget talks to a robust FastAPI backend, ensuring low-latency and high scalability for local businesses.
* **Automated Booking Funnel:** Guides patients through a multi-step booking process (Phone -> Time -> Specialty -> Doctor) with persistent AI memory, saving data directly to a Supabase PostgreSQL database.
* **Live Staff Portal (Streamlit):** A dedicated, real-time dashboard for front-desk staff to monitor flagged conversations, intercept chats, and resolve patient tickets.
* **SMS Integrations (Twilio):** Sends instant confirmation texts to patients upon booking and high-priority SMS alerts to staff when human intervention is requested.
* **Document-Based FAQ (RAG):** Reads directly from a provided `clinic_manual.pdf` to accurately answer clinic-specific questions (hours, insurance, procedures) without hallucinating.

## 📂 Project Structure

* `main.py` - The FastAPI backend and LLM orchestration layer (The Brain).
* `database.py` - Handles all external integrations (Supabase connections, Twilio SMS routing).
* `staff.py` - The Streamlit-powered internal dashboard for front-desk staff.
* `clinic_manual.pdf` - The knowledge base document the AI uses to answer FAQ questions. *(Note: Currently contains placeholder information for "Apex Dental").*
* `HTML/JS Widget` *(Located on the client WordPress/Website)* - The floating patient-facing UI that posts to the `/chat` endpoint.

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI, Uvicorn
* **LLM Engine:** LangChain, Groq (Llama-3.1-8b-instant)
* **Database:** Supabase (PostgreSQL)
* **Staff UI:** Streamlit
* **SMS:** Twilio API
* **RAG:** PyPDF

## ⚙️ Local Setup & Installation

**1. Clone the repository and set up a virtual environment:**
```bash
git clone [https://github.com/yourusername/clinic-triage-ai.git](https://github.com/yourusername/clinic-triage-ai.git)
cd clinic-triage-ai
python3 -m venv venv
source venv/bin/activate

Install dependencies:
Bash
pip install fastapi uvicorn supabase twilio langchain-groq pypdf pydantic streamlit python-dotenv

3. Environment Variables:
Create a .env file in the root directory and add your API keys:

Code snippet
GROQ_API_KEY=your_groq_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_PHONE_NUMBER=your_twilio_number
MY_CELL_PHONE=your_testing_phone_number

4. Database Setup (Supabase):
Ensure your Supabase project has the following tables:

chat_logs: (id, session_id, sender, message, timestamp, needs_intervention)

appointments: (id, patient_id, doctor_name, appointment_time, status)

5. Add the Clinic Manual:
Ensure a valid clinic_manual.pdf is placed in the root directory. The AI will parse this file to answer any FAQ queries dynamically.

🏃‍♂️ Running the System
You need two terminal windows running simultaneously to power the separated environments.

Terminal 1: Start the AI Brain (FastAPI)

Bash
python main.py
# Or: uvicorn main:app --reload

Terminal 2: Start the Staff Portal (Streamlit)

Bash
python -m streamlit run staff.py

🌐 Connecting the Web Widget (Localhost)
If you are testing the client-facing HTML/JS widget locally, you must expose the FastAPI backend to the internet using a tunneling service like ngrok to bypass localhost CORS
restrictions:

Bash
ngrok http 8000
Copy the generated https://...ngrok-free.app URL and update the fetch endpoint inside your webpage's chat widget JavaScript.

🔒 License
MIT License

import streamlit as st
import asyncio
import random
import wave
import edge_tts
import os
import time
import base64
import speech_recognition as sr
import re
import pywhatkit
import threading
from twilio.rest import Client

# --- NOTIFICATION CONFIGURATION ---
# 1. WhatsApp is handled via WhatsApp Web (make sure you're logged in)
# 2. SMS is handled via Twilio (requires Account SID, Auth Token and a Twilio phone number)
TWILIO_SID = "your_account_sid_here"
TWILIO_AUTH_TOKEN = "your_auth_token_here"
TWILIO_PHONE_NUMBER = "your_twilio_phone_number_here"
# ----------------------------------

def send_whatsapp_msg(phone_no):
    try:
        # Send instant message
        pywhatkit.sendwhatmsg_instantly(
            phone_no=phone_no, 
            message="your appointment is fixed", 
            wait_time=15, 
            tab_close=True, 
            close_time=3
        )
    except Exception as e:
        print(f"Failed to send WhatsApp message to {phone_no}: {e}")

def send_sms_msg(phone_no):
    """Sends a traditional SMS via Twilio"""
    if "your_" in TWILIO_SID or "your_" in TWILIO_AUTH_TOKEN or "your_" in TWILIO_PHONE_NUMBER:
        print("SMS NOT SENT: Please configure your Twilio credentials in app.py")
        return

    try:
        client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body="Your appointment at Smile Bright Dental Clinic is fixed.",
            from_=TWILIO_PHONE_NUMBER,
            to=phone_no
        )
        print(f"SMS Sent successfully! Message SID: {message.sid}")
    except Exception as e:
        print(f"Failed to send SMS to {phone_no}: {e}")

# ==========================================
# 1. CORE AUDIO LOGIC
# ==========================================


class AI_Assistant:
    def __init__(self):
        # A list of manual responses suitable for a dental clinic
        self.manual_replies = [
            "Hello, thank you for calling Smile Bright Dental Clinic. How can I assist you today?",
            "I completely understand. To help you schedule an appointment, could I please get your full name and phone number?",
            "Thank you. We actually have an opening tomorrow afternoon at 2 PM, or Thursday morning at 10 AM. Does either of those work for you?",
            "Perfect. I have penciled you in! Appointment booked successfully.",
            "Is there anything else you need help with regarding your dental care?",
            "Alright, we will see you soon. Thank you for calling and have a wonderful day!"
        ]
        self.call_count = 0
        self.recognizer = sr.Recognizer()
        
    def transcribe_audio(self, audio_filepath):
        try:
            with sr.AudioFile(audio_filepath) as source:
                audio_data = self.recognizer.record(source)
                try:
                    text = self.recognizer.recognize_google(audio_data)
                    return text
                except sr.UnknownValueError:
                    return "[Inaudible]"
                except sr.RequestError as e:
                    return f"[Could not request results; {e}]"
        except Exception as e:
            return "[Error processing audio file]"

    def handle_call(self, user_transcript):
        time.sleep(1) # Fake a tiny bit of processing time
        
        # If we are at the stage where we just asked for the name and phone number (count == 1)
        # And we are now processing their reply to that question
        if self.call_count == 2:
            # Look for 10 consecutive digits (ignoring spaces/dashes)
            digits = re.sub(r'\D', '', user_transcript)
            
            # If we don't find exactly 10 digits
            if len(digits) != 10:
                # Do NOT increment call_count so it stays at 2, and return a custom reprompt
                return "I'm sorry, I didn't catch a valid 10-digit phone number. Could you please repeat your name and your 10-digit phone number for me?"
        
        # Otherwise, proceed normally
        reply = self.manual_replies[self.call_count % len(self.manual_replies)]
        self.call_count += 1
        
        return reply

async def generate_speech(text, output_filename):
    try:
        communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
        await communicate.save(output_filename)
        return True
    except Exception as e:
        print(f"TTS failed: {e}")
        return False


# ==========================================
# 2. STREAMLIT APP LOGIC
# ==========================================

st.set_page_config(page_title="AI Receptionist", page_icon="📞", layout="centered")

# Initialize Session State Variables to save history
if "history" not in st.session_state:
    st.session_state.history = []
if "assistant" not in st.session_state:
    # Initialize the assistant ONE time so it remembers its place in the manual replies
    st.session_state.assistant = AI_Assistant()
if "audio_to_play" not in st.session_state:
    st.session_state.audio_to_play = None

# Global state for patient info specifically extracted from transcribed text
if "patient_name" not in st.session_state:
    st.session_state.patient_name = "Pending"
if "patient_phone" not in st.session_state:
    st.session_state.patient_phone = "Pending"
if "messages_sent" not in st.session_state:
    st.session_state.messages_sent = False

st.title("🦷 Smile Bright Dental Receptionist")
st.markdown("Press the button below to arrange an appointment or discuss a dental issue. I will respond to your requests out loud while maintaining a transcript.")

# Display Chat History (Subtitles)
chat_container = st.container()
with chat_container:
    for chat in st.session_state.history:
        if chat["role"] == "user":
            st.markdown(f"**🗣️ Patient:** [Audio Input Sent]")
        else:
            st.info(f"**🤖 Dental Assistant:** {chat['text']}")

# Add an auto-play HTML hack if there's audio waiting to be played 
if st.session_state.audio_to_play:
    audio_file_path = st.session_state.audio_to_play
    if os.path.exists(audio_file_path):
        with open(audio_file_path, "rb") as f:
            audio_bytes = f.read()
        b64 = base64.b64encode(audio_bytes).decode()
        md = f"""
            <audio autoplay="true">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)
        # Clear out the playback queue for next loop
        st.session_state.audio_to_play = None

st.divider()

# Sidebar for Patient Information Board
with st.sidebar:
    st.header("📋 Clinic Dashboard")
    st.divider()
    
    # We define the state based on call_count
    current_count = st.session_state.assistant.call_count
    
    if current_count < 3:
        if st.session_state.patient_name == "Pending" and st.session_state.patient_phone == "Pending":
            st.warning("Awaiting patient details...")
            st.markdown(f"**Name:** {st.session_state.patient_name}")
            st.markdown(f"**Phone:** {st.session_state.patient_phone}")
            st.markdown("**Status:** Needs Intake")
        else:
            st.success("Patient details captured!")
            st.markdown(f"**Name:** {st.session_state.patient_name}")
            st.markdown(f"**Phone:** {st.session_state.patient_phone}")
            st.markdown("**Status:** Initializing Intake")
    else:
        st.success("Patient details captured!")
        st.markdown(f"**Name:** {st.session_state.patient_name}")
        st.markdown(f"**Phone:** {st.session_state.patient_phone}")
        st.markdown("**Status:** Scheduling")
        
        # Manual send button
        if not st.session_state.messages_sent:
            if st.button("📲 SEND APPOINTMENT CONFIRMATION", use_container_width=True):
                captured_phone = re.sub(r'\D', '', st.session_state.patient_phone)
                if len(captured_phone) == 10:
                    target_num = f"+91{captured_phone}"
                else:
                    target_num = "+917093276306"
                
                with st.spinner("Sending notifications..."):
                    # Send WhatsApp
                    t1 = threading.Thread(target=send_whatsapp_msg, args=(target_num,))
                    t1.start()
                    
                    # Send SMS
                    t2 = threading.Thread(target=send_sms_msg, args=(target_num,))
                    t2.start()
                    
                    st.session_state.messages_sent = True
                    st.success("Notifications triggered!")
                    st.rerun()
        else:
            st.info("✅ Confirmation messages have been sent.")

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    audio_val = st.audio_input("🎙️ Speak your request", key="mic_input")
    if audio_val:
        with st.spinner("Processing receptionist reply..."):
            record_file = "user_input.wav"
            with open(record_file, "wb") as f:
                f.write(audio_val.getvalue())
            
            # 2. Transcribe Audio
            user_transcript = st.session_state.assistant.transcribe_audio(record_file)
            
            # Log the exact words the user actually spoke into history instead of [Audio Sent]
            st.session_state.history.append({"role": "user", "text": f'"{user_transcript}"'})
            
            # 3. Very basic extraction logic based on the conversation turn
            # If the assistant just asked for the name and phone number (count == 2)
            if st.session_state.assistant.call_count == 2:
                # Look for 10 consecutive digits specifically
                digits = re.sub(r'\D', '', user_transcript)
                if len(digits) == 10:
                    # Format appropriately
                    st.session_state.patient_phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                else:
                    st.session_state.patient_phone = "Invalid or Missing"
                
                # Very naive name extraction logic
                words = user_transcript.split()
                if len(words) > 0:
                    name_guess = user_transcript
                    # Strip out the numbers they said
                    name_guess = re.sub(r'\d+', '', name_guess).replace('-', '').strip()
                    if name_guess:
                        st.session_state.patient_name = name_guess.title()
                    else:
                        st.session_state.patient_name = "Not provided clearly"

        with st.spinner("Processing receptionist reply..."):
            # 4. Get Response from predefined sequence (now passing the transcript for validation)
            response_text = st.session_state.assistant.handle_call(user_transcript)
            
            if response_text.startswith("SYSTEM_ERROR:"):
                st.error(f"Network or Quota Error connecting to AI. Details: {response_text}")
            elif response_text:
                # Log the AI's dialogue
                st.session_state.history.append({"role": "ai", "text": response_text})
                
                # 3. Generate Speech
                audio_filename = f"response_{int(time.time())}.mp3"
                tts_success = asyncio.run(generate_speech(response_text, audio_filename))
                
                if tts_success:
                    # Store file path in session state to trigger autoplay
                    st.session_state.audio_to_play = audio_filename
                else:
                    st.warning("Speech synthesis unreachable, but you can read the response above.")
                
                # Rerun the Streamlit app to update UI with latest history
                st.rerun()
            else:
                st.error("AI returned an empty response.")

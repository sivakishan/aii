import streamlit as st
import pandas as pd
import os
import requests
import json
import base64
from PIL import Image
import io
import time
from datetime import datetime
import tempfile
import math
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Import specialized services
from elks_service import make_reservation_call, make_connect_reservation_call, notify_user_via_call, send_reminder_sms
from maptiler_service import geocode_address, find_nearby_pharmacies, get_static_map_url, get_interactive_map_url

# TTS function
def text_to_speech(text):
    """Convert text to speech using OpenAI's TTS API"""
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "tts-1",
            "input": text[:4096],
            "voice": "nova",
            "response_format": "mp3"
        }
        
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            temp_file.write(response.content)
            temp_file.close()
            print(f"Generated audio file: {temp_file.name}")
            return temp_file.name
        else:
            print(f"Text-to-speech API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Text-to-speech exception: {str(e)}")
        return None

# GPT service function
def get_gpt_response(user_input, conversation_history, medication_db=None):
    """Get response from GPT-3.5 based on user input and conversation history"""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Prepare context from medication database if available
    medication_context = ""
    if medication_db is not None and not medication_db.empty:
        medication_context = "Here is information about some medications from our database:\n"
        for index, row in medication_db.iterrows():
            medication_context += f"- {row['Medication']}: {row['Purpose']}, Dosage: {row['Dosage']}, Side Effects: {row['Side Effects']}\n"
    
    # Prepare messages for API
    messages = [
        {
            "role": "system",
            "content": f"""You are a helpful healthcare assistant designed specifically for elderly users.
            Your goal is to provide clear, simple, and accurate information about medications.
            You should speak in a kind, patient manner and avoid using complex medical terminology.
            If you're unsure about any medication details, acknowledge it and suggest consulting a healthcare professional.
            Never provide medical advice that could be harmful.
            Keep your responses brief and to the point, as they will be spoken out loud.
            You are currently being used in Stockholm, Sweden.
            
            {medication_context}
            """
        }
    ]
    
    # Add conversation history (limit to last 10 messages to save tokens)
    for message in conversation_history[-10:]:
        if "role" in message and "content" in message:
            messages.append({
                "role": message["role"],
                "content": message["content"]
            })
    
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 300
    }
    
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            print(f"Error in GPT response: {response.status_code} - {response.text}")
            return "I'm sorry, I encountered an error while processing your request. Please try again later."
    except Exception as e:
        print(f"Exception in GPT response: {str(e)}")
        return "I'm sorry, I encountered an error while processing your request. Please try again later."

# Create sample medication database
def create_sample_medication_database():
    """Create a sample medication database"""
    data = {
        'Medication': [
            'Aspirin', 'Lisinopril', 'Metformin', 'Atorvastatin', 'Omeprazole',
            'Amlodipine', 'Levothyroxine', 'Simvastatin', 'Metoprolol', 'Gabapentin'
        ],
        'Purpose': [
            'Pain relief, fever reduction', 'Blood pressure management',
            'Diabetes management', 'Cholesterol management', 'Acid reflux, heartburn',
            'Blood pressure management', 'Thyroid hormone replacement',
            'Cholesterol management', 'Heart rate and blood pressure control',
            'Nerve pain, seizures'
        ],
        'Dosage': [
            '81-325 mg daily', '10-40 mg once daily', '500-1000 mg twice daily',
            '10-80 mg once daily', '20-40 mg once daily', '2.5-10 mg once daily',
            '25-200 mcg once daily', '10-40 mg once daily', '25-100 mg twice daily',
            '300-600 mg three times daily'
        ],
        'Side Effects': [
            'Stomach upset, bleeding risk', 'Dry cough, dizziness',
            'Nausea, diarrhea', 'Muscle pain, liver effects',
            'Headache, diarrhea', 'Swelling, headache',
            'Insomnia, headache', 'Muscle pain, digestive issues',
            'Fatigue, dizziness', 'Drowsiness, dizziness'
        ]
    }
    
    return pd.DataFrame(data)

# Main Streamlit application
def main():
    # Page configuration
    st.set_page_config(
        page_title="Voice Healthcare Assistant",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS and JavaScript for senior-friendly interface and reliable autoplay
    st.markdown("""
    <style>
        body {
            background-color: #121212;
            color: #FFFFFF;
        }
        .main {
            font-size: 1.2rem;
        }
        .stButton button {
            font-size: 1.5rem;
            padding: 1rem 2rem;
            border-radius: 1rem;
            background-color: #4CAF50;
            color: white;
        }
        .voice-button button {
            background-color: #2196F3;
            font-size: 1.8rem;
        }
        .stTextInput input, .stSelectbox select {
            font-size: 1.2rem;
            padding: 0.5rem;
        }
        h1 {
            color: #FFFFFF;
            text-align: center;
            margin-bottom: 2rem;
        }
        h2, h3 {
            margin-bottom: 1rem;
            color: #FFFFFF;
        }
        .highlight {
            background-color: #2d2d2d;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            color: #FFFFFF;
        }
        .user-message {
            background-color: #1e3a8a;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            color: #FFFFFF !important;
            border-left: 4px solid #2563eb;
            font-size: 1.1rem;
        }
        .assistant-message {
            background-color: #1e3a1e;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            color: #FFFFFF !important;
            border-left: 4px solid #22c55e;
            font-size: 1.1rem;
        }
        .selected-pharmacy {
            background-color: #1e3a1e;
            border-left: 4px solid #22c55e;
        }
        .footer {
            margin-top: 50px;
            text-align: center;
            color: #9e9e9e;
            padding: 20px;
        }
        audio {
            width: 100%;
            height: 40px;
            margin-top: 5px;
            background-color: #333;
            border-radius: 5px;
        }
        .stTextArea textarea {
            background-color: #2d2d2d;
            color: white;
        }
        .stTextInput input {
            background-color: #2d2d2d;
            color: white;
        }
        .stSelectbox select {
            background-color: #2d2d2d;
            color: white;
        }
        .test-audio-btn {
            background-color: #ff5722;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin: 10px 0;
            font-size: 16px;
        }
    </style>
    <script>
        function autoPlayLatestAudio() {
            const audios = document.getElementsByTagName('audio');
            if (audios.length > 0) {
                const latestAudio = audios[audios.length - 1];
                if (!latestAudio.hasAttribute('data-played')) {
                    latestAudio.play().then(() => {
                        latestAudio.setAttribute('data-played', 'true');
                        console.log('Playing latest audio');
                    }).catch(err => {
                        console.error('Autoplay failed:', err);
                        document.getElementById('audio-message').style.display = 'block';
                    });
                }
            }
        }

        function initAudioPlayback() {
            document.body.addEventListener('click', () => {
                const silentAudio = new Audio('data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4LjI5LjEwMAAAAAAAAAAAAAAA//tQwAAAAAAAAAAAAAAAAAAAAAAASW5mbwAAAA8AAAACAAABIADAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV6urq6urq6urq6urq6urq6urq6urq6urq6v////////////////////////////////8AAAAATGF2YzU4LjU0AAAAAAAAAAAAAAAAJAYAAAAAAAAAkCBTFDEAAAAAAAAAAAAAAAAAAP/7kMQAAAAAAAAAAAAAAAAAAAAAAFhpbmcAAAAPAAAAAwAAA1gAjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIAAAABMYXZjNTguMTAyAAAAAAAAAAAAAAAAEQAAAAAAAAAAAAAA//swxEsAAAGkAAAAwEAAAL/AAAA0gAAABFRFRUVFRERERERERERERESqqqqqqqqqqqqqqqqqqqqqqoAAAAAAKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqg==');
                silentAudio.play().then(() => {
                    console.log('Audio playback unlocked');
                    setInterval(autoPlayLatestAudio, 1000);
                }).catch(e => console.error('Could not unlock audio:', e));
            }, {once: true});
        }

        function testAudio() {
            const testSound = new Audio('data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4LjI5LjEwMAAAAAAAAAAAAAAA//tQwAAAAAAAAAAAAAAAAAAAAAAASW5mbwAAAA8AAAACAAABIADAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV6urq6urq6urq6urq6urq6urq6urq6urq6v////////////////////////////////8AAAAATGF2YzU4LjU0AAAAAAAAAAAAAAAAJAYAAAAAAAAAkCBTFDEAAAAAAAAAAAAAAAAAAP/7kMQAAAAAAAAAAAAAAAAAAAAAAFhpbmcAAAAPAAAAAwAAA1gAjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIAAAABMYXZjNTguMTAyAAAAAAAAAAAAAAAAEQAAAAAAAAAAAAAA//swxEsAAAGkAAAAwEAAAL/AAAA0gAAABFRFRUVFRERERERERERERESqqqqqqqqqqqqqqqqqqqqqqoAAAAAAKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqg==');
            testSound.play().then(() => {
                console.log('Test audio played');
                document.getElementById('audio-status').innerHTML = 'Audio system working!';
                setInterval(autoPlayLatestAudio, 1000);
            }).catch(e => {
                console.error('Test audio failed:', e);
                document.getElementById('audio-status').innerHTML = 'Please enable audio in your browser settings.';
            });
        }

        document.addEventListener('DOMContentLoaded', initAudioPlayback);
    </script>
    <div id="audio-message" style="display:none; background-color: #ff5722; color: white; padding: 10px; border-radius: 5px; margin: 10px 0;">
        Please interact with the page to enable audio playback. <button onclick="testAudio()" class="test-audio-btn">Test Audio</button>
    </div>
    <div id="audio-status" style="margin-top: 5px;"></div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []
    if "medication_db" not in st.session_state:
        st.session_state.medication_db = create_sample_medication_database()
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = {
            "name": "User",
            "phone": "+46701234567",
            "address": "Sergels Torg, Stockholm",
            "allergies": "",
            "conditions": ""
        }
    if "current_pharmacy" not in st.session_state:
        st.session_state.current_pharmacy = None
    if "pharmacies" not in st.session_state:
        st.session_state.pharmacies = []
    if "voice_active" not in st.session_state:
        st.session_state.voice_active = True
    if "last_response" not in st.session_state:
        st.session_state.last_response = ""
    if "audio_file" not in st.session_state:
        st.session_state.audio_file = None
    if "last_query" not in st.session_state:
        st.session_state.last_query = ""
    if "session_started" not in st.session_state:
        st.session_state.session_started = False
    if "map_url" not in st.session_state:
        stockholm_coords = geocode_address("Stockholm")
        st.session_state.map_url = get_static_map_url(stockholm_coords[0], stockholm_coords[1])
    if "reservation_history" not in st.session_state:
        st.session_state.reservation_history = []
    
    # Main application layout
    st.title("🔊 Voice Healthcare Assistant")
    
    # Sidebar for user profile
    with st.sidebar:
        st.header("User Profile")
        st.session_state.user_profile["name"] = st.text_input("Name", st.session_state.user_profile["name"])
        st.session_state.user_profile["phone"] = st.text_input("Phone", st.session_state.user_profile["phone"])
        st.session_state.user_profile["address"] = st.text_area("Address", st.session_state.user_profile["address"])
        st.session_state.user_profile["allergies"] = st.text_area("Allergies", st.session_state.user_profile["allergies"])
        st.session_state.user_profile["conditions"] = st.text_area("Medical Conditions", st.session_state.user_profile["conditions"])
        
        st.subheader("Voice Settings")
        st.session_state.voice_active = st.toggle("Enable Voice", st.session_state.voice_active)
        
        if st.session_state.reservation_history:
            st.subheader("Recent Reservations")
            for res in st.session_state.reservation_history[-3:]:
                st.markdown(f"""
                <div class="highlight">
                    <strong>{res['medication']}</strong> ({res['quantity']}) at {res['pharmacy']}<br>
                    Status: {res['status']}<br>
                    Time: {res['time']}<br>
                    Call Type: {res['call_type']}
                </div>
                """, unsafe_allow_html=True)
    
    # Welcome message on first load
    if not st.session_state.session_started:
        welcome_msg = f"Hello {st.session_state.user_profile['name']}! I'm your health assistant. How can I help you today?"
        
        if st.session_state.voice_active:
            audio_file = text_to_speech(welcome_msg)
        else:
            audio_file = None
        
        st.session_state.conversation_history.append({
            "role": "assistant",
            "content": welcome_msg,
            "audio_file": audio_file
        })
        
        st.session_state.last_response = welcome_msg
        st.session_state.audio_file = audio_file
        st.session_state.session_started = True
        
        # Find pharmacies at startup
        pharmacies = find_nearby_pharmacies(st.session_state.user_profile["address"] or "Stockholm")
        if pharmacies:
            st.session_state.pharmacies = pharmacies
    
    # Main content columns
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header("Conversation")
        
        # Display conversation history with audio
        conversation_container = st.container()
        with conversation_container:
            for i, message in enumerate(st.session_state.conversation_history):
                role = message.get("role", "")
                content = message.get("content", "")
                
                if role == "user":
                    st.markdown(f"<div class='user-message'><strong>You:</strong> {content}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='assistant-message'><strong>Assistant:</strong> {content}</div>", unsafe_allow_html=True)
                    
                    if st.session_state.voice_active and "audio_file" in message and message["audio_file"]:
                        try:
                            if os.path.exists(message["audio_file"]):
                                st.audio(message["audio_file"], format="audio/mp3")
                            else:
                                st.warning(f"Audio file not found: {message['audio_file']}")
                        except Exception as e:
                            st.warning(f"Error playing audio: {str(e)}")
        
        # Text input for queries
        user_input = st.text_area("Type your query about medications, health, or finding a pharmacy:", height=100)
        
        if st.button("Submit", use_container_width=True):
            if user_input:
                with st.spinner("Processing your request..."):
                    st.session_state.conversation_history.append({"role": "user", "content": user_input})
                    
                    response = get_gpt_response(user_input, st.session_state.conversation_history, st.session_state.medication_db)
                    
                    audio_file = text_to_speech(response) if st.session_state.voice_active else None
                    
                    st.session_state.conversation_history.append({
                        "role": "assistant",
                        "content": response,
                        "audio_file": audio_file
                    })
                    
                    if any(keyword in user_input.lower() for keyword in ["pharmacy", "drugstore", "apoteket", "apotek", "medication", "medicine", "prescription"]):
                        user_address = st.session_state.user_profile["address"] or "Stockholm"
                        
                        pharmacies = find_nearby_pharmacies(user_address)
                        if pharmacies:
                            st.session_state.pharmacies = pharmacies
                            
                            coordinates = geocode_address(user_address)
                            if coordinates:
                                st.session_state.map_url = get_static_map_url(coordinates[0], coordinates[1])
                            
                            pharm_response = f"I found {len(pharmacies)} pharmacies near {user_address}. The closest is {pharmacies[0]['name']} which is {pharmacies[0]['distance']} km away."
                            
                            pharm_audio = text_to_speech(pharm_response) if st.session_state.voice_active else None
                            
                            st.session_state.conversation_history.append({
                                "role": "assistant",
                                "content": pharm_response,
                                "audio_file": pharm_audio
                            })
                    
                st.rerun()
        
        st.subheader("Quick Options")
        col_q1, col_q2, col_q3 = st.columns(3)
        
        with col_q1:
            if st.button("Find nearby pharmacies", use_container_width=True):
                query = f"Where can I find the nearest pharmacy near {st.session_state.user_profile['address'] or 'Stockholm'}?"
                st.session_state.conversation_history.append({"role": "user", "content": query})
                st.session_state.last_query = query
                st.rerun()
                
        with col_q2:
            if st.button("Common medications", use_container_width=True):
                query = "What are some common medications for high blood pressure?"
                st.session_state.conversation_history.append({"role": "user", "content": query})
                st.session_state.last_query = query
                st.rerun()
                
        with col_q3:
            if st.button("Medication reminders", use_container_width=True):
                query = "How can I remember to take my medications on time?"
                st.session_state.conversation_history.append({"role": "user", "content": query})
                st.session_state.last_query = query
                st.rerun()
    
    with col2:
        st.header("Pharmacy Finder")
        
        st.subheader("Map")
        if st.session_state.map_url:
            st.image(st.session_state.map_url, use_column_width=True)
            
            user_address = st.session_state.user_profile["address"] or "Stockholm"
            coordinates = geocode_address(user_address)
            if coordinates:
                interactive_map_url = get_interactive_map_url(coordinates[0], coordinates[1])
                st.markdown(f"[Open interactive map]({interactive_map_url})", unsafe_allow_html=True)
        
        if st.session_state.pharmacies:
            st.subheader("Nearby Pharmacies")
            for i, pharmacy in enumerate(st.session_state.pharmacies):
                is_selected = st.session_state.current_pharmacy and st.session_state.current_pharmacy.get("name") == pharmacy["name"]
                highlight_class = "highlight selected-pharmacy" if is_selected else "highlight"
                
                st.markdown(f"""
                <div class="{highlight_class}">
                    <strong>{pharmacy['name']}</strong><br>
                    {pharmacy['address']}<br>
                    {pharmacy['distance']} km away
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Select {pharmacy['name']}", key=f"select_{i}"):
                    st.session_state.current_pharmacy = pharmacy
                    select_msg = f"Selected {pharmacy['name']}."
                    st.success(select_msg)
                    
                    if st.session_state.voice_active:
                        audio_file = text_to_speech(select_msg)
                        if audio_file:
                            st.audio(audio_file, format="audio/mp3")
        
        if st.session_state.current_pharmacy:
            st.subheader("Reserve Medication")
            st.write(f"Selected: {st.session_state.current_pharmacy['name']}")
            
            medication_options = st.session_state.medication_db['Medication'].tolist()
            medication_name = st.selectbox("Medication:", medication_options)
            quantity = st.number_input("Quantity:", min_value=1, value=1)
            
            use_connect_call = st.checkbox("Connect me directly to the pharmacy", value=False)
            
            if st.button("Make Reservation Call", use_container_width=True):
                if medication_name and st.session_state.user_profile["phone"]:
                    with st.spinner("Setting up reservation call..."):
                        if use_connect_call:
                            result = make_connect_reservation_call(
                                st.session_state.user_profile["name"],
                                st.session_state.user_profile["phone"],
                                st.session_state.current_pharmacy,
                                medication_name,
                                quantity
                            )
                        else:
                            result = make_reservation_call(
                                st.session_state.user_profile["name"],
                                st.session_state.user_profile["phone"],
                                st.session_state.current_pharmacy,
                                medication_name,
                                quantity
                            )
                        
                        if result["success"]:
                            success_msg = f"Reservation call initiated for {quantity} {medication_name} at {st.session_state.current_pharmacy['name']}. {'You will be connected directly.' if use_connect_call else 'The pharmacy will receive a call to confirm your reservation.'}"
                            st.success(success_msg)
                            
                            audio_file = text_to_speech(success_msg) if st.session_state.voice_active else None
                            st.session_state.conversation_history.append({
                                "role": "assistant",
                                "content": success_msg,
                                "audio_file": audio_file
                            })
                            
                            st.session_state.reservation_history.append({
                                "medication": medication_name,
                                "quantity": quantity,
                                "pharmacy": st.session_state.current_pharmacy["name"],
                                "status": "Pending",
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "reservation_id": result.get("reservation_id", ""),
                                "call_id": result.get("call_id", ""),
                                "call_type": result.get("call_type", "ivr")
                            })
                            
                            if audio_file:
                                st.audio(audio_file, format="audio/mp3")
                            
                            st.info("Waiting for pharmacy confirmation...")
                        else:
                            st.error(f"Failed to set up reservation: {result['message']}")
                else:
                    st.warning("Please fill in medication name and ensure your phone number is set in your profile")
            
            if st.button("Schedule SMS Reminder", use_container_width=True):
                with st.spinner("Setting up medication reminder..."):
                    reminder_result = send_reminder_sms(
                        st.session_state.user_profile["name"],
                        st.session_state.user_profile["phone"],
                        medication_name,
                        "now"
                    )
                    
                    if reminder_result["success"]:
                        st.success(f"SMS reminder for {medication_name} has been set up.")
                    else:
                        st.error(f"Failed to set up reminder: {reminder_result['message']}")
    
    # Footer
    st.markdown("---")
    
    col_clear, col_help = st.columns(2)
    
    with col_clear:
        if st.button("🧹 Clear Conversation", use_container_width=True):
            reservation_history = st.session_state.reservation_history
            map_url = st.session_state.map_url
            pharmacies = st.session_state.pharmacies
            current_pharmacy = st.session_state.current_pharmacy
            
            st.session_state.conversation_history = []
            st.session_state.last_response = ""
            st.session_state.audio_file = None
            st.session_state.session_started = False
            
            st.session_state.reservation_history = reservation_history
            st.session_state.map_url = map_url
            st.session_state.pharmacies = pharmacies
            st.session_state.current_pharmacy = current_pharmacy
            
            st.rerun()
    
    with col_help:
        if st.button("❓ Help & Instructions", use_container_width=True):
            help_msg = """
            This healthcare assistant helps you with:
            
            1. Information about medications
            2. Finding nearby pharmacies in Stockholm
            3. Setting up medication reservations and reminders
            
            Use the text area to type questions, or try the quick option buttons.
            When you find a pharmacy you like, select it and use the reservation feature.
            Check 'Connect me directly to the pharmacy' to speak with the pharmacy directly.
            
            If you don't hear any audio, click the page to enable voice.
            """
            
            st.session_state.conversation_history.append({
                "role": "assistant",
                "content": help_msg,
                "audio_file": text_to_speech(help_msg) if st.session_state.voice_active else None
            })
            
            st.rerun()
    
    st.markdown("<div class='footer'>Healthcare Assistant v2.1 | Voice-Enabled & Sweden-Ready</div>", unsafe_allow_html=True)

    # Process last query if present
    if st.session_state.last_query and st.session_state.last_query != "":
        response = get_gpt_response(st.session_state.last_query, st.session_state.conversation_history, st.session_state.medication_db)
        
        audio_file = text_to_speech(response) if st.session_state.voice_active else None
        
        st.session_state.conversation_history.append({
            "role": "assistant",
            "content": response,
            "audio_file": audio_file
        })
        
        st.session_state.last_query = ""
        
        st.rerun()

if __name__ == "__main__":
    main()
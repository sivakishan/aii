# === Voice Healthcare Assistant with Persistent Autoplay Fix ===
# Streamlit app with improved one-time audio unlock using localStorage

import streamlit as st
import pandas as pd
import os
import requests
import json
import tempfile
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# TTS function
def text_to_speech(text):
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
    response = requests.post("https://api.openai.com/v1/audio/speech", headers=headers, json=payload)
    if response.status_code == 200:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_file.write(response.content)
        temp_file.close()
        return temp_file.name
    return None

# GPT function
def get_gpt_response(user_input, history=[]):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    messages = [{"role": "system", "content": "You are a helpful assistant for elderly healthcare guidance."}]
    messages += history[-5:] + [{"role": "user", "content": user_input}]
    payload = {"model": "gpt-3.5-turbo", "messages": messages}
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    return "I'm sorry, something went wrong."

# App
st.set_page_config(page_title="Voice Healthcare Assistant", layout="centered")
st.title("🩺 Voice Healthcare Assistant")

st.markdown("""
<style>
    audio {
        width: 100%;
        height: 40px;
        margin-top: 5px;
        background-color: #333;
        border-radius: 5px;
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

    function unlockAudioPlayback() {
        const silentAudio = new Audio('data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4LjI5LjEwMAAAAAAAAAAAAAAA...');
        silentAudio.play().then(() => {
            console.log('Audio playback unlocked');
            localStorage.setItem('audioUnlocked', 'true');
            setInterval(autoPlayLatestAudio, 1000);
        }).catch(e => console.error('Could not unlock audio:', e));
    }

    document.addEventListener('DOMContentLoaded', () => {
        const alreadyUnlocked = localStorage.getItem('audioUnlocked') === 'true';
        if (!alreadyUnlocked) {
            document.body.addEventListener('click', unlockAudioPlayback, { once: true });
            document.getElementById('audio-message').style.display = 'block';
        } else {
            unlockAudioPlayback();
        }
    });
</script>
<div id="audio-message" style="display:none; background-color: #ff5722; color: white; padding: 10px; border-radius: 5px; margin: 10px 0;">
    🔊 Please click anywhere once to enable voice playback.
</div>
""", unsafe_allow_html=True)

if "conversation" not in st.session_state:
    st.session_state.conversation = []

st.markdown("""
Type or ask a health-related question. The assistant will speak back.  
Voice will autoplay after your first interaction.
""")

user_input = st.text_input("Your question:")
if user_input:
    st.session_state.conversation.append({"role": "user", "content": user_input})
    reply = get_gpt_response(user_input, st.session_state.conversation)
    st.session_state.conversation.append({"role": "assistant", "content": reply})
    st.markdown(f"**Assistant:** {reply}")
    audio_file = text_to_speech(reply)
    if audio_file:
        st.audio(audio_file, format="audio/mp3")
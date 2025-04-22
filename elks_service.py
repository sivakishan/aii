import requests
import base64
import datetime
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# 46elks API credentials from .env
ELKS_API_USERNAME = os.getenv("ELKS_API_USERNAME")
ELKS_API_PASSWORD = os.getenv("ELKS_API_PASSWORD")
ELKS_FROM_NUMBER = os.getenv("ELKS_FROM_NUMBER")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

def format_phone_number(phone):
    """Format phone number to ensure it has a country code"""
    # Remove any spaces, dashes, or parentheses
    phone = ''.join(filter(str.isdigit, phone))
    
    # If the number doesn't start with +, add +46 (Sweden country code)
    if not phone.startswith('+'):
        if phone.startswith('46'):
            phone = '+' + phone
        elif phone.startswith('0'):  # Swedish number starting with 0
            phone = '+46' + phone[1:]
        else:
            phone = '+46' + phone
            
    return phone

def make_reservation_call(user_name, user_phone, pharmacy, medication_name, quantity):
    """Make a reservation call to the pharmacy using 46elks API with IVR"""
    # Format phone numbers correctly for Sweden
    user_phone = format_phone_number(user_phone)
    pharmacy_phone = format_phone_number(pharmacy.get("phone", ""))
    
    # For development/testing purposes, print the actual numbers being used
    print(f"User phone: {user_phone}")
    print(f"Pharmacy phone: {pharmacy_phone}")
    
    # Create voice XML content
    voice_start = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <ivr>
        <play>
            <voice>
                This is a call from the Healthcare Assistant app on behalf of {user_name}.
                A request has been made to reserve {quantity} of {medication_name}.
                If you can fulfill this request, please call {user_phone} to confirm.
                Thank you.
            </voice>
        </play>
    </ivr>
    """
    
    try:
        # Set up authentication for 46elks API
        auth = base64.b64encode(f"{ELKS_API_USERNAME}:{ELKS_API_PASSWORD}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Prepare the payload for the call
        payload = {
            "from": ELKS_FROM_NUMBER,
            "to": pharmacy_phone,
            "voice_start": voice_start,
            "next": WEBHOOK_URL  # Webhook for call status updates
        }
        
        # For debug purposes, print the payload
        print(f"Payload: {payload}")
        
        # Make the API request to 46elks
        response = requests.post(
            "https://api.46elks.com/a1/calls",
            headers=headers,
            data=payload
        )
        
        # Log the complete response for debugging
        print(f"46elks response status: {response.status_code}")
        print(f"46elks response content: {response.text}")
        
        if response.status_code == 200:
            call_info = response.json()
            return {
                "success": True,
                "message": "Call initiated successfully",
                "call_id": call_info.get("id", ""),
                "reservation_id": f"res_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "call_type": "ivr"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to initiate call: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        print(f"Exception details: {str(e)}")
        return {
            "success": False,
            "message": f"Exception during call initiation: {str(e)}"
        }

def make_connect_reservation_call(user_name, user_phone, pharmacy, medication_name, quantity):
    """Make a reservation call to the pharmacy and connect to the user using 46elks API"""
    # Format phone numbers correctly for Sweden
    user_phone = format_phone_number(user_phone)
    pharmacy_phone = format_phone_number(pharmacy.get("phone", ""))
    
    # For development/testing purposes, print the actual numbers being used
    print(f"User phone: {user_phone}")
    print(f"Pharmacy phone: {pharmacy_phone}")
    
    # Create voice_start JSON for connect action
    voice_start = json.dumps({"connect": user_phone})
    
    try:
        # Set up authentication for 46elks API
        auth = (ELKS_API_USERNAME, ELKS_API_PASSWORD)
        
        # Prepare the payload for the call
        payload = {
            "from": ELKS_FROM_NUMBER,
            "to": pharmacy_phone,
            "voice_start": voice_start,
            "next": WEBHOOK_URL  # Webhook for call status updates
        }
        
        # For debug purposes, print the payload
        print(f"Payload: {payload}")
        
        # Make the API request to 46elks
        response = requests.post(
            "https://api.46elks.com/a1/calls",
            auth=auth,
            data=payload
        )
        
        # Log the complete response for debugging
        print(f"46elks response status: {response.status_code}")
        print(f"46elks response content: {response.text}")
        
        if response.status_code == 200:
            call_info = response.json()
            return {
                "success": True,
                "message": "Connect call initiated successfully",
                "call_id": call_info.get("id", ""),
                "reservation_id": f"res_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "call_type": "connect"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to initiate connect call: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        print(f"Exception details: {str(e)}")
        return {
            "success": False,
            "message": f"Exception during connect call initiation: {str(e)}"
        }

def notify_user_via_call(user_name, user_phone, reservation_status, pharmacy_name, medication_name, quantity):
    """Call the user to notify them about their reservation status"""
    # Format phone number
    user_phone = format_phone_number(user_phone)
    
    # Create voice message based on status
    if reservation_status == 'confirmed':
        message = f"""
        Hello {user_name}, this is your healthcare assistant.
        Good news! Your reservation for {quantity} of {medication_name} has been accepted by {pharmacy_name}.
        You can pick up your medication at your convenience.
        """
    else:
        message = f"""
        Hello {user_name}, this is your healthcare assistant.
        Unfortunately, {pharmacy_name} was unable to fulfill your reservation for {medication_name}.
        You may want to try a different pharmacy.
        """
    
    # Create voice XML content
    voice_start = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <ivr>
        <play>
            <voice>{message}</voice>
        </play>
        <gather timeout="5" numdigits="1">
            <play>
                <voice>Press 1 to confirm you received this message.</voice>
            </play>
        </gather>
    </ivr>
    """
    
    try:
        # Set up authentication for 46elks API
        auth = base64.b64encode(f"{ELKS_API_USERNAME}:{ELKS_API_PASSWORD}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Prepare the payload for the call
        payload = {
            "from": ELKS_FROM_NUMBER,
            "to": user_phone,
            "voice_start": voice_start,
            "next": WEBHOOK_URL,
            "recordcall": "no"
        }
        
        # Make the API request to 46elks
        response = requests.post(
            "https://api.46elks.com/a1/calls",
            headers=headers,
            data=payload
        )
        
        if response.status_code == 200:
            call_info = response.json()
            return {
                "success": True,
                "message": "Notification call initiated successfully",
                "call_id": call_info.get("id", "")
            }
        else:
            return {
                "success": False,
                "message": f"Failed to initiate notification call: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"Exception during notification call: {str(e)}"
        }

def send_reminder_sms(user_name, user_phone, medication_name, time):
    """Send an SMS reminder to take medication"""
    # Format phone number
    user_phone = format_phone_number(user_phone)
    
    # Create SMS message
    message = f"Hello {user_name}, this is your healthcare assistant. It's time to take your {medication_name}."
    
    try:
        # Set up authentication for 46elks API
        auth = base64.b64encode(f"{ELKS_API_USERNAME}:{ELKS_API_PASSWORD}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Prepare the payload for the SMS
        payload = {
            "from": "HealthApp",
            "to": user_phone,
            "message": message
        }
        
        # Make the API request to 46elks
        response = requests.post(
            "https://api.46elks.com/a1/sms",
            headers=headers,
            data=payload
        )
        
        if response.status_code == 200:
            sms_info = response.json()
            return {
                "success": True,
                "message": "SMS sent successfully",
                "sms_id": sms_info.get("id", "")
            }
        else:
            return {
                "success": False,
                "message": f"Failed to send SMS: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"Exception during SMS sending: {str(e)}"
        }
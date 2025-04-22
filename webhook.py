from flask import Flask, request, Response
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route('/webhook/46elks', methods=['POST'])
def webhook():
    data = request.form.to_dict()
    with open('call_log.json', 'a') as f:
        json.dump(data, f)
        f.write('\n')
    print(f"Webhook received: {data}")
    
    # Simulate notifying user when call is answered
    if data.get('status') == 'answered':
        print("Call answered, triggering user notification")
        # In a real app, trigger notify_user_via_call here
        # For demo, log the event
        with open('notifications.txt', 'a') as f:
            f.write(f"Notification triggered for call {data.get('id')} at {datetime.now()}\n")
    
    return Response(status=200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
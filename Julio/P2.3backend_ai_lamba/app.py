import boto3
import requests
import json

"""
AWS Lambda Function - GroupMe + Gemini AI Integration
-----------------------------------------------------
Phase: P2.3
This Lambda receives GroupMe messages via a bot callback,
sends the text to Google's Gemini API, parses the AI's JSON response,
and logs the structured event data to CloudWatch for validation.
"""

# === Secure Key Retrieval (P2.1) ===
def get_gemini_api_key():
    s3 = boto3.client('s3')
    bucket_name = 'groupme-bucket'         # ✅ your S3 bucket name
    file_key = 'gemini_api_key.txt'            # ✅ your file name in S3
    response = s3.get_object(Bucket=bucket_name, Key=file_key)
    return response['Body'].read().decode('utf-8').strip()


# === Main Lambda Handler (P2.2 + P2.3) ===
def lambda_handler(event, context):
    # Step 1: Parse incoming GroupMe message
    try:
        data = json.loads(event["body"]) if "body" in event else event
        message_text = data.get("text", "")
        sender = data.get("name", "Unknown")
        print(f"📩 Message from {sender}: {message_text}")
    except Exception as e:
        print("⚠️ Error reading message:", e)
        message_text = "Test: Soccer Club meeting Friday 6PM in the gym"

    # Step 2: Load Gemini API key securely
    api_key = get_gemini_api_key()

    # Step 3: Call Gemini API with structured prompt
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}

    prompt = f"""
Analyze the following message and extract event details in JSON format.
Respond ONLY with valid JSON, no extra text.

Message: "{message_text}"

Output format:
{{
  "event_found": true/false,
  "event_title": "string",
  "event_date": "string",
  "event_time": "string",
  "event_location": "string"
}}
"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            ai_text = data["candidates"][0]["content"]["parts"][0]["text"]
            print(f"🤖 Gemini Raw Output:\n{ai_text}")

            # Step 4: Parse Gemini JSON output (smart filter)
            try:
                event_data = json.loads(ai_text)
                print("🧩 Parsed Event Data:", event_data)

                if event_data.get("event_found"):
                    print("✅ Valid event detected! Logging event details:")
                    print(json.dumps(event_data, indent=2))
                else:
                    print("ℹ️ No event detected in message.")

            except json.JSONDecodeError:
                print("⚠️ Gemini output was not valid JSON.")
                print(ai_text)
        else:
            print(f"⚠️ Gemini API Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"⚠️ Request to Gemini failed: {e}")

    # Step 5: Always return 200 OK so GroupMe doesn’t retry endlessly
    return {
        "statusCode": 200,
        "body": json.dumps({"received": message_text})
    }

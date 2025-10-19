import boto3
import requests
import json

"""
AWS Lambda Function - GroupMe + Gemini AI Integration (Secure Version)
----------------------------------------------------------------------
Phase: P2.4
Adds robust error handling and IAM-secure design for S3 + Gemini API....
"""

# === Secure Key Retrieval with Error Handling (P2.4) ===
def get_gemini_api_key():
    try:
        s3 = boto3.client('s3')
        bucket_name = 'groupme-bucket'
        file_key = 'gemini_api_key.txt'

        response = s3.get_object(Bucket=bucket_name, Key=file_key)
        api_key = response['Body'].read().decode('utf-8').strip()

        if not api_key:
            raise ValueError("Gemini API key is empty in S3.")
        return api_key

    except Exception as e:
        print(f"🚨 Failed to retrieve Gemini API key: {e}")
        raise


# === Main Lambda Handler ===
def lambda_handler(event, context):
    try:
        # Step 1: Parse incoming message
        try:
            data = json.loads(event["body"]) if "body" in event else event
            message_text = data.get("text", "")
            sender = data.get("name", "Unknown")
            print(f"📩 Message from {sender}: {message_text}")
        except Exception as e:
            print(f"⚠️ Failed to parse incoming event: {e}")
            message_text = "Test: Club meeting Friday 6PM in the gym"

        # Step 2: Load Gemini API key securely
        try:
            api_key = get_gemini_api_key()
        except Exception as e:
            print("❌ Cannot proceed: Gemini API key unavailable.")
            return {"statusCode": 500, "body": json.dumps({"error": "Missing Gemini API key."})}

        # Step 3: Prepare Gemini request
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

        # Step 4: Send request to Gemini
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
        except requests.exceptions.Timeout:
            print("⚠️ Gemini API request timed out.")
            return {"statusCode": 504, "body": json.dumps({"error": "Gemini API timeout."})}
        except Exception as e:
            print(f"⚠️ Gemini API request failed: {e}")
            return {"statusCode": 500, "body": json.dumps({"error": "Gemini API request error."})}

        # Step 5: Process Gemini response
        if response.status_code == 200:
            try:
                data = response.json()
                ai_text = data["candidates"][0]["content"]["parts"][0]["text"]
                print(f"🤖 Gemini Raw Output:\n{ai_text}")

                # Parse JSON safely
                try:
                    event_data = json.loads(ai_text)
                    print("🧩 Parsed Event Data:", event_data)

                    if event_data.get("event_found"):
                        print("✅ Valid event detected! Logging event:")
                        print(json.dumps(event_data, indent=2))
                    else:
                        print("ℹ️ No event detected.")
                except json.JSONDecodeError:
                    print("⚠️ Gemini output invalid JSON. Logging raw text.")
                    print(ai_text)

            except Exception as e:
                print(f"⚠️ Failed to parse Gemini response JSON: {e}")
        else:
            print(f"⚠️ Gemini API error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"🚨 Unexpected Lambda failure: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    return {
        "statusCode": 200,
        "body": json.dumps({"received": message_text})
    }

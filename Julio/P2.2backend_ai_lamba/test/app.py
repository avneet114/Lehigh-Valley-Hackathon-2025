import boto3
import requests
import json

"""
AWS Lambda Function - GroupMe + Gemini AI Integration
-----------------------------------------------------
Phase: P2.2
This Lambda receives GroupMe messages via a bot callback,
sends the text to Google's Gemini API for AI summarization,
and logs the result to CloudWatch for verification.
"""

# Function to securely read Gemini key from S3 (from P2.1)
def get_gemini_api_key():
    s3 = boto3.client('s3')
    bucket_name = 'groupme-bucket'
    file_key = 'gemini_api_key.txt'
    response = s3.get_object(Bucket=bucket_name, Key=file_key)
    return response['Body'].read().decode('utf-8').strip()


def lambda_handler(event, context):
    # Step 1: Parse message directly from GroupMe callback
    try:
        data = json.loads(event["body"]) if "body" in event else event
        message_text = data.get("text", "")
        sender = data.get("name", "Unknown")
        print(f"📩 Message from {sender}: {message_text}")
    except Exception as e:
        print("⚠️ Error reading message:", e)
        message_text = "Test: Soccer Club meeting Friday 6PM in the gym"

    # Step 2: Get Gemini API key securely
    api_key = get_gemini_api_key()

    # Step 3: Call Gemini API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {"parts": [{"text": f"Summarize this message briefly: {message_text}"}]}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            ai_reply = data["candidates"][0]["content"]["parts"][0]["text"]
            print(f"🤖 Gemini Response: {ai_reply}")
        else:
            print(f"⚠️ Gemini API Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"⚠️ Request failed: {e}")

    return {
        "statusCode": 200,
        "body": json.dumps({"received": message_text})
    }

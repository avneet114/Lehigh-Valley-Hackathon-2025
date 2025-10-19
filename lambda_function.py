import json
import logging
import boto3
import requests
from datetime import datetime, timedelta

# --- Configuration ---
S3_BUCKET_NAME = 'groupme-bucket'
S3_GEMINI_KEY_FILE = 'gemini_api_key.txt'
S3_GOOGLE_CREDS_FILE = 'google_creds.json'
S3_CALENDAR_ID_FILE = 'calendar_id.txt'
TIMEZONE = 'America/New_York'
# ---------------------

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3 = boto3.client('s3')


# === Secure Secret Retrieval ===
def get_secret(file_key):
    """Retrieves a single secret string from S3 with strong error handling."""
    try:
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=file_key)
        secret = response['Body'].read().decode('utf-8').strip()
        if not secret:
            raise ValueError(f"S3 secret file '{file_key}' is empty.")
        return secret
    except Exception as e:
        logger.error(f"🚨 CRITICAL S3 ERROR: Could not load '{file_key}': {e}")
        return None


# === AI Logic (Gemini Integration) ===
def extract_event_data(api_key, raw_text):
    """Sends text to Gemini AI, handles errors, and parses structured JSON."""
    if not api_key:
        logger.error("❌ Gemini API key missing or empty.")
        return {"event_found": False}

    prompt = f"""
    You are an expert event extraction assistant. Analyze the following GroupMe message. 
    Respond ONLY with a JSON object (no commentary or markdown).

    If a clear event is found, set "event_found" to true.
    If the time is missing, assume 18:00.
    If the date is relative (e.g., 'next Friday'), resolve it using current date: {datetime.now().strftime('%Y-%m-%d')}.
    Otherwise, set "event_found" to false.

    Message: "{raw_text}"
    JSON Schema:
    {{
        "event_found": boolean,
        "title": string,
        "date": "YYYY-MM-DD" or null,
        "time": "HH:MM" or null,
        "location": string,
        "description": string
    }}
    """

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(
            url,
            headers=headers,
            data=json.dumps(payload).encode('utf-8'),  # 🔧 Fix UTF-8 encoding
            timeout=10
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("⚠️ Gemini API request timed out.")
        return {"event_found": False}
    except Exception as e:
        logger.error(f"⚠️ Gemini API request failed: {e}")
        return {"event_found": False}

    try:
        gemini_output = response.json()
        json_text_raw = gemini_output["candidates"][0]["content"]["parts"][0]["text"]

        # 🔧 Clean up Gemini’s response (strip out ```json wrappers)
        json_text = json_text_raw.strip().lstrip("```json").rstrip("```")

        event_data = json.loads(json_text)
        return event_data
    except json.JSONDecodeError:
        logger.error("⚠️ Gemini output invalid JSON. Logging raw output.")
        logger.error(json_text_raw)
        return {"event_found": False}
    except Exception as e:
        logger.error(f"⚠️ Gemini parsing failed: {e}")
        return {"event_found": False}


# === Google OAuth Access Token Refresh ===
def refresh_access_token(creds):
    """Uses refresh token to get a new, short-lived access token."""

    # ✅ Handle nested Google OAuth formats
    if "installed" in creds:
        creds = creds["installed"]
    elif "web" in creds:
        creds = creds["web"]

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": creds.get("client_id"),
        "client_secret": creds.get("client_secret"),
        "refresh_token": creds.get("refresh_token"),
        "grant_type": "refresh_token"
    }

    if not all([token_data["client_id"], token_data["client_secret"], token_data["refresh_token"]]):
        logger.error(f"❌ Missing required Google credential field(s). token_data: {token_data}")
        return None

    response = requests.post(token_url, data=token_data)
    response.raise_for_status()
    token_response = response.json()
    logger.info("🔑 Token refreshed. Expires in: %s sec", token_response.get("expires_in"))
    return token_response["access_token"]


# === Google Calendar Event Creation ===
def create_google_event(access_token, calendar_id, event_data):
    """Creates Google Calendar event."""
    try:
        start_str = f"{event_data['date']}T{event_data['time']}:00"
        start_dt = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S')
        end_dt = start_dt + timedelta(hours=1)
    except Exception as e:
        logger.error(f"Failed to format date/time: {e}")
        return {"status": "error", "message": "Invalid date/time"}

    event_body = {
        "summary": event_data['title'],
        "location": event_data['location'],
        "description": f"Group: {event_data['group_context']}\nDetails: {event_data['description']}",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE}
    }

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"

    response = requests.post(url, headers=headers, json=event_body)
    response.raise_for_status()
    return response.json()


# === MAIN LAMBDA HANDLER ===
def lambda_handler(event, context):
    try:
        # 1️⃣ Load secrets from S3
        gemini_key = get_secret(S3_GEMINI_KEY_FILE)
        google_creds_json = get_secret(S3_GOOGLE_CREDS_FILE)
        calendar_id = get_secret(S3_CALENDAR_ID_FILE)

        logger.info(f"✅ Secrets loaded | Gemini: {bool(gemini_key)}, Google: {bool(google_creds_json)}, CalID: {bool(calendar_id)}")

        if not all([gemini_key, google_creds_json, calendar_id]):
            logger.error("🚨 Missing one or more required secrets from S3.")
            return {"statusCode": 500, "body": json.dumps("Missing secrets.")}

        google_creds = json.loads(google_creds_json)

        # 2️⃣ Parse GroupMe message
        groupme_payload = json.loads(event["body"])
        if groupme_payload.get("sender_type") == "bot":
            return {"statusCode": 200, "body": "Ignored bot message"}

        raw_text = groupme_payload.get("text", "")
        group_name = groupme_payload.get("group_name", "Unknown Group")

        logger.info(f"🧠 Starting Gemini extraction for message: {raw_text[:100]}")

        # 3️⃣ Run Gemini AI extraction
        event_data = extract_event_data(gemini_key, raw_text)
        event_data["group_context"] = group_name

        logger.info(f"🗓️  Ready to create Google Calendar event for: {event_data.get('title')}")

        if event_data.get("event_found"):
            logger.info("✅ Event Detected: %s", event_data)
            access_token = refresh_access_token(google_creds)
            if not access_token:
                return {"statusCode": 500, "body": json.dumps("Failed to refresh Google access token.")}

            calendar_response = create_google_event(access_token, calendar_id, event_data)
            logger.info("🎉 Event Added to Calendar: %s", calendar_response.get("htmlLink"))
            return {
                "statusCode": 200,
                "body": json.dumps({"status": "Event created.", "link": calendar_response.get("htmlLink")})
            }
        else:
            logger.info("☑️ No event detected in message.")
            return {"statusCode": 200, "body": json.dumps({"status": "No event found."})}

    except requests.exceptions.RequestException as req_err:
        logger.error(f"!!! External API Call Error: {req_err}")
        return {"statusCode": 500, "body": json.dumps(f"API Call Error: {str(req_err)}")}
    except Exception as e:
        logger.error(f"!!! Unexpected Lambda Error: {e}")
        return {"statusCode": 500, "body": json.dumps(f"Unexpected Error: {str(e)}")}

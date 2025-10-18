import pickle
import os.path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import json

# Define the scope (permissions) for calendar event creation
# This must match the scope you configured in the Google Cloud Console
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def main():
    # Load credentials from the 'credentials.json' file
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    
    # --- CRITICAL: Force the script to request the REFRESH TOKEN ---
    # access_type='offline' is what ensures the long-term token is returned.
    creds = flow.run_local_server(
        port=0, 
        access_type='offline', 
        prompt='consent'
    )

    # --- Print the CRUCIAL SECRETS ---
    print("-" * 50)
    print("✅ REFRESH TOKEN GENERATED SUCCESSFULLY!")
    print("\n🚨🚨🚨 IMMEDIATELY SAVE THESE 3 VALUES FOR S3 (P3.5): 🚨🚨🚨")
    print("-" * 50)
    print(f"1. CLIENT ID:     {creds.client_id}")
    print(f"2. CLIENT SECRET: {creds.client_secret}")
    # This is the long-term key your Lambda will use!
    print(f"3. REFRESH TOKEN: {creds.refresh_token}")
    print("-" * 50)

if __name__ == '__main__':
    main()
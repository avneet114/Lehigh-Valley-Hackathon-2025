# Lehigh-Valley-Hackathon-2025: evento.ai

Problem: 
College students (especially freshman) join 20+ clubs at the start of the semester and drown in GroupMe messages. But event information is unstructured and easily lost. Students miss club meetings, deadlines, and social events because they can't manually sort through hundreds of casual messages.

Solution:
evento.ai is a serverless application that turns casual chat messages into perfectly scheduled Google Calendar events, automatically.

Our Core Innovation: 
We built the intelligence layer that existing automation tools like IFTTT lack. We don't rely on keywords; we rely on Generative AI to truly understand the context of the message.

How We Did It (The Architecture):

Our solution is an event-driven pipeline built on minimal, scalable services, highlighting the efficient use of the provided resources:

1. The Pipeline: Triggering the Brain
Plumbing (AWS + GroupMe): We set up a single, secure AWS API Gateway endpoint connected to an AWS Lambda function (Python 3.11). This endpoint is the webhook that receives every message in real-time from GroupMe (via a registered Bot ID).

Secure Secrets: We securely stored all necessary keys—the Gemini API Key, Google Client Secrets, and Refresh Token—in an Amazon S3 bucket. The Lambda's IAM Execution Role was specifically granted only the least privilege (s3:GetObject) needed to read those secrets.

2. The Intelligence: 
When a message hits the Lambda function, the Python code does two things:
- It checks the incoming message to avoid infinite bot loops.
- It sends the raw text (e.g., "Meeting Tuesday at 7 in the CUC 212.") to the Gemini AI.

The AI's Job: We engineered a Gemini Prompt to force the AI to execute a semantic extraction. It must detect the event, resolve relative dates ("Tuesday"), and return the data as clean, structured JSON (Title, YYYY-MM-DD, HH:MM, Location).

3. The Final Push: Calendar Creation
Token Refresh: The Lambda code retrieves the Google secrets from S3 and uses the long-lived Refresh Token to get a brand new, short-lived Access Token.

Scheduling: Finally, it uses the fresh Access Token to send a direct HTTP POST request to the Google Calendar API, creating the event instantly on the user's primary calendar.

This system guarantees that no event is lost, making student life simpler and more organized.

Try it out here: https://evento-ai.vercel.app/
Demo Video: https://youtu.be/znxbHXgup5M

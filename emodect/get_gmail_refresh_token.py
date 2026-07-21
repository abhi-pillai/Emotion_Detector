"""
One-time helper to get a Gmail API refresh token for this app to send
verification / password-reset emails from a chosen Gmail account.

Run this locally (it opens a browser window):

    pip install google-auth-oauthlib   # already in requirements.txt
    python get_gmail_refresh_token.py

You'll be asked to log into the Gmail account you want emails to be sent
FROM, and to grant this app permission to send mail as that account.
Google will then hand back a refresh token, printed to the console -
copy it into your .env as GMAIL_REFRESH_TOKEN.

This only needs to be run once per Gmail sending account. Refresh tokens
don't expire on their own (they only stop working if revoked, unused for
6 months, or the OAuth consent screen is still in "Testing" mode and it's
been 7 days - in that case just rerun this script).

Prerequisites (see .env.example for the full walkthrough):
  - A Google Cloud project with the Gmail API enabled
  - An OAuth "Desktop app" client ID + secret from that project
"""
import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main():
    client_id = os.getenv("GMAIL_CLIENT_ID") or input("Gmail OAuth client ID: ").strip()
    client_secret = os.getenv("GMAIL_CLIENT_SECRET") or input("Gmail OAuth client secret: ").strip()

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    # Opens a browser window; after you approve, this captures the tokens.
    creds = flow.run_local_server(port=0)

    print("\nSuccess! Add these to your .env:\n")
    print(f"GMAIL_CLIENT_ID={client_id}")
    print(f"GMAIL_CLIENT_SECRET={client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("\n(Set MAIL_DEFAULT_SENDER to the Gmail address you just logged in with.)")


if __name__ == "__main__":
    main()

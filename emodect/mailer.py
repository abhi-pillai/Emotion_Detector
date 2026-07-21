"""
Minimal email sending helper - uses the Gmail API over HTTPS to send mail
through a real Gmail account.

Why an HTTPS API instead of SMTP: many PaaS hosts (Render included) block
outbound SMTP ports (25/465/587) at the network level to prevent their
infrastructure being used for spam. HTTPS (443) is never blocked, so
sending mail via Google's REST API sidesteps that entirely.

Why OAuth2 + a refresh token (not just an "API key"): the Gmail API has no
concept of a simple static API key for sending mail - Google requires
OAuth2 so it knows *which* Gmail account is sending and that whoever is
calling was actually granted permission to send as that account. In
practice this means a one-time interactive authorization to obtain a
refresh token, which this app then uses forever after (refresh tokens
don't expire unless revoked) to silently mint short-lived access tokens.

One-time setup:
  1. In Google Cloud Console (https://console.cloud.google.com):
       a. Create/select a project.
       b. Enable the "Gmail API" (APIs & Services -> Library).
       c. Configure the OAuth consent screen (External is fine; add your
          own Gmail address under "Test users" if it stays in "Testing").
       d. Create OAuth client credentials of type "Desktop app"
          (APIs & Services -> Credentials -> Create Credentials ->
          OAuth client ID). Download the client_id and client_secret.
  2. Run the one-time helper script to authorize and get a refresh token:
         python get_gmail_refresh_token.py
     (opens a browser, asks you to log into the Gmail account you want to
     send from, and prints a refresh token to paste into your .env)
  3. Set these in your environment:
       GMAIL_CLIENT_ID
       GMAIL_CLIENT_SECRET
       GMAIL_REFRESH_TOKEN
       MAIL_DEFAULT_SENDER   (the Gmail address you authorized in step 2)

If GMAIL_REFRESH_TOKEN isn't configured (local development), emails are
logged instead of sent, so you can copy the link straight out of the
console.
"""
import base64
import logging
from email.mime.text import MIMEText

import requests

logger = logging.getLogger("emotion-analyzer.mail")

GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def _get_access_token(app):
    """Exchange the stored refresh token for a short-lived access token."""
    response = requests.post(
        GMAIL_TOKEN_URL,
        data={
            "client_id": app.config["GMAIL_CLIENT_ID"],
            "client_secret": app.config["GMAIL_CLIENT_SECRET"],
            "refresh_token": app.config["GMAIL_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def send_email(app, to_address, subject, body):
    """Send a plain-text email via the Gmail API.

    Returns True if the send succeeded (or was intentionally suppressed
    for local dev), False if it failed.
    """
    if app.config.get("MAIL_SUPPRESS_SEND"):
        logger.info(
            "MAIL_SUPPRESS_SEND is on (no GMAIL_REFRESH_TOKEN configured) - not sending email.\n"
            "--- Would have sent ---\nTo: %s\nSubject: %s\n\n%s\n------------------------",
            to_address,
            subject,
            body,
        )
        return True

    try:
        access_token = _get_access_token(app)
    except requests.RequestException:
        logger.exception("Failed to refresh Gmail access token")
        return False

    message = MIMEText(body)
    message["to"] = to_address
    message["from"] = app.config["MAIL_DEFAULT_SENDER"]
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            GMAIL_SEND_URL, json={"raw": raw}, headers=headers, timeout=10
        )
        if response.status_code >= 400:
            logger.error(
                "Gmail API returned %s sending to %s: %s",
                response.status_code, to_address, response.text,
            )
            return False
        return True
    except requests.RequestException:
        logger.exception("Failed to send email to %s", to_address)
        return False

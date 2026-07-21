"""
Minimal email sending helper.

Uses plain smtplib so we don't need an extra dependency (Flask-Mail) for
two email types: verification links and password reset links.

If MAIL_SERVER isn't configured (local development), emails are logged
instead of sent, so you can copy the link straight out of the console.
"""
"""
Minimal email sending helper - uses the Brevo (formerly Sendinblue) HTTPS
transactional email API.

Why an HTTPS API instead of SMTP: many PaaS hosts (Render included) block
outbound SMTP ports (25/465/587) at the network level to prevent their
infrastructure being used for spam. HTTPS (443) is never blocked, so
sending mail via a provider's REST API sidesteps that entirely.

Why Brevo specifically (over Resend): Resend only lets you send to your
own account email until you verify a domain you own. Brevo's free tier
lets you send to ANY recipient as soon as you verify a single sender
email address (just click a link Brevo emails you) - no domain needed.
Free tier: 300 emails/day, no expiration.

Setup:
  1. Sign up free at https://app.brevo.com
  2. Add your sender email under Senders, Domains & Dedicated IPs ->
     Senders -> Add a Sender, then click the verification link Brevo
     emails you.
  3. Create an API key under SMTP & API -> API Keys -> Generate a new API key.
  4. Set BREVO_API_KEY and MAIL_DEFAULT_SENDER (the verified sender
     address) in your environment.

If BREVO_API_KEY isn't configured (local development), emails are logged
instead of sent, so you can copy the link straight out of the console.
"""
import logging
import requests

logger = logging.getLogger("emotion-analyzer.mail")

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(app, to_address, subject, body):
    """Send a plain-text email via the Brevo API.

    Returns True if the send succeeded (or was intentionally suppressed
    for local dev), False if it failed.
    """
    if app.config.get("MAIL_SUPPRESS_SEND"):
        logger.info(
            "MAIL_SUPPRESS_SEND is on (no BREVO_API_KEY configured) - not sending email.\n"
            "--- Would have sent ---\nTo: %s\nSubject: %s\n\n%s\n------------------------",
            to_address,
            subject,
            body,
        )
        return True

    payload = {
        "sender": {"email": app.config["MAIL_DEFAULT_SENDER"]},
        "to": [{"email": to_address}],
        "subject": subject,
        "textContent": body,
    }
    headers = {
        "api-key": app.config["BREVO_API_KEY"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=10)
        if response.status_code >= 400:
            logger.error(
                "Brevo API returned %s sending to %s: %s",
                response.status_code, to_address, response.text,
            )
            return False
        return True
    except requests.RequestException:
        logger.exception("Failed to send email to %s", to_address)
        return False

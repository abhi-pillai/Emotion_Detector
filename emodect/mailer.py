"""
Minimal email sending helper.

Uses plain smtplib so we don't need an extra dependency (Flask-Mail) for
two email types: verification links and password reset links.

If MAIL_SERVER isn't configured (local development), emails are logged
instead of sent, so you can copy the link straight out of the console.
"""
import logging
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger("emotion-analyzer.mail")


def send_email(app, to_address, subject, body):
    """Send a plain-text email using the app's MAIL_* config.

    Returns True if a real send was attempted successfully (or suppressed
    intentionally for local dev), False if sending failed.
    """
    if app.config.get("MAIL_SUPPRESS_SEND"):
        logger.info(
            "MAIL_SUPPRESS_SEND is on (no MAIL_SERVER configured) - not sending email.\n"
            "--- Would have sent ---\nTo: %s\nSubject: %s\n\n%s\n------------------------",
            to_address,
            subject,
            body,
        )
        return True

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = app.config["MAIL_DEFAULT_SENDER"]
    msg["To"] = to_address

    try:
        with smtplib.SMTP(app.config["MAIL_SERVER"], app.config["MAIL_PORT"], timeout=10) as server:
            if app.config.get("MAIL_USE_TLS"):
                server.starttls()
            if app.config.get("MAIL_USERNAME"):
                server.login(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])
            server.sendmail(app.config["MAIL_DEFAULT_SENDER"], [to_address], msg.as_string())
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_address)
        return False

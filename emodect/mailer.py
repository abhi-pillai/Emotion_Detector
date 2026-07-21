"""
Minimal email sending helper.

Uses plain smtplib so we don't need an extra dependency (Flask-Mail) for
two email types: verification links and password reset links.

If MAIL_SERVER isn't configured (local development), emails are logged
instead of sent, so you can copy the link straight out of the console.
"""
import logging
import smtplib
import socket
from email.mime.text import MIMEText

logger = logging.getLogger("emotion-analyzer.mail")


def _connect_ipv4(host, port, timeout):
    """Connect to (host, port) forcing IPv4.

    Many PaaS hosts (Render included) don't have real IPv6 egress, even
    though the container's socket library will happily try an IPv6 address
    first if the DNS record has one. That produces `OSError: [Errno 101]
    Network is unreachable` instead of a clean connection failure or
    timeout. Explicitly resolving and connecting over IPv4 avoids this.
    """
    infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    last_exc = None
    for family, socktype, proto, _canonname, sockaddr in infos:
        try:
            sock = socket.socket(family, socktype, proto)
            sock.settimeout(timeout)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            last_exc = exc
    raise last_exc or OSError(f"Could not resolve/connect to {host}:{port} over IPv4")


class _IPv4SMTP(smtplib.SMTP):
    """smtplib.SMTP subclass that connects over IPv4 only.

    The hostname is still passed through normally, so TLS certificate
    hostname verification (starttls) continues to work correctly - only
    the underlying socket connection is forced to IPv4.
    """

    def _get_socket(self, host, port, timeout):
        return _connect_ipv4(host, port, timeout)


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
        with _IPv4SMTP(app.config["MAIL_SERVER"], app.config["MAIL_PORT"], timeout=10) as server:
            if app.config.get("MAIL_USE_TLS"):
                server.starttls()
            if app.config.get("MAIL_USERNAME"):
                server.login(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])
            server.sendmail(app.config["MAIL_DEFAULT_SENDER"], [to_address], msg.as_string())
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_address)
        return False

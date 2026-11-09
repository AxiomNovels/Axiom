import os
import smtplib
import ssl
from email.message import EmailMessage

import httpx

# Importing core.config as a side effect ensures backend/.env has already
# been loaded (core/config.py calls load_dotenv() at import time) even if
# this module happens to be imported before anything else in core/.
import core.config  # noqa: F401


SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_ADDRESS = os.getenv("SMTP_FROM_ADDRESS") or "no-reply@axiom.app"
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Axiom")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() != "false"


class EmailDeliveryError(Exception):
    """A delivery error with a message that is safe to log."""


def send_email(to_address: str, subject: str, body: str, *, delivery_id: str) -> None:
    """Submit one message to the configured mail provider."""
    subject = " ".join(subject.splitlines())
    sender = f"{SMTP_FROM_NAME} <{SMTP_FROM_ADDRESS.strip()}>"
    if SMTP_HOST and SMTP_HOST.strip().lower() == "smtp.resend.com":
        # Existing Resend SMTP passwords are also API keys.
        _send_with_resend(sender, to_address, subject, body, delivery_id)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to_address
    message.set_content(body)

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
    try:
        if SMTP_USE_TLS:
            server.starttls(context=ssl.create_default_context())
        if SMTP_USERNAME and SMTP_PASSWORD:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(message, to_addrs=[to_address])
    finally:
        # Once DATA is accepted, a QUIT failure must not retry the message.
        server.close()


def _send_with_resend(sender: str, recipient: str, subject: str, body: str, delivery_id: str) -> None:
    if not SMTP_PASSWORD or not SMTP_PASSWORD.strip():
        raise EmailDeliveryError("Resend API key missing from SMTP_PASSWORD")

    response = httpx.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {SMTP_PASSWORD.strip()}",
            "Idempotency-Key": f"inbox/{delivery_id}",
        },
        json={"from": sender, "to": [recipient], "subject": subject, "text": body},
        timeout=15,
    )
    if response.is_success:
        return

    # Resend's raw response can contain addresses. Only log known error labels.
    detail = ""
    try:
        error = response.json()
    except ValueError:
        error = None
    if isinstance(error, dict):
        name = error.get("name")
        if name in (
            "validation_error", "missing_api_key", "restricted_api_key", "suspended_api_key",
            "invalid_permission", "daily_quota_exceeded", "monthly_quota_exceeded", "rate_limit_exceeded",
            "concurrent_idempotent_requests", "invalid_idempotent_request",
        ):
            detail = f" ({name})"
        message = error.get("message")
        if response.status_code == 403 and name == "validation_error" and isinstance(message, str):
            if "domain is not verified" in message.lower():
                detail = " (sender domain not verified for this key)"
            elif "only send testing emails" in message.lower():
                detail = " (sender restricted to test emails)"
    raise EmailDeliveryError(f"Resend HTTP {response.status_code}{detail}")

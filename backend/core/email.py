import os
import smtplib
from email.message import EmailMessage

# Importing core.config as a side effect ensures backend/.env has already
# been loaded (core/config.py calls load_dotenv() at import time) even if
# this module happens to be imported before anything else in core/.
import core.config  # noqa: F401


SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_ADDRESS = os.getenv("SMTP_FROM_ADDRESS", "no-reply@axiom.app")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Axiom")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() != "false"


def send_email(to_address: str, subject: str, body: str) -> None:
    """Best-effort transactional email send.

    Configuration lives in backend/.env:
        SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
        SMTP_FROM_ADDRESS, SMTP_FROM_NAME, SMTP_USE_TLS

    If SMTP isn't configured (e.g. local dev without a mail provider),
    this logs instead of raising, so it never blocks the action (like
    signup) that triggered the notification. Any delivery failure is
    caught for the same reason -- a flaky mail server should not turn
    into a 500 for the user.
    """
    if not to_address:
        return

    if not SMTP_HOST:
        print(f"[email] SMTP not configured; skipping email to {to_address}: {subject}")
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_ADDRESS}>"
    message["To"] = to_address
    message.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
    except Exception as error:
        print(f"[email] failed to send email to {to_address}: {error}")
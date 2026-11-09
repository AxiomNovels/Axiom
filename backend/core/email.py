import os
import smtplib
import ssl
from email.message import EmailMessage

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


def send_email(to_address: str, subject: str, body: str) -> None:
    """Submit one message to SMTP, raising if the server does not accept it."""
    message = EmailMessage()
    message["Subject"] = " ".join(subject.splitlines())
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_ADDRESS}>"
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

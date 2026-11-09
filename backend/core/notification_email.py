import asyncio
import logging
from contextlib import asynccontextmanager

from core.config import FRONTEND_ORIGINS
from core.database import create_service_client
from core.email import EmailDeliveryError, RESEND_API_KEY, SMTP_HOST, USE_RESEND, send_email


logger = logging.getLogger(__name__)


def deliver_next_email() -> bool:
    client = create_service_client()
    jobs = client.rpc("claim_notification_email").execute().data
    if not jobs:
        return False

    job = jobs[0]
    body = job["body"]
    if FRONTEND_ORIGINS:
        body += f"\n\nOpen your Axiom inbox: {FRONTEND_ORIGINS[0]}/inbox.html"

    try:
        send_email(job["email"], job["subject"], body, delivery_id=job["id"])
    except Exception as error:
        # Raw provider exceptions can include addresses or credentials.
        reason = str(error) if isinstance(error, EmailDeliveryError) else type(error).__name__
        logger.warning(
            "Inbox email %s attempt %s failed (%s)", job["id"], job["attempt"], reason,
        )
    else:
        client.rpc("complete_notification_email", {"p_id": job["id"], "p_attempt": job["attempt"]}).execute()
    return True


async def _deliver_emails(stopping: asyncio.Event) -> None:
    while not stopping.is_set():
        try:
            if await asyncio.to_thread(deliver_next_email):
                continue
        except Exception as error:
            logger.warning("Inbox email queue unavailable (%s)", type(error).__name__)

        try:
            await asyncio.wait_for(stopping.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def notification_email_lifespan(_app):
    if USE_RESEND and not RESEND_API_KEY:
        logger.warning("Inbox email paused: set RESEND_API_KEY in the backend environment")

    if not (RESEND_API_KEY if USE_RESEND else SMTP_HOST):
        yield
        return

    stopping = asyncio.Event()
    worker = asyncio.create_task(_deliver_emails(stopping))
    try:
        yield
    finally:
        stopping.set()
        await worker

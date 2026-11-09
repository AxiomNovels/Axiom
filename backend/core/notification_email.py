import asyncio
import logging
from contextlib import asynccontextmanager

from core.config import FRONTEND_ORIGINS
from core.database import create_service_client
from core.email import SMTP_HOST, send_email


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
        send_email(job["email"], job["subject"], body)
    except Exception as error:
        # SMTP exceptions can include recipient addresses or server credentials.
        logger.warning(
            "Inbox email %s attempt %s failed (%s)", job["id"], job["attempt"], type(error).__name__,
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
    if not SMTP_HOST:
        yield
        return

    stopping = asyncio.Event()
    worker = asyncio.create_task(_deliver_emails(stopping))
    try:
        yield
    finally:
        stopping.set()
        await worker

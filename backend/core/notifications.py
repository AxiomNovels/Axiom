from core.database import create_service_client
from core.email import send_email


def create_notification(
    user_id: str,
    subject: str,
    body: str,
    email: str | None = None,
    notif_type: str = "system",
    data: dict | None = None,
) -> dict | None:
    """Write an inbox notification and, if an email address is supplied,
    mirror it to the user's email.

    Notifications are always written with the service-role client: the
    `notifications` table intentionally has no INSERT policy for regular
    users, since notifications only ever come from the system, never
    from other users. This is the single place that should ever write to
    that table.

    `notif_type` / `data` let the frontend render richer, interactive
    notifications (e.g. "friend_request", carrying the friendship id and
    sender info) instead of only plain text. Both the DB write and the
    email send are best-effort -- a failure here should never break the
    system event (e.g. signup, sending a friend request) that triggered
    it.

    Returns the inserted notification row, or None if the write failed,
    so callers that need to reference the new row (e.g. to store its id
    elsewhere) can.
    """
    inserted = None
    try:
        response = (
            create_service_client()
            .table("notifications")
            .insert(
                {
                    "user_id": user_id,
                    "subject": subject,
                    "body": body,
                    "type": notif_type,
                    "data": data or {},
                }
            )
            .execute()
        )
        rows = response.data or []
        inserted = rows[0] if rows else None
    except Exception as error:
        print(f"[notifications] failed to create notification for user {user_id}: {error}")

    if email:
        send_email(email, subject, body)

    return inserted


def send_welcome_notification(user_id: str, username: str, email: str) -> None:
    """The one automatic system notification sent today: once, right
    after a new account is created."""
    subject = "Welcome to Axiom!"
    body = (
        f"Hi {username},\n\n"
        "Thank you for creating an Axiom account. We're glad you're here.\n\n"
        "Axiom helps you find novels by the philosophical questions, themes, and "
        "character traits that matter to you -- not just by genre. Here's a quick "
        "look at what you can do:\n\n"
        "- Series Finder: Combine ratings, tags, and protagonist, philosophy, and "
        "storytelling profiles to search with real precision.\n"
        "- Reading Lists: Save novels you're reading or want to read, organize them "
        "into lists, and track your current chapter on each one.\n"
        "- Reviews: Rate and write reviews to help other readers find their next "
        "novel.\n"
        "- Manage Profile: Add an avatar, a short bio, and tag preferences so Axiom "
        "can start tailoring what it shows you.\n\n"
        "This Inbox is where we'll reach you with important account notifications "
        "going forward.\n\n"
        "Happy reading,\n"
        "The Axiom Team"
    )
    create_notification(user_id, subject, body, email)
"""
Axiom - User Database demo.

Run this to create axiom_users.db and walk through the core flows:
sign up -> favorite a protagonist -> track reading status -> save a
trait filter -> leave a review -> submit a contribution -> get it
approved. Safe to re-run (wipes and rebuilds the DB each time).
"""

import os

from database import DB_PATH, get_session, init_db
from models import ContributionType, ReadingStatus, UserRole
import crud


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    print(f"Initialized database at {DB_PATH}\n")

    with get_session() as session:
        # -- sign up two readers --
        alice = crud.create_user(session, "alice", "alice@example.com", "hunter2!", display_name="Alice")
        bob = crud.create_user(
            session, "bob_the_builder", "bob@example.com", "correcthorse", role=UserRole.contributor
        )
        print(f"Created: {alice}")
        print(f"Created: {bob}\n")

        # -- login check --
        auth_ok = crud.authenticate_user(session, "alice", "hunter2!")
        auth_bad = crud.authenticate_user(session, "alice", "wrong-password")
        print(f"Auth with correct password: {'OK' if auth_ok else 'FAILED'}")
        print(f"Auth with wrong password:   {'REJECTED' if auth_bad is None else 'FAILED (should reject)'}\n")

        # -- Alice loves protagonist of novel_id=7 (e.g. a ruthless strategist) --
        fav = crud.add_favorite(session, alice.id, novel_id=7, reason="The cold, calculating long-game planning.")
        print(f"Alice favorited novel #7: {fav}")

        # -- Alice tracks her reading --
        crud.set_reading_status(session, alice.id, novel_id=7, status=ReadingStatus.completed)
        crud.set_reading_status(session, alice.id, novel_id=12, status=ReadingStatus.reading)
        reading_now = crud.get_reading_list(session, alice.id, status=ReadingStatus.reading)
        print(f"Alice is currently reading: {[e.novel_id for e in reading_now]}, aka {[e.novel_]}\n")

        # -- Alice saves a discovery filter --
        sf = crud.save_filter(
            session,
            alice.id,
            name="Ruthless masterminds, no romance",
            filter_dict={
                "strategic_thinking": {"gt": 90},
                "romance": {"lt": 10},
                "political_intrigue": {"gt": 70},
                "emotional_attachment": {"lt": 20},
            },
        )
        print(f"Saved filter: {sf.name} -> {sf.filter_json}\n")

        # -- Alice reviews the novel --
        review = crud.add_or_update_review(session, alice.id, novel_id=7, rating=9, review_text="Cold and brilliant.")
        print(f"Review added: {review}\n")

        # -- Bob (a contributor) submits a brand-new novel for review --
        contribution = crud.submit_contribution(
            session,
            bob.id,
            contribution_type=ContributionType.new_novel,
            payload={
                "title": "The Ashen Throne",
                "synopsis": "A deposed strategist claws back power through pure political calculation.",
                "traits": {"strategic_thinking": 96, "ruthlessness": 89, "compassion": 8},
            },
        )
        print(f"Bob submitted contribution: {contribution}")

        pending = crud.get_pending_contributions(session)
        print(f"Pending contributions in queue: {len(pending)}")

        # -- a moderator approves it (using alice as a stand-in moderator id for demo) --
        crud.review_contribution(session, contribution.id, reviewer_id=alice.id, approve=True, notes="Looks solid, added to DB.")
        print(f"Contribution after review: {contribution}\n")

        print("All core User DB flows executed successfully.")


if __name__ == "__main__":
    main()
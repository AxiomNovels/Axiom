"""
Axiom - User Database CRUD layer.

Thin, dependency-free-ish functions that wrap common operations so the
future web app (FastAPI/Flask/etc.) never has to write raw SQLAlchemy
queries inline. Every function takes an open `session` as its first
argument so callers control the transaction boundary (see database.get_session).
"""

from datetime import datetime
from typing import Optional

import bcrypt
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import (
    Contribution,
    ContributionStatus,
    ContributionType,
    Favorite,
    ReadingListEntry,
    ReadingStatus,
    Review,
    SavedFilter,
    User,
    UserRole,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def create_user(
    session: Session,
    username: str,
    email: str,
    password: str,
    display_name: Optional[str] = None,
    role: UserRole = UserRole.reader,
) -> User:
    existing = (
        session.query(User)
        .filter(or_(User.username == username, User.email == email))
        .first()
    )
    if existing:
        raise ValueError("Username or email already registered.")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        display_name=display_name or username,
        role=role,
    )
    session.add(user)
    session.flush()  # populate user.id without ending the transaction
    return user


def authenticate_user(session: Session, username_or_email: str, password: str) -> Optional[User]:
    user = (
        session.query(User)
        .filter(or_(User.username == username_or_email, User.email == username_or_email))
        .first()
    )
    if user and user.is_active and verify_password(password, user.password_hash):
        return user
    return None


def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    return session.query(User).get(user_id)


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.query(User).filter(User.username == username).first()


def update_profile(
    session: Session,
    user_id: int,
    display_name: Optional[str] = None,
    bio: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> User:
    user = get_user_by_id(session, user_id)
    if not user:
        raise ValueError("User not found.")
    if display_name is not None:
        user.display_name = display_name
    if bio is not None:
        user.bio = bio
    if avatar_url is not None:
        user.avatar_url = avatar_url
    user.updated_at = datetime.utcnow()
    return user


# ---------------------------------------------------------------------------
# Favorites (the core "I loved this protagonist" signal)
# ---------------------------------------------------------------------------

def add_favorite(session: Session, user_id: int, novel_id: int, reason: Optional[str] = None) -> Favorite:
    existing = (
        session.query(Favorite)
        .filter(Favorite.user_id == user_id, Favorite.novel_id == novel_id)
        .first()
    )
    if existing:
        return existing

    fav = Favorite(user_id=user_id, novel_id=novel_id, reason=reason)
    session.add(fav)
    session.flush()
    return fav


def remove_favorite(session: Session, user_id: int, novel_id: int) -> bool:
    fav = (
        session.query(Favorite)
        .filter(Favorite.user_id == user_id, Favorite.novel_id == novel_id)
        .first()
    )
    if not fav:
        return False
    session.delete(fav)
    return True


def get_user_favorites(session: Session, user_id: int):
    return session.query(Favorite).filter(Favorite.user_id == user_id).all()


# ---------------------------------------------------------------------------
# Reading list
# ---------------------------------------------------------------------------

def set_reading_status(
    session: Session, user_id: int, novel_id: int, status: ReadingStatus
) -> ReadingListEntry:
    entry = (
        session.query(ReadingListEntry)
        .filter(ReadingListEntry.user_id == user_id, ReadingListEntry.novel_id == novel_id)
        .first()
    )
    if entry:
        entry.status = status
        entry.updated_at = datetime.utcnow()
    else:
        entry = ReadingListEntry(user_id=user_id, novel_id=novel_id, status=status)
        session.add(entry)
    session.flush()
    return entry


def get_reading_list(session: Session, user_id: int, status: Optional[ReadingStatus] = None):
    query = session.query(ReadingListEntry).filter(ReadingListEntry.user_id == user_id)
    if status is not None:
        query = query.filter(ReadingListEntry.status == status)
    return query.all()


# ---------------------------------------------------------------------------
# Saved trait/theme/style filters
# ---------------------------------------------------------------------------

def save_filter(session: Session, user_id: int, name: str, filter_dict: dict) -> SavedFilter:
    sf = SavedFilter(user_id=user_id, name=name, filter_json=filter_dict)
    session.add(sf)
    session.flush()
    return sf


def get_saved_filters(session: Session, user_id: int):
    return session.query(SavedFilter).filter(SavedFilter.user_id == user_id).all()


def delete_saved_filter(session: Session, filter_id: int, user_id: int) -> bool:
    sf = (
        session.query(SavedFilter)
        .filter(SavedFilter.id == filter_id, SavedFilter.user_id == user_id)
        .first()
    )
    if not sf:
        return False
    session.delete(sf)
    return True


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

def add_or_update_review(
    session: Session, user_id: int, novel_id: int, rating: int, review_text: Optional[str] = None
) -> Review:
    if not (1 <= rating <= 10):
        raise ValueError("rating must be between 1 and 10.")

    review = (
        session.query(Review)
        .filter(Review.user_id == user_id, Review.novel_id == novel_id)
        .first()
    )
    if review:
        review.rating = rating
        review.review_text = review_text
    else:
        review = Review(user_id=user_id, novel_id=novel_id, rating=rating, review_text=review_text)
        session.add(review)
    session.flush()
    return review


def get_reviews_for_novel(session: Session, novel_id: int):
    return session.query(Review).filter(Review.novel_id == novel_id).all()


# ---------------------------------------------------------------------------
# Contributions (new-novel submissions & trait-profile edits from readers)
# ---------------------------------------------------------------------------

def submit_contribution(
    session: Session,
    user_id: int,
    contribution_type: ContributionType,
    payload: dict,
    novel_id: Optional[int] = None,
) -> Contribution:
    contribution = Contribution(
        user_id=user_id,
        novel_id=novel_id,
        contribution_type=contribution_type,
        payload_json=payload,
        status=ContributionStatus.pending,
    )
    session.add(contribution)
    session.flush()
    return contribution


def review_contribution(
    session: Session,
    contribution_id: int,
    reviewer_id: int,
    approve: bool,
    notes: Optional[str] = None,
) -> Contribution:
    contribution = session.query(Contribution).get(contribution_id)
    if not contribution:
        raise ValueError("Contribution not found.")

    contribution.status = ContributionStatus.approved if approve else ContributionStatus.rejected
    contribution.reviewer_id = reviewer_id
    contribution.reviewer_notes = notes
    contribution.reviewed_at = datetime.utcnow()
    return contribution


def get_pending_contributions(session: Session):
    return (
        session.query(Contribution)
        .filter(Contribution.status == ContributionStatus.pending)
        .order_by(Contribution.submitted_at.asc())
        .all()
    )
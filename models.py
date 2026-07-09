"""
Axiom - User Database Models
=============================

Defines every table that stores user-side data for the platform:
accounts, favorites (the core signal for "find similar protagonists"),
reading list, saved trait-filter searches, reviews, and community
contributions (new novel / profile submissions from readers).

The Book/Novel database (titles, protagonist trait scores, philosophy
and storytelling-style profiles) is intentionally a SEPARATE database.
Tables here only store `novel_id` as a plain integer reference so the
two databases can live independently and be joined at the application
layer -- this keeps the User DB reusable even if the Novel DB schema
changes.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    reader = "reader"           # default account
    contributor = "contributor" # trusted user, submissions get lighter review
    moderator = "moderator"     # can approve/reject contributions
    admin = "admin"


class ReadingStatus(str, enum.Enum):
    want_to_read = "want_to_read"
    reading = "reading"
    completed = "completed"
    on_hold = "on_hold"
    dropped = "dropped"


class ContributionType(str, enum.Enum):
    new_novel = "new_novel"           # propose a novel that isn't in the DB yet
    edit_novel_info = "edit_novel_info"       # fix title/synopsis/links/etc.
    edit_trait_profile = "edit_trait_profile" # propose changed trait scores


class ContributionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


# ---------------------------------------------------------------------------
# Core account table
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    display_name = Column(String(100))
    bio = Column(Text)
    avatar_url = Column(String(500))

    role = Column(Enum(UserRole), default=UserRole.reader, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    reading_list = relationship("ReadingListEntry", back_populates="user", cascade="all, delete-orphan")
    saved_filters = relationship("SavedFilter", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="user", cascade="all, delete-orphan")
    contributions = relationship(
        "Contribution",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Contribution.user_id",
    )

    def __repr__(self):
        return f"<User id={self.id} username={self.username!r} role={self.role.value}>"


# ---------------------------------------------------------------------------
# Favorites -- When a user favorites a novel's protagonist,
# that becomes the seed for "find me more novels like this one."
# ---------------------------------------------------------------------------

class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    novel_id = Column(Integer, nullable=False)  # references Book DB
    reason = Column(Text)  # optional free-text: what they loved about this protagonist
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="favorites")

    __table_args__ = (UniqueConstraint("user_id", "novel_id", name="uq_user_novel_favorite"),)

    def __repr__(self):
        return f"<Favorite user_id={self.user_id} novel_id={self.novel_id}>"


# ---------------------------------------------------------------------------
# Reading list / shelf tracking
# ---------------------------------------------------------------------------

class ReadingListEntry(Base):
    __tablename__ = "reading_list"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    novel_id = Column(Integer, nullable=False)  # references Book DB
    status = Column(Enum(ReadingStatus), default=ReadingStatus.want_to_read, nullable=False)

    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="reading_list")

    __table_args__ = (UniqueConstraint("user_id", "novel_id", name="uq_user_novel_reading"),)

    def __repr__(self):
        return f"<ReadingListEntry user_id={self.user_id} novel_id={self.novel_id} status={self.status.value}>"


# ---------------------------------------------------------------------------
# Saved trait-based searches, e.g. "Strategic Thinking > 90 AND Romance < 10"
# ---------------------------------------------------------------------------

class SavedFilter(Base):
    __tablename__ = "saved_filters"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)

    # Stored as JSON so it can express any trait/theme/style condition, e.g.:
    # {"strategic_thinking": {"gt": 90}, "romance": {"lt": 10}, "political_intrigue": {"gt": 70}}
    filter_json = Column(JSON, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="saved_filters")

    def __repr__(self):
        return f"<SavedFilter user_id={self.user_id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Reviews / ratings
# ---------------------------------------------------------------------------

class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    novel_id = Column(Integer, nullable=False)  # references Book DB
    rating = Column(Integer)  # 1-10 scale
    review_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="reviews")

    __table_args__ = (UniqueConstraint("user_id", "novel_id", name="uq_user_novel_review"),)

    def __repr__(self):
        return f"<Review user_id={self.user_id} novel_id={self.novel_id} rating={self.rating}>"


# ---------------------------------------------------------------------------
# Community contributions -- new novel submissions & trait-profile edits.
# Supports the "find people who can contribute" launch goal.
# ---------------------------------------------------------------------------

class Contribution(Base):
    __tablename__ = "contributions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    novel_id = Column(Integer, nullable=True)  # null when proposing a brand-new novel

    contribution_type = Column(Enum(ContributionType), nullable=False)
    payload_json = Column(JSON, nullable=False)  # proposed novel data / trait scores

    status = Column(Enum(ContributionStatus), default=ContributionStatus.pending, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    reviewed_at = Column(DateTime)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer_notes = Column(Text)

    user = relationship("User", back_populates="contributions", foreign_keys=[user_id])

    def __repr__(self):
        return f"<Contribution id={self.id} type={self.contribution_type.value} status={self.status.value}>"
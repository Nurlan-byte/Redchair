import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .core.database import Base


class Visibility(enum.StrEnum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"


# VARCHAR + CHECK instead of a native ENUM: a new value is a migration of the
# CHECK, not ALTER TYPE, and downgrade doesn't leave a stray type behind.
# The CHECK is declared on each table: alembic check ignores type-bound
# constraints in the models but still sees them in the database.
VisibilityType = Enum(Visibility, native_enum=False, length=16, name="visibility")
VISIBILITY_CHECK = "visibility IN ('PUBLIC', 'PRIVATE')"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(
        String(64), default="UTC", server_default="UTC", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    # onupdate fires only for UPDATEs issued through SQLAlchemy.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Diary(Base):
    __tablename__ = "diaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    is_public: Mapped[bool] = mapped_column(
        default=True, server_default=text("TRUE"), nullable=False
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # SHA-256 hex digest; the token itself is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Goal(Base):
    __tablename__ = "goals"
    __table_args__ = (CheckConstraint(VISIBILITY_CHECK, name="visibility"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    diary_id: Mapped[int] = mapped_column(
        ForeignKey("diaries.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[Visibility] = mapped_column(
        VisibilityType,
        default=Visibility.PUBLIC,
        server_default=Visibility.PUBLIC.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # lazy="raise": an accidental lazy load fails right here instead of as
    # MissingGreenlet somewhere deep in serialization.
    statistic: Mapped["GoalStatistic"] = relationship(back_populates="goal", lazy="raise")


class GoalStatistic(Base):
    __tablename__ = "goal_statistics"
    __table_args__ = (
        CheckConstraint("current_streak >= 0", name="current_streak_non_negative"),
        CheckConstraint("longest_streak >= current_streak", name="longest_streak_gte_current"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    current_streak: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    longest_streak: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    last_entry_date: Mapped[date | None] = mapped_column(Date)

    goal: Mapped[Goal] = relationship(back_populates="statistic", lazy="raise")

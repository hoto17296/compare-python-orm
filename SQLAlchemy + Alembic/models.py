import uuid
from datetime import datetime
from typing import NotRequired, TypedDict

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ------------------------------------------------------------
# Base
# ------------------------------------------------------------
class Base(DeclarativeBase):
    """Alembic が autogenerate で拾うための Base"""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        sort_order=-1,
    )


# ------------------------------------------------------------
# Mixins
# ------------------------------------------------------------
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=func.now(),
        index=True,
        sort_order=-1,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
        sort_order=-1,
    )


# ------------------------------------------------------------
# JSON Types
# ------------------------------------------------------------
class UserMeta(TypedDict):
    tags: NotRequired[list[str]]


# ------------------------------------------------------------
# Models
# ------------------------------------------------------------
class UserTable(Base, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        index=True,
    )

    meta: Mapped[UserMeta] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )

    articles: Mapped[list[ArticleTable]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    comments: Mapped[list[CommentTable]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ArticleTable(Base, TimestampMixin):
    __tablename__ = "articles"

    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    # relationships
    author: Mapped[UserTable] = relationship(
        back_populates="articles",
    )

    comments: Mapped[list[CommentTable]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CommentTable(Base, TimestampMixin):
    __tablename__ = "comments"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # relationships
    article: Mapped[ArticleTable] = relationship(
        back_populates="comments",
    )

    author: Mapped[UserTable] = relationship(
        back_populates="comments",
    )

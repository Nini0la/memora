from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from memora.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    study_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_recall_mode: Mapped[str] = mapped_column(String(50), default="typing")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    sessions: Mapped[list[SessionToken]] = relationship(back_populates="user")
    notes: Mapped[list[Note]] = relationship(back_populates="user")


class SessionToken(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(20), default="paste")
    warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(30), default="stored")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship(back_populates="notes")
    subtopics: Mapped[list[Subtopic]] = relationship(
        back_populates="note", cascade="all, delete-orphan"
    )


class Subtopic(Base):
    __tablename__ = "subtopics"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    key_concepts_json: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    note: Mapped[Note] = relationship(back_populates="subtopics")
    prompts: Mapped[list[RecallPrompt]] = relationship(
        back_populates="subtopic", cascade="all, delete-orphan"
    )
    review_schedules: Mapped[list[ReviewSchedule]] = relationship(
        back_populates="subtopic", cascade="all, delete-orphan"
    )
    mastery_status: Mapped[MasteryStatus | None] = relationship(
        back_populates="subtopic", cascade="all, delete-orphan", uselist=False
    )


class RecallPrompt(Base):
    __tablename__ = "recall_prompts"

    id: Mapped[int] = mapped_column(primary_key=True)
    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id"), index=True)
    question_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    subtopic: Mapped[Subtopic] = relationship(back_populates="prompts")
    attempts: Mapped[list[RecallAttempt]] = relationship(
        back_populates="prompt", cascade="all, delete-orphan"
    )


class RecallAttempt(Base):
    __tablename__ = "recall_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("recall_prompts.id"), index=True)
    answer_text: Mapped[str] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(nullable=True)
    level: Mapped[int | None] = mapped_column(nullable=True)
    missing_concepts_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    prompt: Mapped[RecallPrompt] = relationship(back_populates="attempts")


class ReviewSchedule(Base):
    __tablename__ = "review_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id"), index=True)
    review_stage: Mapped[int] = mapped_column()
    interval_days: Mapped[int] = mapped_column()
    next_review_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    subtopic: Mapped[Subtopic] = relationship(back_populates="review_schedules")


class MasteryStatus(Base):
    __tablename__ = "mastery_status"

    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id"), primary_key=True)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    mastery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    subtopic: Mapped[Subtopic] = relationship(back_populates="mastery_status")

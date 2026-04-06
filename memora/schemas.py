from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str | None = None
    study_goal: str | None = None
    preferred_recall_mode: str = "typing"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str | None
    study_goal: str | None
    preferred_recall_mode: str
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class NoteCreateRequest(BaseModel):
    raw_text: str
    title: str | None = None


class NoteResponse(BaseModel):
    id: int
    user_id: int
    title: str | None
    raw_text: str
    source_type: str
    warning: str | None
    processing_status: str
    created_at: datetime


class SubtopicResponse(BaseModel):
    id: int
    note_id: int
    title: str
    key_concepts: list[str]
    summary: str | None
    recall_prompts: list[str]


class StartRecallCTA(BaseModel):
    label: str
    path: str


class SubtopicPreviewResponse(BaseModel):
    subtopic_id: int
    title: str
    key_concepts: list[str]
    summary: str | None
    recall_prompts: list[str]
    start_recall_cta: StartRecallCTA


class PromptResponse(BaseModel):
    id: int
    subtopic_id: int
    question_text: str


class RecallAttemptCreateRequest(BaseModel):
    prompt_id: int
    answer_text: str


class RecallAttemptResponse(BaseModel):
    id: int
    prompt_id: int
    answer_text: str
    score: int | None
    level: int | None
    missing_concepts: list[str]
    feedback: str | None
    created_at: datetime


class RecallEvaluationResponse(BaseModel):
    attempt_id: int
    score: int
    level: int
    missing_concepts: list[str]
    feedback: str


class ReviewItemResponse(BaseModel):
    id: int
    review_stage: int
    interval_days: int
    next_review_date: datetime


class ReviewScheduleResponse(BaseModel):
    subtopic_id: int
    reviews: list[ReviewItemResponse]


class SubtopicHistoryAttemptResponse(BaseModel):
    attempt_id: int
    prompt_id: int
    score: int | None
    level: int | None
    created_at: datetime


class SubtopicHistoryResponse(BaseModel):
    subtopic_id: int
    attempts: list[SubtopicHistoryAttemptResponse]
    trend: str


class MasteryStatusResponse(BaseModel):
    subtopic_id: int
    mastered: bool
    mastery_date: datetime | None


class NoteOutlineResponse(BaseModel):
    note_id: int
    topic_title: str
    subtopics: list[SubtopicResponse]


class NoteProcessResponse(BaseModel):
    note_id: int
    processing_status: str
    subtopic_count: int

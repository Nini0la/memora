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

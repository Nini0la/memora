from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

import memora.models as models_module
from memora.config import Settings
from memora.db import Base, build_engine, build_session_factory
from memora.evaluation import evaluate_answer
from memora.extraction import SUPPORTED_UPLOAD_TYPES, extract_text_from_upload
from memora.models import (
    MasteryStatus,
    Note,
    RecallAttempt,
    RecallPrompt,
    ReviewSchedule,
    SessionToken,
    Subtopic,
    User,
)
from memora.schemas import (
    AuthResponse,
    LoginRequest,
    MasteryStatusResponse,
    NoteCreateRequest,
    NoteOutlineResponse,
    NoteProcessResponse,
    NoteResponse,
    PromptResponse,
    RecallAttemptCreateRequest,
    RecallAttemptResponse,
    RecallEvaluationResponse,
    ReviewItemResponse,
    ReviewScheduleResponse,
    SignupRequest,
    StartRecallCTA,
    SubtopicHistoryAttemptResponse,
    SubtopicHistoryResponse,
    SubtopicResponse,
    SubtopicPreviewResponse,
    UserResponse,
)
from memora.security import create_session_token, hash_password, verify_password
from memora.structuring import generate_outline

logger = logging.getLogger("memora")
security = HTTPBearer(auto_error=False)


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        study_goal=user.study_goal,
        preferred_recall_mode=user.preferred_recall_mode,
        created_at=user.created_at,
    )


def _note_response(note: Note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        user_id=note.user_id,
        title=note.title,
        raw_text=note.raw_text,
        source_type=note.source_type,
        warning=note.warning,
        processing_status=note.processing_status,
        created_at=note.created_at,
    )


def _subtopic_response(subtopic: Subtopic) -> SubtopicResponse:
    try:
        key_concepts = json.loads(subtopic.key_concepts_json)
        if not isinstance(key_concepts, list):
            key_concepts = []
    except json.JSONDecodeError:
        key_concepts = []

    return SubtopicResponse(
        id=subtopic.id,
        note_id=subtopic.note_id,
        title=subtopic.title,
        key_concepts=[str(item) for item in key_concepts],
        summary=subtopic.summary,
        recall_prompts=[prompt.question_text for prompt in subtopic.prompts],
    )


def _long_note_warning(raw_text: str, settings: Settings) -> str | None:
    if len(raw_text) > settings.long_note_warning_chars:
        return (
            "This note is very long and may reduce processing quality in later stages. "
            "Consider splitting it into smaller chunks."
        )
    return None


def _attempt_response(attempt: RecallAttempt) -> RecallAttemptResponse:
    try:
        missing_concepts = (
            json.loads(attempt.missing_concepts_json) if attempt.missing_concepts_json else []
        )
        if not isinstance(missing_concepts, list):
            missing_concepts = []
    except json.JSONDecodeError:
        missing_concepts = []

    return RecallAttemptResponse(
        id=attempt.id,
        prompt_id=attempt.prompt_id,
        answer_text=attempt.answer_text,
        score=attempt.score,
        level=attempt.level,
        missing_concepts=[str(item) for item in missing_concepts],
        feedback=attempt.feedback,
        created_at=attempt.created_at,
    )


def _schedule_intervals(level: int) -> list[int]:
    if level <= 2:
        return [1, 2, 4, 7, 14]
    return [1, 3, 7, 14, 30]


def _ensure_review_schedule(
    db: Session, subtopic_id: int, level: int, reference_time: datetime
) -> None:
    existing = db.scalars(select(ReviewSchedule).where(ReviewSchedule.subtopic_id == subtopic_id)).all()
    if existing:
        return

    for stage, interval_days in enumerate(_schedule_intervals(level), start=1):
        db.add(
            ReviewSchedule(
                subtopic_id=subtopic_id,
                review_stage=stage,
                interval_days=interval_days,
                next_review_date=reference_time + timedelta(days=interval_days),
            )
        )


def _update_mastery_status(db: Session, subtopic_id: int, reference_time: datetime) -> None:
    mastery = db.get(MasteryStatus, subtopic_id)
    if mastery is None:
        mastery = MasteryStatus(subtopic_id=subtopic_id, mastered=False, mastery_date=None)
        db.add(mastery)
        db.flush()

    if mastery.mastered:
        return

    high_level_attempt_dates = db.scalars(
        select(RecallAttempt.created_at)
        .join(RecallPrompt, RecallPrompt.id == RecallAttempt.prompt_id)
        .where(RecallPrompt.subtopic_id == subtopic_id, RecallAttempt.level >= 4)
    ).all()
    distinct_days = {attempt_date.date() for attempt_date in high_level_attempt_dates}

    if len(distinct_days) >= 2:
        mastery.mastered = True
        mastery.mastery_date = reference_time


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings()

    engine = build_engine(runtime_settings.database_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(bind=engine)
        yield

    app = FastAPI(title="Memora API", version="0.1.0", lifespan=lifespan)
    app.state.settings = runtime_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.models = models_module

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info("request.start method=%s path=%s", request.method, request.url.path)
        response = await call_next(request)
        logger.info(
            "request.end method=%s path=%s status=%s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        logger.exception("unhandled.error", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    def get_db(request: Request):
        db = request.app.state.session_factory()
        try:
            yield db
        finally:
            db.close()

    def require_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
        db: Session = Depends(get_db),
    ) -> User:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Missing authentication")

        token = credentials.credentials
        session_row = db.scalar(select(SessionToken).where(SessionToken.token == token))
        if session_row is None:
            raise HTTPException(status_code=401, detail="Invalid authentication token")

        return session_row.user

    @app.post("/auth/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
    def signup(payload: SignupRequest, db: Session = Depends(get_db)):
        if len(payload.password) < runtime_settings.password_min_length:
            raise HTTPException(status_code=400, detail="Password is too short")

        existing = db.scalar(select(User).where(User.email == payload.email))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email already exists")

        user = User(
            email=str(payload.email),
            password_hash=hash_password(payload.password, runtime_settings.password_pepper),
            name=payload.name,
            study_goal=payload.study_goal,
            preferred_recall_mode=payload.preferred_recall_mode,
        )
        db.add(user)
        db.flush()

        token_value = create_session_token()
        db.add(SessionToken(token=token_value, user_id=user.id))
        db.commit()
        db.refresh(user)

        return AuthResponse(access_token=token_value, user=_user_response(user))

    @app.post("/auth/login", response_model=AuthResponse)
    def login(payload: LoginRequest, db: Session = Depends(get_db)):
        user = db.scalar(select(User).where(User.email == payload.email))
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not verify_password(payload.password, user.password_hash, runtime_settings.password_pepper):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token_value = create_session_token()
        db.add(SessionToken(token=token_value, user_id=user.id))
        db.commit()

        return AuthResponse(access_token=token_value, user=_user_response(user))

    @app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
        db: Session = Depends(get_db),
    ):
        if credentials is None:
            raise HTTPException(status_code=401, detail="Missing authentication")

        token = credentials.credentials
        result = db.execute(delete(SessionToken).where(SessionToken.token == token))
        if result.rowcount == 0:
            raise HTTPException(status_code=401, detail="Invalid authentication token")

        db.commit()
        return None

    @app.get("/me", response_model=UserResponse)
    def me(current_user: User = Depends(require_current_user)):
        return _user_response(current_user)

    @app.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
    def create_note(
        payload: NoteCreateRequest,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        cleaned = payload.raw_text.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="Note content cannot be empty")

        note = Note(
            user_id=current_user.id,
            title=payload.title,
            raw_text=cleaned,
            source_type="paste",
            warning=_long_note_warning(cleaned, runtime_settings),
            processing_status="stored",
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        return _note_response(note)

    @app.post("/notes/upload", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
    async def upload_note(
        file: UploadFile = File(...),
        title: str | None = Form(default=None),
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        if file.content_type not in SUPPORTED_UPLOAD_TYPES:
            raise HTTPException(status_code=415, detail="Unsupported file type")

        blob = await file.read()
        if len(blob) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        try:
            raw_text = extract_text_from_upload(file.content_type, blob)
        except ValueError as exc:
            detail = str(exc)
            if detail == "unsupported file type":
                raise HTTPException(status_code=415, detail="Unsupported file type") from exc
            raise HTTPException(status_code=400, detail=detail) from exc

        note = Note(
            user_id=current_user.id,
            title=title,
            raw_text=raw_text,
            source_type="upload",
            warning=_long_note_warning(raw_text, runtime_settings),
            processing_status="stored",
        )
        db.add(note)
        db.commit()
        db.refresh(note)

        return _note_response(note)

    @app.get("/notes/{note_id}", response_model=NoteResponse)
    def get_note(
        note_id: int,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        note = db.scalar(select(Note).where(Note.id == note_id, Note.user_id == current_user.id))
        if note is None:
            raise HTTPException(status_code=404, detail="Note not found")

        return _note_response(note)

    @app.post("/notes/{note_id}/process", response_model=NoteProcessResponse)
    def process_note(
        note_id: int,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        note = db.scalar(
            select(Note)
            .where(Note.id == note_id, Note.user_id == current_user.id)
            .options(selectinload(Note.subtopics).selectinload(Subtopic.prompts))
        )
        if note is None:
            raise HTTPException(status_code=404, detail="Note not found")

        note.subtopics.clear()
        db.flush()

        generated = generate_outline(note.title, note.raw_text)
        note.topic_title = generated["topic_title"]
        note.processing_status = "processed"

        for subtopic_payload in generated["subtopics"]:
            subtopic = Subtopic(
                note_id=note.id,
                title=subtopic_payload["title"],
                key_concepts_json=json.dumps(subtopic_payload["key_concepts"]),
                summary=subtopic_payload["summary"],
            )
            for prompt in subtopic_payload["recall_prompts"]:
                subtopic.prompts.append(RecallPrompt(question_text=prompt))
            db.add(subtopic)

        db.commit()
        db.refresh(note)

        subtopic_count = db.query(Subtopic).filter(Subtopic.note_id == note.id).count()
        return NoteProcessResponse(
            note_id=note.id, processing_status=note.processing_status, subtopic_count=subtopic_count
        )

    @app.get("/notes/{note_id}/outline", response_model=NoteOutlineResponse)
    def get_note_outline(
        note_id: int,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        note = db.scalar(
            select(Note)
            .where(Note.id == note_id, Note.user_id == current_user.id)
            .options(selectinload(Note.subtopics).selectinload(Subtopic.prompts))
        )
        if note is None:
            raise HTTPException(status_code=404, detail="Note not found")
        if not note.subtopics:
            raise HTTPException(status_code=409, detail="Note has not been processed yet")

        subtopics = [_subtopic_response(subtopic) for subtopic in note.subtopics]
        return NoteOutlineResponse(
            note_id=note.id,
            topic_title=note.topic_title or note.title or "Untitled Topic",
            subtopics=subtopics,
        )

    @app.get("/subtopics/{subtopic_id}", response_model=SubtopicResponse)
    def get_subtopic(
        subtopic_id: int,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        subtopic = db.scalar(
            select(Subtopic)
            .join(Note, Note.id == Subtopic.note_id)
            .where(Subtopic.id == subtopic_id, Note.user_id == current_user.id)
            .options(selectinload(Subtopic.prompts))
        )
        if subtopic is None:
            raise HTTPException(status_code=404, detail="Subtopic not found")

        return _subtopic_response(subtopic)

    @app.get("/subtopics/{subtopic_id}/prompts", response_model=list[PromptResponse])
    def get_subtopic_prompts(
        subtopic_id: int,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        subtopic = db.scalar(
            select(Subtopic)
            .join(Note, Note.id == Subtopic.note_id)
            .where(Subtopic.id == subtopic_id, Note.user_id == current_user.id)
            .options(selectinload(Subtopic.prompts))
        )
        if subtopic is None:
            raise HTTPException(status_code=404, detail="Subtopic not found")

        return [
            PromptResponse(id=prompt.id, subtopic_id=subtopic.id, question_text=prompt.question_text)
            for prompt in subtopic.prompts
        ]

    @app.get("/subtopics/{subtopic_id}/preview", response_model=SubtopicPreviewResponse)
    def get_subtopic_preview(
        subtopic_id: int,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        subtopic = db.scalar(
            select(Subtopic)
            .join(Note, Note.id == Subtopic.note_id)
            .where(Subtopic.id == subtopic_id, Note.user_id == current_user.id)
            .options(selectinload(Subtopic.prompts))
        )
        if subtopic is None:
            raise HTTPException(status_code=404, detail="Subtopic not found")

        response = _subtopic_response(subtopic)
        return SubtopicPreviewResponse(
            subtopic_id=response.id,
            title=response.title,
            key_concepts=response.key_concepts,
            summary=response.summary,
            recall_prompts=response.recall_prompts,
            start_recall_cta=StartRecallCTA(
                label="Start Recall Training", path=f"/recall/subtopics/{subtopic_id}/start"
            ),
        )

    @app.post(
        "/recall/attempts",
        response_model=RecallAttemptResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_recall_attempt(
        payload: RecallAttemptCreateRequest,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        cleaned_answer = payload.answer_text.strip()
        if not cleaned_answer:
            raise HTTPException(status_code=400, detail="Answer cannot be empty")

        prompt = db.scalar(
            select(RecallPrompt)
            .join(Subtopic, Subtopic.id == RecallPrompt.subtopic_id)
            .join(Note, Note.id == Subtopic.note_id)
            .where(RecallPrompt.id == payload.prompt_id, Note.user_id == current_user.id)
        )
        if prompt is None:
            raise HTTPException(status_code=404, detail="Prompt not found")

        attempt = RecallAttempt(prompt_id=prompt.id, answer_text=cleaned_answer)
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        return _attempt_response(attempt)

    @app.get("/recall/attempts/{attempt_id}", response_model=RecallAttemptResponse)
    def get_recall_attempt(
        attempt_id: int,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        attempt = db.scalar(
            select(RecallAttempt)
            .join(RecallPrompt, RecallPrompt.id == RecallAttempt.prompt_id)
            .join(Subtopic, Subtopic.id == RecallPrompt.subtopic_id)
            .join(Note, Note.id == Subtopic.note_id)
            .where(RecallAttempt.id == attempt_id, Note.user_id == current_user.id)
        )
        if attempt is None:
            raise HTTPException(status_code=404, detail="Recall attempt not found")

        return _attempt_response(attempt)

    @app.post("/recall/attempts/{attempt_id}/evaluate", response_model=RecallEvaluationResponse)
    def evaluate_recall_attempt(
        attempt_id: int,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        attempt = db.scalar(
            select(RecallAttempt)
            .join(RecallPrompt, RecallPrompt.id == RecallAttempt.prompt_id)
            .join(Subtopic, Subtopic.id == RecallPrompt.subtopic_id)
            .join(Note, Note.id == Subtopic.note_id)
            .where(RecallAttempt.id == attempt_id, Note.user_id == current_user.id)
            .options(
                selectinload(RecallAttempt.prompt)
                .selectinload(RecallPrompt.subtopic)
                .selectinload(Subtopic.prompts)
            )
        )
        if attempt is None:
            raise HTTPException(status_code=404, detail="Recall attempt not found")

        try:
            key_concepts = json.loads(attempt.prompt.subtopic.key_concepts_json)
            if not isinstance(key_concepts, list):
                key_concepts = []
        except json.JSONDecodeError:
            key_concepts = []

        evaluated = evaluate_answer(attempt.answer_text, [str(item) for item in key_concepts])
        attempt.score = evaluated["score"]
        attempt.level = evaluated["level"]
        attempt.missing_concepts_json = json.dumps(evaluated["missing_concepts"])
        attempt.feedback = evaluated["feedback"]
        db.flush()

        reference_time = datetime.now(timezone.utc)
        subtopic_id = attempt.prompt.subtopic_id
        _ensure_review_schedule(db, subtopic_id, evaluated["level"], reference_time)
        _update_mastery_status(db, subtopic_id, reference_time)
        db.commit()

        return RecallEvaluationResponse(
            attempt_id=attempt.id,
            score=evaluated["score"],
            level=evaluated["level"],
            missing_concepts=evaluated["missing_concepts"],
            feedback=evaluated["feedback"],
        )

    @app.get("/subtopics/{subtopic_id}/review-schedule", response_model=ReviewScheduleResponse)
    def get_subtopic_review_schedule(
        subtopic_id: int,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        subtopic = db.scalar(
            select(Subtopic)
            .join(Note, Note.id == Subtopic.note_id)
            .where(Subtopic.id == subtopic_id, Note.user_id == current_user.id)
            .options(selectinload(Subtopic.review_schedules))
        )
        if subtopic is None:
            raise HTTPException(status_code=404, detail="Subtopic not found")

        reviews = sorted(subtopic.review_schedules, key=lambda item: item.review_stage)
        return ReviewScheduleResponse(
            subtopic_id=subtopic.id,
            reviews=[
                ReviewItemResponse(
                    id=review.id,
                    review_stage=review.review_stage,
                    interval_days=review.interval_days,
                    next_review_date=review.next_review_date,
                )
                for review in reviews
            ],
        )

    @app.get("/subtopics/{subtopic_id}/history", response_model=SubtopicHistoryResponse)
    def get_subtopic_history(
        subtopic_id: int,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        subtopic = db.scalar(
            select(Subtopic)
            .join(Note, Note.id == Subtopic.note_id)
            .where(Subtopic.id == subtopic_id, Note.user_id == current_user.id)
        )
        if subtopic is None:
            raise HTTPException(status_code=404, detail="Subtopic not found")

        attempts = db.scalars(
            select(RecallAttempt)
            .join(RecallPrompt, RecallPrompt.id == RecallAttempt.prompt_id)
            .where(RecallPrompt.subtopic_id == subtopic_id)
            .order_by(RecallAttempt.created_at.desc())
        ).all()

        scored = [attempt.score for attempt in attempts if attempt.score is not None]
        if len(scored) < 2:
            trend = "insufficient_data"
        else:
            delta = scored[0] - scored[-1]
            if delta > 5:
                trend = "improving"
            elif delta < -5:
                trend = "declining"
            else:
                trend = "steady"

        return SubtopicHistoryResponse(
            subtopic_id=subtopic_id,
            attempts=[
                SubtopicHistoryAttemptResponse(
                    attempt_id=attempt.id,
                    prompt_id=attempt.prompt_id,
                    score=attempt.score,
                    level=attempt.level,
                    created_at=attempt.created_at,
                )
                for attempt in attempts
            ],
            trend=trend,
        )

    @app.get("/subtopics/{subtopic_id}/mastery", response_model=MasteryStatusResponse)
    def get_subtopic_mastery(
        subtopic_id: int,
        current_user: User = Depends(require_current_user),
        db: Session = Depends(get_db),
    ):
        subtopic = db.scalar(
            select(Subtopic)
            .join(Note, Note.id == Subtopic.note_id)
            .where(Subtopic.id == subtopic_id, Note.user_id == current_user.id)
        )
        if subtopic is None:
            raise HTTPException(status_code=404, detail="Subtopic not found")

        mastery = db.get(MasteryStatus, subtopic_id)
        if mastery is None:
            mastery = MasteryStatus(subtopic_id=subtopic_id, mastered=False, mastery_date=None)
            db.add(mastery)
            db.commit()
            db.refresh(mastery)

        return MasteryStatusResponse(
            subtopic_id=subtopic_id, mastered=mastery.mastered, mastery_date=mastery.mastery_date
        )

    return app


app = create_app()

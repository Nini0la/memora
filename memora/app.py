from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from memora.config import Settings
from memora.db import Base, build_engine, build_session_factory
from memora.models import Note, SessionToken, User
from memora.schemas import (
    AuthResponse,
    LoginRequest,
    NoteCreateRequest,
    NoteResponse,
    SignupRequest,
    UserResponse,
)
from memora.security import create_session_token, hash_password, verify_password

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


def _long_note_warning(raw_text: str, settings: Settings) -> str | None:
    if len(raw_text) > settings.long_note_warning_chars:
        return (
            "This note is very long and may reduce processing quality in later stages. "
            "Consider splitting it into smaller chunks."
        )
    return None


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
        if file.content_type != "text/plain":
            raise HTTPException(status_code=415, detail="Unsupported file type")

        blob = await file.read()
        if len(blob) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        try:
            raw_text = blob.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Could not decode uploaded file") from exc

        if not raw_text:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

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

    return app


app = create_app()

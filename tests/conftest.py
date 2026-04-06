from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from memora.app import create_app
from memora.config import Settings


@pytest.fixture
def app(tmp_path: Path):
    database_path = tmp_path / "test.db"
    settings = Settings(database_url=f"sqlite:///{database_path}")
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as api_client:
        yield api_client


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/auth/signup",
        json={"email": "notes-user@example.com", "password": "strong-password-123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

from io import BytesIO

from docx import Document
from reportlab.pdfgen import canvas


def test_signup_login_me_logout_flow(client):
    signup_payload = {
        "email": "ada@example.com",
        "password": "strong-password-123",
        "name": "Ada",
        "study_goal": "Ace systems design",
        "preferred_recall_mode": "typing",
    }

    signup_response = client.post("/auth/signup", json=signup_payload)
    assert signup_response.status_code == 201
    signup_body = signup_response.json()
    assert signup_body["user"]["email"] == "ada@example.com"
    assert signup_body["user"]["name"] == "Ada"
    assert signup_body["user"]["study_goal"] == "Ace systems design"
    token = signup_body["access_token"]

    me_response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "ada@example.com"

    logout_response = client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert logout_response.status_code == 204

    me_after_logout = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me_after_logout.status_code == 401

    login_response = client.post(
        "/auth/login",
        json={"email": "ada@example.com", "password": "strong-password-123"},
    )
    assert login_response.status_code == 200
    login_token = login_response.json()["access_token"]

    me_after_login = client.get(
        "/me", headers={"Authorization": f"Bearer {login_token}"}
    )
    assert me_after_login.status_code == 200
    assert me_after_login.json()["email"] == "ada@example.com"


def test_duplicate_signup_rejected(client):
    payload = {"email": "dup@example.com", "password": "strong-password-123"}
    first = client.post("/auth/signup", json=payload)
    assert first.status_code == 201

    second = client.post("/auth/signup", json=payload)
    assert second.status_code == 409


def test_paste_note_requires_auth(client):
    response = client.post(
        "/notes",
        json={"raw_text": "This is a note.", "title": "Lecture 1"},
    )
    assert response.status_code == 401


def test_create_and_fetch_paste_note(client, auth_headers):
    create_response = client.post(
        "/notes",
        headers=auth_headers,
        json={"raw_text": "Distributed systems basics", "title": "DS Intro"},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["title"] == "DS Intro"
    assert created["source_type"] == "paste"

    note_id = created["id"]
    fetch_response = client.get(f"/notes/{note_id}", headers=auth_headers)
    assert fetch_response.status_code == 200
    fetched = fetch_response.json()
    assert fetched["raw_text"] == "Distributed systems basics"


def test_empty_paste_note_rejected(client, auth_headers):
    response = client.post(
        "/notes", headers=auth_headers, json={"raw_text": "   ", "title": "Bad"}
    )
    assert response.status_code == 400


def test_long_note_returns_warning(client, auth_headers):
    very_long_note = "x" * 12001
    response = client.post(
        "/notes",
        headers=auth_headers,
        json={"raw_text": very_long_note, "title": "Long note"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["warning"] is not None


def test_upload_plain_text_note(client, auth_headers):
    file_content = b"TCP has a three-way handshake"
    response = client.post(
        "/notes/upload",
        headers=auth_headers,
        files={"file": ("networks.txt", BytesIO(file_content), "text/plain")},
        data={"title": "Networking"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "upload"
    assert "three-way handshake" in body["raw_text"]


def test_upload_empty_file_rejected(client, auth_headers):
    response = client.post(
        "/notes/upload",
        headers=auth_headers,
        files={"file": ("empty.txt", BytesIO(b""), "text/plain")},
    )

    assert response.status_code == 400


def test_upload_unsupported_file_type(client, auth_headers):
    response = client.post(
        "/notes/upload",
        headers=auth_headers,
        files={"file": ("payload.bin", BytesIO(b"abc"), "application/octet-stream")},
    )

    assert response.status_code == 415


def test_upload_invalid_utf8_text_rejected(client, auth_headers):
    response = client.post(
        "/notes/upload",
        headers=auth_headers,
        files={"file": ("bad.txt", BytesIO(b"\xff\xfe\xfd"), "text/plain")},
    )

    assert response.status_code == 400


def test_upload_pdf_note_extracts_text(client, auth_headers):
    pdf_blob = BytesIO()
    pdf = canvas.Canvas(pdf_blob)
    pdf.drawString(72, 720, "OSI model has seven layers")
    pdf.save()
    pdf_blob.seek(0)

    response = client.post(
        "/notes/upload",
        headers=auth_headers,
        files={"file": ("osi.pdf", pdf_blob, "application/pdf")},
        data={"title": "OSI"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "upload"
    assert "seven layers" in body["raw_text"].lower()


def test_upload_docx_note_extracts_text(client, auth_headers):
    docx_blob = BytesIO()
    doc = Document()
    doc.add_paragraph("B-tree indexes improve lookup performance")
    doc.save(docx_blob)
    docx_blob.seek(0)

    response = client.post(
        "/notes/upload",
        headers=auth_headers,
        files={
            "file": (
                "indexes.docx",
                docx_blob,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "upload"
    assert "b-tree indexes" in body["raw_text"].lower()


def test_upload_corrupted_pdf_rejected(client, auth_headers):
    response = client.post(
        "/notes/upload",
        headers=auth_headers,
        files={"file": ("bad.pdf", BytesIO(b"not-a-real-pdf"), "application/pdf")},
    )

    assert response.status_code == 400


def test_upload_corrupted_docx_rejected(client, auth_headers):
    response = client.post(
        "/notes/upload",
        headers=auth_headers,
        files={
            "file": (
                "bad.docx",
                BytesIO(b"not-a-real-docx"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 400

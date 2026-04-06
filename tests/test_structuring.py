
def test_process_note_requires_auth(client, auth_headers):
    note_response = client.post(
        "/notes",
        headers=auth_headers,
        json={"raw_text": "Networks include routers and switches.", "title": "Net"},
    )
    note_id = note_response.json()["id"]

    process_response = client.post(f"/notes/{note_id}/process")
    assert process_response.status_code == 401


def test_process_note_generates_outline_and_subtopics(client, auth_headers):
    note_response = client.post(
        "/notes",
        headers=auth_headers,
        json={
            "title": "Computer Networks",
            "raw_text": (
                "OSI has seven layers. Physical and data link are foundational. "
                "TCP and UDP are transport protocols. "
                "Routing determines packet paths across networks."
            ),
        },
    )
    note_id = note_response.json()["id"]

    process_response = client.post(f"/notes/{note_id}/process", headers=auth_headers)
    assert process_response.status_code == 200
    process_body = process_response.json()
    assert process_body["note_id"] == note_id
    assert process_body["processing_status"] == "processed"
    assert process_body["subtopic_count"] >= 1

    outline_response = client.get(f"/notes/{note_id}/outline", headers=auth_headers)
    assert outline_response.status_code == 200
    outline = outline_response.json()
    assert outline["note_id"] == note_id
    assert outline["topic_title"]
    assert len(outline["subtopics"]) >= 1

    first_subtopic = outline["subtopics"][0]
    assert first_subtopic["title"]
    assert len(first_subtopic["key_concepts"]) >= 1
    assert len(first_subtopic["recall_prompts"]) >= 1

    subtopic_id = first_subtopic["id"]
    subtopic_response = client.get(f"/subtopics/{subtopic_id}", headers=auth_headers)
    assert subtopic_response.status_code == 200
    subtopic = subtopic_response.json()
    assert subtopic["id"] == subtopic_id
    assert subtopic["note_id"] == note_id
    assert len(subtopic["key_concepts"]) >= 1


def test_process_note_for_another_user_returns_not_found(client, auth_headers):
    note_response = client.post(
        "/notes",
        headers=auth_headers,
        json={"raw_text": "Shared note", "title": "Private"},
    )
    note_id = note_response.json()["id"]

    other_user_signup = client.post(
        "/auth/signup",
        json={"email": "other@example.com", "password": "strong-password-123"},
    )
    other_token = other_user_signup.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    process_response = client.post(f"/notes/{note_id}/process", headers=other_headers)
    assert process_response.status_code == 404


def test_reprocessing_note_replaces_old_subtopics(client, auth_headers):
    note_response = client.post(
        "/notes",
        headers=auth_headers,
        json={"raw_text": "Databases use indexes for queries.", "title": "DB"},
    )
    note_id = note_response.json()["id"]

    first_process = client.post(f"/notes/{note_id}/process", headers=auth_headers)
    assert first_process.status_code == 200
    first_count = first_process.json()["subtopic_count"]

    second_process = client.post(f"/notes/{note_id}/process", headers=auth_headers)
    assert second_process.status_code == 200
    second_count = second_process.json()["subtopic_count"]

    outline_response = client.get(f"/notes/{note_id}/outline", headers=auth_headers)
    assert outline_response.status_code == 200
    outline = outline_response.json()
    assert len(outline["subtopics"]) == second_count
    assert second_count == first_count

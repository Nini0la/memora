
def _create_processed_subtopic(client, auth_headers):
    note_response = client.post(
        "/notes",
        headers=auth_headers,
        json={
            "title": "Operating Systems",
            "raw_text": (
                "Processes and threads are execution units. "
                "Scheduling policies determine CPU fairness."
            ),
        },
    )
    note_id = note_response.json()["id"]
    process_response = client.post(f"/notes/{note_id}/process", headers=auth_headers)
    assert process_response.status_code == 200

    outline_response = client.get(f"/notes/{note_id}/outline", headers=auth_headers)
    subtopic_id = outline_response.json()["subtopics"][0]["id"]
    return subtopic_id


def test_subtopic_preview_requires_auth(client, auth_headers):
    subtopic_id = _create_processed_subtopic(client, auth_headers)

    response = client.get(f"/subtopics/{subtopic_id}/preview")
    assert response.status_code == 401


def test_subtopic_preview_returns_expected_fields(client, auth_headers):
    subtopic_id = _create_processed_subtopic(client, auth_headers)

    response = client.get(f"/subtopics/{subtopic_id}/preview", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["subtopic_id"] == subtopic_id
    assert body["title"]
    assert len(body["key_concepts"]) >= 1
    assert body["summary"] is not None
    assert len(body["recall_prompts"]) >= 1
    assert body["start_recall_cta"]["label"] == "Start Recall Training"
    assert body["start_recall_cta"]["path"] == f"/recall/subtopics/{subtopic_id}/start"


def test_subtopic_preview_for_other_user_is_not_found(client, auth_headers):
    subtopic_id = _create_processed_subtopic(client, auth_headers)

    other_user_signup = client.post(
        "/auth/signup",
        json={"email": "preview-other@example.com", "password": "strong-password-123"},
    )
    other_headers = {"Authorization": f"Bearer {other_user_signup.json()['access_token']}"}

    response = client.get(f"/subtopics/{subtopic_id}/preview", headers=other_headers)
    assert response.status_code == 404

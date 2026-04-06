
def _create_prompt_id(client, auth_headers):
    note_response = client.post(
        "/notes",
        headers=auth_headers,
        json={
            "title": "Databases",
            "raw_text": (
                "Indexes improve query performance. "
                "Transactions ensure consistency and isolation."
            ),
        },
    )
    note_id = note_response.json()["id"]
    process_response = client.post(f"/notes/{note_id}/process", headers=auth_headers)
    assert process_response.status_code == 200

    outline = client.get(f"/notes/{note_id}/outline", headers=auth_headers).json()
    subtopic_id = outline["subtopics"][0]["id"]

    prompts_response = client.get(f"/subtopics/{subtopic_id}/prompts", headers=auth_headers)
    assert prompts_response.status_code == 200
    return prompts_response.json()[0]["id"]


def test_create_recall_attempt_requires_auth(client, auth_headers):
    prompt_id = _create_prompt_id(client, auth_headers)

    response = client.post(
        "/recall/attempts",
        json={"prompt_id": prompt_id, "answer_text": "Indexes speed lookups."},
    )
    assert response.status_code == 401


def test_create_and_evaluate_recall_attempt(client, auth_headers):
    prompt_id = _create_prompt_id(client, auth_headers)

    create_response = client.post(
        "/recall/attempts",
        headers=auth_headers,
        json={
            "prompt_id": prompt_id,
            "answer_text": "Indexes improve query speed while transactions maintain consistency.",
        },
    )
    assert create_response.status_code == 201
    attempt_id = create_response.json()["id"]

    evaluate_response = client.post(
        f"/recall/attempts/{attempt_id}/evaluate", headers=auth_headers
    )
    assert evaluate_response.status_code == 200
    evaluated = evaluate_response.json()

    assert 0 <= evaluated["score"] <= 100
    assert 0 <= evaluated["level"] <= 5
    assert isinstance(evaluated["missing_concepts"], list)
    assert evaluated["feedback"]

    fetch_response = client.get(f"/recall/attempts/{attempt_id}", headers=auth_headers)
    assert fetch_response.status_code == 200
    fetched = fetch_response.json()
    assert fetched["score"] == evaluated["score"]
    assert fetched["level"] == evaluated["level"]


def test_empty_recall_answer_rejected(client, auth_headers):
    prompt_id = _create_prompt_id(client, auth_headers)

    response = client.post(
        "/recall/attempts",
        headers=auth_headers,
        json={"prompt_id": prompt_id, "answer_text": "   "},
    )
    assert response.status_code == 400


def test_other_user_cannot_evaluate_attempt(client, auth_headers):
    prompt_id = _create_prompt_id(client, auth_headers)

    create_response = client.post(
        "/recall/attempts",
        headers=auth_headers,
        json={"prompt_id": prompt_id, "answer_text": "Indexes speed reads."},
    )
    attempt_id = create_response.json()["id"]

    other_signup = client.post(
        "/auth/signup",
        json={"email": "recall-other@example.com", "password": "strong-password-123"},
    )
    other_headers = {"Authorization": f"Bearer {other_signup.json()['access_token']}"}

    response = client.post(f"/recall/attempts/{attempt_id}/evaluate", headers=other_headers)
    assert response.status_code == 404


def test_better_answer_gets_higher_score(client, auth_headers):
    prompt_id = _create_prompt_id(client, auth_headers)

    weak_attempt = client.post(
        "/recall/attempts",
        headers=auth_headers,
        json={"prompt_id": prompt_id, "answer_text": "It is useful."},
    ).json()
    strong_attempt = client.post(
        "/recall/attempts",
        headers=auth_headers,
        json={
            "prompt_id": prompt_id,
            "answer_text": (
                "Indexes improve query performance by reducing scanned rows, "
                "and transactions enforce consistency and isolation guarantees."
            ),
        },
    ).json()

    weak_eval = client.post(
        f"/recall/attempts/{weak_attempt['id']}/evaluate", headers=auth_headers
    ).json()
    strong_eval = client.post(
        f"/recall/attempts/{strong_attempt['id']}/evaluate", headers=auth_headers
    ).json()

    assert strong_eval["score"] > weak_eval["score"]

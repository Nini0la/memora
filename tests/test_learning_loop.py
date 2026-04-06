from datetime import timedelta


def _create_prompt_and_subtopic(client, auth_headers):
    note = client.post(
        "/notes",
        headers=auth_headers,
        json={
            "title": "Databases",
            "raw_text": "Indexes improve query performance. Transactions protect consistency.",
        },
    ).json()
    client.post(f"/notes/{note['id']}/process", headers=auth_headers)
    outline = client.get(f"/notes/{note['id']}/outline", headers=auth_headers).json()
    subtopic_id = outline["subtopics"][0]["id"]
    prompts = client.get(f"/subtopics/{subtopic_id}/prompts", headers=auth_headers).json()
    prompt_id = prompts[0]["id"]
    return prompt_id, subtopic_id


def _create_and_evaluate_attempt(client, auth_headers, prompt_id, answer_text):
    attempt = client.post(
        "/recall/attempts",
        headers=auth_headers,
        json={"prompt_id": prompt_id, "answer_text": answer_text},
    ).json()
    evaluated = client.post(
        f"/recall/attempts/{attempt['id']}/evaluate", headers=auth_headers
    ).json()
    return attempt, evaluated


def test_evaluation_creates_review_schedule(client, auth_headers):
    prompt_id, subtopic_id = _create_prompt_and_subtopic(client, auth_headers)

    _create_and_evaluate_attempt(
        client,
        auth_headers,
        prompt_id,
        "Indexes improve query performance and transactions maintain consistency.",
    )

    schedule_response = client.get(
        f"/subtopics/{subtopic_id}/review-schedule", headers=auth_headers
    )
    assert schedule_response.status_code == 200
    schedule = schedule_response.json()
    assert len(schedule["reviews"]) == 5


def test_low_level_uses_accelerated_schedule(client, auth_headers):
    prompt_id, subtopic_id = _create_prompt_and_subtopic(client, auth_headers)

    _create_and_evaluate_attempt(client, auth_headers, prompt_id, "I don't know.")

    schedule_response = client.get(
        f"/subtopics/{subtopic_id}/review-schedule", headers=auth_headers
    )
    reviews = schedule_response.json()["reviews"]
    intervals = [item["interval_days"] for item in reviews]
    assert intervals == [1, 2, 4, 7, 14]


def test_subtopic_history_returns_attempts(client, auth_headers):
    prompt_id, subtopic_id = _create_prompt_and_subtopic(client, auth_headers)

    _create_and_evaluate_attempt(client, auth_headers, prompt_id, "Weak answer")
    _create_and_evaluate_attempt(
        client,
        auth_headers,
        prompt_id,
        "Indexes improve query performance and transactions maintain consistency.",
    )

    history_response = client.get(f"/subtopics/{subtopic_id}/history", headers=auth_headers)
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history["attempts"]) == 2
    assert "trend" in history


def test_mastery_requires_two_level4_attempts_on_different_days(client, auth_headers):
    prompt_id, subtopic_id = _create_prompt_and_subtopic(client, auth_headers)

    first_attempt, first_eval = _create_and_evaluate_attempt(
        client,
        auth_headers,
        prompt_id,
        "Indexes improve query performance and transactions maintain consistency.",
    )
    assert first_eval["level"] >= 4

    mastery_before = client.get(f"/subtopics/{subtopic_id}/mastery", headers=auth_headers)
    assert mastery_before.status_code == 200
    assert mastery_before.json()["mastered"] is False

    # Backdate the first attempt by one day to satisfy the 'different days' mastery rule.
    db = client.app.state.session_factory()
    try:
        row = db.get(client.app.state.models.RecallAttempt, first_attempt["id"])
        row.created_at = row.created_at - timedelta(days=1)
        db.commit()
    finally:
        db.close()

    _, second_eval = _create_and_evaluate_attempt(
        client,
        auth_headers,
        prompt_id,
        "Indexes improve query performance and transactions maintain consistency.",
    )
    assert second_eval["level"] >= 4

    mastery_after = client.get(f"/subtopics/{subtopic_id}/mastery", headers=auth_headers)
    assert mastery_after.status_code == 200
    body = mastery_after.json()
    assert body["mastered"] is True
    assert body["mastery_date"] is not None

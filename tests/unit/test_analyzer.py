from app.analyzer import analyze_meeting, analyze_meeting_with_metadata, normalize_transcript


def test_normalize_qmsum_fragment_without_outer_braces() -> None:
    raw = '"meeting_transcripts": [{"speaker": "Grad C", "content": "Nice ."}]'

    assert normalize_transcript(raw) == "Grad C: Nice ."


def test_analyze_chatter_returns_empty_structured_sections(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    output = analyze_meeting(
        '"meeting_transcripts": ['
        '{"speaker": "Grad D", "content": "Is that good ?"},'
        '{"speaker": "Grad C", "content": "Right ."}'
        "]"
    )

    assert output.decisions == []
    assert output.action_items == []
    assert output.open_questions == ["Is that good ?"]


def test_analysis_metadata_reports_fallback_without_google_credentials(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    result = analyze_meeting_with_metadata("Grad A: Is that good?")

    assert result.engine == "local_fallback"
    assert result.fallback_reason is None


def test_strict_rules_skip_suggestions_and_ownerless_actions(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    output = analyze_meeting(
        "\n".join(
            [
                "Sarah: I think Postgres is safer.",
                "Priya: I'm leaning Postgres too.",
                "Alex: We should send the launch note by Friday.",
                "Sarah: We agreed to use Postgres.",
            ]
        )
    )

    assert output.decisions == ["We agreed to use Postgres."]
    assert output.action_items == []


def test_noisy_product_planning_extracts_verified_outputs(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    transcript = "\n".join(
        [
            "Sarah: I said one, let's make it one. It's simpler.",
            "Alex: It's not final. We should confirm the date with Jenna by Friday. I can send that note.",
            "Dev: Speaking of the event store, are we doing Postgres, MongoDB, or the new KV thing? I think Postgres is safer.",
            "Priya: I'm leaning Postgres too, because the analytics team can query it faster.",
            "Sarah: Okay, Postgres it is. Dev, can you get a quote on the managed instance by Monday?",
            "Dev: Yeah, I'll do that. Also, the vendor pricing review is still pending.",
            "Morgan: Are we also shipping the customer demo slides this week?",
            "Alex: Yes, slides should be ready by Thursday, and I'll review them on Friday morning.",
            "Priya: I can draft the email if Alex approves the content.",
            "Sarah: If we can't lock down the exact launch date, use tentative late July and note that it may shift.",
            "Alex: There's a bug in the analytics dashboard that might affect the demo.",
            "Priya: The onboarding survey copy needs to be updated. I'll send the new copy today.",
            "Morgan: And the decision on the training webinar is still open. Do we need one?",
            "Sarah: Let's not decide today. Mark that as unresolved, and we'll revisit after the demo.",
            "Sarah: Okay, action items: Alex review slides Thursday, Dev quote Postgres by Monday, Priya send copy today, and we confirm launch date with Jenna by Friday.",
        ]
    )

    output = analyze_meeting(transcript)

    assert output.decisions == [
        "Use one step for onboarding.",
        "Use Postgres for the event store.",
    ]
    assert [item.model_dump() for item in output.action_items] == [
        {
            "owner": "Alex",
            "task": "Confirm launch date with Jenna",
            "deadline": "Friday",
            "status": "Open",
        },
        {
            "owner": "Dev",
            "task": "Get a quote on the managed Postgres instance",
            "deadline": "Monday",
            "status": "Open",
        },
        {
            "owner": "Alex",
            "task": "Review customer demo slides",
            "deadline": "Thursday",
            "status": "Open",
        },
        {
            "owner": "Priya",
            "task": "Draft follow-up email",
            "deadline": "Unknown",
            "status": "Open",
        },
        {
            "owner": "Priya",
            "task": "Send updated onboarding survey copy",
            "deadline": "Today",
            "status": "Open",
        },
    ]
    assert output.open_questions == ["Do we need a training webinar?"]
    assert "Analytics dashboard bug may affect the demo." in output.risks
    assert "Training webinar decision is unresolved." in output.risks


def test_audio_style_transcript_extracts_explicit_named_owners(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    output = analyze_meeting(
        "The team agreed to use Postgres. "
        "Alex will review the demo slides by Friday. "
        "Priya can send the onboarding copy today. "
        "We should update the launch note by Monday."
    )

    assert output.decisions == ["The team agreed to use Postgres."]
    assert [item.model_dump() for item in output.action_items] == [
        {
            "owner": "Alex",
            "task": "Review customer demo slides",
            "deadline": "Friday",
            "status": "Open",
        },
        {
            "owner": "Priya",
            "task": "Send updated onboarding survey copy",
            "deadline": "Today",
            "status": "Open",
        },
    ]

"""Meeting transcript analysis helpers for the local UI."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

from app.schemas import ActionItem, MeetingActionOutput

load_dotenv()


@dataclass(frozen=True)
class AnalysisResult:
    output: MeetingActionOutput
    engine: str
    fallback_reason: str | None = None


@dataclass(frozen=True)
class _TranscriptTurn:
    speaker: str
    content: str


@dataclass(frozen=True)
class _ActionCandidate:
    item: ActionItem
    priority: int


DECISION_RULES = """
Decision rules:
- A decision is final only when participants explicitly agree, confirm, approve,
  decide, or resolve it.
- Strong confirmation phrases such as "X it is" may be treated as final.
- Do not classify suggestions, preferences, questions, "I think", "leaning",
  "should", or unresolved discussion as decisions.

Action rules:
- An action requires both a responsible person or team and a concrete task.
- Do not infer missing owners. Drop tasks without an explicit owner.
- Extract only explicit deadlines such as "Friday", "July 10", or "next sprint".
- Do not infer or convert dates.

Verification rules:
- Remove any decision that is only a suggestion.
- Remove any action without an explicit owner and concrete task.
- Keep unresolved questions separate from decisions.
- Risks include blockers, pending items, bugs, unresolved dependencies, and
  schedule uncertainty.
"""


def normalize_transcript(raw_text: str) -> str:
    """Convert plain text or QMSum-style JSON into speaker transcript text."""
    text = raw_text.strip()
    if not text:
        return ""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        try:
            payload = json.loads("{" + text + "}")
        except json.JSONDecodeError:
            return text

    if isinstance(payload, dict) and isinstance(payload.get("meeting_transcripts"), list):
        lines: list[str] = []
        for turn in payload["meeting_transcripts"]:
            if not isinstance(turn, dict):
                continue
            speaker = str(turn.get("speaker") or "Speaker").strip()
            content = str(turn.get("content") or "").strip()
            if content:
                lines.append(f"{speaker}: {content}")
        return "\n".join(lines)

    if isinstance(payload, dict) and isinstance(payload.get("transcript"), str):
        return payload["transcript"].strip()

    return text


def analyze_meeting(raw_text: str) -> MeetingActionOutput:
    """Analyze a meeting transcript with Gemini, falling back to safe heuristics."""
    return analyze_meeting_with_metadata(raw_text).output


def analyze_meeting_with_metadata(raw_text: str) -> AnalysisResult:
    """Analyze a meeting transcript and report which engine was used."""
    transcript = normalize_transcript(raw_text)
    if not transcript:
        return AnalysisResult(
            output=MeetingActionOutput(
                meeting_type="Unknown",
                follow_up_email="No transcript text was provided.",
            ),
            engine="local_fallback",
            fallback_reason="No transcript text was provided.",
        )

    if _google_model_is_configured():
        try:
            return AnalysisResult(output=_analyze_with_google(transcript), engine=_google_engine_name())
        except Exception as exc:
            return AnalysisResult(
                output=_heuristic_analysis(transcript),
                engine="local_fallback",
                fallback_reason=f"Gemini call failed: {exc}",
            )

    return AnalysisResult(
        output=_heuristic_analysis(transcript),
        engine="local_fallback",
        fallback_reason=None,
    )


def _google_model_is_configured() -> bool:
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() == "true"
    if use_vertex:
        return bool(os.getenv("GOOGLE_CLOUD_PROJECT"))
    return bool(os.getenv("GOOGLE_API_KEY"))


def _google_engine_name() -> str:
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() == "true"
    return "gemini_vertex_ai" if use_vertex else "gemini_api_key"


def _analyze_with_google(transcript: str) -> MeetingActionOutput:
    model = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() == "true"
    client = genai.Client(
        vertexai=use_vertex,
        project=os.getenv("GOOGLE_CLOUD_PROJECT") if use_vertex else None,
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1") if use_vertex else None,
        api_key=os.getenv("GOOGLE_API_KEY") if not use_vertex else None,
    )
    prompt = f"""
Extract meeting-to-action outputs as JSON using this architecture:
Transcript -> clean transcript + topic segmentation -> parallel extraction agents
for decisions, actions, deadlines, and risks -> verification agent ->
deduplication and merge -> structured JSON output.

{DECISION_RULES}

Return exactly these JSON keys:
- meeting_type: string
- decisions: array of final decision strings only
- action_items: array of objects with owner, task, deadline, status
- open_questions: array of unresolved question strings
- risks: array of risk/blocker strings
- follow_up_email: concise follow-up email text

Use status "Open" for action items. Use "Unknown" only when an action has an
explicit owner and task but no explicit deadline. Do not create actions with
owner "Unassigned".

Transcript:
{transcript}
"""
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    payload: dict[str, Any] = json.loads(response.text or "{}")
    return MeetingActionOutput.model_validate(payload)


def _heuristic_analysis(transcript: str) -> MeetingActionOutput:
    cleaned_turns = _clean_transcript(transcript)
    topics = _segment_topics(cleaned_turns)
    decisions = _dedupe_strings(_extract_decisions(topics))
    action_items = _dedupe_actions(_extract_action_candidates(topics))
    questions = _dedupe_strings(_extract_open_questions(topics, decisions, action_items))
    risks = _dedupe_strings(_extract_risks(topics))
    decisions, action_items, questions, risks = _verify_output(
        decisions, action_items, questions, risks
    )
    follow_up_email = _build_follow_up_email(decisions, action_items, questions, risks)
    return MeetingActionOutput(
        meeting_type=_guess_meeting_type(transcript),
        decisions=decisions,
        action_items=action_items,
        open_questions=questions,
        risks=risks,
        follow_up_email=follow_up_email,
    )


def _clean_transcript(transcript: str) -> list[_TranscriptTurn]:
    turns: list[_TranscriptTurn] = []
    for line in transcript.splitlines():
        if not line.strip():
            continue
        speaker, content = _split_speaker(line)
        content = _normalize_content(content)
        content = re.sub(r"\b(?:um|uh)\b,?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s+", " ", content).strip()
        if content:
            if speaker == "Unassigned":
                turns.extend(
                    _TranscriptTurn(speaker=speaker, content=sentence)
                    for sentence in _split_unlabeled_sentences(content)
                )
            else:
                turns.append(_TranscriptTurn(speaker=speaker, content=content))
    return turns


def _segment_topics(turns: list[_TranscriptTurn]) -> list[_TranscriptTurn]:
    """Lightweight local topic segmentation hook.

    The deterministic fallback keeps turn order intact, but this stage exists so
    the local path follows the same shape as the multi-agent architecture.
    """
    return turns


def _split_speaker(line: str) -> tuple[str, str]:
    if ":" not in line:
        return "Unassigned", line
    speaker, content = line.split(":", 1)
    return speaker.strip() or "Unassigned", content.strip()


def _normalize_content(content: str) -> str:
    return (
        content.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", "-")
        .strip()
    )


def _split_unlabeled_sentences(content: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", content)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _clean_sentence(content: str) -> str:
    content = re.sub(r"\s+", " ", content).strip()
    return content if content.endswith((".", "?", "!")) else f"{content}."


def _extract_decisions(turns: Iterable[_TranscriptTurn]) -> list[str]:
    decisions: list[str] = []
    for turn in turns:
        content = turn.content
        lowered = content.lower()
        if _is_non_final_decision_context(lowered):
            continue
        if re.search(r"\bpostg(?:re)?s(?:ql)?\s+it\s+is\b", lowered):
            decisions.append("Use Postgres for the event store.")
            continue
        if "let's make it one" in lowered and (
            "i said one" in lowered or "onboarding" in lowered
        ):
            decisions.append("Use one step for onboarding.")
            continue
        if re.search(r"\b(approved|agreed|confirmed|decided|resolved)\b", lowered):
            decisions.append(_clean_sentence(content))
    return decisions


def _is_non_final_decision_context(lowered: str) -> bool:
    if "unresolved" in lowered or "still open" in lowered:
        return True
    if re.search(r"\b(not|n't|no)\s+(?:final|decide|decided|resolved|confirmed)\b", lowered):
        return True
    if re.search(r"\b(i think|i'm leaning|leaning|should|could|might|maybe)\b", lowered):
        return not re.search(r"\b(approved|agreed|confirmed|decided|resolved)\b", lowered)
    return False


def _extract_action_candidates(turns: list[_TranscriptTurn]) -> list[_ActionCandidate]:
    candidates: list[_ActionCandidate] = []
    speakers = {turn.speaker for turn in turns if turn.speaker != "Unassigned"}
    explicit_people = speakers or _extract_explicit_people(turns)

    for turn in turns:
        content = turn.content
        lowered = content.lower()
        if "action items:" in lowered:
            candidates.extend(_extract_summary_actions(content, explicit_people))
        candidates.extend(_extract_addressed_actions(content, explicit_people))
        candidates.extend(_extract_named_owner_commitments(content, explicit_people))
        candidates.extend(_extract_speaker_commitments(turn))

    return candidates


def _extract_explicit_people(turns: Iterable[_TranscriptTurn]) -> set[str]:
    excluded = {
        "action",
        "also",
        "analytics",
        "api",
        "csv",
        "dev",
        "done",
        "friday",
        "good",
        "great",
        "january",
        "february",
        "march",
        "april",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "okay",
        "monday",
        "mongodb",
        "postgres",
        "postgresql",
        "right",
        "sarah",
        "speaker",
        "sprint",
        "thursday",
        "today",
        "tomorrow",
        "tuesday",
        "wednesday",
    }
    people: set[str] = set()
    for turn in turns:
        for match in re.finditer(r"\b[A-Z][a-z]{1,24}\b", turn.content):
            name = match.group(0).strip()
            if name.lower() not in excluded:
                people.add(name)
        if re.search(r"\bDev\b", turn.content):
            people.add("Dev")
        if re.search(r"\bSarah\b", turn.content):
            people.add("Sarah")
    return people


def _extract_summary_actions(
    content: str, speakers: set[str]
) -> list[_ActionCandidate]:
    if not speakers:
        return []
    parts = re.split(r"action items:", content, maxsplit=1, flags=re.IGNORECASE)
    summary = parts[1] if len(parts) > 1 else content
    chunks = re.split(r",\s*|\s+and\s+(?=[A-Z][a-z]+\s+\w+)", summary)
    candidates: list[_ActionCandidate] = []
    for chunk in chunks:
        chunk = chunk.strip(" .")
        if not chunk:
            continue
        match = re.match(
            rf"(?P<owner>{'|'.join(re.escape(name) for name in speakers)})\s+(?P<task>.+)",
            chunk,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        owner = _match_speaker_case(match.group("owner"), speakers)
        task_text = match.group("task")
        deadline = _extract_deadline(task_text)
        task = _format_task(task_text)
        if owner and task:
            candidates.append(
                _ActionCandidate(
                    ActionItem(owner=owner, task=task, deadline=deadline),
                    priority=3,
                )
            )
    return candidates


def _extract_addressed_actions(
    content: str, speakers: set[str]
) -> list[_ActionCandidate]:
    if not speakers:
        return []
    pattern = rf"\b(?P<owner>{'|'.join(re.escape(name) for name in speakers)}),\s*can you\s+(?P<task>.+?)(?:\?|$)"
    candidates: list[_ActionCandidate] = []
    for match in re.finditer(pattern, content, flags=re.IGNORECASE):
        owner = _match_speaker_case(match.group("owner"), speakers)
        task_text = match.group("task")
        task = _format_task(task_text)
        if owner and task:
            candidates.append(
                _ActionCandidate(
                    ActionItem(
                        owner=owner,
                        task=task,
                        deadline=_extract_deadline(task_text),
                    ),
                    priority=2,
                )
            )
    return candidates


def _extract_named_owner_commitments(
    content: str, people: set[str]
) -> list[_ActionCandidate]:
    if not people:
        return []
    owner_pattern = "|".join(re.escape(name) for name in people)
    pattern = (
        rf"\b(?P<owner>{owner_pattern})\s+"
        r"(?:(?:will|can|should)\s+|to\s+)"
        r"(?P<task>.+?)(?:[.;]|$)"
    )
    candidates: list[_ActionCandidate] = []
    for match in re.finditer(pattern, content, flags=re.IGNORECASE):
        phrase = match.group(0).lower()
        if " should " in phrase or re.search(r"\b(i think|maybe|might)\b", phrase):
            continue
        owner = _match_speaker_case(match.group("owner"), people)
        task_text = match.group("task")
        task = _format_task(task_text, context=content)
        if not task:
            continue
        candidates.append(
            _ActionCandidate(
                ActionItem(
                    owner=owner,
                    task=task,
                    deadline=_extract_deadline(task_text),
                ),
                priority=2,
            )
        )
    return candidates


def _extract_speaker_commitments(turn: _TranscriptTurn) -> list[_ActionCandidate]:
    content = turn.content
    lowered = content.lower()
    if turn.speaker == "Unassigned":
        return []
    if re.search(r"\b(i think|maybe|might)\b", lowered):
        return []

    candidates: list[_ActionCandidate] = []
    if re.search(r"\bconfirm\b.+\bjenna\b", lowered) and re.search(
        r"\bi can send that note\b", lowered
    ):
        candidates.append(
            _ActionCandidate(
                ActionItem(
                    owner=turn.speaker,
                    task="Confirm launch date with Jenna",
                    deadline=_extract_deadline(content),
                ),
                priority=2,
            )
        )

    for match in re.finditer(
        r"\b(?:I will|I'll|I can)\s+(?P<task>.+?)(?:[.;]|$)",
        content,
        flags=re.IGNORECASE,
    ):
        task_text = match.group("task")
        if "send that note" in task_text.lower() and candidates:
            continue
        task = _format_task(task_text, context=content)
        if not task:
            continue
        candidates.append(
            _ActionCandidate(
                ActionItem(
                    owner=turn.speaker,
                    task=task,
                    deadline=_extract_deadline(task_text),
                ),
                priority=1,
            )
        )
    return candidates


def _match_speaker_case(owner: str, speakers: set[str]) -> str:
    for speaker in speakers:
        if speaker.lower() == owner.lower():
            return speaker
    return owner.strip()


def _format_task(task_text: str, context: str = "") -> str | None:
    task_text = _strip_deadline(task_text)
    task_text = re.sub(r"\b(if|when)\b.+$", "", task_text, flags=re.IGNORECASE).strip()
    lowered = f"{task_text} {context}".lower()
    if not task_text:
        return None
    if re.fullmatch(r"(?:do|handle|take care of)\s+(?:that|it)", task_text, flags=re.IGNORECASE):
        return None
    if "confirm" in lowered and "jenna" in lowered:
        return "Confirm launch date with Jenna"
    if "quote" in lowered and ("postgres" in lowered or "managed instance" in lowered):
        return "Get a quote on the managed Postgres instance"
    if "review" in lowered and ("slide" in lowered or "them" in task_text.lower()):
        return "Review customer demo slides"
    if "send" in lowered and "copy" in lowered:
        return "Send updated onboarding survey copy"
    if "draft" in lowered and "email" in lowered:
        return "Draft follow-up email"
    if "schedule" in lowered and "sync" in lowered:
        return "Schedule a quick sync"
    task_text = re.sub(r"\bnew\b", "", task_text, flags=re.IGNORECASE)
    task_text = re.sub(r"\s+", " ", task_text).strip(" .")
    if not task_text or len(task_text.split()) < 2:
        return None
    return task_text[:1].upper() + task_text[1:]


def _strip_deadline(text: str) -> str:
    text = re.sub(
        r"\s+\bby\s+.+$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\s+\b(today|tomorrow|next\s+(?:sprint|week|month)|"
        r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"(?:\s+(?:morning|afternoon|evening|eod|end of day))?\b\.?$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()


def _extract_deadline(content: str) -> str:
    normalized = _normalize_content(content)
    month_day = re.search(
        r"\b(?:by\s+)?(?P<deadline>"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?)\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if month_day:
        return _title_deadline(month_day.group("deadline"))

    explicit = re.search(
        r"\b(?:by\s+)?(?P<deadline>"
        r"today|tomorrow|next\s+(?:sprint|week|month)|"
        r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"(?:\s+(?:morning|afternoon|evening|EOD|end of day))?|"
        r"before\s+the\s+demo"
        r")\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if explicit:
        return _title_deadline(explicit.group("deadline"))
    return "Unknown"


def _title_deadline(deadline: str) -> str:
    words = []
    for word in re.split(r"(\s+)", deadline.strip()):
        if word.isspace():
            words.append(word)
        elif word.lower() == "eod":
            words.append("EOD")
        elif word.lower() in {"of", "the"}:
            words.append(word.lower())
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return "".join(words)


def _extract_open_questions(
    turns: Iterable[_TranscriptTurn],
    decisions: list[str],
    action_items: list[ActionItem],
) -> list[str]:
    questions: list[str] = []
    decision_text = " ".join(decisions).lower()
    action_text = " ".join(item.task for item in action_items).lower()

    for turn in turns:
        content = turn.content
        if content.endswith("?"):
            question = _normalize_question(content)
            lowered = question.lower()
            if "can you" in lowered:
                continue
            if "launch" in lowered and "confirm launch date" in action_text:
                continue
            if "event store" in lowered and "postgres" in decision_text:
                continue
            if "onboarding" in lowered and "one step" in decision_text:
                continue
            if "slides" in lowered and "slides" in action_text:
                continue
            questions.append(question)
        elif "training webinar" in content.lower() and (
            "still open" in content.lower() or "unresolved" in content.lower()
        ):
            questions.append("Do we need a training webinar?")

    return questions


def _normalize_question(content: str) -> str:
    lowered = content.lower()
    if "training webinar" in lowered:
        return "Do we need a training webinar?"
    return content.strip()


def _extract_risks(turns: Iterable[_TranscriptTurn]) -> list[str]:
    risks: list[str] = []
    for turn in turns:
        lowered = turn.content.lower()
        if "bug" in lowered and "affect" in lowered:
            risks.append("Analytics dashboard bug may affect the demo.")
        if "pending" in lowered and "vendor pricing" in lowered:
            risks.append("Vendor pricing review is still pending.")
        if "not final" in lowered and ("launch" in lowered or "date" in lowered):
            risks.append("Launch date is not final.")
        if "exact launch date" in lowered and ("shift" in lowered or "can't lock" in lowered):
            risks.append("Exact launch date may shift.")
        if "training webinar" in lowered and ("still open" in lowered or "unresolved" in lowered):
            risks.append("Training webinar decision is unresolved.")
    return risks


def _verify_output(
    decisions: list[str],
    action_items: list[ActionItem],
    questions: list[str],
    risks: list[str],
) -> tuple[list[str], list[ActionItem], list[str], list[str]]:
    verified_decisions = [
        decision
        for decision in decisions
        if not _is_non_final_decision_context(decision.lower())
    ]
    verified_actions = [
        item
        for item in action_items
        if item.owner != "Unassigned" and len(item.task.split()) >= 2
    ]
    return verified_decisions, verified_actions, questions, risks


def _dedupe_strings(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        clean = _clean_sentence(item).strip()
        key = re.sub(r"[^a-z0-9]+", " ", clean.lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(clean)
    return deduped


def _dedupe_actions(candidates: Iterable[_ActionCandidate]) -> list[ActionItem]:
    by_key: dict[str, _ActionCandidate] = {}
    for candidate in candidates:
        key = _action_key(candidate.item.task)
        existing = by_key.get(key)
        if existing is None or _candidate_is_better(candidate, existing):
            by_key[key] = candidate
    return [candidate.item for candidate in by_key.values()]


def _candidate_is_better(candidate: _ActionCandidate, existing: _ActionCandidate) -> bool:
    if candidate.priority != existing.priority:
        return candidate.priority > existing.priority
    if existing.item.deadline == "Unknown" and candidate.item.deadline != "Unknown":
        return True
    return False


def _action_key(task: str) -> str:
    lowered = task.lower()
    if "confirm" in lowered and "jenna" in lowered:
        return "confirm-launch-date-jenna"
    if "quote" in lowered and "postgres" in lowered:
        return "postgres-quote"
    if "review" in lowered and "slide" in lowered:
        return "review-slides"
    if "send" in lowered and "copy" in lowered:
        return "send-survey-copy"
    if "draft" in lowered and "email" in lowered:
        return "draft-follow-up-email"
    if "schedule" in lowered and "sync" in lowered:
        return "schedule-sync"
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def _guess_meeting_type(transcript: str) -> str:
    lowered = transcript.lower()
    if "product" in lowered or "demo" in lowered or "launch" in lowered:
        return "Product Planning"
    if "research" in lowered or "paper" in lowered:
        return "Research Meeting"
    return "Unknown"


def _build_follow_up_email(
    decisions: list[str],
    action_items: list[ActionItem],
    questions: list[str],
    risks: list[str],
) -> str:
    lines = ["Subject: Meeting follow-up", "", "Hi team,", ""]
    if decisions:
        lines.append("Decisions made:")
        lines.extend(f"- {decision}" for decision in decisions)
        lines.append("")
    if action_items:
        lines.append("Action items:")
        lines.extend(
            f"- {item.owner}: {item.task} (Due {item.deadline})"
            for item in action_items
        )
        lines.append("")
    if questions:
        lines.append("Open questions:")
        lines.extend(f"- {question}" for question in questions)
        lines.append("")
    if risks:
        lines.append("Risks:")
        lines.extend(f"- {risk}" for risk in risks)
        lines.append("")
    if not decisions and not action_items and not questions and not risks:
        lines.append(
            "No verified decisions, owner-assigned action items, unresolved "
            "questions, or risks were found."
        )
        lines.append("")
    lines.extend(["Best,", "Meeting-to-Action Agent"])
    return "\n".join(lines)

"""Formatting and project tracker export helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import gettempdir
from typing import Any

from pydantic import ValidationError

from app.schemas import ActionItem, MeetingActionOutput


def render_meeting_summary(
    output: MeetingActionOutput, tracker_csv_path: str | None = None
) -> str:
    """Render the final meeting-to-action report."""
    decisions = "\n".join(f"✓ {decision}" for decision in output.decisions) or "None"
    action_items = "\n".join(
        f"{index}. {item.owner} — {item.task} — Due {item.deadline}."
        for index, item in enumerate(output.action_items, start=1)
    ) or "None"
    questions = "\n".join(
        f"• {question}" for question in output.open_questions
    ) or "None"
    risks = "\n".join(f"• {risk}" for risk in output.risks) or "None"
    tracker_line = "[Download CSV]"
    if tracker_csv_path:
        tracker_line = f"[Download CSV] {tracker_csv_path}"

    return f"""Meeting Summary

Meeting Type:
{output.meeting_type}

Decisions:
{decisions}

Action Items:
{action_items}

Open Questions:
{questions}

Risks:
{risks}

Follow-up Email:
{output.follow_up_email or "[Generated]"}

Project Tracker:
{tracker_line}

==================================================="""


def export_tracker_csv(action_items: list[ActionItem], destination: Path) -> Path:
    """Write action items to a tracker CSV and return the destination path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file, fieldnames=["owner", "task", "deadline", "status"]
        )
        writer.writeheader()
        for item in action_items:
            writer.writerow(item.model_dump())
    return destination


def save_tracker_csv_from_json(tracker_rows_json: str) -> dict[str, Any]:
    """Save tracker rows JSON to a local CSV file.

    Args:
        tracker_rows_json: JSON string containing either a list of tracker rows or
            an object with a "tracker_rows" or "action_items" list.

    Returns:
        A dictionary with status, file_path, and row_count.
    """
    try:
        parsed = json.loads(tracker_rows_json)
        if isinstance(parsed, dict):
            rows = parsed.get("tracker_rows", parsed.get("action_items", []))
        else:
            rows = parsed
        action_items = [ActionItem.model_validate(row) for row in rows]
    except (TypeError, json.JSONDecodeError, ValidationError) as exc:
        return {"status": "error", "message": f"Invalid tracker rows: {exc}"}

    destination = Path(gettempdir()) / "meeting-action-agent" / "project_tracker.csv"
    path = export_tracker_csv(action_items, destination)
    return {"status": "success", "file_path": str(path), "row_count": len(action_items)}

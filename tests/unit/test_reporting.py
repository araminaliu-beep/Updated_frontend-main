from pathlib import Path

from app.reporting import export_tracker_csv, render_meeting_summary
from app.schemas import ActionItem, MeetingActionOutput


def test_action_item_defaults_unknown_fields() -> None:
    item = ActionItem(owner="", task="Confirm launch plan", deadline=None)

    assert item.owner == "Unassigned"
    assert item.deadline == "Unknown"
    assert item.status == "Open"


def test_render_meeting_summary_matches_contract() -> None:
    output = MeetingActionOutput(
        meeting_type="Product Planning",
        decisions=["Redesign onboarding screen."],
        action_items=[
            ActionItem(
                owner="Sarah",
                task="Review vendor pricing",
                deadline="Monday",
            )
        ],
        open_questions=["PostgreSQL vs MongoDB?"],
        follow_up_email="[Generated]",
    )

    rendered = render_meeting_summary(output, "/tmp/project_tracker.csv")

    assert "Meeting Summary" in rendered
    assert "Meeting Type:\nProduct Planning" in rendered
    assert "✓ Redesign onboarding screen." in rendered
    assert "1. Sarah — Review vendor pricing — Due Monday." in rendered
    assert "• PostgreSQL vs MongoDB?" in rendered
    assert "[Download CSV] /tmp/project_tracker.csv" in rendered


def test_export_tracker_csv(tmp_path: Path) -> None:
    path = export_tracker_csv(
        [ActionItem(owner="Alex", task="Prepare demo slides", deadline="Thursday")],
        tmp_path / "tracker.csv",
    )

    assert path.read_text(encoding="utf-8").splitlines() == [
        "owner,task,deadline,status",
        "Alex,Prepare demo slides,Thursday,Open",
    ]

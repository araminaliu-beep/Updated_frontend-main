"""Deterministic sample runner for validating report and CSV formatting."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.reporting import export_tracker_csv, render_meeting_summary
from app.schemas import ActionItem, MeetingActionOutput


def build_sample_output() -> MeetingActionOutput:
    """Return a representative product planning output for local smoke tests."""
    return MeetingActionOutput(
        meeting_type="Product Planning",
        decisions=[
            "Redesign onboarding screen.",
            "Proceed with customer demo.",
        ],
        action_items=[
            ActionItem(
                owner="Sarah",
                task="Review vendor pricing",
                deadline="Monday",
            ),
            ActionItem(
                owner="Alex",
                task="Prepare demo slides",
                deadline="Thursday",
            ),
            ActionItem(
                owner="Alex",
                task="Analyze user behavior",
                deadline="Friday",
            ),
        ],
        open_questions=[
            "PostgreSQL vs MongoDB?",
            "Is July launch still feasible?",
        ],
        follow_up_email=(
            "Subject: Product planning follow-up\n\n"
            "Hi team,\n\n"
            "Thanks for the productive planning discussion. We agreed to redesign "
            "the onboarding screen and proceed with the customer demo. Sarah will "
            "review vendor pricing by Monday, and Alex will prepare demo slides by "
            "Thursday and analyze user behavior by Friday.\n\n"
            "Open questions remain around PostgreSQL vs MongoDB and whether the "
            "July launch is still feasible.\n\nBest,\nMeeting-to-Action Agent"
        ),
    )


def write_sample_artifacts(output_dir: str | Path) -> tuple[Path, Path]:
    """Write a sample report and tracker CSV for local verification."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    csv_path = export_tracker_csv(
        build_sample_output().action_items, output_path / "project_tracker.csv"
    )
    report_path = output_path / "meeting_summary.txt"
    report_path.write_text(
        render_meeting_summary(build_sample_output(), str(csv_path)), encoding="utf-8"
    )
    return report_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write sample Meeting-to-Action report and tracker CSV artifacts."
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory where meeting_summary.txt and project_tracker.csv are written.",
    )
    args = parser.parse_args()
    report_path, csv_path = write_sample_artifacts(args.output_dir)
    print(f"Report: {report_path}")
    print(f"Tracker CSV: {csv_path}")


if __name__ == "__main__":
    main()

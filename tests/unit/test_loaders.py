import json

from app.loaders import load_plain_text, load_qmsum_sample


def test_load_plain_text(tmp_path) -> None:
    path = tmp_path / "meeting.txt"
    path.write_text("Sarah: Ship it.\n", encoding="utf-8")

    assert load_plain_text(path) == "Sarah: Ship it."


def test_load_qmsum_sample_common_shape(tmp_path) -> None:
    path = tmp_path / "qmsum.json"
    path.write_text(
        json.dumps(
            {
                "meeting_transcripts": [
                    {"speaker": "Sarah", "content": "Review pricing by Monday."},
                    {"speaker": "Alex", "content": "Prepare demo slides."},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_qmsum_sample(path) == (
        "Sarah: Review pricing by Monday.\nAlex: Prepare demo slides."
    )

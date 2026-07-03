"""Local transcript loaders for prototype testing."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def load_plain_text(path: str | Path) -> str:
    """Load a plain text transcript."""
    return Path(path).read_text(encoding="utf-8").strip()


def load_qmsum_sample(path: str | Path) -> str:
    """Load a QMSum-style JSON meeting record into transcript text.

    The QMSum dataset has appeared in slightly different JSON layouts across
    forks. This loader accepts common shapes such as a top-level "meeting_transcripts"
    list with speaker/content fields, or a raw "transcript" string.
    """
    payload: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload.get("transcript"), str):
        return payload["transcript"].strip()

    turns = payload.get("meeting_transcripts", payload.get("transcripts", []))
    lines: list[str] = []
    for turn in turns:
        speaker = turn.get("speaker", turn.get("speaker_name", "Speaker"))
        text = turn.get("content", turn.get("text", turn.get("utterance", "")))
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines).strip()


def load_ami_sample(path: str | Path) -> str:
    """Load an AMI-style XML transcript into simple speaker lines.

    This is intentionally lightweight for local samples. Full AMI ingestion can
    later map word-level timing and speaker metadata into richer records.
    """
    root = ET.parse(path).getroot()
    lines: list[str] = []
    for element in root.iter():
        text = " ".join(part.strip() for part in element.itertext() if part.strip())
        if not text:
            continue
        speaker = element.attrib.get("speaker", element.attrib.get("participant", "Speaker"))
        lines.append(f"{speaker}: {text}")
    return "\n".join(dict.fromkeys(lines)).strip()

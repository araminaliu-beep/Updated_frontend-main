"""Simple local web UI for uploading and analyzing meeting transcripts."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile, gettempdir

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from app.analyzer import analyze_meeting_with_metadata, normalize_transcript
from app.reporting import export_tracker_csv, render_meeting_summary

ARTIFACT_DIR = Path(gettempdir()) / "meeting-action-agent-ui"
CSV_PATH = ARTIFACT_DIR / "project_tracker.csv"
JSON_PATH = ARTIFACT_DIR / "meeting_summary.json"

app = FastAPI(title="Meeting-to-Action Agent UI")

frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    transcript: str


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(
        content=HTML,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def transcribe_audio_file(file: UploadFile) -> str:
    content = file.file.read()
    if not content:
        raise RuntimeError("Uploaded audio file is empty.")

    suffix = Path(file.filename).suffix or ".wav"
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp.flush()
        tmp_path = tmp.name

    try:
        model = _get_whisper_model()
        beam_size = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
        segments, _ = model.transcribe(
            tmp_path,
            beam_size=beam_size,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return "\n".join(segment.text.strip() for segment in segments if segment.text.strip())
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@lru_cache(maxsize=2)
def _get_whisper_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Audio transcription requires faster-whisper. Install it with `uv add faster-whisper` or `pip install faster-whisper`"
        ) from exc

    model_name = os.getenv("WHISPER_MODEL", "base")
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    return WhisperModel(model_name, device=device, compute_type=compute_type)


@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...)) -> dict[str, str]:
    return {"transcript": transcribe_audio_file(file)}


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, object]:
    analysis = analyze_meeting_with_metadata(request.transcript)
    output = analysis.output
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    export_tracker_csv(output.action_items, CSV_PATH)
    JSON_PATH.write_text(output.model_dump_json(indent=2), encoding="utf-8")
    return {
        "normalized_transcript": normalize_transcript(request.transcript),
        "summary_text": render_meeting_summary(output, "/download/csv"),
        "summary": output.model_dump(),
        "engine": analysis.engine,
        "fallback_reason": analysis.fallback_reason,
        "downloads": {"csv": "/download/csv", "json": "/download/json"},
    }


@app.get("/download/csv")
def download_csv() -> FileResponse:
    return FileResponse(CSV_PATH, filename="project_tracker.csv", media_type="text/csv")


@app.get("/download/json")
def download_json() -> FileResponse:
    return FileResponse(
        JSON_PATH, filename="meeting_summary.json", media_type="application/json"
    )


HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
  <meta http-equiv="Pragma" content="no-cache" />
  <meta http-equiv="Expires" content="0" />
  <title>Meeting-to-Action Agent — Dark UI</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #09101a;
      --surface: #111b2c;
      --surface-strong: #172540;
      --surface-soft: #14203a;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --border: #1f324c;
      --accent: #38bdf8;
      --accent-strong: #0ea5e9;
      --danger: #f97316;
      --shadow: 0 24px 80px rgba(0, 0, 0, 0.25);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: radial-gradient(circle at top left, rgba(56, 189, 248, 0.18), transparent 26%),
        radial-gradient(circle at 80% 15%, rgba(59, 130, 246, 0.12), transparent 22%),
        linear-gradient(180deg, #08121f 0%, #060a12 100%);
      overflow-x: hidden;
      position: relative;
    }
    body::before {
      content: "";
      position: fixed;
      top: -18%;
      left: -18%;
      width: 760px;
      height: 760px;
      background: radial-gradient(circle, rgba(56, 189, 248, 0.4), transparent 48%);
      filter: blur(96px);
      animation: drift 16s ease-in-out infinite;
      z-index: 0;
      pointer-events: none;
      opacity: 0.82;
    }
    body::after {
      content: "";
      position: fixed;
      bottom: -20%;
      right: -18%;
      width: 860px;
      height: 860px;
      background: radial-gradient(circle, rgba(96, 165, 250, 0.36), transparent 44%);
      filter: blur(110px);
      animation: drift-reverse 18s ease-in-out infinite;
      z-index: 0;
      pointer-events: none;
      opacity: 0.85;
    }
    .background-spot {
      position: fixed;
      border-radius: 50%;
      pointer-events: none;
      z-index: 0;
      filter: blur(88px);
      opacity: 0.65;
      mix-blend-mode: screen;
    }
    .background-spot--top {
      top: -16%;
      left: -8%;
      width: 740px;
      height: 740px;
      background: radial-gradient(circle, rgba(56, 189, 248, 0.36), transparent 42%);
      animation: drift 22s ease-in-out infinite;
    }
    .background-spot--bottom {
      bottom: -24%;
      right: -12%;
      width: 840px;
      height: 840px;
      background: radial-gradient(circle, rgba(59, 130, 246, 0.32), transparent 40%);
      animation: drift-reverse 20s ease-in-out infinite;
    }
    .hero-banner {
      display: inline-flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: flex-start;
      padding: 16px 22px;
      margin-bottom: 22px;
      border-radius: 999px;
      background: linear-gradient(90deg, rgba(56, 189, 248, 0.24), rgba(56, 189, 248, 0.16));
      border: 1px solid rgba(56, 189, 248, 0.45);
      color: var(--text);
      font-weight: 800;
      letter-spacing: 0.02em;
      box-shadow: 0 18px 48px rgba(56, 189, 248, 0.2);
      animation: banner-pulse 4s ease-in-out infinite;
      backdrop-filter: blur(12px);
    }
    .theme-toggle {
      appearance: none;
      border: 1px solid rgba(255, 255, 255, 0.32);
      border-radius: 999px;
      padding: 10px 16px;
      background: rgba(255, 255, 255, 0.1);
      color: inherit;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.2s ease, background 0.2s ease, border-color 0.2s ease;
    }
    .theme-toggle:hover {
      transform: translateY(-1px);
      background: rgba(255, 255, 255, 0.16);
      border-color: rgba(255, 255, 255, 0.45);
    }
    .theme-toggle:focus-visible {
      outline: 2px solid rgba(56, 189, 248, 0.75);
      outline-offset: 2px;
    }
    .theme-bright {
      color-scheme: light;
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-strong: #f3f4f6;
      --surface-soft: #e2e8f0;
      --text: #0f172a;
      --muted: #64748b;
      --border: #cbd5e1;
      --accent: #0284c7;
      --accent-strong: #075985;
      --danger: #dc2626;
      --shadow: 0 24px 80px rgba(15, 23, 42, 0.08);
      background: radial-gradient(circle at top left, rgba(56, 189, 248, 0.12), transparent 26%),
        radial-gradient(circle at 80% 15%, rgba(59, 130, 246, 0.1), transparent 22%),
        linear-gradient(180deg, #f8fafc 0%, #edf2f7 100%);
    }
    main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px;
      position: relative;
      z-index: 1;
    }
    h1 {
      margin: 0 0 24px;
      font-size: 34px;
      letter-spacing: -0.03em;
      color: var(--text);
      animation: float 8s ease-in-out infinite;
    }
    h2 {
      margin: 0 0 14px;
      font-size: 18px;
      letter-spacing: -0.02em;
      color: var(--text);
    }
    .layout {
      display: grid;
      grid-template-columns: minmax(320px, 420px) 1fr;
      gap: 22px;
      align-items: start;
    }
    .input-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 18px;
      margin-bottom: 18px;
    }
    .input-card {
      background: var(--surface-strong);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 20px;
    }
    .input-card label {
      display: block;
      margin-bottom: 10px;
    }
    .input-card textarea {
      min-height: 250px;
    }
    .input-card input[type="file"] {
      margin-bottom: 18px;
    }
    section {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 24px;
      box-shadow: var(--shadow);
      transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
    }
    section:hover {
      transform: translateY(-3px);
      border-color: rgba(56, 189, 248, 0.35);
      box-shadow: 0 28px 90px rgba(0, 0, 0, 0.25);
    }
    label {
      display: block;
      font-weight: 700;
      margin-bottom: 10px;
      color: var(--text);
    }
    input[type="file"], textarea, button {
      width: 100%;
      font: inherit;
    }
    input[type="file"] {
      border: 1px dashed rgba(148, 163, 184, 0.45);
      border-radius: 16px;
      padding: 14px;
      background: rgba(255, 255, 255, 0.04);
      color: var(--text);
      transition: border-color 0.2s ease, background 0.2s ease;
    }
    input[type="file"]:focus-within {
      border-color: rgba(56, 189, 248, 0.65);
      background: rgba(255, 255, 255, 0.06);
    }
    textarea {
      min-height: 300px;
      resize: vertical;
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
      line-height: 1.6;
      margin-top: 16px;
      background: var(--surface-soft);
      color: var(--text);
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    textarea:focus {
      border-color: rgba(56, 189, 248, 0.6);
      box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.12);
      outline: none;
    }
    textarea::placeholder {
      color: rgba(226, 232, 240, 0.55);
    }
    button {
      margin-top: 16px;
      border: 0;
      border-radius: 14px;
      padding: 14px 16px;
      color: #0f172a;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      cursor: pointer;
      font-weight: 800;
      transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
      box-shadow: 0 12px 30px rgba(56, 189, 248, 0.18);
    }
    button:hover {
      transform: translateY(-1px) scale(1.01);
      filter: brightness(1.05);
      background: linear-gradient(135deg, #22d3ee, #0ea5e9);
    }
    button:disabled {
      opacity: .62;
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
    }
    .tabs {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .tab {
      border: 1px solid transparent;
      background: rgba(255, 255, 255, 0.04);
      color: var(--muted);
      margin: 0;
      padding: 11px 12px;
      font-size: 13px;
      min-height: 42px;
      border-radius: 14px;
      transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
    }
    .tab:hover {
      transform: translateY(-1px);
      background: rgba(56, 189, 248, 0.07);
    }
    .tab.active {
      background: rgba(56, 189, 248, 0.16);
      border-color: rgba(56, 189, 248, 0.35);
      color: var(--text);
    }
    .result-box {
      min-height: 340px;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.03);
      padding: 20px;
      white-space: pre-wrap;
      line-height: 1.65;
      color: var(--text);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      transition: transform 0.25s ease, box-shadow 0.25s ease, background 0.5s ease;
    }
    .result-box:hover {
      transform: translateY(-2px);
      box-shadow: 0 22px 60px rgba(0, 0, 0, 0.18);
    }
    .result-box.active {
      animation: shimmer 2.8s ease-in-out infinite;
      background: linear-gradient(145deg, rgba(255,255,255,0.04), rgba(56,189,248,0.08), rgba(255,255,255,0.02));
      border-color: rgba(56, 189, 248, 0.45);
    }
    .downloads {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
    }
    .downloads a {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 92px;
      min-height: 44px;
      border-radius: 16px;
      text-decoration: none;
      color: var(--text);
      background: rgba(56, 189, 248, 0.18);
      border: 1px solid rgba(56, 189, 248, 0.28);
      font-weight: 700;
      transition: background 0.2s ease, transform 0.2s ease;
    }
    .downloads a:hover {
      background: rgba(56, 189, 248, 0.28);
      transform: translateY(-1px);
    }
    .note {
      margin-top: 14px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .warning {
      color: var(--danger);
      font-weight: 700;
    }
    @keyframes drift {
      0% { transform: translate(0, 0) scale(1); opacity: 0.72; }
      20% { transform: translate(16px, 12px) scale(1.02); opacity: 0.84; }
      40% { transform: translate(28px, 24px) scale(1.05); opacity: 1; }
      60% { transform: translate(18px, 18px) scale(1.04); opacity: 0.88; }
      80% { transform: translate(8px, 10px) scale(1.02); opacity: 0.8; }
      100% { transform: translate(0, 0) scale(1); opacity: 0.72; }
    }
    @keyframes drift-reverse {
      0% { transform: translate(0, 0) scale(1); opacity: 0.72; }
      20% { transform: translate(-16px, 14px) scale(1.02); opacity: 0.86; }
      40% { transform: translate(-30px, 28px) scale(1.05); opacity: 1; }
      60% { transform: translate(-20px, 20px) scale(1.04); opacity: 0.9; }
      80% { transform: translate(-10px, 12px) scale(1.02); opacity: 0.82; }
      100% { transform: translate(0, 0) scale(1); opacity: 0.72; }
    }
    @keyframes banner-pulse {
      0%, 100% { transform: translateY(0); opacity: 1; }
      25% { transform: translateY(-2px); opacity: 0.96; }
      50% { transform: translateY(-5px); opacity: 0.9; }
      75% { transform: translateY(-2px); opacity: 0.96; }
    }
    @keyframes status-blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.45; }
    }
    @keyframes shimmer {
      0%, 100% { background-position: -280px 0; }
      50% { background-position: 280px 0; }
    }
    @keyframes float {
      0%, 100% { transform: translateY(0); }
      25% { transform: translateY(-4px); }
      50% { transform: translateY(-12px); }
      75% { transform: translateY(-4px); }
    }
    @media (max-width: 860px) {
      main { padding: 20px; }
      .layout { grid-template-columns: 1fr; }
      .tabs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    button:hover {
      transform: translateY(-1px);
      background: linear-gradient(135deg, #22d3ee, #0ea5e9);
    }
    button:disabled {
      opacity: .62;
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
    }
    .tabs {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .tab {
      border: 1px solid transparent;
      background: rgba(255, 255, 255, 0.04);
      color: var(--muted);
      margin: 0;
      padding: 11px 12px;
      font-size: 13px;
      min-height: 42px;
      border-radius: 14px;
      transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease;
    }
    .tab.active {
      background: rgba(56, 189, 248, 0.16);
      border-color: rgba(56, 189, 248, 0.35);
      color: #ffffff;
    }
    .result-box {
      min-height: 340px;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.03);
      padding: 20px;
      white-space: pre-wrap;
      line-height: 1.65;
      color: var(--text);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }
    .downloads {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
    }
    .downloads a {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 92px;
      min-height: 44px;
      border-radius: 16px;
      text-decoration: none;
      color: var(--text);
      background: rgba(56, 189, 248, 0.18);
      border: 1px solid rgba(56, 189, 248, 0.28);
      font-weight: 700;
      transition: background 0.2s ease;
    }
    .downloads a:hover {
      background: rgba(56, 189, 248, 0.28);
    }
    .note {
      margin-top: 14px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .warning {
      color: var(--danger);
      font-weight: 700;
    }
    @media (max-width: 860px) {
      main { padding: 20px; }
      .layout { grid-template-columns: 1fr; }
      .tabs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <div class="background-spot background-spot--top"></div>
  <div class="background-spot background-spot--bottom"></div>
  <main>
    <div class="hero-banner">
      <span id="themeBannerText">Dark theme active</span>
      <button id="themeToggleButton" class="theme-toggle" type="button">Switch to Bright</button>
    </div>
    <h1>Meeting-to-Action Agent</h1>
    <div class="layout">
      <section>
        <h2>Upload Transcript</h2>
        <div class="input-grid">
          <div class="input-card">
            <label for="textFileInput">Transcript file</label>
            <input id="textFileInput" type="file" accept=".txt,.json,.md,.transcript" />
            <textarea id="transcript" placeholder='Paste transcript text or QMSum JSON like: {"meeting_transcripts":[{"speaker":"Grad C","content":"Nice."}]}'></textarea>
            <div class="note">Upload a plain text or QMSum-style transcript, or paste text directly.</div>
          </div>
          <div class="input-card">
            <label for="audioInput">Audio file</label>
            <input id="audioInput" type="file" accept=".wav,.mp3,.m4a,.ogg,.flac,audio/*" />
            <div class="note">Upload audio and the transcript will be generated automatically.</div>
          </div>
        </div>
        <button id="analyzeButton">Analyze Meeting</button>
      </section>

      <section>
        <h2>Meeting Summary</h2>
        <div class="tabs">
          <button class="tab active" data-view="summary">Summary</button>
          <button class="tab" data-view="decisions">Decisions</button>
          <button class="tab" data-view="actions">Actions</button>
          <button class="tab" data-view="questions">Questions</button>
          <button class="tab" data-view="email">Email</button>
        </div>
        <div id="result" class="result-box">Upload or paste a transcript, then analyze the meeting.</div>
        <div class="downloads">
          <a id="csvLink" href="/download/csv" aria-disabled="true">CSV</a>
          <a id="jsonLink" href="/download/json" aria-disabled="true">JSON</a>
        </div>
        <div id="status" class="note"></div>
      </section>
    </div>
  </main>
  <script>
    const textFileInput = document.getElementById("textFileInput");
    const audioInput = document.getElementById("audioInput");
    const transcript = document.getElementById("transcript");
    const analyzeButton = document.getElementById("analyzeButton");
    const result = document.getElementById("result");
    const status = document.getElementById("status");
    const themeBannerText = document.getElementById("themeBannerText");
    const themeToggleButton = document.getElementById("themeToggleButton");
    const tabs = Array.from(document.querySelectorAll(".tab"));
    let latest = null;
    let activeView = "summary";
    let isBright = false;

    function updateTheme() {
      document.body.classList.toggle("theme-bright", isBright);
      if (isBright) {
        themeBannerText.textContent = "Bright theme active";
        themeToggleButton.textContent = "Switch to Dark";
      } else {
        themeBannerText.textContent = "Dark theme active";
        themeToggleButton.textContent = "Switch to Bright";
      }
    }

    themeToggleButton.addEventListener("click", () => {
      isBright = !isBright;
      updateTheme();
    });

    updateTheme();

    textFileInput.addEventListener("change", async () => {
      const file = textFileInput.files[0];
      if (!file) return;
      transcript.value = await file.text();
      status.textContent = "";
    });

    audioInput.addEventListener("change", async () => {
      const file = audioInput.files[0];
      if (!file) return;
      status.textContent = "Transcribing audio...";
      try {
        const formData = new FormData();
        formData.append("file", file);
        const response = await fetch("/api/transcribe", {
          method: "POST",
          body: formData,
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = await response.json();
        transcript.value = payload.transcript;
        status.textContent = payload.transcript ? "Audio transcript ready." : "No text was detected in the audio.";
      } catch (error) {
        transcript.value = "";
        status.textContent = "Audio transcription failed: " + error.message;
      }
    });

    tabs.forEach(tab => {
      tab.addEventListener("click", () => {
        tabs.forEach(item => item.classList.remove("active"));
        tab.classList.add("active");
        activeView = tab.dataset.view;
        render();
      });
    });

    analyzeButton.addEventListener("click", async () => {
      analyzeButton.disabled = true;
      status.textContent = "Analyzing...";
      status.classList.add("animating");
      result.textContent = "";
      result.classList.add("active");
      try {
        const response = await fetch("/api/analyze", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({transcript: transcript.value})
        });
        if (!response.ok) throw new Error(await response.text());
        latest = await response.json();
        const engineLabel = latest.engine === "gemini_vertex_ai"
          ? "Gemini via Vertex AI"
          : latest.engine === "gemini_api_key"
            ? "Gemini API key"
            : "local fallback";
        const engineNote = latest.fallback_reason ? ` Used ${engineLabel}: ${latest.fallback_reason}` : ` Used ${engineLabel}.`;
        status.innerHTML = latest.summary.decisions.length || latest.summary.action_items.length || latest.summary.open_questions.length
          ? "Analysis complete." + engineNote
          : "<span class='warning'>No clear decisions, action items, or unresolved questions were found in this excerpt.</span>" + engineNote;
        render();
      } catch (error) {
        result.textContent = "Analysis failed: " + error.message;
        status.textContent = "";
      } finally {
        analyzeButton.disabled = false;
        status.classList.remove("animating");
        result.classList.remove("active");
      }
    });

    function render() {
      if (!latest) return;
      const summary = latest.summary;
      if (activeView === "summary") {
        result.textContent = latest.summary_text;
      } else if (activeView === "decisions") {
        result.textContent = summary.decisions.length ? summary.decisions.map(item => "✓ " + item).join("\\n") : "No decisions found.";
      } else if (activeView === "actions") {
        result.textContent = summary.action_items.length
          ? summary.action_items.map((item, index) => `${index + 1}. ${item.owner} — ${item.task} — Due ${item.deadline}.`).join("\\n")
          : "No action items found.";
      } else if (activeView === "questions") {
        result.textContent = summary.open_questions.length ? summary.open_questions.map(item => "• " + item).join("\\n") : "No open questions found.";
      } else if (activeView === "email") {
        result.textContent = summary.follow_up_email || "[Generated]";
      }
    }
  </script>
</body>
</html>
"""


def main() -> None:
    import uvicorn

    uvicorn.run("app.ui_app:app", host="127.0.0.1", port=8008, reload=False)


if __name__ == "__main__":
    main()

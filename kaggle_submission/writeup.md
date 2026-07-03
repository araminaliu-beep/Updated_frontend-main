# AI Meeting-to-Action Agent: From Transcripts to Verified Decisions, Tasks, Risks, and Project Dashboards

**Subtitle:** A local AI agent system that turns messy meeting transcripts and audio into verified execution artifacts for project teams.

**Recommended Track:** AI Agents / Agentic Workflow  

**Public Project Link:** https://github.com/Thomas-Wu-01/Updated_frontend

**Video Link:** TODO: Add YouTube URL after recording  

**Cover Image:** TODO: Upload a dashboard screenshot to the Kaggle Media Gallery

## Project Overview

Meetings often contain the raw material of project execution: decisions, action items, deadlines, blockers, and follow-up commitments. The problem is that these details are usually buried inside noisy conversation. People hedge, interrupt each other, revisit old topics, and leave ownership ambiguous. Our project, the **AI Meeting-to-Action Agent**, addresses this gap by transforming meeting transcripts and audio files into structured project artifacts.

The system accepts pasted transcripts, uploaded transcript files, or uploaded audio. It produces a verified meeting summary, final decisions, owner-assigned action items, explicit deadlines, unresolved questions, risks, a follow-up email draft, and downloadable tracker files. A React/Next.js dashboard presents the results in a project-management layout inspired by tools such as Jira, Otter.ai, and Fireflies.ai.

## Motivation

The goal was not just to summarize meetings. A normal summary may be readable, but it is often not actionable. We wanted an agent that could answer project-execution questions:

- What did the team actually decide?
- Who is responsible for the next step?
- What deadlines were explicitly stated?
- What risks or blockers were mentioned?
- What should be exported into a tracker?

This required stricter rules than a generic summarizer. For example, a suggestion such as “I think Postgres is safer” should not become a decision. A phrase like “we should update the launch note” should not become an action unless an owner is explicit. The project therefore focuses on verified extraction rather than optimistic inference.

## System Architecture

The final architecture follows a meeting-intelligence pipeline:

```text
Transcript
  -> Clean transcript + topic segmentation
  -> Parallel extraction agents
       Decisions | Actions | Deadlines | Risks
  -> Verification agent
  -> Deduplication and merge
  -> Structured JSON output
  -> CSV / tracker export
  -> Interactive meeting dashboard
```

The backend is implemented in Python with FastAPI. The core analysis code lives in `app/analyzer.py`, typed output contracts live in `app/schemas.py`, and CSV/report generation lives in `app/reporting.py`. The dashboard is a Next.js frontend in `frontend/`, connected to the FastAPI backend through `/api/analyze` and `/api/transcribe`.

The project supports Gemini through Google Vertex AI or Gemini API key mode when credentials are configured. If credentials are unavailable, it falls back to deterministic local rules so the application remains usable in demos and development.

## Agent and Verification Logic

The most important design choice was adding strict verification rules. We defined:

**Decision:** A decision is only final if participants explicitly approve, agree, confirm, decide, resolve, or otherwise clearly finalize it. Suggestions, preferences, and open questions are excluded.

**Action item:** An action requires a responsible person or team and a concrete task. Missing owners are not inferred.

**Deadline:** A deadline is copied only when explicitly stated, such as “Friday,” “July 10,” or “next sprint.” Dates are not inferred or converted.

**Risk:** Risks include blockers, pending items, bugs, unresolved dependencies, and schedule uncertainty.

These rules are encoded both in the Gemini prompt and in the local fallback analyzer. The fallback path is useful because it gives predictable behavior for testing and allows the project to run without paid model access.

## Dashboard Experience

The frontend presents meeting intelligence as an execution dashboard rather than a plain text report. The layout includes:

- A top navigation bar for Projects, Tasks, Meetings, Decisions, and AI Copilot.
- A project panel listing active projects.
- A Jira-like execution board with TODO, IN PROGRESS, and DONE columns.
- Task cards showing owner, deadline, and source meeting link.
- A right-side AI Copilot panel for asking about summaries, risks, decisions, and extracted actions.
- Download links for CSV and JSON artifacts.

This design makes the output feel closer to a workflow tool than a chatbot response. The user can paste or upload a meeting, analyze it, and immediately see project-ready action cards.

## Audio Transcription

The app also supports audio upload through `faster-whisper`. During development, we discovered that audio transcription could be slow and that raw audio transcripts often lack speaker labels. This caused early versions of the analyzer to output very little because the strict action rules depended on speaker-labeled lines.

We improved this in two ways. First, we optimized transcription by using a smaller default Whisper model, caching the model after first load, using beam size 1, and enabling voice activity detection. Second, we updated the analyzer to handle unlabeled audio-style text when owners are explicitly named, such as “Alex will review the demo slides by Friday.” This preserves the “do not infer owners” rule while making audio transcripts useful.

## Testing and Evaluation

The project includes unit tests for transcript normalization, loaders, reporting, and analyzer behavior. The tests verify that:

- QMSum-style JSON snippets normalize correctly.
- Suggestions are not classified as decisions.
- Ownerless tasks are not extracted as action items.
- Noisy product-planning transcripts produce verified decisions, actions, risks, and open questions.
- Audio-style unlabeled text still extracts explicitly named owners.
- CSV export and report rendering match the expected contract.

At the time of the final version, the unit test suite passes with 11 tests.

## Example Output

For a noisy product-planning transcript, the system extracts decisions such as:

- Use one step for onboarding.
- Use Postgres for the event store.

It extracts owner-assigned actions such as:

- Alex: Confirm launch date with Jenna, due Friday.
- Dev: Get a quote on the managed Postgres instance, due Monday.
- Priya: Send updated onboarding survey copy, due today.

It also separates unresolved questions and risks, such as the training webinar decision and the analytics dashboard bug that may affect the demo.

## What We Learned

The main lesson is that meeting automation needs verification, not just summarization. LLMs are good at producing plausible project summaries, but project management requires conservative extraction. Incorrectly inventing an owner or turning a suggestion into a decision can create real confusion for a team.

We also learned that audio support changes the extraction problem. Audio transcripts may be noisy, lack speakers, or include unrelated conversation. A useful system needs graceful fallback behavior and clear rules about what can be trusted.

## Future Work

Future improvements include:

- Real Jira, Linear, or Notion export integrations.
- Better speaker diarization and speaker correction in the UI.
- More robust topic segmentation for long meetings.
- A richer AI Copilot that can answer follow-up questions using the structured JSON.
- Evaluation against larger real meeting datasets.
- Hosted deployment so judges and users can try the dashboard without local setup.

## Conclusion

The AI Meeting-to-Action Agent turns messy meetings into structured execution artifacts. It combines transcript cleaning, agent-style extraction, verification, deduplication, CSV/JSON export, and an interactive dashboard. The result is a practical prototype for teams that need meetings to become decisions, tasks, deadlines, and risks without losing the uncertainty and nuance of the original conversation.


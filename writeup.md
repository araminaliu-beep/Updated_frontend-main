# AI Meeting-to-Action Agent: From Meetings to Verified Execution

**Subtitle:** A publicly deployed AI meeting intelligence app that turns transcripts and large audio recordings into verified summaries, decisions, tasks, risks, and project dashboards.

**Recommended Track:** AI Agents / Agentic Workflow

**Public App:** https://meeting-action-agent-154103579883.us-central1.run.app/

**Public Project Link:** https://github.com/araminaliu-beep/Meeting_AI_Agent

**Video Link:** https://youtu.be/PBAfDgKamhE

## Project Overview

Meetings often contain the raw material of project execution: decisions, action items, deadlines, blockers, unresolved questions, and follow-up commitments. The hard part is that these details are buried inside noisy conversation. People hedge, interrupt each other, revisit old topics, and leave ownership ambiguous.

The **AI Meeting-to-Action Agent** turns pasted transcripts, transcript files, and audio recordings into structured project artifacts. It generates:

- A meeting summary
- Final decisions
- Owner-assigned action items
- Explicit deadlines
- Open questions
- Risks and blockers
- Follow-up email text
- Downloadable CSV and JSON artifacts
- A project dashboard for reviewing the extracted work

The current version is publicly hosted on Google Cloud Run. Users can open the deployed Next.js app, upload a meeting transcript or audio file, run analysis, and review the output without running anything locally.

## Motivation

The goal was not just to summarize meetings. A generic summary can be readable but still fail to answer project execution questions:

- What did the team actually decide?
- Who owns the next step?
- What deadlines were explicitly stated?
- What risks or blockers were mentioned?
- What should be exported into a tracker?

This required stricter rules than a normal summarizer. For example, “I think Postgres is safer” should not become a decision. “We should update the launch note” should not become an action unless an owner is explicit. The project therefore focuses on verified extraction rather than optimistic inference.

## Current System Architecture

The deployed system is split into two public Cloud Run services:

- **Frontend:** `meeting-action-agent`
  - Next.js dashboard in `frontend/`
  - Public URL: https://meeting-action-agent-154103579883.us-central1.run.app
  - Uses `frontend/Dockerfile`

- **Backend API:** `meeting-action-agent-api`
  - FastAPI app in `app/ui_app.py`
  - Public API base URL: https://meeting-action-agent-api-154103579883.us-central1.run.app
  - Uses the root `Dockerfile`

The frontend calls the backend through:

- `POST /api/transcribe` for audio transcription
- `POST /api/analyze` for meeting analysis
- `GET /download/csv` and `GET /download/json` for exported artifacts

The core backend modules are:

- `app/analyzer.py` for Gemini/Vertex AI analysis, chunked long-transcript handling, verification, and deterministic fallback
- `app/ui_app.py` for FastAPI routes, CORS, audio transcription, and downloadable artifacts
- `app/schemas.py` for typed output contracts
- `app/reporting.py` for summary rendering and CSV export
- `frontend/app/page.jsx` and `frontend/app/globals.css` for the dashboard UI

## Meeting Intelligence Pipeline

The extraction flow is designed as a conservative meeting-intelligence pipeline:

```text
Transcript or audio
  -> Audio transcription when needed
  -> Transcript normalization
  -> Gemini / Vertex AI structured extraction
  -> Chunked Gemini analysis for long transcripts
  -> Verification rules
  -> Deduplication and merge
  -> Structured JSON output
  -> CSV / JSON export
  -> Interactive dashboard
```

If Gemini/Vertex AI is unavailable or a model call fails, the backend falls back to deterministic local rules. The UI now displays the fallback reason when that happens, so users can tell whether the app used Vertex AI or local analysis.

## Gemini and Vertex AI Behavior

The project is configured to use Gemini through Vertex AI:

```bash
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=my-test-project-499617
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_MODEL=gemini-2.5-flash
```

For normal transcripts, the backend calls Gemini once and validates the JSON response against `MeetingActionOutput`. For long transcripts, the analyzer now retries with chunked Gemini analysis before falling back. This matters for long audio meetings because the transcript can become too large for a single model call or can produce output that fails schema validation.

The analyzer returns metadata with each response:

- `engine: "gemini_vertex_ai"` when Vertex AI succeeds
- `engine: "gemini_api_key"` when API-key mode is used
- `engine: "local_fallback"` when deterministic rules are used
- `fallback_reason` when a Gemini call failed

## Verification Rules

The most important design choice is strict verification. The app uses the same conservative extraction philosophy in the Gemini prompt and in the local fallback analyzer.

**Decision:** A decision is final only when participants explicitly approve, agree, confirm, decide, resolve, or otherwise clearly finalize it. Suggestions, preferences, and open questions are excluded.

**Action item:** An action requires both a responsible person or team and a concrete task. Missing owners are not inferred.

**Deadline:** A deadline is copied only when explicitly stated, such as “Friday,” “July 10,” or “next sprint.” Dates are not inferred or converted.

**Risk:** Risks include blockers, pending items, bugs, unresolved dependencies, schedule uncertainty, and unresolved business decisions.

This makes the system intentionally conservative. It may extract less than a generic summarizer, but it avoids creating false project commitments.

## Audio Support

The app supports audio upload through `faster-whisper` on the backend. The backend caches the Whisper model after first load, uses beam size 1 by default, enables voice activity detection, and removes uploaded temporary files after transcription.

The current frontend also supports large audio files. Cloud Run has practical request-size limits, so uploading an 80+ MB recording directly can fail before the request reaches FastAPI. To handle this, the frontend now:

1. Detects large audio files.
2. Decodes the audio in the browser.
3. Downmixes to mono.
4. Resamples to 16 kHz.
5. Encodes chunks as WAV.
6. Sends each chunk to `/api/transcribe`.
7. Merges the returned text into one transcript.

This lets users upload large recordings such as `Bed016.interaction.wav` without manually splitting or compressing the file.

## Dashboard Experience

The frontend has evolved from a static dashboard into tab-specific views. The top navigation now changes the actual page layout:

- **Projects:** Default front page with project list, meeting intake, summary, metrics, kanban board, and copilot.
- **Tasks:** Action-item table plus kanban board.
- **Meetings:** Focused transcript/audio upload workspace and generated summary.
- **Decisions:** Separate panels for confirmed decisions, risks, and open questions.
- **AI Copilot:** Wider assistant workspace with meeting context beside it.

The front page now displays the meeting summary prominently near the top, before the task board, so users see the main result immediately after analysis.

## Example Output

For a noisy product-planning transcript, the system can extract decisions such as:

- Use one step for onboarding.
- Use Postgres for the event store.

It extracts owner-assigned actions such as:

- Alex: Confirm launch date with Jenna, due Friday.
- Dev: Get a quote on the managed Postgres instance, due Monday.
- Priya: Send updated onboarding survey copy, due today.

It also separates unresolved questions and risks, such as whether a training webinar is needed or whether an analytics dashboard bug may affect a demo.

## Testing and Evaluation

The project includes unit and integration tests for transcript normalization, loaders, reporting, analyzer behavior, and server/API behavior. The current Python suite passes:

```text
16 passed
```

The frontend production build also passes:

```text
npm run build
```

The project also includes an `agents-cli` eval smoke dataset under `tests/eval/`. A recent smoke eval completed successfully with a mean score of `5.0` on the included two-case dataset. That eval is small, so it is best interpreted as a deployment sanity check rather than a full product-quality benchmark.

## Deployment

The app is currently deployed publicly on Cloud Run:

- Frontend service: `meeting-action-agent`
- API service: `meeting-action-agent-api`
- Region: `us-central1`
- Frontend public URL: https://meeting-action-agent-154103579883.us-central1.run.app
- API public URL: https://meeting-action-agent-api-154103579883.us-central1.run.app

The deployment uses public unauthenticated Cloud Run access so users can try the dashboard in a browser. The frontend points to the deployed API through `NEXT_PUBLIC_API_BASE_URL`.

## What We Learned

The main lesson is that meeting automation needs verification, not just summarization. LLMs are good at producing plausible project narratives, but project management requires conservative extraction. Incorrectly inventing an owner or turning a suggestion into a decision can create real confusion for a team.

We also learned that audio support changes the product architecture. Long recordings can exceed request limits, audio transcripts may lack speaker labels, and model calls can fail on long transcripts. Handling these realities required browser-side audio chunking, backend model caching, long-transcript chunked Gemini analysis, and clear fallback messaging.

Finally, the UI matters. A plain text response is useful, but a dashboard with task boards, decision panels, downloads, and copilot views makes the output feel closer to a real workflow tool.

## Future Work

Future improvements include:

- Real Jira, Linear, or Notion export integrations.
- Better speaker diarization and speaker correction in the UI.
- Persistent project and meeting history instead of session-only artifacts.
- More robust topic segmentation for long meetings.
- A richer AI Copilot that answers questions over the structured JSON and transcript.
- Larger eval datasets with real meeting transcripts.
- Authenticated team workspaces for production use.

## Conclusion

The AI Meeting-to-Action Agent turns messy meetings into structured execution artifacts. It combines audio transcription, transcript normalization, Gemini/Vertex AI extraction, long-transcript chunking, conservative verification, deterministic fallback, CSV/JSON export, and an interactive Next.js dashboard. The result is a practical deployed prototype for teams that need meetings to become decisions, tasks, deadlines, risks, and follow-up material without losing the uncertainty and nuance of the original conversation.

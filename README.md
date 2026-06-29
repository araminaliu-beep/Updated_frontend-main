# meeting-action-agent

AI Meeting-to-Action Agent
Agent generated with `agents-cli` version `0.5.0`

This local prototype turns meeting transcripts into:

- decisions made
- action items
- owners
- deadlines
- unresolved questions
- follow-up email text
- project tracker CSV rows

The agent uses a verified meeting-intelligence pipeline:

```text
                    Transcript
                        │
         ┌──────────────┴───────────────┐
         │                              │
    Clean transcript              Topic segmentation
         │                              │
         └──────────────┬───────────────┘
                        │
               Parallel AI Agents
        ┌────────┬────────┬────────┬────────┐
        │        │        │        │        │
   Decisions  Actions  Deadlines  Risks
        │        │        │        │
        └────────┴────────┴────────┘
                  │
          Verification Agent
                  │
          Deduplication & Merge
                  │
          Structured JSON Output
                  │
      Jira / Linear / Notion Export
                  │
        Interactive Meeting Dashboard
```

## Project Structure

```
meeting-action-agent/
├── app/         # Core agent code
│   ├── agent.py               # Manager and specialist ADK agents
│   ├── loaders.py             # Plain text, QMSum-style, and AMI-style loaders
│   ├── reporting.py           # Summary rendering and tracker CSV export
│   ├── sample_runner.py       # Deterministic sample artifact generator
│   ├── schemas.py             # Typed output contracts
│   └── app_utils/             # App utilities and helpers
├── frontend/    # Next.js dashboard frontend
├── samples/                   # Local sample transcript
├── tests/                     # Unit, integration, and load tests
├── AGENTS.md                  # AI-assisted development guide
└── pyproject.toml             # Project dependencies
```

> 💡 **Tip:** Use [Gemini CLI](https://github.com/google-gemini/gemini-cli) for AI-assisted development - project context is pre-configured in `GEMINI.md`.

## Requirements

Before you begin, ensure you have:
- **uv**: Python package manager (used for all dependency management in this project) - [Install](https://docs.astral.sh/uv/getting-started/installation/) ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with `uv add <package>`)
- **agents-cli**: Agents CLI - Install with `uv tool install google-agents-cli`
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)


## Quick Start

Install `agents-cli` and its skills if not already installed:

```bash
uvx google-agents-cli setup
```

Install required packages:

```bash
agents-cli install
```

Configure Google Gemini credentials.

Recommended for using Google Cloud credits: use Vertex AI with your Google Cloud project:

```bash
cp .env.example .env
# edit .env and set GOOGLE_CLOUD_PROJECT
gcloud auth application-default login
gcloud services enable aiplatform.googleapis.com
```

Your `.env` should look like:

```bash
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-google-cloud-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_MODEL=gemini-2.5-flash
```

Alternative Gemini API-key mode:

```bash
GOOGLE_GENAI_USE_VERTEXAI=false
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_MODEL=gemini-2.5-flash
```

If you want to use the $300 Google Cloud trial credits, Vertex AI is the better fit. A Gemini API key may be billed through a different setup depending on how your Google account/project is configured.

Test the agent with a local web server:

```bash
agents-cli playground
```

You can also use features from the [ADK](https://adk.dev/) CLI with `uv run adk`.

Run the upload/paste UI:

```bash
uv run python -m app.ui_app
```

Then open:

```text
http://127.0.0.1:8008
```

Run the React/Next.js dashboard frontend:

```bash
# Terminal 1: start the analyzer API
uv run python -m app.ui_app

# Terminal 2: start the Next.js app
cd frontend
npm install
npm run dev
```

Then open:

```text
http://localhost:3000
```

The dashboard calls the analyzer API at `http://127.0.0.1:8008` by default.
Override it with `NEXT_PUBLIC_API_BASE_URL` if your backend runs elsewhere.

Use this UI for QMSum-style JSON snippets such as:

```json
{
  "meeting_transcripts": [
    {"speaker": "Grad C", "content": "Nice ."}
  ]
}
```

If your snippet starts directly with `"meeting_transcripts": [...]`, the UI backend will still normalize it.

Generate deterministic sample report artifacts without calling an LLM:

```bash
uv run meeting-action-sample --output-dir outputs
```

Run tests:

```bash
uv run pytest tests/unit
```

## Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `agents-cli install` | Install dependencies using uv                                                         |
| `agents-cli playground` | Launch local development environment                                                  |
| `agents-cli lint`    | Run code quality checks                                                               |
| `agents-cli eval`    | Evaluate agent behavior (generate, grade, analyze, and more — see `agents-cli eval --help`) |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests                                                        |

## 🛠️ Project Management

| Command | What It Does |
|---------|--------------|
| `agents-cli scaffold enhance` | Add CI/CD pipelines and Terraform infrastructure |
| `agents-cli infra cicd` | One-command setup of entire CI/CD pipeline + infrastructure |
| `agents-cli scaffold upgrade` | Auto-upgrade to latest version while preserving customizations |

---

## Development

Edit your agent logic in `app/agent.py` and test with `agents-cli playground` - it auto-reloads on save.

## Data Loaders

The prototype intentionally does not download or ingest external datasets. It includes loader hooks so local QMSum or AMI samples can be added later:

- `app.loaders.load_plain_text(path)`
- `app.loaders.load_qmsum_sample(path)`
- `app.loaders.load_ami_sample(path)`

The QMSum loader accepts common JSON transcript shapes. The AMI loader accepts lightweight XML transcript samples; full AMI ingestion can be expanded later with word timing and richer speaker metadata.

## Safety Rules

- Do not guess owners. Use `Unassigned` when the transcript does not explicitly assign one.
- Do not guess deadlines. Use `Unknown` when the transcript does not explicitly provide one.
- Do not classify suggestions as decisions. Decisions require explicit approval, agreement, confirmation, deciding, resolving, or similarly clear final confirmation.
- Extract action items only when there is an explicit responsible person or team and a concrete task.
- Keep decisions, action items, and unresolved questions separate.
- Generate follow-up email and tracker CSV artifacts only; do not send email or update external trackers.

## GitHub Handoff

After you approve, initialize/link the project to GitHub from this directory:

```bash
git init
git add .
git commit -m "Initial meeting action agent prototype"
gh repo create meeting-action-agent --private --source=. --remote=origin --push
```

Choose `--public` instead of `--private` if you want an open repository.

## Deployment

```bash
gcloud config set project <your-project-id>
agents-cli deploy
```

To add CI/CD and Terraform, run `agents-cli scaffold enhance`.
To set up your production infrastructure, run `agents-cli infra cicd`.

## Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging.

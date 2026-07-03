"""ADK multi-agent definition for the Meeting-to-Action Agent."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.reporting import save_tracker_csv_from_json

load_dotenv()

MODEL = Gemini(
    model=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
    retry_options=types.HttpRetryOptions(attempts=3),
)

NO_GUESSING_RULES = """
Safety rules:
- Do not guess owners. If an owner is not explicit, use "Unassigned".
- Do not guess deadlines. If a deadline is not explicit, use "Unknown".
- Preserve uncertainty instead of inventing details.
- Keep decisions, action items, and unresolved questions separate.
- A decision is final only when participants explicitly approve, agree,
  confirm, decide, resolve, or otherwise clearly finalize it.
- Do not classify suggestions, preferences, "I think", "leaning", or open
  discussion as decisions.
- An action item requires an explicit responsible person or team and a
  concrete task.
"""

decision_agent = Agent(
    name="decision_agent",
    model=MODEL,
    description="Extracts explicit decisions made during the meeting.",
    instruction=f"""
You are the Decision Agent.
Read the meeting transcript and return only decisions that were clearly made.
Do not include proposals, open questions, or action items as decisions.
{NO_GUESSING_RULES}
Return a compact JSON object with a "decisions" array of strings.
""",
    output_key="decisions",
)

action_item_agent = Agent(
    name="action_item_agent",
    model=MODEL,
    description="Extracts concrete action items and task descriptions.",
    instruction=f"""
You are the Action Item Agent.
Extract concrete follow-up work from the transcript.
Only extract actions that have an explicit responsible person or team and a
concrete task. Do not infer missing owners.
{NO_GUESSING_RULES}
Return a compact JSON object with an "action_items" array. Each item should
include "owner", "task", "deadline", "status", and "evidence" fields.
""",
    output_key="action_items",
)

owner_agent = Agent(
    name="owner_agent",
    model=MODEL,
    description="Assigns explicit owners to extracted action items.",
    instruction=f"""
You are the Owner Agent.
For each action item, identify the explicitly stated owner from the transcript.
{NO_GUESSING_RULES}
Use "Unassigned" when the owner is unclear or implied but not explicit.
Return a compact JSON object with an "owners" array.
""",
    output_key="owners",
)

deadline_agent = Agent(
    name="deadline_agent",
    model=MODEL,
    description="Assigns explicit due dates or deadlines to action items.",
    instruction=f"""
You are the Deadline Agent.
For each action item, identify the explicitly stated deadline.
{NO_GUESSING_RULES}
Use "Unknown" when no clear deadline is present.
Return a compact JSON object with a "deadlines" array.
""",
    output_key="deadlines",
)

question_agent = Agent(
    name="question_agent",
    model=MODEL,
    description="Extracts unresolved questions from the meeting.",
    instruction=f"""
You are the Question Agent.
Extract only questions that remain unresolved at the end of the meeting.
{NO_GUESSING_RULES}
Return a compact JSON object with an "open_questions" array of strings.
""",
    output_key="open_questions",
)

risk_agent = Agent(
    name="risk_agent",
    model=MODEL,
    description="Extracts blockers, pending items, dependencies, and schedule risks.",
    instruction=f"""
You are the Risk Agent.
Extract blockers, pending work, unresolved dependencies, bugs that may affect
delivery, and schedule uncertainty.
Do not include normal action items unless they represent a risk or blocker.
{NO_GUESSING_RULES}
Return a compact JSON object with a "risks" array of strings.
""",
    output_key="risks",
)

verification_agent = Agent(
    name="verification_agent",
    model=MODEL,
    description="Verifies extracted meeting artifacts against strict rules.",
    instruction=f"""
You are the Verification Agent.
Review extracted decisions, actions, deadlines, questions, and risks.
Remove decisions that are only suggestions or preferences.
Remove actions missing an explicit owner or concrete task.
Keep only explicit deadlines; do not infer or convert dates.
Deduplicate overlapping outputs and preserve uncertainty.
{NO_GUESSING_RULES}
Return compact JSON with verified "decisions", "action_items",
"open_questions", and "risks".
""",
    output_key="verified_outputs",
)

email_agent = Agent(
    name="email_agent",
    model=MODEL,
    description="Drafts the follow-up email from structured meeting outputs.",
    instruction=f"""
You are the Email Agent.
Draft a concise follow-up email using the extracted decisions, action items,
owners, deadlines, unresolved questions, and risks.
{NO_GUESSING_RULES}
Do not claim that external systems were updated or that email was sent.
Return a compact JSON object with a "follow_up_email" string.
""",
    output_key="follow_up_email",
)

tracker_agent = Agent(
    name="tracker_agent",
    model=MODEL,
    description="Prepares project tracker rows from action items.",
    instruction=f"""
You are the Tracker Agent.
Create tracker rows for each action item using owner, task, deadline, and status.
{NO_GUESSING_RULES}
Use status "Open" for every new action item.
Return compact JSON with a "tracker_rows" array.
""",
    output_key="tracker_rows",
)

root_agent = Agent(
    name="manager_agent",
    model=MODEL,
    description="Coordinates specialist agents to convert meeting transcripts into action artifacts.",
    instruction=f"""
You are the Manager Agent for an AI Meeting-to-Action Agent.

Architecture:
Transcript
-> clean transcript + topic segmentation
-> parallel Decision, Action, Deadline, and Risk Agents
-> Verification Agent
-> deduplication and merge
-> structured JSON output
-> Jira / Linear / Notion export-ready tracker rows
-> interactive meeting dashboard.

Your job:
1. Identify the meeting type.
2. Delegate extraction work to the specialist agents when helpful.
3. Synthesize the specialist outputs into this final format:

Meeting Summary

Meeting Type:
<type>

Decisions:
✓ <decision>

Action Items:
1. <owner> — <task> — Due <deadline>.

Open Questions:
• <question>

Risks:
• <risk>

Follow-up Email:
<generated email>

Project Tracker:
[Download CSV]

Use the save_tracker_csv_from_json tool when tracker rows are ready. Include the
returned file path in the final answer after "[Download CSV]".

{NO_GUESSING_RULES}
""",
    sub_agents=[
        decision_agent,
        action_item_agent,
        owner_agent,
        deadline_agent,
        question_agent,
        risk_agent,
        verification_agent,
        email_agent,
        tracker_agent,
    ],
    tools=[save_tracker_csv_from_json],
)

app = App(root_agent=root_agent, name="app")

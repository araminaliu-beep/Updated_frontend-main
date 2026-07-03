"use client";

import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  FileJson,
  FileText,
  Link2,
  Loader2,
  Mic2,
  PanelsTopLeft,
  Send,
  Sparkles,
  Upload,
  UserRound,
} from "lucide-react";
import { useMemo, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8008";

const sampleTranscript = `Sarah: Okay, um, so we're, uh, looking at the onboarding flow again. I think we, like, definitely need to cut one step.
Alex: Yeah, I mean, the analytics show a huge drop off on the first screen, but, um, the thing is, we also have the video demo to finish.
Priya: Wait, did we decide if the onboarding needs to be one step or two? I'm still not sure.
Sarah: I said one, let's make it one. It's simpler. The launch is, like, late July, right?
Alex: It's not final. We should confirm the date with Jenna by Friday. I can send that note.
Dev: Speaking of the event store, are we doing Postgres, MongoDB, or the new KV thing? Uh, I think Postgres is safer.
Priya: I'm leaning Postgres too, because the analytics team can query it faster.
Sarah: Okay, Postgres it is. Dev, can you get a quote on the managed instance by Monday?
Dev: Yeah, I'll do that. Also, the vendor pricing review is, uh, still pending.
Morgan: Sorry, I missed the earlier part. Are we also shipping the customer demo slides this week?
Alex: Yes, slides should be ready by Thursday, and I'll review them on Friday morning.
Sarah: We also need to decide who owns the follow-up email. It can't just be vague.
Priya: I can draft the email if Alex approves the content. We should include the new rollout date and next steps.
Sarah: Great. If we can't lock down the exact launch date, use "tentative late July" and note that it may shift.
Alex: There's a bug in the analytics dashboard that might affect the demo, but not the onboarding itself.
Dev: Uh, the dev team can patch that before the demo, I think. I'll schedule a quick sync.
Priya: One more thing - the onboarding survey copy needs to be updated. I'll send the new copy today.
Morgan: And the decision on the training webinar is still open. Do we need one?
Sarah: Let's not decide today. Mark that as unresolved, and we'll revisit after the demo.
Alex: Good call.
Priya: Cool.
Sarah: Okay, action items: Alex review slides Thursday, Dev quote Postgres by Monday, Priya send copy today, and we confirm launch date with Jenna by Friday.
Alex: Right. Also, note that owners are explicit, and deadlines are mostly known except the webinar decision.
Priya: Unassigned on the webinar decision for now.`;

const projects = [
  {
    id: "product",
    name: "Project A",
    label: "Onboarding refresh",
    health: "At risk",
    meetings: 6,
    accent: "coral",
  },
  {
    id: "enterprise",
    name: "Project B",
    label: "Enterprise rollout",
    health: "On track",
    meetings: 4,
    accent: "green",
  },
  {
    id: "insights",
    name: "Project C",
    label: "Insights platform",
    health: "Review",
    meetings: 3,
    accent: "blue",
  },
];

const fallbackSummary = {
  meeting_type: "Product Planning",
  decisions: [
    "Use one step for onboarding.",
    "Use Postgres for the event store.",
  ],
  action_items: [
    {
      owner: "Alex",
      task: "Review customer demo slides",
      deadline: "Friday morning",
      status: "In Progress",
    },
    {
      owner: "Dev",
      task: "Get a quote on the managed Postgres instance",
      deadline: "Monday",
      status: "Open",
    },
    {
      owner: "Priya",
      task: "Send updated onboarding survey copy",
      deadline: "Today",
      status: "Done",
    },
  ],
  open_questions: ["Do we need a training webinar?"],
  risks: [
    "Launch date is not final.",
    "Analytics dashboard bug may affect the demo.",
  ],
  follow_up_email:
    "Subject: Product planning follow-up\n\nHi team,\n\nWe confirmed a one-step onboarding flow and Postgres for the event store. Alex will review slides, Dev will get the managed Postgres quote, and Priya will send survey copy.\n\nBest,\nMeeting-to-Action Agent",
};

const boardColumns = [
  { id: "todo", title: "TODO", tone: "neutral" },
  { id: "progress", title: "IN PROGRESS", tone: "blue" },
  { id: "done", title: "DONE", tone: "green" },
];

const navItems = ["Projects", "Tasks", "Meetings", "Decisions", "AI Copilot"];

const quickPrompts = [
  { label: "summarize", prompt: "Summarize the meeting into project updates." },
  { label: "extract", prompt: "Extract action items with owners and deadlines." },
  { label: "risks", prompt: "List risks and blockers from this meeting." },
  { label: "decisions", prompt: "Show the decisions made in this meeting." },
];

function statusToColumn(status = "Open") {
  const normalized = status.toLowerCase();
  if (normalized.includes("done") || normalized.includes("complete")) return "done";
  if (normalized.includes("progress") || normalized.includes("review")) {
    return "progress";
  }
  return "todo";
}

function getCopilotAnswer(prompt, summary) {
  const normalized = prompt.toLowerCase();
  if (!prompt.trim()) {
    return "Ask about actions, decisions, risks, or the meeting summary.";
  }

  if (normalized.includes("risk") || normalized.includes("blocker")) {
    const risks = summary.risks || [];
    return risks.length
      ? `Risks and blockers:\n${risks.map((item) => `- ${item}`).join("\n")}`
      : "No explicit unresolved risks or blockers were found.";
  }

  if (normalized.includes("decision")) {
    const decisions = summary.decisions || [];
    return decisions.length
      ? `Decisions:\n${decisions.map((item) => `- ${item}`).join("\n")}`
      : "No explicit decisions were found.";
  }

  if (normalized.includes("extract") || normalized.includes("action")) {
    const items = summary.action_items || [];
    return items.length
      ? `Action items:\n${items
          .map((item) => `- ${item.owner}: ${item.task} (Due ${item.deadline})`)
          .join("\n")}`
      : "No action items were found.";
  }

  return `Meeting type: ${summary.meeting_type || "Unknown"}\nDecisions: ${
    summary.decisions?.length || 0
  }\nAction items: ${summary.action_items?.length || 0}\nOpen questions: ${
    summary.open_questions?.length || 0
  }\nRisks: ${
    summary.risks?.length || 0
  }`;
}

export default function DashboardPage() {
  const [activeNav, setActiveNav] = useState("Projects");
  const [activeProject, setActiveProject] = useState(projects[0].id);
  const [transcript, setTranscript] = useState(sampleTranscript);
  const [summary, setSummary] = useState(fallbackSummary);
  const [summaryText, setSummaryText] = useState("");
  const [engine, setEngine] = useState("local preview");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Preview data loaded.");
  const [askText, setAskText] = useState("extract");
  const [copilotAnswer, setCopilotAnswer] = useState(
    getCopilotAnswer("extract", fallbackSummary),
  );
  const [downloadLinks, setDownloadLinks] = useState(null);

  const selectedProject = projects.find((item) => item.id === activeProject);

  const columns = useMemo(() => {
    const grouped = {
      todo: [],
      progress: [],
      done: [],
    };
    for (const item of summary.action_items || []) {
      const key = statusToColumn(item.status);
      grouped[key].push(item);
    }
    return grouped;
  }, [summary.action_items]);

  const totalTasks = summary.action_items?.length || 0;
  const completedTasks = columns.done.length;
  const openQuestions = summary.open_questions?.length || 0;
  const risks = summary.risks?.length || 0;

  async function handleAnalyze() {
    setIsAnalyzing(true);
    setStatusMessage("Analyzing transcript...");
    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript }),
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const payload = await response.json();
      setSummary(payload.summary);
      setSummaryText(payload.summary_text);
      setEngine(
        payload.engine === "gemini_vertex_ai"
          ? "Gemini via Vertex AI"
          : payload.engine === "gemini_api_key"
            ? "Gemini API key"
            : "Local fallback",
      );
      setDownloadLinks(payload.downloads);
      setCopilotAnswer(getCopilotAnswer(askText, payload.summary));
      const hasFindings =
        payload.summary.decisions?.length ||
        payload.summary.action_items?.length ||
        payload.summary.open_questions?.length ||
        payload.summary.risks?.length;
      const engineNote =
        payload.engine === "local_fallback"
          ? "Local rule-based analysis complete."
          : "Analysis complete.";
      setStatusMessage(
        hasFindings
          ? engineNote
          : `${engineNote} No verified decisions, owner-assigned actions, open questions, or risks were found.`,
      );
    } catch (error) {
      setStatusMessage(`Analysis failed: ${error.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handleTranscriptFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setTranscript(await file.text());
    setStatusMessage(`${file.name} loaded.`);
  }

  async function handleAudioFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setStatusMessage("Transcribing audio. First upload may take longer while the model loads...");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${API_BASE_URL}/api/transcribe`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const payload = await response.json();
      setTranscript(payload.transcript || "");
      setStatusMessage(payload.transcript ? "Audio transcript ready." : "No speech found.");
    } catch (error) {
      setStatusMessage(`Audio transcription failed: ${error.message}`);
    }
  }

  function handleAsk(prompt = askText) {
    setAskText(prompt);
    setCopilotAnswer(getCopilotAnswer(prompt, summary));
  }

  return (
    <main className="dashboard-shell">
      <nav className="top-nav" aria-label="Primary">
        <div className="brand">
          <span className="brand-mark">
            <PanelsTopLeft size={18} />
          </span>
          <span>Meeting Action Agent</span>
        </div>
        <div className="nav-links">
          {navItems.map((item) => (
            <button
              className={activeNav === item ? "nav-link active" : "nav-link"}
              key={item}
              onClick={() => setActiveNav(item)}
              type="button"
            >
              {item}
            </button>
          ))}
        </div>
      </nav>

      <section className="workspace" aria-label="Project execution dashboard">
        <aside className="project-panel">
          <div className="panel-heading">
            <span>Projects</span>
            <span className="count-pill">{projects.length}</span>
          </div>

          <div className="project-list">
            {projects.map((project) => (
              <button
                className={
                  activeProject === project.id
                    ? `project-row active ${project.accent}`
                    : `project-row ${project.accent}`
                }
                key={project.id}
                onClick={() => setActiveProject(project.id)}
                type="button"
              >
                <span className="project-dot" />
                <span className="project-copy">
                  <strong>{project.name}</strong>
                  <small>{project.label}</small>
                </span>
                <span className="project-health">{project.health}</span>
              </button>
            ))}
          </div>

          <div className="project-metrics" aria-label="Project metrics">
            <div>
              <span>{totalTasks}</span>
              <small>Tasks</small>
            </div>
            <div>
              <span>{completedTasks}</span>
              <small>Done</small>
            </div>
            <div>
              <span>{risks}</span>
              <small>Risks</small>
            </div>
          </div>

          <div className="meeting-intake">
            <div className="section-title">
              <Mic2 size={16} />
              <span>Meeting Intake</span>
            </div>
            <textarea
              aria-label="Meeting transcript"
              value={transcript}
              onChange={(event) => setTranscript(event.target.value)}
            />
            <div className="file-actions">
              <label className="file-button">
                <Upload size={15} />
                <span>Transcript</span>
                <input
                  accept=".txt,.json,.md,.transcript"
                  onChange={handleTranscriptFile}
                  type="file"
                />
              </label>
              <label className="file-button">
                <Mic2 size={15} />
                <span>Audio</span>
                <input
                  accept=".wav,.mp3,.m4a,.ogg,.flac,audio/*"
                  onChange={handleAudioFile}
                  type="file"
                />
              </label>
            </div>
            <button
              className="primary-action"
              disabled={isAnalyzing || !transcript.trim()}
              onClick={handleAnalyze}
              type="button"
            >
              {isAnalyzing ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
              <span>Analyze Meeting</span>
            </button>
            <p className="status-line">{statusMessage}</p>
          </div>
        </aside>

        <section className="execution-board">
          <header className="board-header">
            <div>
              <p className="eyebrow">Execution Board</p>
              <h1>{selectedProject?.label}</h1>
            </div>
            <div className="header-actions">
              <span className="engine-pill">{engine}</span>
              {downloadLinks?.csv ? (
                <a className="icon-link" href={`${API_BASE_URL}${downloadLinks.csv}`}>
                  <FileText size={16} />
                  CSV
                </a>
              ) : null}
              {downloadLinks?.json ? (
                <a className="icon-link" href={`${API_BASE_URL}${downloadLinks.json}`}>
                  <FileJson size={16} />
                  JSON
                </a>
              ) : null}
            </div>
          </header>

          <div className="insight-strip">
            <div className="insight-card">
              <span className="insight-icon coral">
                <ClipboardList size={18} />
              </span>
              <div>
                <strong>{summary.meeting_type || "Unknown"}</strong>
                <small>Meeting type</small>
              </div>
            </div>
            <div className="insight-card">
              <span className="insight-icon green">
                <CheckCircle2 size={18} />
              </span>
              <div>
                <strong>{summary.decisions?.length || 0}</strong>
                <small>Decisions</small>
              </div>
            </div>
            <div className="insight-card">
              <span className="insight-icon blue">
                <CalendarClock size={18} />
              </span>
              <div>
                <strong>{openQuestions}</strong>
                <small>Open questions</small>
              </div>
            </div>
            <div className="insight-card">
              <span className="insight-icon amber">
                <AlertTriangle size={18} />
              </span>
              <div>
                <strong>{risks}</strong>
                <small>Risks</small>
              </div>
            </div>
          </div>

          <div className="kanban-grid" aria-label="Task board">
            {boardColumns.map((column) => (
              <section className="kanban-column" key={column.id}>
                <div className={`column-title ${column.tone}`}>
                  <span>{column.title}</span>
                  <span>{columns[column.id].length}</span>
                </div>
                <div className="task-stack">
                  {columns[column.id].length ? (
                    columns[column.id].map((task, index) => (
                      <article className="task-card" key={`${task.task}-${index}`}>
                        <div className="task-card-top">
                          <span className="source-tag">Product sync</span>
                          <span className="task-status">{task.status || "Open"}</span>
                        </div>
                        <h2>{task.task}</h2>
                        <div className="task-meta">
                          <span>
                            <UserRound size={14} />
                            {task.owner || "Unassigned"}
                          </span>
                          <span>
                            <CalendarClock size={14} />
                            {task.deadline || "Unknown"}
                          </span>
                          <span>
                            <Link2 size={14} />
                            Meeting link
                          </span>
                        </div>
                      </article>
                    ))
                  ) : (
                    <div className="empty-column">No cards</div>
                  )}
                </div>
              </section>
            ))}
          </div>

          <div className="lower-grid">
            <section className="decisions-panel">
              <div className="section-title">
                <CheckCircle2 size={16} />
                <span>Decisions</span>
              </div>
              <ul>
                {(summary.decisions || []).map((decision) => (
                  <li key={decision}>{decision}</li>
                ))}
              </ul>
            </section>
            <section className="risks-panel">
              <div className="section-title">
                <AlertTriangle size={16} />
                <span>Risks</span>
              </div>
              <ul>
                {(summary.risks || []).map((risk) => (
                  <li key={risk}>{risk}</li>
                ))}
              </ul>
            </section>
            <section className="summary-panel">
              <div className="section-title">
                <FileText size={16} />
                <span>Summary</span>
              </div>
              <pre>{summaryText || summary.follow_up_email || "Analyze a meeting to generate summary text."}</pre>
            </section>
          </div>
        </section>

        <aside className="ai-sidebar">
          <div className="copilot-header">
            <span className="copilot-mark">
              <Bot size={18} />
            </span>
            <div>
              <strong>AI Copilot</strong>
              <small>Meeting intelligence</small>
            </div>
          </div>

          <div className="prompt-list">
            {quickPrompts.map((item) => (
              <button
                className={askText === item.label ? "prompt-chip active" : "prompt-chip"}
                key={item.label}
                onClick={() => handleAsk(item.label)}
                type="button"
              >
                <ArrowRight size={14} />
                {item.label}
              </button>
            ))}
          </div>

          <div className="ask-box">
            <label htmlFor="copilotAsk">Ask</label>
            <textarea
              id="copilotAsk"
              value={askText}
              onChange={(event) => setAskText(event.target.value)}
            />
            <button className="secondary-action" onClick={() => handleAsk()} type="button">
              <Send size={15} />
              Ask Copilot
            </button>
          </div>

          <div className="answer-box">
            <pre>{copilotAnswer}</pre>
          </div>
        </aside>
      </section>
    </main>
  );
}

# CrossExamine — Design Specification

Two AI agents argue over a legal case using actual case documents as ground truth.
One defends the witness account, one tries to destroy it. The user watches (and can
intervene), and at the end gets a vulnerability report showing every inconsistency
the attacking agent found, ranked by severity, with exact source passages.

## Stack

- **Backend:** FastAPI (Python)
- **Frontend:** Next.js + Tailwind CSS
- **AI Agents:** Claude API (claude-sonnet-4-6) via Anthropic SDK
- **Voice:** ElevenLabs streaming TTS
- **Document Indexing:** LlamaIndex with in-memory VectorStoreIndex
- **Embeddings:** HuggingFace `BAAI/bge-small-en-v1.5` (local, no extra API key)
- **PDF Export:** jsPDF (frontend, WYSIWYG)

No database. No auth. Session state in memory. This is a hackathon project.

## Architecture

Five backend modules, three frontend pages, three external services.

### Backend Modules

**`main.py`** — FastAPI app. Thin routing layer that wires everything together.
Routes: file upload, session creation, SSE streaming, interjection POST, report
retrieval, and static audio file serving. Includes `CORSMiddleware` configured
for localhost origins in dev (Next.js dev server runs on a different port than
FastAPI — without CORS config, every frontend fetch silently fails and you'll
waste 20 minutes debugging it).

**`ingest.py`** — Document ingestion pipeline. Takes uploaded files (PDF, TXT, DOCX
via LlamaIndex's SimpleDirectoryReader), chunks them with SentenceSplitter (512
tokens, 50 token overlap), attaches metadata (source filename, page reference,
chunk index), builds an in-memory VectorStoreIndex. One index per session.

**`agents.py`** — The core. Defines Attack and Defense agent functions. Runs the
debate loop: per-round retrieval, Claude API calls with streaming, interjection
injection, early termination checks. This module owns both the agents AND the
orchestration — keeps the logic in one place.

**`voice.py`** — ElevenLabs TTS wrapper. Takes agent text + role, calls ElevenLabs
with the appropriate voice ID, saves audio to a temp file, returns the filename.
Cleans up temp files after the frontend fetches them, or on session end.

**`session.py`** — In-memory session store. Each session holds: its vector index,
conversation history, config (num rounds, voice on/off), interjection queue,
cited_chunks set, and the final vulnerability report.

### Data Flow

```
1. User uploads docs + witness statement        -> POST /upload
   POST /upload does everything: saves files, chunks them, builds the vector
   index, creates the session object, returns the session_id. This is synchronous
   — the frontend shows "INDEXING..." until it gets the response. For a few PDFs
   this takes seconds, not minutes. The SSE connection does NOT trigger indexing.
2. (indexing happens inside step 1)
3. User starts session                           -> GET /session/{id}/stream (SSE)
4. Per round:
   a. agents.py drains session.interjection_queue
   b. Agent queries index for relevant chunks
   c. Agent calls Claude, streams text tokens via SSE
   d. After text complete: voice.py generates audio, saves temp file
   e. SSE sends audio filename (or audio_failed event)
   f. Frontend fetches GET /audio/{filename} and plays it
5. Between rounds: check for new interjections
6. After N rounds (or early termination): generate vulnerability report
7. Report available at GET /session/{id}/report
```

### Streaming Protocol (SSE Events)

Frontend connects to `GET /session/{id}/stream`. Events:

```json
{"type": "token", "agent": "attack", "text": "According to ", "round": 2}
{"type": "token", "agent": "attack", "text": "the police report...", "round": 2}
{"type": "turn_complete", "agent": "attack", "round": 2, "audio_status": "pending"}
{"type": "audio", "agent": "attack", "round": 2, "file": "round-2-attack.mp3"}
{"type": "interjection_ack", "text": "Ask about the timeline gap"}
{"type": "token", "agent": "defense", "text": "While the timing...", "round": 2}
{"type": "turn_complete", "agent": "defense", "round": 2, "audio_status": "pending"}
{"type": "audio_failed", "agent": "defense", "round": 2}
{"type": "session_complete", "reason": "all_rounds" | "exhausted"}
```

`turn_complete` always includes `audio_status: "pending"`. Frontend then waits for
either an `audio` event (play it) or `audio_failed` event (skip, move on). This
prevents the frontend from hanging if audio generation fails.

`session_complete` fires when all rounds are done OR when the debate ends early.
The `reason` field tells the frontend why.

### Interjection Flow

```
User types interjection -> POST /session/{id}/interject
                        -> session.interjection_queue.append(text)
                        -> agents.py drains queue at start of next turn
                        -> Formatted as "judge's instruction" in agent context
                        -> SSE sends interjection_ack so frontend renders it
```

Interjections go into the user message alongside retrieved chunks, NOT into the
system prompt. Framing:

```
[JUDGE'S INSTRUCTION]: The observing party has directed: "{user's text}"
Incorporate this direction into your next response.
```

The agent treats it as a directive from the judge — must address it, stays in character.

## Document Ingestion (`ingest.py`)

### Chunking

- SentenceSplitter: 512 token chunks, 50 token overlap
- Each chunk gets metadata: source filename, page reference, chunk index

### Page Number Handling

Use `metadata['page_label']` if the PDF provides it. If not, fall back to chunk
index divided by estimated chunks-per-page. If that's also garbage, output
"approx. page unknown". Never confidently cite "page 0" on everything.

### Retrieval

Retrieve top-5 chunks per agent turn via `index.as_retriever(similarity_top_k=5)`.
Extract the raw nodes (text + metadata + similarity score). Do NOT use LlamaIndex's
built-in synthesizer or response generation — we handle prompting ourselves. The
retriever returns nodes, we extract text and metadata, pass them as context to our
own Claude call.

### Relevance Threshold

LlamaIndex exposes a similarity score on each returned node. If all 5 returned
chunks score below 0.3, the agent receives a signal that retrieval came up empty.
The agent should then say "I don't have documentary support for this line of
attack/defense" instead of confidently citing irrelevant passages.

This is the grounding integrity guarantee. If an agent can't find a real passage
to cite, it says so. The whole point is trustworthy adversarial analysis.

### Cited Chunks Tracking

`session.py` maintains a `cited_chunks` set and a list of source filenames from
the uploaded documents. After each agent turn, the citation detection works like
this:

1. Scan the agent's response text for any source filename from the session's
   document list (substring match, case-insensitive). Also check for page
   reference patterns like "p. 3", "page 3", "(p3)".
2. If any filename match is found, add the above-threshold retrieved chunks from
   that turn's context to cited_chunks.
3. If no filename match is found (agent didn't cite anything, or said "I don't
   have documentary support"), don't add the chunks.

This is a concrete, mechanical check — not a judgment call. The source filename
list is built during ingestion and stored on the session object.

At report generation time, only cited_chunks are passed to the summarizer. Smaller
context, more focused, and it means the summarizer works with evidence that was
actually argued, not retrieval noise.

## Agent System (`agents.py`)

### Agent Design

Two functions, not classes. Same calling convention, different system prompts.

**Attack Agent** system prompt goals:
- Find every place the witness statement contradicts the case documents
- MUST cite specific passages with document name and page reference
- If no documentary support exists for a line of attack, say so explicitly
- Respond directly to what Defense just said — don't repeat conceded points
- Structure: state the claim being challenged -> quote the contradicting passage
  -> explain why it matters

**Defense Agent** system prompt goals:
- Rehabilitate the witness account using the case documents
- Find passages that SUPPORT the witness, explain away contradictions
- Respond directly to Attack's specific challenges — don't ignore strong points
- If a contradiction is genuinely damning and indefensible, concede the point
  and pivot to what IS defensible

### Per-Turn Agent Context

Each agent receives per turn:
- System prompt (role and goals)
- The witness statement
- Retrieved chunks (top-5, with metadata and relevance scores)
- Conversation history (last 8 turns — see History Management below)
- Any pending user interjections (formatted as judge's instruction)

### The Debate Loop

```python
for round in range(num_rounds):
    # 1. Drain interjections
    interjections = session.drain_interjections()

    # 2. Attack turn
    # Round 1: seed with "contradictions inconsistencies {witness_statement}"
    # to bias retrieval toward conflict-relevant passages
    # Later rounds: query against what Defense just said
    attack_query = (
        f"contradictions inconsistencies {witness_statement}"
        if round == 0
        else last_defense_text
    )
    attack_chunks = retrieve(index, query=attack_query, top_k=5)
    attack_response = stream_agent(
        "attack", chunks=attack_chunks,
        history=history, interjections=interjections
    )
    # yield SSE token events as they arrive
    # after complete: generate audio, yield audio/audio_failed SSE event

    # 3. Drain interjections again (user might react to attack)
    interjections = session.drain_interjections()

    # 4. Defense turn
    # Query against what Attack just said — looking for supporting evidence
    defense_chunks = retrieve(index, query=attack_response_text, top_k=5)
    defense_response = stream_agent(
        "defense", chunks=defense_chunks,
        history=history, interjections=interjections
    )

    # 5. Early termination check
    if should_terminate_early(attack_response, session):
        yield session_complete_event(reason="exhausted")
        break
```

### Adversarial Retrieval

The retrieval queries are adversarial by design:
- Attack queries against what Defense just said (looking for contradictions)
- Defense queries against what Attack just said (looking for supporting evidence)

This means both agents pull DIFFERENT chunks each round based on what's being
argued. Not two monologues pulling the same context.

### History Management

Full conversation history bloats fast. Pass history as a list of
`{role, content, agent}` dicts. Only include the last 8 turns unless it's
round 1-2 (where history is short anyway). 8 turns = 4 full exchanges (attack
+ defense each), which gives enough context to respond coherently.

This is intentional, not a bug. The agents have the witness statement and fresh
RAG context each turn — they don't need turn 1's arguments in round 5. A comment
in the code should explain this so nobody "fixes" it later.

### Early Termination

If the Attack agent produces zero new citations in the last two consecutive rounds,
the debate ends early. The loop checks "did Attack cite any new passages this turn"
by comparing cited chunks against the session's existing cited_chunks set.

When this happens, the SSE sends `{"type": "session_complete", "reason": "exhausted"}`
and the frontend displays "The attacking agent exhausted its documentary ammunition."
This is actually informative for the report — it means the remaining witness claims
survived adversarial scrutiny.

## Voice Integration (`voice.py`)

### Interface

```python
def generate_audio(text: str, agent: str) -> str | None:
    """
    Calls ElevenLabs TTS, saves MP3 to temp file, returns filename.
    Returns None if ElevenLabs is unavailable or voice is disabled.
    """
```

### Voice Configuration

- Attack voice: configured via `ELEVEN_ATTACK_VOICE_ID` env var
- Defense voice: configured via `ELEVEN_DEFENSE_VOICE_ID` env var
- API key: `ELEVENLABS_API_KEY` env var
- No hardcoded voice IDs or placeholder values anywhere

### Audio Serving

`main.py` serves audio via `GET /audio/{filename}` mapped to the temp directory.
Temp files are cleaned up after the frontend fetches them (via a simple
after-response hook) or at session teardown.

### Failure Handling

If ElevenLabs is down, times out, or the API key isn't set, `generate_audio`
returns None. The debate loop sends `audio_failed` via SSE. The frontend skips
playback for that turn. Voice is nice-to-have — text debate works without it.

### Not Doing

Real-time streaming TTS (audio plays while text generates). That requires
sentence-level buffering, per-chunk audio generation, and playback sync.
For a hackathon: generate full turn audio after text is complete, then play it.

## Vulnerability Report

The actual deliverable. This is the most important part of the application.

### Generation

After the last debate round, make one final Claude call with a dedicated
summarizer prompt. Inputs:
- Full conversation history (all rounds, not windowed)
- Only `cited_chunks` from session (chunks actually referenced in arguments,
  not all retrieved chunks)
- The witness statement

### Two Signal Types

The summarizer scans for:

1. **Attack-surfaced contradictions** — things the Attack agent cited with
   documentary evidence
2. **Defense concessions** — places where Defense used concession language:
   "I cannot dispute", "this does present a challenge", "I must acknowledge",
   "the defense concedes", etc.

Defense concessions are higher-confidence findings than Attack claims because
the adversarial Defense couldn't rebut them.

### Output Schema

```json
{
  "claim": "What the witness stated",
  "contradiction": "What the document actually says",
  "source": "Exact quote, document name, page reference",
  "severity": "high | medium | low",
  "explanation": "One sentence on why this matters in a real case",
  "conceded": true
}
```

### Severity Heuristic

Defined in the summarizer prompt:
- **High:** Direct factual contradiction with documentary proof (witness said X,
  document says not-X)
- **Medium:** Inconsistency that could be explained but is suspicious (timeline
  gaps, changed details)
- **Low:** Minor discrepancy that could be innocent (approximate times, imprecise
  descriptions)

### Deduplication

The summarizer prompt explicitly instructs deduplication. Attack agents tend to
hammer the same contradiction across multiple rounds. Without dedup, the report
lists the same vulnerability 3 times with slightly different wording, which makes
it look noisy and untrustworthy. The summarizer consolidates repeated attacks on
the same claim into a single entry.

### Export

- **PDF:** jsPDF on the frontend. The report page renders as clean HTML; the
  export button converts what's on screen to PDF. WYSIWYG, no backend round-trip.
- **Copy JSON:** Copies the raw vulnerability array to clipboard. Useful for
  pasting into other tools.

## Frontend Design

### Design Language

Editorial, forensic, no decoration. Cues from naughtyduk.com — big type,
deliberate whitespace, high contrast, nothing on the page unless it does a job.

**Typography:**
- One font: IBM Plex Mono (free, sharp, signals precision)
- Headings: large, left-aligned, never centered, never italic
- Body: 13-14px, line-height 1.5
- Labels: ALL CAPS, letter-spacing 2px, 11px, used for metadata not headings

**Palette:**
- Background: #0a0a0f
- Primary text: #e8e8e8 (slightly warm, not pure white)
- Attack: #e84040 (used sparingly, for signal not decoration)
- Defense: #9b5cf6
- Concession/warning: #d4a017 (amber)
- Borders: #1e1e2a
- Low severity: #4a8c5c

**Rules:**
- No emojis anywhere (UI, console.log, comments). Use text or geometric symbols.
- No component libraries (no shadcn, no Radix, no HeadlessUI). Raw HTML + CSS.
- No hover animations on text blocks. No tooltips. No breadcrumbs.
- No transitions longer than 150ms.
- No loading skeletons — show plain "LOADING" text if data isn't ready.
- No hardcoded secrets or placeholder values.
- Must work at 1280px, 1440px, and 1920px. No fixed pixel widths on content.

### Upload Page (`/`)

One screen, not a wizard. Split layout.

**Left half:** File drop target. Rectangle with 1px #1e1e2a border, background
#0f0f18. When files are dropped, listed as plain text lines with x to remove.
No chips, no file icons, no dotted border animation.

**Right half:** Two inputs stacked. Textarea for witness statement (label:
"WITNESS STATEMENT", all caps 11px). Below: round count (number input,
default 4). Voice toggle as two text buttons ("ON" / "OFF"), active one
underlined.

**Bottom right:** "BEGIN" in 18px, 1px border on hover. When clicked, disabled,
text changes to "INDEXING..." — the only loading state.

### Session Arena (`/session/[id]`)

Full width. No sidebar. The debate IS the page.

**Status bar** (top, single line):
```
ROUND 2 / 4  ●  3 CONTRADICTIONS  ●  1 CONCESSION  ●  2 DOCS CITED
```
11px all-caps, separated by bullet symbols. Updates live.

**Agent turns:** Each turn is a block with a 2px left border (red for attack,
purple for defense). Structure:

```
[dot] ATTACK — ROUND 2                    doc: police_report.pdf p.3
The witness claims she arrived at 9pm...
```

- Agent label: 11px all-caps, colored
- Citation reference: floats right, same line as label, dimmer color
- Citation reference truncates with ellipsis if the document name is long;
  full path available on hover via title attribute
- Turn text: 14px, full width below the label
- No card background. No shadow. No avatar.

**Active speaker:** 6px filled circle before agent label, same color, CSS
animation opacity 1 -> 0.3 -> 1, 1.2s ease-in-out. Stops on turn complete.

**Streaming cursor:** 1px wide blinking cursor at the end of the active turn's
text. The cursor appears when the frontend receives the first `token` event for
a new agent+round combination (this is how the frontend knows a new turn started
— no separate `turn_start` event needed). The cursor disappears on `turn_complete`.

**Judge's instruction:** Same block format but amber left border, label
"JUDGE'S INSTRUCTION" in amber.

**Interjection input** (bottom, pinned): Single text input (placeholder:
"Interject as judge...") and "SUBMIT" text button. Both 1px border, no
background fill. Lives at the bottom of the content flow.

**Responsive check:** At 1280px, ensure the status bar doesn't wrap and the
debate text column doesn't feel cramped. Content max-width of 960px keeps
readability at wider viewports.

### Report Page (`/report/[id]`)

**Header:** "VULNERABILITY REPORT" in 32px left-aligned. Subtitle line with
session metadata (session ID, date, doc count, rounds completed). Horizontal
rule below.

**Actions** (top right): "COPY JSON" and "EXPORT PDF" — text buttons, 1px
border, no fill, side by side.

**Summary line** (not cards):
```
HIGH: 2  ●  MEDIUM: 3  ●  LOW: 1  ●  CONCEDED: 2
```
Numbers colored inline (red, amber, green, amber). Just text.

**Vulnerability list:** Each item is a block with 2px left border colored by
severity (red/amber/green). No card background. Structure:

```
[HIGH]  Arrival Time                          CONCEDED BY DEFENSE
CLAIM: Witness states she arrived at approximately 8:15 PM.
CONTRADICTION: Traffic camera shows witness arriving at 8:22 PM...
SOURCE: traffic-camera-log.pdf, p. 1 — "Subject matching witness..."
WHY IT MATTERS: Direct timestamp contradiction undermines the alibi.
```

- Severity + title on top line, "CONCEDED BY DEFENSE" in amber right-aligned
- Labels (CLAIM, CONTRADICTION, SOURCE, WHY IT MATTERS): 11px all-caps
- Values: 13px normal weight
- At 1280px, check that severity label and concession badge don't collide.
  If viewport is tight, concession badge wraps below the title line.

## Project Structure

```
/backend
  main.py          # FastAPI routes, SSE endpoint, audio serving
  agents.py        # Attack + Defense agents, debate loop orchestration
  ingest.py        # Document chunking, indexing, retrieval with threshold
  voice.py         # ElevenLabs TTS wrapper
  session.py       # In-memory session state, interjection queue, cited_chunks

/frontend
  pages/index.tsx        # Upload page
  pages/session/[id].tsx # Session arena
  pages/report/[id].tsx  # Vulnerability report
```

## API Endpoints

```
POST   /upload                     Upload files + witness statement, returns session_id
GET    /session/{id}/stream        SSE stream of the debate
POST   /session/{id}/interject     Submit a user interjection
GET    /session/{id}/report        Get the vulnerability report JSON
GET    /audio/{filename}           Serve a generated audio file
```

## Environment Variables

```
ANTHROPIC_API_KEY          # Claude API access
ELEVENLABS_API_KEY         # ElevenLabs TTS (optional — voice disabled without it)
ELEVEN_ATTACK_VOICE_ID     # Voice for attack agent
ELEVEN_DEFENSE_VOICE_ID    # Voice for defense agent
```

No other configuration. No database URLs. No auth tokens.

## Implementation Order

1. Backend: document ingestion (`ingest.py` + `session.py`)
2. Backend: agent loop (`agents.py`)
3. Backend: API routes and SSE (`main.py`)
4. Frontend: upload page + report page (these are simpler, mostly static rendering)
5. Frontend: session arena (SSE rendering, audio queuing, interjection flow,
   live status bar — build this AFTER backend SSE is verified working)
6. Voice integration (`voice.py`) — nice-to-have, core logic is not

## What Not To Do

- Don't fake document grounding. If retrieval comes up empty, agents say so.
- Don't build auth or a database. In-memory, session-scoped state.
- Don't add loading spinners for everything. One "INDEXING..." state on upload.
- Don't validate uploads aggressively. Try to read it, catch the exception.
- Don't give agents infinite context. RAG top-5 per turn, not the whole dump.
- Don't use console.log with emoji. Plain strings.
- Don't reach for component libraries. Raw HTML + Tailwind utilities.
- Don't add placeholder API keys or voice IDs. Env vars with comments.
- Don't abstract prematurely. One working version first.

## Code Style

- Comments explain WHY, not WHAT. Written for a smart friend, not documentation.
- If something is a hack, say it's a hack.
- Functions short enough to understand in one read. Split if they get long.
- No emojis in code, logs, or UI.

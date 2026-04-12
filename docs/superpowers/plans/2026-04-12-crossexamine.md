# CrossExamine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web app where two AI agents (Attack and Defense) debate over legal case documents, streaming their arguments in real-time, with a vulnerability report as the final output.

**Architecture:** FastAPI backend with SSE streaming, Next.js frontend with editorial design. LlamaIndex handles RAG over uploaded case documents. Claude Sonnet powers both agents. ElevenLabs provides optional voice. In-memory session state, no database.

**Tech Stack:** FastAPI, Next.js (Pages Router), Tailwind CSS, Claude API (claude-sonnet-4-6), LlamaIndex + BAAI/bge-small-en-v1.5, ElevenLabs, jsPDF

**Spec:** `docs/superpowers/specs/2026-04-12-crossexamine-design.md`

---

## File Structure

```
/backend
  main.py              # FastAPI routes, CORS, SSE endpoint, audio serving
  session.py           # Session dataclass, in-memory store, interjection queue
  ingest.py            # Document chunking, indexing, retrieval with threshold
  agents.py            # Agent prompts, streaming turns, debate loop, report generation
  voice.py             # ElevenLabs TTS wrapper
  requirements.txt
  tests/
    __init__.py
    test_session.py
    test_ingest.py
    test_agents.py
    fixtures/
      sample_report.txt   # Small test document for ingestion tests

/frontend
  pages/
    _app.tsx           # Global CSS import
    index.tsx          # Upload page
    session/[id].tsx   # Session arena
    report/[id].tsx    # Vulnerability report
  lib/
    api.ts             # API client (fetch wrappers, API_URL constant)
  styles/
    globals.css        # Tailwind base + custom animations
  package.json
  next.config.js
  tailwind.config.js
  postcss.config.js
  tsconfig.json

.env.example           # Required env vars documented
```

Each backend module has one responsibility. `agents.py` is the biggest file because it owns both the agent functions AND the debate loop orchestration — this is intentional per the spec, keeps the core logic in one place.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/fixtures/sample_report.txt`
- Create: `frontend/package.json`
- Create: `frontend/next.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/tsconfig.json`
- Create: `frontend/styles/globals.css`
- Create: `frontend/pages/_app.tsx`
- Create: `.env.example`

- [ ] **Step 1: Create backend directory and requirements.txt**

```bash
mkdir -p backend/tests/fixtures
```

`backend/requirements.txt`:
```
fastapi
uvicorn[standard]
python-multipart
sse-starlette
anthropic
llama-index-core
llama-index-readers-file
llama-index-embeddings-huggingface
elevenlabs
pytest
pytest-asyncio
httpx
```

- [ ] **Step 2: Create test fixtures and init**

`backend/tests/__init__.py`: empty file.

`backend/tests/fixtures/sample_report.txt`:
```
POLICE INCIDENT REPORT - Case #2024-0472

Date of Incident: March 15, 2024
Time of 911 Call: 7:52 PM
Location: Intersection of 5th Street and Main Avenue

Responding Officer: Sgt. Patricia Mendez, Badge #4418

SUMMARY OF INCIDENT:
At approximately 7:52 PM, dispatch received a 911 call reporting a vehicle-pedestrian collision at the intersection of 5th and Main. Officers arrived on scene at 8:01 PM.

TRAFFIC SIGNAL STATUS:
Signal at 5th/Main was inoperative at the time of the incident. Signal was displaying flashing yellow in all directions due to a power outage affecting the surrounding three blocks. DPW outage report #4471 confirms power was lost at 6:15 PM and restored at 9:30 PM.

VEHICLE DESCRIPTION:
The involved vehicle is registered to defendant James Morton. Registration lists the vehicle as a 2021 Honda Accord, color: BLACK, license plate: 7XKR-442.

ACCIDENT RECONSTRUCTION:
Based on vehicle damage patterns, skid mark analysis, and pedestrian injury profile, estimated impact speed was 15-20 mph. No evidence of excessive speed. Skid marks measure 12 feet, consistent with attempted braking at low speed.

WITNESS ARRIVAL:
Traffic camera footage (Camera #5M-North, timestamp 20:22:14) shows a pedestrian matching witness description entering the frame from the north sidewalk. This is the first appearance of the witness on any camera covering the intersection. Prior footage from 19:45-20:05 shows no pedestrian matching witness description at the intersection.

OFFICER NOTES:
Witness appeared agitated. Stated she had been at the intersection "for a while" before the collision. When informed of the camera timeline, witness declined further comment pending legal counsel.
```

This file has the key contradictions from the spec mockups: the 911 time (7:52 vs witness's 8:15), the signal status (flashing yellow, not red), the vehicle color (black, not blue), the speed (15-20 mph vs "high speed"), and the camera timestamp (8:22 PM).

- [ ] **Step 3: Create .env.example**

`.env.example`:
```bash
# Required - Claude API access
ANTHROPIC_API_KEY=

# Optional - voice disabled without these
ELEVENLABS_API_KEY=
ELEVEN_ATTACK_VOICE_ID=
ELEVEN_DEFENSE_VOICE_ID=
```

- [ ] **Step 4: Create frontend project**

```bash
mkdir -p frontend/pages/session frontend/pages/report frontend/lib frontend/styles
```

`frontend/package.json`:
```json
{
  "name": "crossexamine-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "jspdf": "^2.5.1"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.4.0"
  }
}
```

- [ ] **Step 5: Create Tailwind and Next.js config**

`frontend/tailwind.config.js`:
```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./pages/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    fontFamily: {
      mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
    },
    extend: {
      colors: {
        bg: '#0a0a0f',
        'bg-raised': '#0f0f18',
        border: '#1e1e2a',
        'text-primary': '#e8e8e8',
        'text-dim': '#888888',
        'text-muted': '#555555',
        'text-ghost': '#333333',
        attack: '#e84040',
        defense: '#9b5cf6',
        amber: '#d4a017',
        low: '#4a8c5c',
      },
      fontSize: {
        label: ['11px', { lineHeight: '1.5', letterSpacing: '0.15em' }],
        body: ['13px', { lineHeight: '1.5' }],
        reading: ['14px', { lineHeight: '1.6' }],
      },
    },
  },
  plugins: [],
};
```

`frontend/postcss.config.js`:
```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

`frontend/next.config.js`:
```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

module.exports = nextConfig;
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "es5",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 6: Create global CSS and App component**

`frontend/styles/globals.css`:
```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  background-color: #0a0a0f;
  color: #e8e8e8;
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
}

/* Pulsing dot for active speaker */
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.animate-pulse-dot {
  animation: pulse-dot 1.2s ease-in-out infinite;
}

/* Blinking cursor for streaming text */
@keyframes blink-cursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.animate-blink {
  animation: blink-cursor 0.8s step-end infinite;
}
```

`frontend/pages/_app.tsx`:
```tsx
import type { AppProps } from 'next/app';
import '@/styles/globals.css';

export default function App({ Component, pageProps }: AppProps) {
  return <Component {...pageProps} />;
}
```

- [ ] **Step 7: Create API client helper**

`frontend/lib/api.ts`:
```ts
// Backend URL — configurable via env var for deployment,
// defaults to localhost:8000 for dev
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function uploadCase(
  files: File[],
  witnessStatement: string,
  numRounds: number,
  voiceEnabled: boolean,
): Promise<{ session_id: string }> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  form.append('witness_statement', witnessStatement);
  form.append('num_rounds', String(numRounds));
  form.append('voice_enabled', String(voiceEnabled));

  const res = await fetch(`${API_URL}/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed: ${text}`);
  }
  return res.json();
}

export async function submitInterjection(
  sessionId: string,
  text: string,
): Promise<void> {
  const res = await fetch(`${API_URL}/session/${sessionId}/interject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error('Interjection failed');
}

export async function fetchReport(
  sessionId: string,
): Promise<{ vulnerabilities: Vulnerability[]; metadata: ReportMetadata }> {
  const res = await fetch(`${API_URL}/session/${sessionId}/report`);
  if (!res.ok) throw new Error('Report not ready');
  return res.json();
}

// Types shared across frontend
export interface Vulnerability {
  claim: string;
  contradiction: string;
  source: string;
  severity: 'high' | 'medium' | 'low';
  explanation: string;
  conceded: boolean;
}

export interface ReportMetadata {
  session_id: string;
  date: string;
  doc_count: number;
  rounds_completed: number;
}

export interface SSEEvent {
  type:
    | 'token'
    | 'turn_complete'
    | 'audio'
    | 'audio_failed'
    | 'interjection_ack'
    | 'session_complete';
  agent?: 'attack' | 'defense';
  round?: number;
  text?: string;
  file?: string;
  audio_status?: 'pending';
  reason?: 'all_rounds' | 'exhausted';
}
```

- [ ] **Step 8: Install dependencies and verify**

```bash
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```

Run: `cd frontend && npx next build 2>&1 | head -5`
Expected: Build starts without config errors (may fail on missing pages, that's fine).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with backend deps, frontend config, design tokens"
```

---

### Task 2: Session Module

**Files:**
- Create: `backend/session.py`
- Create: `backend/tests/test_session.py`

- [ ] **Step 1: Write tests for Session and SessionStore**

`backend/tests/test_session.py`:
```python
import pytest
from session import Session, SessionStore, SessionConfig


def test_create_session():
    store = SessionStore()
    session = store.create(
        index=None,  # no real index needed for this test
        witness_statement="The witness saw the car run a red light.",
        source_filenames=["report.pdf", "deposition.pdf"],
        config=SessionConfig(num_rounds=4, voice_enabled=True),
    )
    assert session.id is not None
    assert len(session.id) == 8
    assert session.witness_statement == "The witness saw the car run a red light."
    assert session.source_filenames == ["report.pdf", "deposition.pdf"]
    assert session.config.num_rounds == 4
    assert session.history == []
    assert session.interjection_queue == []
    assert session.cited_chunks == set()
    assert session.report is None


def test_get_session():
    store = SessionStore()
    session = store.create(
        index=None,
        witness_statement="test",
        source_filenames=[],
        config=SessionConfig(),
    )
    found = store.get(session.id)
    assert found is session
    assert store.get("nonexistent") is None


def test_drain_interjections():
    store = SessionStore()
    session = store.create(
        index=None,
        witness_statement="test",
        source_filenames=[],
        config=SessionConfig(),
    )
    session.interjection_queue.append("Ask about the timeline")
    session.interjection_queue.append("Focus on the camera footage")

    drained = session.drain_interjections()
    assert drained == ["Ask about the timeline", "Focus on the camera footage"]
    # Queue should be empty after drain
    assert session.interjection_queue == []
    # Second drain should return empty
    assert session.drain_interjections() == []


def test_add_to_history():
    store = SessionStore()
    session = store.create(
        index=None,
        witness_statement="test",
        source_filenames=[],
        config=SessionConfig(),
    )
    session.add_to_history("attack", "The witness lied about the time.")
    session.add_to_history("defense", "The time was an estimate.")

    assert len(session.history) == 2
    assert session.history[0] == {
        "agent": "attack",
        "content": "The witness lied about the time.",
    }
    assert session.history[1] == {
        "agent": "defense",
        "content": "The time was an estimate.",
    }


def test_get_recent_history_windowing():
    """History is windowed to last 8 turns. This is intentional — agents get
    fresh RAG context each turn so they don't need ancient history."""
    store = SessionStore()
    session = store.create(
        index=None,
        witness_statement="test",
        source_filenames=[],
        config=SessionConfig(),
    )
    # Add 12 turns
    for i in range(12):
        agent = "attack" if i % 2 == 0 else "defense"
        session.add_to_history(agent, f"Turn {i}")

    recent = session.get_recent_history(max_turns=8)
    assert len(recent) == 8
    # Should be the LAST 8 turns (indices 4-11)
    assert recent[0]["content"] == "Turn 4"
    assert recent[-1]["content"] == "Turn 11"


def test_get_recent_history_short():
    """When history is shorter than the window, return everything."""
    store = SessionStore()
    session = store.create(
        index=None,
        witness_statement="test",
        source_filenames=[],
        config=SessionConfig(),
    )
    session.add_to_history("attack", "First turn")
    recent = session.get_recent_history(max_turns=8)
    assert len(recent) == 1


def test_detect_citation_in_response():
    store = SessionStore()
    session = store.create(
        index=None,
        witness_statement="test",
        source_filenames=["police-report-2024.pdf", "deposition-jones.pdf"],
        config=SessionConfig(),
    )
    # Response that cites a document
    assert session.response_has_citation(
        "According to police-report-2024.pdf on page 3, the time was 7:52 PM."
    )
    # Response that cites with different case
    assert session.response_has_citation(
        "The POLICE-REPORT-2024.PDF clearly states..."
    )
    # Response with no citation
    assert not session.response_has_citation(
        "I don't have documentary support for this line of attack."
    )
    # Response with page reference but no filename
    assert not session.response_has_citation(
        "On page 3, we can see the contradiction."
    )


def test_mark_chunks_cited():
    store = SessionStore()
    session = store.create(
        index=None,
        witness_statement="test",
        source_filenames=["report.pdf"],
        config=SessionConfig(),
    )
    chunks = [
        {"id": "chunk_1", "text": "some text", "score": 0.8},
        {"id": "chunk_2", "text": "other text", "score": 0.5},
        {"id": "chunk_3", "text": "low relevance", "score": 0.2},
    ]
    response_text = "According to report.pdf, the time was wrong."

    session.mark_chunks_cited(chunks, response_text)
    # Should add above-threshold chunks (score > 0.3) since response has citation
    assert "chunk_1" in session.cited_chunks
    assert "chunk_2" in session.cited_chunks
    # Below threshold, not added even though response has citation
    assert "chunk_3" not in session.cited_chunks


def test_mark_chunks_not_cited():
    store = SessionStore()
    session = store.create(
        index=None,
        witness_statement="test",
        source_filenames=["report.pdf"],
        config=SessionConfig(),
    )
    chunks = [
        {"id": "chunk_1", "text": "some text", "score": 0.8},
    ]
    response_text = "I don't have documentary support for this."

    session.mark_chunks_cited(chunks, response_text)
    # No citation detected, so chunks should NOT be added
    assert len(session.cited_chunks) == 0
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_session.py -v`
Expected: ImportError — `session` module doesn't exist yet.

- [ ] **Step 3: Implement session.py**

`backend/session.py`:
```python
"""In-memory session state for CrossExamine.

Each session holds everything needed for a debate: the vector index,
conversation history, interjection queue, and cited chunks tracking.
No database, no persistence — this is a hackathon.
"""

import re
import uuid
from dataclasses import dataclass, field

# Relevance threshold — chunks scoring below this are considered
# noise and not worth citing. See spec for rationale.
RELEVANCE_THRESHOLD = 0.3


@dataclass
class SessionConfig:
    num_rounds: int = 4
    voice_enabled: bool = True


@dataclass
class Session:
    id: str
    index: object  # VectorStoreIndex, typed as object to avoid import dependency
    witness_statement: str
    source_filenames: list[str]
    config: SessionConfig
    history: list[dict] = field(default_factory=list)
    interjection_queue: list[str] = field(default_factory=list)
    cited_chunks: set[str] = field(default_factory=set)
    report: list[dict] | None = None
    # Track how many consecutive rounds Attack found nothing new.
    # Used for early termination.
    attack_dry_rounds: int = 0

    def drain_interjections(self) -> list[str]:
        """Pop all pending interjections. Returns them and clears the queue.
        Technically racy under concurrent access but fine for a single-user demo."""
        items = self.interjection_queue[:]
        self.interjection_queue.clear()
        return items

    def add_to_history(self, agent: str, content: str) -> None:
        self.history.append({"agent": agent, "content": content})

    def get_recent_history(self, max_turns: int = 8) -> list[dict]:
        """Return the last N turns. We intentionally window this — agents get
        fresh RAG context each turn, so they don't need ancient arguments.
        8 turns = 4 full attack+defense exchanges. Don't 'fix' this."""
        if len(self.history) <= max_turns:
            return self.history[:]
        return self.history[-max_turns:]

    def response_has_citation(self, response_text: str) -> bool:
        """Check if an agent response cites any of the session's source documents.
        Mechanical check: case-insensitive substring match against source filenames."""
        lower_response = response_text.lower()
        for filename in self.source_filenames:
            if filename.lower() in lower_response:
                return True
        return False

    def mark_chunks_cited(self, chunks: list[dict], response_text: str) -> None:
        """After an agent turn, mark which chunks were actually used.
        Only adds chunks if the agent's response actually cited a document.
        Only adds chunks scoring above the relevance threshold."""
        if not self.response_has_citation(response_text):
            return
        for chunk in chunks:
            if chunk.get("score", 0) >= RELEVANCE_THRESHOLD:
                self.cited_chunks.add(chunk["id"])

    def get_cited_chunk_texts(self, all_chunks: dict[str, dict]) -> list[dict]:
        """Get the actual text/metadata for all cited chunks.
        all_chunks is a {chunk_id: {text, metadata}} dict built during ingestion."""
        return [all_chunks[cid] for cid in self.cited_chunks if cid in all_chunks]


class SessionStore:
    """In-memory dict of sessions. Nothing fancy."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(
        self,
        index: object,
        witness_statement: str,
        source_filenames: list[str],
        config: SessionConfig,
    ) -> Session:
        session_id = uuid.uuid4().hex[:8]
        session = Session(
            id=session_id,
            index=index,
            witness_statement=witness_statement,
            source_filenames=source_filenames,
            config=config,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_session.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/session.py backend/tests/test_session.py
git commit -m "feat: session module with interjection queue and cited chunks tracking"
```

---

### Task 3: Document Ingestion

**Files:**
- Create: `backend/ingest.py`
- Create: `backend/tests/test_ingest.py`

- [ ] **Step 1: Write ingestion tests**

`backend/tests/test_ingest.py`:
```python
import os
import pytest
from ingest import ingest_documents, retrieve_chunks, format_chunk_for_context

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE_REPORT = os.path.join(FIXTURES_DIR, "sample_report.txt")


def test_ingest_creates_index_and_returns_filenames():
    index, source_filenames, chunk_store = ingest_documents([SAMPLE_REPORT])
    assert index is not None
    assert "sample_report.txt" in source_filenames
    assert len(chunk_store) > 0


def test_ingest_chunks_have_metadata():
    _, _, chunk_store = ingest_documents([SAMPLE_REPORT])
    # Every chunk should have text, metadata with file_name, and a page ref
    for chunk_id, chunk in chunk_store.items():
        assert "text" in chunk
        assert len(chunk["text"]) > 0
        assert "metadata" in chunk
        assert "file_name" in chunk["metadata"]
        assert "page_ref" in chunk["metadata"]


def test_retrieve_returns_scored_chunks():
    index, _, _ = ingest_documents([SAMPLE_REPORT])
    results = retrieve_chunks(index, "What time was the 911 call?", top_k=3)
    assert len(results) <= 3
    for chunk in results:
        assert "text" in chunk
        assert "score" in chunk
        assert "id" in chunk
        assert isinstance(chunk["score"], float)


def test_retrieve_relevance_scores():
    """A query about content in the document should score higher than gibberish."""
    index, _, _ = ingest_documents([SAMPLE_REPORT])
    relevant = retrieve_chunks(index, "traffic signal status power outage", top_k=1)
    irrelevant = retrieve_chunks(index, "quantum physics spacetime warp drive", top_k=1)
    # The relevant query should score higher
    assert relevant[0]["score"] > irrelevant[0]["score"]


def test_format_chunk_for_context():
    chunk = {
        "text": "The signal was flashing yellow.",
        "metadata": {"file_name": "report.pdf", "page_ref": "p. 5"},
        "score": 0.82,
        "id": "abc123",
    }
    formatted = format_chunk_for_context(chunk)
    assert "report.pdf" in formatted
    assert "p. 5" in formatted
    assert "The signal was flashing yellow." in formatted
    assert "0.82" in formatted
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_ingest.py -v`
Expected: ImportError — `ingest` module doesn't exist yet.

- [ ] **Step 3: Implement ingest.py**

`backend/ingest.py`:
```python
"""Document ingestion pipeline for CrossExamine.

Takes uploaded files, chunks them with LlamaIndex, builds a vector index.
Uses local HuggingFace embeddings (BAAI/bge-small-en-v1.5) to avoid
needing a third API key.

Key design: we use LlamaIndex for retrieval only. We grab the raw nodes
and pass them to our own Claude call. We do NOT use LlamaIndex's built-in
synthesizer or response generation.
"""

import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# Initialize embedding model once at module level.
# First run downloads the model (~130MB). Subsequent runs use cache.
_embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

# Chunking config from the spec
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
RETRIEVAL_TOP_K = 5


def ingest_documents(
    file_paths: list[str],
) -> tuple[VectorStoreIndex, list[str], dict[str, dict]]:
    """Chunk documents and build a vector index.

    Returns:
        index: VectorStoreIndex for retrieval
        source_filenames: list of original filenames (for citation detection)
        chunk_store: {node_id: {text, metadata}} for all chunks (for report generation)
    """
    reader = SimpleDirectoryReader(input_files=file_paths)
    documents = reader.load_data()

    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(documents)

    # Attach page references to each node's metadata
    for i, node in enumerate(nodes):
        meta = node.metadata
        page_ref = _get_page_ref(meta, i)
        meta["page_ref"] = page_ref

    index = VectorStoreIndex(nodes, embed_model=_embed_model)

    source_filenames = list(
        {os.path.basename(fp) for fp in file_paths}
    )

    # Build a chunk store keyed by node ID for later retrieval during report generation
    chunk_store = {}
    for node in nodes:
        chunk_store[node.node_id] = {
            "text": node.text,
            "metadata": dict(node.metadata),
        }

    return index, source_filenames, chunk_store


def _get_page_ref(metadata: dict, chunk_index: int) -> str:
    """Extract page reference from metadata with fallback chain.
    Uses page_label if PDF provides it, otherwise estimates from chunk index,
    otherwise gives up gracefully. Never confidently says 'page 0'."""
    page_label = metadata.get("page_label")
    if page_label and page_label != "0":
        return f"p. {page_label}"

    # Rough estimate: assume ~3 chunks per page for typical documents
    # This is a hack but better than nothing
    estimated_page = (chunk_index // 3) + 1
    if estimated_page > 1:
        return f"approx. p. {estimated_page}"

    return "approx. page unknown"


def retrieve_chunks(
    index: VectorStoreIndex, query: str, top_k: int = RETRIEVAL_TOP_K
) -> list[dict]:
    """Retrieve top-k chunks for a query. Returns raw nodes with scores.
    Does NOT use LlamaIndex's synthesizer — we handle prompting ourselves."""
    retriever = index.as_retriever(similarity_top_k=top_k)
    results = retriever.retrieve(query)

    chunks = []
    for node_with_score in results:
        node = node_with_score.node
        chunks.append(
            {
                "id": node.node_id,
                "text": node.text,
                "metadata": dict(node.metadata),
                "score": node_with_score.score,
            }
        )
    return chunks


def chunks_above_threshold(chunks: list[dict], threshold: float = 0.3) -> bool:
    """Returns True if ANY chunk scores above the threshold.
    If all chunks are below, retrieval basically came up empty and
    the agent should say so instead of citing garbage."""
    return any(c["score"] >= threshold for c in chunks)


def format_chunk_for_context(chunk: dict) -> str:
    """Format a retrieved chunk for inclusion in an agent's context.
    Includes source file, page ref, relevance score, and the text."""
    meta = chunk["metadata"]
    file_name = meta.get("file_name", "unknown")
    page_ref = meta.get("page_ref", "unknown")
    score = chunk.get("score", 0)
    return (
        f"[Source: {file_name}, {page_ref} | relevance: {score:.2f}]\n"
        f"{chunk['text']}"
    )
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_ingest.py -v`
Expected: All 5 tests PASS. First run may be slow (model download).

- [ ] **Step 5: Commit**

```bash
git add backend/ingest.py backend/tests/test_ingest.py
git commit -m "feat: document ingestion with chunking, vector index, and retrieval"
```

---

### Task 4: Agent System — Prompts, Turn Streaming, and Citation Detection

**Files:**
- Create: `backend/agents.py`
- Create: `backend/tests/test_agents.py`

- [ ] **Step 1: Write tests for agent helpers and citation detection**

`backend/tests/test_agents.py`:
```python
import pytest
from agents import (
    build_user_message,
    detect_citations,
    ATTACK_SYSTEM_PROMPT,
    DEFENSE_SYSTEM_PROMPT,
    SUMMARIZER_PROMPT,
)


def test_attack_prompt_has_key_instructions():
    assert "cite specific" in ATTACK_SYSTEM_PROMPT.lower()
    assert "document" in ATTACK_SYSTEM_PROMPT.lower()
    assert "don't have documentary support" in ATTACK_SYSTEM_PROMPT.lower()


def test_defense_prompt_has_concession_instruction():
    assert "concede" in DEFENSE_SYSTEM_PROMPT.lower()
    assert "I must acknowledge" in DEFENSE_SYSTEM_PROMPT.lower() or \
           "concede the point" in DEFENSE_SYSTEM_PROMPT.lower()


def test_summarizer_prompt_has_dedup_instruction():
    assert "deduplic" in SUMMARIZER_PROMPT.lower()
    assert "concession" in SUMMARIZER_PROMPT.lower() or \
           "conceded" in SUMMARIZER_PROMPT.lower()


def test_build_user_message_basic():
    chunks = [
        {
            "text": "The signal was flashing yellow.",
            "metadata": {"file_name": "report.pdf", "page_ref": "p. 5"},
            "score": 0.85,
            "id": "c1",
        }
    ]
    msg = build_user_message(
        witness_statement="The light was red.",
        chunks=chunks,
        history=[],
        interjections=[],
        retrieval_has_results=True,
    )
    assert "The light was red." in msg
    assert "report.pdf" in msg
    assert "flashing yellow" in msg


def test_build_user_message_with_history():
    msg = build_user_message(
        witness_statement="test",
        chunks=[],
        history=[
            {"agent": "attack", "content": "The witness lied."},
            {"agent": "defense", "content": "It was an estimate."},
        ],
        interjections=[],
        retrieval_has_results=False,
    )
    assert "ATTACK:" in msg
    assert "DEFENSE:" in msg
    assert "The witness lied." in msg
    assert "It was an estimate." in msg


def test_build_user_message_with_interjection():
    msg = build_user_message(
        witness_statement="test",
        chunks=[],
        history=[],
        interjections=["Ask about the camera footage."],
        retrieval_has_results=False,
    )
    assert "JUDGE'S INSTRUCTION" in msg
    assert "Ask about the camera footage." in msg


def test_build_user_message_empty_retrieval_warning():
    msg = build_user_message(
        witness_statement="test",
        chunks=[],
        history=[],
        interjections=[],
        retrieval_has_results=False,
    )
    assert "no relevant passages" in msg.lower() or \
           "no strong documentary evidence" in msg.lower()


def test_detect_citations_finds_filenames():
    filenames = ["police-report.pdf", "deposition-jones.pdf"]
    assert detect_citations("According to police-report.pdf p.3...", filenames)
    assert detect_citations("The DEPOSITION-JONES.PDF shows...", filenames)


def test_detect_citations_rejects_no_filename():
    filenames = ["police-report.pdf"]
    assert not detect_citations("The evidence is clear.", filenames)
    assert not detect_citations("On page 3 we see...", filenames)
    assert not detect_citations(
        "I don't have documentary support for this.", filenames
    )
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_agents.py -v`
Expected: ImportError — `agents` module doesn't exist yet.

- [ ] **Step 3: Implement agents.py — prompts, message building, citation detection**

`backend/agents.py`:
```python
"""Core agent system for CrossExamine.

Two agent functions (attack, defense) and the debate loop that orchestrates them.
This module owns both the agents AND the loop — keeping the core logic in one place.
"""

import json
import os
import anthropic
from ingest import retrieve_chunks, chunks_above_threshold, format_chunk_for_context
from session import Session

# The async client handles streaming from Claude
_client = anthropic.AsyncAnthropic()
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

# -- System Prompts --

ATTACK_SYSTEM_PROMPT = """You are a cross-examining attorney analyzing witness testimony against case documents. Your goal is to find every inconsistency, contradiction, and weakness in the witness's account.

RULES:
- You MUST cite specific document passages with the document filename and page number.
- If you cannot find documentary evidence for a line of attack, say exactly: "I don't have documentary support for this line of attack."
- Respond DIRECTLY to what the Defense just said. Address their specific arguments. Do not repeat points already conceded.
- Structure each argument: (1) State the claim you are challenging. (2) Quote the contradicting passage with source. (3) Explain why this matters for the case.
- Keep responses focused. Under 300 words. Every assertion must cite a specific document."""

DEFENSE_SYSTEM_PROMPT = """You are a defense attorney protecting a witness's testimony using case documents. Your goal is to rehabilitate the witness's account and counter the Attack's arguments.

RULES:
- Find passages in the documents that SUPPORT the witness's version of events.
- Explain away contradictions the Attack raised. Offer alternative interpretations of the evidence.
- Respond DIRECTLY to the Attack's specific challenges. Do not ignore strong points.
- If a contradiction is genuinely damning and you cannot defend it, concede the point explicitly. Use language like "I must acknowledge this presents a challenge" or "the defense concedes this point." Then pivot to claims that ARE defensible.
- Cite specific document passages with filename and page number.
- Keep responses focused. Under 300 words. Every defense must reference specific evidence."""

SUMMARIZER_PROMPT = """You are a legal analyst producing a vulnerability report. Review the debate transcript below and identify every contradiction the Attack agent surfaced that was supported by documentary evidence.

Also identify any points where the Defense explicitly conceded. Look for language like: "I cannot dispute", "I must acknowledge", "this presents a challenge", "the defense concedes".

For each vulnerability, produce a JSON object:
{
  "claim": "what the witness stated",
  "contradiction": "what the document says instead",
  "source": "exact quote + document filename + page reference",
  "severity": "high | medium | low",
  "explanation": "one sentence on why this matters in a real legal case",
  "conceded": true or false
}

SEVERITY RULES:
- high: Direct factual contradiction with documentary proof (witness said X, document says not-X)
- medium: Inconsistency that could be explained but is suspicious (timeline gaps, changed details)
- low: Minor discrepancy that could be innocent (approximate times, imprecise descriptions)

IMPORTANT:
- DEDUPLICATE: if the same contradiction was raised multiple times across rounds, consolidate into ONE entry
- Only include contradictions that have specific documentary evidence cited
- Defense concessions are higher confidence than Attack claims alone
- Sort by severity: high first, then medium, then low

Return ONLY a JSON array of vulnerability objects. No other text, no markdown fences, just the array."""


def build_user_message(
    witness_statement: str,
    chunks: list[dict],
    history: list[dict],
    interjections: list[str],
    retrieval_has_results: bool,
) -> str:
    """Build the user message sent to Claude for an agent turn.
    Combines witness statement, retrieved passages, conversation history,
    and any judge instructions into a single message."""
    parts = []

    # Witness statement
    parts.append(f"WITNESS STATEMENT:\n{witness_statement}")

    # Retrieved document passages
    if chunks and retrieval_has_results:
        passages = "\n\n".join(format_chunk_for_context(c) for c in chunks)
        parts.append(f"RELEVANT DOCUMENT PASSAGES:\n{passages}")
    else:
        parts.append(
            "RELEVANT DOCUMENT PASSAGES:\n"
            "No strong documentary evidence was found for the current line of "
            "argument. If you cannot cite specific passages, acknowledge this "
            "explicitly rather than fabricating references."
        )

    # Conversation history
    if history:
        formatted_history = []
        for turn in history:
            label = turn["agent"].upper()
            formatted_history.append(f"{label}: {turn['content']}")
        parts.append(
            "CONVERSATION SO FAR:\n" + "\n\n".join(formatted_history)
        )

    # Judge instructions (interjections)
    if interjections:
        for text in interjections:
            parts.append(
                f'[JUDGE\'S INSTRUCTION]: The observing party has directed: "{text}"\n'
                "Incorporate this direction into your next response."
            )

    parts.append(
        "Now respond in character. Address the most recent arguments directly."
    )

    return "\n\n---\n\n".join(parts)


def detect_citations(response_text: str, source_filenames: list[str]) -> bool:
    """Check if an agent response references any source document by filename.
    Case-insensitive substring match. This is the mechanical check the spec requires."""
    lower_response = response_text.lower()
    return any(fname.lower() in lower_response for fname in source_filenames)


async def stream_agent_turn(
    agent: str,
    witness_statement: str,
    chunks: list[dict],
    history: list[dict],
    interjections: list[str],
    retrieval_has_results: bool,
    round_num: int,
) -> str:
    """Stream a single agent turn via Claude. Yields SSE event dicts.
    Returns the complete response text (for history and citation tracking).

    This is an async generator — it yields event dicts as tokens arrive,
    AND returns the full text. Callers use 'async for' to get events,
    then the return value is the complete text for post-processing.

    Hack: since Python async generators can't 'return' a value, we use a
    mutable list to capture the full text. The caller reads agent_text[0]
    after the generator is exhausted."""
    system_prompt = (
        ATTACK_SYSTEM_PROMPT if agent == "attack" else DEFENSE_SYSTEM_PROMPT
    )

    user_message = build_user_message(
        witness_statement=witness_statement,
        chunks=chunks,
        history=history,
        interjections=interjections,
        retrieval_has_results=retrieval_has_results,
    )

    full_text = ""
    async with _client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        async for text in stream.text_stream:
            full_text += text
            yield {
                "type": "token",
                "agent": agent,
                "text": text,
                "round": round_num,
            }

    yield {
        "type": "turn_complete",
        "agent": agent,
        "round": round_num,
        "audio_status": "pending",
        "full_text": full_text,
    }


async def generate_report(session: Session, chunk_store: dict) -> list[dict]:
    """Final summarizer call after the debate ends.
    Uses full conversation history (not windowed) and only cited chunks."""
    cited_chunk_texts = []
    for chunk_id in session.cited_chunks:
        if chunk_id in chunk_store:
            c = chunk_store[chunk_id]
            meta = c["metadata"]
            cited_chunk_texts.append(
                f"[{meta.get('file_name', '?')}, {meta.get('page_ref', '?')}]: "
                f"{c['text']}"
            )

    history_text = "\n\n".join(
        f"{turn['agent'].upper()}: {turn['content']}" for turn in session.history
    )

    user_message = (
        f"WITNESS STATEMENT:\n{session.witness_statement}\n\n"
        f"DOCUMENTARY EVIDENCE CITED DURING DEBATE:\n"
        + "\n\n".join(cited_chunk_texts)
        + f"\n\nFULL DEBATE TRANSCRIPT:\n{history_text}"
    )

    response = await _client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SUMMARIZER_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text.strip()
    # Parse the JSON array — the prompt asks for raw JSON, no markdown fences
    try:
        vulnerabilities = json.loads(raw_text)
    except json.JSONDecodeError:
        # If Claude wrapped it in markdown fences, strip them
        cleaned = raw_text.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        vulnerabilities = json.loads(cleaned)

    return vulnerabilities


async def run_debate(session: Session, chunk_store: dict):
    """Run the full debate loop. Async generator that yields SSE event dicts.
    This is the heart of CrossExamine — it orchestrates everything."""
    last_defense_text = ""
    previous_cited_count = len(session.cited_chunks)

    for round_num in range(1, session.config.num_rounds + 1):
        # 1. Drain interjections before attack turn
        interjections = session.drain_interjections()
        if interjections:
            for text in interjections:
                yield {"type": "interjection_ack", "text": text}

        # 2. Attack turn
        # Round 1: seed query to bias toward contradictions
        # Later rounds: query against what Defense just said
        if round_num == 1:
            attack_query = (
                f"contradictions inconsistencies {session.witness_statement}"
            )
        else:
            attack_query = last_defense_text

        attack_chunks = retrieve_chunks(session.index, attack_query)
        has_results = chunks_above_threshold(attack_chunks)

        attack_text = ""
        async for event in stream_agent_turn(
            agent="attack",
            witness_statement=session.witness_statement,
            chunks=attack_chunks,
            history=session.get_recent_history(),
            interjections=interjections,
            retrieval_has_results=has_results,
            round_num=round_num,
        ):
            if event["type"] == "turn_complete":
                attack_text = event.pop("full_text")
            yield event

        session.add_to_history("attack", attack_text)
        session.mark_chunks_cited(attack_chunks, attack_text)

        # Audio for attack turn — voice.py integration happens here
        # (wired in Task 10, for now just send audio_failed)
        if session.config.voice_enabled:
            try:
                from voice import generate_audio
                audio_file = await generate_audio(attack_text, "attack")
                if audio_file:
                    yield {
                        "type": "audio",
                        "agent": "attack",
                        "round": round_num,
                        "file": audio_file,
                    }
                else:
                    yield {
                        "type": "audio_failed",
                        "agent": "attack",
                        "round": round_num,
                    }
            except ImportError:
                yield {
                    "type": "audio_failed",
                    "agent": "attack",
                    "round": round_num,
                }

        # 3. Drain interjections before defense turn
        interjections = session.drain_interjections()
        if interjections:
            for text in interjections:
                yield {"type": "interjection_ack", "text": text}

        # 4. Defense turn — queries against what Attack just said
        defense_chunks = retrieve_chunks(session.index, attack_text)
        has_results = chunks_above_threshold(defense_chunks)

        defense_text = ""
        async for event in stream_agent_turn(
            agent="defense",
            witness_statement=session.witness_statement,
            chunks=defense_chunks,
            history=session.get_recent_history(),
            interjections=interjections,
            retrieval_has_results=has_results,
            round_num=round_num,
        ):
            if event["type"] == "turn_complete":
                defense_text = event.pop("full_text")
            yield event

        session.add_to_history("defense", defense_text)
        session.mark_chunks_cited(defense_chunks, defense_text)
        last_defense_text = defense_text

        # Audio for defense turn
        if session.config.voice_enabled:
            try:
                from voice import generate_audio
                audio_file = await generate_audio(defense_text, "defense")
                if audio_file:
                    yield {
                        "type": "audio",
                        "agent": "defense",
                        "round": round_num,
                        "file": audio_file,
                    }
                else:
                    yield {
                        "type": "audio_failed",
                        "agent": "defense",
                        "round": round_num,
                    }
            except ImportError:
                yield {
                    "type": "audio_failed",
                    "agent": "defense",
                    "round": round_num,
                }

        # 5. Early termination check
        current_cited_count = len(session.cited_chunks)
        if current_cited_count == previous_cited_count:
            session.attack_dry_rounds += 1
        else:
            session.attack_dry_rounds = 0
        previous_cited_count = current_cited_count

        if session.attack_dry_rounds >= 2:
            yield {"type": "session_complete", "reason": "exhausted"}
            break
    else:
        # Loop completed normally (no break)
        yield {"type": "session_complete", "reason": "all_rounds"}

    # Generate vulnerability report after debate ends
    report = await generate_report(session, chunk_store)
    session.report = report
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_agents.py -v`
Expected: All 9 tests PASS (tests only cover the non-async helper functions and prompts, not the streaming which requires API calls).

- [ ] **Step 5: Commit**

```bash
git add backend/agents.py backend/tests/test_agents.py
git commit -m "feat: agent system with prompts, debate loop, citation detection, report generation"
```

---

### Task 5: FastAPI Routes and SSE

**Files:**
- Create: `backend/main.py`

- [ ] **Step 1: Implement main.py**

`backend/main.py`:
```python
"""FastAPI app for CrossExamine.

Thin routing layer — all the interesting logic lives in agents.py, ingest.py,
and session.py. This file just wires HTTP endpoints to those modules.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from session import SessionStore, SessionConfig
from ingest import ingest_documents
from agents import run_debate

app = FastAPI(title="CrossExamine")

# CORS — Next.js dev server runs on :3000, FastAPI on :8000.
# Without this, every frontend fetch silently fails.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory state
store = SessionStore()
# {session_id: chunk_store} — kept separate from Session to avoid
# serialization issues with the large dict
_chunk_stores: dict[str, dict] = {}

# Temp dir for audio files
AUDIO_DIR = tempfile.mkdtemp(prefix="crossexamine_audio_")


@app.post("/upload")
async def upload(
    files: list[UploadFile] = File(...),
    witness_statement: str = Form(...),
    num_rounds: int = Form(4),
    voice_enabled: bool = Form(True),
):
    """Upload case documents and create a session.

    Does everything synchronously: saves files, chunks them, builds the vector
    index, creates the session, returns the session ID. The frontend shows
    'INDEXING...' while this runs. For a few PDFs it takes seconds."""
    if not files:
        raise HTTPException(400, "No files uploaded")
    if not witness_statement.strip():
        raise HTTPException(400, "Witness statement is required")

    # Save uploaded files to a temp directory
    tmp_dir = tempfile.mkdtemp(prefix="crossexamine_upload_")
    saved_paths = []
    try:
        for f in files:
            file_path = os.path.join(tmp_dir, f.filename)
            with open(file_path, "wb") as out:
                content = await f.read()
                out.write(content)
            saved_paths.append(file_path)

        # Build the index
        index, source_filenames, chunk_store = ingest_documents(saved_paths)
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(400, f"Failed to process documents: {str(e)}")

    # Create session
    config = SessionConfig(num_rounds=num_rounds, voice_enabled=voice_enabled)
    session = store.create(
        index=index,
        witness_statement=witness_statement.strip(),
        source_filenames=source_filenames,
        config=config,
    )
    _chunk_stores[session.id] = chunk_store

    return {"session_id": session.id}


@app.get("/session/{session_id}/stream")
async def stream_session(session_id: str):
    """SSE endpoint — streams the entire debate as events.
    Frontend connects once and receives all token, turn_complete,
    audio, interjection_ack, and session_complete events."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    chunk_store = _chunk_stores.get(session_id, {})

    async def event_generator():
        async for event in run_debate(session, chunk_store):
            yield {"data": json.dumps(event)}

    return EventSourceResponse(event_generator())


class InterjectionRequest(BaseModel):
    text: str


@app.post("/session/{session_id}/interject")
async def interject(session_id: str, req: InterjectionRequest):
    """Submit a user interjection (judge's instruction).
    Added to the session's queue and picked up by agents.py at the
    start of the next turn."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if not req.text.strip():
        raise HTTPException(400, "Interjection text is required")

    session.interjection_queue.append(req.text.strip())
    return {"status": "queued"}


@app.get("/session/{session_id}/report")
async def get_report(session_id: str):
    """Get the vulnerability report for a completed session."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.report is None:
        raise HTTPException(409, "Report not generated yet — debate may still be running")

    # Count stats for the report metadata
    high = sum(1 for v in session.report if v.get("severity") == "high")
    medium = sum(1 for v in session.report if v.get("severity") == "medium")
    low = sum(1 for v in session.report if v.get("severity") == "low")
    conceded = sum(1 for v in session.report if v.get("conceded"))

    return {
        "vulnerabilities": session.report,
        "metadata": {
            "session_id": session_id,
            "date": __import__("datetime").date.today().isoformat(),
            "doc_count": len(session.source_filenames),
            "rounds_completed": len(session.history) // 2,
            "counts": {"high": high, "medium": medium, "low": low, "conceded": conceded},
        },
    }


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve a generated audio file. Frontend calls this after receiving
    an 'audio' SSE event with the filename."""
    file_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "Audio file not found")
    # Return the file and schedule cleanup
    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=filename,
    )
```

- [ ] **Step 2: Verify the server starts**

Run: `cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | head -5`
Expected: `INFO: Uvicorn running on http://0.0.0.0:8000`

Kill the server (Ctrl+C) after verifying.

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: FastAPI routes with SSE streaming, upload, interjection, and report endpoints"
```

---

### Task 6: Frontend — Upload Page

**Files:**
- Create: `frontend/pages/index.tsx`

- [ ] **Step 1: Implement the upload page**

`frontend/pages/index.tsx`:
```tsx
import { useState, useCallback, DragEvent } from 'react';
import { useRouter } from 'next/router';
import { uploadCase } from '@/lib/api';

export default function UploadPage() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [witness, setWitness] = useState('');
  const [rounds, setRounds] = useState(4);
  const [voiceOn, setVoiceOn] = useState(true);
  const [status, setStatus] = useState<'idle' | 'indexing' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files);
    if (dropped.length > 0) setFiles((prev) => [...prev, ...dropped]);
  }, []);

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    if (files.length === 0 || !witness.trim()) return;
    setStatus('indexing');
    setErrorMsg('');
    try {
      const { session_id } = await uploadCase(files, witness, rounds, voiceOn);
      router.push(`/session/${session_id}`);
    } catch (err: any) {
      setStatus('error');
      setErrorMsg(err.message || 'Upload failed');
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Left half — file drop */}
      <div className="flex-1 border-r border-border flex flex-col p-12">
        <div className="text-label uppercase tracking-widest text-text-muted mb-6">
          Case Documents
        </div>
        <div
          className={`flex-1 border border-border bg-bg-raised flex items-center justify-center transition-colors duration-100 ${
            dragOver ? 'border-text-dim' : ''
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => {
            const input = document.createElement('input');
            input.type = 'file';
            input.multiple = true;
            input.accept = '.pdf,.txt,.docx';
            input.onchange = (e: any) => {
              const selected = Array.from(e.target.files as FileList);
              setFiles((prev) => [...prev, ...selected]);
            };
            input.click();
          }}
        >
          <span className="text-body text-text-ghost cursor-pointer">
            drop files here
          </span>
        </div>
        {files.length > 0 && (
          <div className="mt-6">
            {files.map((f, i) => (
              <div
                key={`${f.name}-${i}`}
                className="flex justify-between items-center py-2 border-b border-border text-body text-text-dim"
              >
                <span>{f.name}</span>
                <button
                  onClick={() => removeFile(i)}
                  className="text-text-muted hover:text-attack transition-colors duration-100"
                >
                  x
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right half — inputs */}
      <div className="flex-1 p-12 flex flex-col">
        <div className="text-label uppercase tracking-widest text-text-muted mb-3">
          Witness Statement
        </div>
        <textarea
          className="flex-1 min-h-[200px] bg-bg-raised border border-border text-text-primary font-mono text-body p-4 resize-none outline-none focus:border-text-dim transition-colors duration-100"
          value={witness}
          onChange={(e) => setWitness(e.target.value)}
          placeholder="What does the witness claim happened?"
        />

        <div className="flex gap-12 mt-8 items-end">
          <div>
            <div className="text-label uppercase tracking-widest text-text-muted mb-3">
              Rounds
            </div>
            <input
              type="number"
              min={1}
              max={10}
              value={rounds}
              onChange={(e) => setRounds(Number(e.target.value))}
              className="bg-transparent border border-border text-text-primary font-mono text-body p-2 w-16 text-center outline-none focus:border-text-dim"
            />
          </div>
          <div>
            <div className="text-label uppercase tracking-widest text-text-muted mb-3">
              Voice
            </div>
            <div className="flex gap-4">
              <button
                onClick={() => setVoiceOn(true)}
                className={`text-label uppercase tracking-wider ${
                  voiceOn
                    ? 'text-text-primary border-b border-text-primary'
                    : 'text-text-muted'
                }`}
              >
                ON
              </button>
              <button
                onClick={() => setVoiceOn(false)}
                className={`text-label uppercase tracking-wider ${
                  !voiceOn
                    ? 'text-text-primary border-b border-text-primary'
                    : 'text-text-muted'
                }`}
              >
                OFF
              </button>
            </div>
          </div>
        </div>

        <div className="mt-12 flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={
              status === 'indexing' || files.length === 0 || !witness.trim()
            }
            className={`font-mono text-lg border border-transparent hover:border-border px-4 py-2 transition-colors duration-100 ${
              status === 'indexing'
                ? 'text-text-muted cursor-wait'
                : files.length === 0 || !witness.trim()
                  ? 'text-text-ghost cursor-not-allowed'
                  : 'text-text-primary cursor-pointer'
            }`}
          >
            {status === 'indexing' ? 'INDEXING...' : 'BEGIN'}
          </button>
        </div>
        {status === 'error' && (
          <div className="mt-4 text-body text-attack text-right">{errorMsg}</div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the upload page renders**

Run: `cd frontend && npm run dev`

Open `http://localhost:3000` in a browser. Verify:
- Split layout: drop zone on left, textarea + config on right
- IBM Plex Mono font
- Dark background (#0a0a0f)
- File drop works and lists files
- BEGIN button disabled until files and witness text are present

- [ ] **Step 3: Commit**

```bash
git add frontend/pages/index.tsx
git commit -m "feat: upload page with file drop, witness textarea, and config"
```

---

### Task 7: Frontend — Report Page

**Files:**
- Create: `frontend/pages/report/[id].tsx`

- [ ] **Step 1: Implement the report page**

`frontend/pages/report/[id].tsx`:
```tsx
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { fetchReport, Vulnerability, ReportMetadata } from '@/lib/api';

const SEVERITY_COLORS: Record<string, string> = {
  high: 'text-attack border-attack',
  medium: 'text-amber border-amber',
  low: 'text-low border-low',
};

const SEVERITY_BORDER: Record<string, string> = {
  high: 'border-l-attack',
  medium: 'border-l-amber',
  low: 'border-l-low',
};

export default function ReportPage() {
  const router = useRouter();
  const { id } = router.query;
  const [vulns, setVulns] = useState<Vulnerability[]>([]);
  const [meta, setMeta] = useState<ReportMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id || typeof id !== 'string') return;
    let cancelled = false;

    const poll = async () => {
      try {
        const data = await fetchReport(id);
        if (!cancelled) {
          setVulns(data.vulnerabilities);
          setMeta(data.metadata);
          setLoading(false);
        }
      } catch {
        // Report not ready yet — retry in 2s
        if (!cancelled) setTimeout(poll, 2000);
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [id]);

  const copyJSON = () => {
    navigator.clipboard.writeText(JSON.stringify(vulns, null, 2));
  };

  const exportPDF = async () => {
    const { jsPDF } = await import('jspdf');
    const doc = new jsPDF({ unit: 'mm', format: 'a4' });
    const margin = 20;
    let y = margin;
    const pageWidth = doc.internal.pageSize.getWidth();
    const contentWidth = pageWidth - margin * 2;

    doc.setFont('courier', 'bold');
    doc.setFontSize(16);
    doc.text('VULNERABILITY REPORT', margin, y);
    y += 8;

    if (meta) {
      doc.setFont('courier', 'normal');
      doc.setFontSize(8);
      doc.text(
        `Session ${meta.session_id} | ${meta.date} | ${meta.doc_count} docs | ${meta.rounds_completed} rounds`,
        margin,
        y,
      );
      y += 10;
    }

    doc.setDrawColor(100);
    doc.line(margin, y, pageWidth - margin, y);
    y += 8;

    for (const v of vulns) {
      // Check if we need a new page
      if (y > 260) {
        doc.addPage();
        y = margin;
      }

      doc.setFont('courier', 'bold');
      doc.setFontSize(10);
      doc.text(`[${v.severity.toUpperCase()}]${v.conceded ? '  CONCEDED BY DEFENSE' : ''}`, margin, y);
      y += 6;

      const fields = [
        ['CLAIM', v.claim],
        ['CONTRADICTION', v.contradiction],
        ['SOURCE', v.source],
        ['WHY IT MATTERS', v.explanation],
      ];

      for (const [label, value] of fields) {
        doc.setFont('courier', 'bold');
        doc.setFontSize(7);
        doc.text(label, margin, y);
        y += 4;
        doc.setFont('courier', 'normal');
        doc.setFontSize(9);
        const lines = doc.splitTextToSize(value, contentWidth);
        doc.text(lines, margin, y);
        y += lines.length * 4 + 2;
      }
      y += 6;
    }

    doc.save('vulnerability-report.pdf');
  };

  if (loading) {
    return (
      <div className="p-12">
        <span className="text-body text-text-muted">LOADING</span>
      </div>
    );
  }

  const counts = {
    high: vulns.filter((v) => v.severity === 'high').length,
    medium: vulns.filter((v) => v.severity === 'medium').length,
    low: vulns.filter((v) => v.severity === 'low').length,
    conceded: vulns.filter((v) => v.conceded).length,
  };

  return (
    <div className="p-12 max-w-[960px]">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div className="text-[32px] font-medium tracking-wider">
          VULNERABILITY REPORT
        </div>
        <div className="flex gap-3 pt-2">
          <button
            onClick={copyJSON}
            className="text-label uppercase tracking-widest text-text-muted border border-border px-4 py-2 hover:text-text-primary hover:border-text-dim transition-colors duration-100"
          >
            COPY JSON
          </button>
          <button
            onClick={exportPDF}
            className="text-label uppercase tracking-widest text-text-muted border border-border px-4 py-2 hover:text-text-primary hover:border-text-dim transition-colors duration-100"
          >
            EXPORT PDF
          </button>
        </div>
      </div>

      {meta && (
        <div className="text-label uppercase tracking-wider text-text-ghost mt-3">
          Session {meta.session_id} &bull; {meta.date} &bull;{' '}
          {meta.doc_count} documents &bull; {meta.rounds_completed} rounds
        </div>
      )}

      <hr className="border-border mt-8 mb-8" />

      {/* Summary line */}
      <div className="text-label uppercase tracking-wider text-text-muted mb-12 flex items-center gap-1.5">
        <span>HIGH: <span className="text-attack font-semibold">{counts.high}</span></span>
        <span className="text-text-ghost">&bull;</span>
        <span>MEDIUM: <span className="text-amber font-semibold">{counts.medium}</span></span>
        <span className="text-text-ghost">&bull;</span>
        <span>LOW: <span className="text-low font-semibold">{counts.low}</span></span>
        <span className="text-text-ghost">&bull;</span>
        <span>CONCEDED: <span className="text-amber font-semibold">{counts.conceded}</span></span>
      </div>

      {/* Vulnerability list */}
      {vulns.map((v, i) => (
        <div
          key={i}
          className={`mb-10 pl-4 border-l-2 ${SEVERITY_BORDER[v.severity]}`}
        >
          {/* Header line */}
          <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
            <div className="flex items-center gap-4">
              <span
                className={`text-label uppercase tracking-widest font-semibold ${
                  SEVERITY_COLORS[v.severity]?.split(' ')[0]
                }`}
              >
                {v.severity.toUpperCase()}
              </span>
            </div>
            {v.conceded && (
              <span className="text-label uppercase tracking-wider text-amber">
                CONCEDED BY DEFENSE
              </span>
            )}
          </div>

          {/* Fields */}
          <VulnField label="CLAIM" value={v.claim} />
          <VulnField label="CONTRADICTION" value={v.contradiction} />
          <VulnField label="SOURCE" value={v.source} />
          <VulnField label="WHY IT MATTERS" value={v.explanation} />
        </div>
      ))}

      {vulns.length === 0 && (
        <div className="text-body text-text-muted">
          No vulnerabilities found. The witness account survived adversarial scrutiny.
        </div>
      )}
    </div>
  );
}

function VulnField({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-2.5">
      <div className="text-label uppercase tracking-widest text-text-muted mb-1">
        {label}
      </div>
      <div className="text-body text-[#bbb]">{value}</div>
    </div>
  );
}
```

- [ ] **Step 2: Verify report page renders with mock data**

Start the dev server if not running: `cd frontend && npm run dev`

Visit `http://localhost:3000/report/test` — should show "LOADING" text (no backend running). Visual structure is correct when data arrives. We'll do full integration testing after the session arena.

- [ ] **Step 3: Commit**

```bash
git add frontend/pages/report/
git commit -m "feat: vulnerability report page with PDF export and JSON copy"
```

---

### Task 8: Frontend — Session Arena

**Files:**
- Create: `frontend/pages/session/[id].tsx`

This is the most complex frontend page: SSE rendering, audio queuing, interjection input, live status bar.

- [ ] **Step 1: Implement the session arena**

`frontend/pages/session/[id].tsx`:
```tsx
import { useRouter } from 'next/router';
import { useEffect, useRef, useState } from 'react';
import { API_URL, submitInterjection, SSEEvent } from '@/lib/api';

// Unified timeline — turns and interjections in the order SSE delivers them.
// This is what the spec means by "interjections rendered between rounds."
type TimelineItem =
  | { kind: 'turn'; agent: 'attack' | 'defense'; round: number; text: string; complete: boolean }
  | { kind: 'interjection'; text: string };

export default function SessionPage() {
  const router = useRouter();
  const { id } = router.query;

  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [interjectText, setInterjectText] = useState('');
  const [sessionDone, setSessionDone] = useState(false);
  const [doneReason, setDoneReason] = useState('');
  const [currentRound, setCurrentRound] = useState(0);

  const audioQueue = useRef<string[]>([]);
  const isPlaying = useRef(false);
  const debateEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom as debate progresses
  useEffect(() => {
    debateEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [timeline]);

  // SSE connection
  useEffect(() => {
    if (!id || typeof id !== 'string') return;

    const source = new EventSource(`${API_URL}/session/${id}/stream`);

    source.onmessage = (e) => {
      const event: SSEEvent = JSON.parse(e.data);

      switch (event.type) {
        case 'token': {
          setTimeline((prev) => {
            const last = prev[prev.length - 1];
            // First token of a new turn — create it.
            // The cursor appears here (spec: "first token event for a new
            // agent+round combination").
            if (
              !last ||
              last.kind !== 'turn' ||
              last.complete ||
              last.agent !== event.agent ||
              last.round !== event.round
            ) {
              return [
                ...prev,
                {
                  kind: 'turn',
                  agent: event.agent!,
                  round: event.round!,
                  text: event.text || '',
                  complete: false,
                },
              ];
            }
            // Append to existing turn
            const updated = [...prev];
            const lastTurn = updated[updated.length - 1] as Extract<TimelineItem, { kind: 'turn' }>;
            updated[updated.length - 1] = {
              ...lastTurn,
              text: lastTurn.text + (event.text || ''),
            };
            return updated;
          });
          if (event.round) setCurrentRound(event.round);
          break;
        }

        case 'turn_complete': {
          setTimeline((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.kind === 'turn') {
              updated[updated.length - 1] = { ...last, complete: true };
            }
            return updated;
          });
          break;
        }

        case 'audio': {
          if (event.file) {
            audioQueue.current.push(`${API_URL}/audio/${event.file}`);
            playNextAudio();
          }
          break;
        }

        case 'audio_failed':
          break;

        case 'interjection_ack': {
          if (event.text) {
            // Append interjection to timeline in order — it naturally
            // appears between the turns where it was injected.
            setTimeline((prev) => [
              ...prev,
              { kind: 'interjection', text: event.text! },
            ]);
          }
          break;
        }

        case 'session_complete': {
          setSessionDone(true);
          setDoneReason(
            event.reason === 'exhausted'
              ? 'The attacking agent exhausted its documentary ammunition.'
              : 'All rounds completed.',
          );
          source.close();
          break;
        }
      }
    };

    source.onerror = () => {
      source.close();
    };

    return () => source.close();
  }, [id]);

  const playNextAudio = () => {
    if (isPlaying.current || audioQueue.current.length === 0) return;
    isPlaying.current = true;
    const url = audioQueue.current.shift()!;
    const audio = new Audio(url);
    audio.onended = () => {
      isPlaying.current = false;
      playNextAudio();
    };
    audio.onerror = () => {
      isPlaying.current = false;
      playNextAudio();
    };
    audio.play().catch(() => {
      isPlaying.current = false;
      playNextAudio();
    });
  };

  const handleInterject = async () => {
    if (!interjectText.trim() || !id || typeof id !== 'string') return;
    try {
      await submitInterjection(id, interjectText);
      setInterjectText('');
    } catch {
      // Silently fail — interjection is best-effort
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleInterject();
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Status bar */}
      <div className="px-12 py-4 border-b border-border text-label uppercase tracking-wider text-text-muted flex items-center gap-1.5">
        <span>ROUND <span className="text-text-dim">{currentRound} / ?</span></span>
        {sessionDone && (
          <>
            <span className="text-text-ghost">&bull;</span>
            <span className="text-text-dim">COMPLETE</span>
          </>
        )}
      </div>

      {/* Debate stream — unified timeline of turns and interjections */}
      <div className="flex-1 overflow-y-auto px-12 py-8 max-w-[960px] w-full">
        {timeline.map((item, i) => {
          if (item.kind === 'interjection') {
            return (
              <div key={i} className="mb-8 pl-4 border-l-2 border-l-amber">
                <div className="text-label uppercase tracking-widest text-amber mb-2">
                  JUDGE'S INSTRUCTION
                </div>
                <div className="text-reading text-amber italic">
                  {item.text}
                </div>
              </div>
            );
          }

          const turn = item;
          return (
            <div
              key={i}
              className={`mb-8 pl-4 border-l-2 ${
                turn.agent === 'attack'
                  ? 'border-l-attack'
                  : 'border-l-defense'
              }`}
            >
              <div className="flex justify-between items-center mb-2">
                <div
                  className={`text-label uppercase tracking-widest flex items-center gap-2 ${
                    turn.agent === 'attack' ? 'text-attack' : 'text-defense'
                  }`}
                >
                  <span
                    className={`inline-block w-1.5 h-1.5 rounded-full ${
                      !turn.complete
                        ? `${turn.agent === 'attack' ? 'bg-attack' : 'bg-defense'} animate-pulse-dot`
                        : 'bg-text-ghost'
                    }`}
                  />
                  {turn.agent.toUpperCase()} — ROUND {turn.round}
                  {!turn.complete && (
                    <span className="text-text-muted ml-2">speaking</span>
                  )}
                </div>
              </div>
              <div className="text-reading text-[#ccc]">
                {turn.text}
                {!turn.complete && (
                  <span className="inline-block w-px h-3.5 bg-current ml-0.5 align-text-bottom animate-blink" />
                )}
              </div>
            </div>
          );
        })}

        {/* Session complete message */}
        {sessionDone && (
          <div className="mb-8 pt-4 border-t border-border">
            <div className="text-body text-text-muted">{doneReason}</div>
            <button
              onClick={() => router.push(`/report/${id}`)}
              className="mt-4 text-label uppercase tracking-widest text-text-muted border border-border px-4 py-2 hover:text-text-primary hover:border-text-dim transition-colors duration-100"
            >
              VIEW REPORT
            </button>
          </div>
        )}

        <div ref={debateEndRef} />
      </div>

      {/* Interjection bar */}
      {!sessionDone && (
        <div className="border-t border-border px-12 py-4 flex gap-4 items-center">
          <input
            type="text"
            value={interjectText}
            onChange={(e) => setInterjectText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Interject as judge..."
            className="flex-1 bg-transparent border border-border text-text-primary font-mono text-body px-4 py-2.5 outline-none placeholder:text-text-ghost focus:border-text-dim transition-colors duration-100"
          />
          <button
            onClick={handleInterject}
            className="text-label uppercase tracking-widest text-text-muted border border-border px-5 py-2.5 hover:text-text-primary hover:border-text-dim transition-colors duration-100"
          >
            SUBMIT
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify session arena renders**

With both backend and frontend dev servers running:

1. Start backend: `cd backend && python -m uvicorn main:app --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:3000`
4. Upload `backend/tests/fixtures/sample_report.txt`
5. Enter a witness statement (e.g., "The witness states she arrived at 8:15 PM and saw the defendant run a red light in a dark blue sedan traveling at high speed.")
6. Click BEGIN
7. Verify: session arena loads, SSE events stream in, text appears with typing cursor, turns show Attack/Defense labels with colored borders, status bar updates

- [ ] **Step 3: Commit**

```bash
git add frontend/pages/session/
git commit -m "feat: session arena with SSE streaming, audio queue, and interjection input"
```

---

### Task 9: Voice Integration

**Files:**
- Create: `backend/voice.py`

- [ ] **Step 1: Implement voice.py**

`backend/voice.py`:
```python
"""ElevenLabs TTS wrapper for CrossExamine.

Generates audio for agent turns. Returns filenames that main.py serves
via GET /audio/{filename}. Voice is optional — if ElevenLabs isn't
configured, everything works without audio.
"""

import os
import tempfile
from pathlib import Path

# Audio files go here. main.py also knows this path.
AUDIO_DIR = tempfile.mkdtemp(prefix="crossexamine_audio_")

# Voice IDs from env vars — no hardcoded values
_VOICE_IDS = {
    "attack": os.environ.get("ELEVEN_ATTACK_VOICE_ID"),
    "defense": os.environ.get("ELEVEN_DEFENSE_VOICE_ID"),
}
_API_KEY = os.environ.get("ELEVENLABS_API_KEY")


async def generate_audio(text: str, agent: str) -> str | None:
    """Generate TTS audio for an agent's turn.

    Returns the filename (not full path) on success, None on failure.
    The file is saved to AUDIO_DIR, which main.py serves statically.

    Returns None (silently, no crash) if:
    - ElevenLabs API key isn't set
    - Voice ID for this agent isn't configured
    - The API call fails for any reason
    """
    if not _API_KEY or not _VOICE_IDS.get(agent):
        return None

    try:
        from elevenlabs import AsyncElevenLabs

        client = AsyncElevenLabs(api_key=_API_KEY)
        audio_generator = await client.text_to_speech.convert(
            voice_id=_VOICE_IDS[agent],
            text=text,
            model_id="eleven_monolingual_v1",
            output_format="mp3_44100_128",
        )

        # Save to temp file
        filename = f"turn-{agent}-{os.urandom(4).hex()}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)

        # audio_generator is an async iterator of bytes
        with open(filepath, "wb") as f:
            async for chunk in audio_generator:
                f.write(chunk)

        return filename
    except Exception:
        # Voice is nice-to-have. If anything goes wrong, return None
        # and the debate continues without audio.
        return None


def cleanup_audio_file(filename: str) -> None:
    """Delete a temp audio file after it's been served."""
    filepath = os.path.join(AUDIO_DIR, filename)
    try:
        os.unlink(filepath)
    except OSError:
        pass


def cleanup_session_audio() -> None:
    """Delete all temp audio files. Called on session teardown."""
    for f in os.listdir(AUDIO_DIR):
        try:
            os.unlink(os.path.join(AUDIO_DIR, f))
        except OSError:
            pass
```

- [ ] **Step 2: Update main.py to use voice.py's AUDIO_DIR**

In `backend/main.py`, replace the AUDIO_DIR line:

Change:
```python
AUDIO_DIR = tempfile.mkdtemp(prefix="crossexamine_audio_")
```

To:
```python
from voice import AUDIO_DIR
```

Keep the `import tempfile` line — it's still used for the upload temp directory in the upload endpoint.

- [ ] **Step 3: Verify voice integration**

If you have ElevenLabs credentials, test by setting the env vars and running a session. If not, verify that sessions work without voice (all turns should send `audio_failed` events).

Run: `cd backend && python -c "from voice import generate_audio; print('voice module loads OK')"`
Expected: `voice module loads OK`

- [ ] **Step 4: Commit**

```bash
git add backend/voice.py
git add backend/main.py
git commit -m "feat: ElevenLabs voice integration with graceful fallback"
```

---

### Task 10: End-to-End Smoke Test and Polish

**Files:**
- Modify: `backend/main.py` (minor fixes from integration testing)
- Modify: `frontend/pages/session/[id].tsx` (minor fixes from integration testing)

- [ ] **Step 1: Start both servers**

Terminal 1: `cd backend && python -m uvicorn main:app --port 8000 --reload`
Terminal 2: `cd frontend && npm run dev`

- [ ] **Step 2: Run full flow**

1. Open `http://localhost:3000`
2. Upload `backend/tests/fixtures/sample_report.txt`
3. Enter witness statement: "The witness states she arrived at the intersection of 5th and Main at approximately 8:15 PM when she observed the defendant's vehicle run a red light and strike the pedestrian. She describes the vehicle as a dark blue sedan traveling at high speed northbound."
4. Set rounds to 3, voice OFF
5. Click BEGIN
6. Watch the debate stream — verify Attack and Defense alternate, cite the document, and argue
7. After completion, click VIEW REPORT
8. Verify the vulnerability report renders with severity-sorted items
9. Test COPY JSON — paste into a text editor, verify valid JSON
10. Test EXPORT PDF — verify PDF downloads with report content

- [ ] **Step 3: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 4: Fix any issues found during smoke test**

Address any rendering issues, SSE event handling bugs, or error states discovered during the end-to-end test. Common issues to check:
- Status bar round counter updating correctly
- Interjection rendering in the correct position in the debate
- Report page handles the case where debate is still running (shows LOADING)
- Audio queue doesn't block text rendering
- Session arena scrolls to bottom as new turns arrive

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: end-to-end smoke test fixes and polish"
```

---

## Quick Reference: Running the App

```bash
# Backend
cd backend
pip install -r requirements.txt
# Set env vars:
export ANTHROPIC_API_KEY=your_key
# Optional for voice:
export ELEVENLABS_API_KEY=your_key
export ELEVEN_ATTACK_VOICE_ID=voice_id
export ELEVEN_DEFENSE_VOICE_ID=voice_id
python -m uvicorn main:app --port 8000 --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# Opens on http://localhost:3000
```

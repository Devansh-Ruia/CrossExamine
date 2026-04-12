# CrossExamine

Adversarial AI agents cross-examine witness testimony against case documents. An attack agent finds contradictions; a defense agent rehabilitates the testimony. A final summarizer produces a severity-ranked vulnerability report.

## How it works

1. Upload case documents (PDF, TXT, DOCX) and a witness statement.
2. Documents are chunked, embedded (HuggingFace BGE), and indexed for retrieval.
3. Two LLM agents (Groq / Llama 3.3 70B) debate in alternating rounds:
   - **Attack** -- cites document passages that contradict the testimony.
   - **Defense** -- finds supporting evidence or concedes indefensible points.
4. A judge can interject mid-debate to redirect either agent.
5. The debate ends after all rounds or when the attack runs out of new evidence.
6. A summarizer agent produces a vulnerability report with severity ratings.

The full debate streams to the browser in real time via SSE. Optional ElevenLabs voice gives each agent a distinct voice.

## Tech stack

| Layer    | Tech                                                    |
|----------|---------------------------------------------------------|
| Backend  | FastAPI, Groq SDK, LlamaIndex, HuggingFace embeddings  |
| Frontend | Next.js 14, TypeScript, Tailwind CSS                    |
| Voice    | ElevenLabs TTS (optional)                               |
| Model    | llama-3.3-70b-versatile via Groq                        |

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Groq API key](https://console.groq.com)
- (Optional) An [ElevenLabs API key](https://elevenlabs.io) for voice

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```
GROQ_API_KEY=gsk_...
ELEVENLABS_API_KEY=...          # optional
ELEVEN_ATTACK_VOICE_ID=...      # optional
ELEVEN_DEFENSE_VOICE_ID=...     # optional
```

The first run downloads the embedding model (~130 MB).

```bash
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## API routes

| Method | Path                              | Description                        |
|--------|-----------------------------------|------------------------------------|
| POST   | `/upload`                         | Upload files + witness statement   |
| GET    | `/session/{id}/stream`            | SSE stream of the debate           |
| POST   | `/session/{id}/interject`         | Submit a judge interjection        |
| GET    | `/session/{id}/report`            | Fetch the vulnerability report     |
| GET    | `/audio/{filename}`               | Serve generated audio files        |

## Project structure

```
backend/
  main.py           FastAPI routes and SSE streaming
  agents.py         Attack/defense agents and debate loop
  session.py        In-memory session state
  ingest.py         Document chunking, embedding, retrieval
  voice.py          ElevenLabs TTS integration
  tests/            pytest suite

frontend/
  pages/
    index.tsx       Upload page (files + witness statement)
    session/[id]    Live debate viewer with judge input
    report/[id]     Vulnerability report with PDF export
  lib/api.ts        API client and shared types
```

## Tests

```bash
cd backend
pytest
```

## Notes

- Sessions are stored in memory. Restarting the backend clears all state.
- Groq free tier has rate limits. The backend adds pauses between agent turns.
- If ElevenLabs is not configured, the app works without voice.
- The debate terminates early if the attack agent fails to cite new evidence for two consecutive rounds.

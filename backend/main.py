"""FastAPI app for CrossExamine.

Thin routing layer -- all the interesting logic lives in agents.py, ingest.py,
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

# CORS -- Next.js dev server runs on :3000, FastAPI on :8000.
# Without this, every frontend fetch silently fails.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = SessionStore()
_chunk_stores: dict[str, dict] = {}

from voice import AUDIO_DIR


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
    'INDEXING...' while this runs."""
    if not files:
        raise HTTPException(400, "No files uploaded")
    if not witness_statement.strip():
        raise HTTPException(400, "Witness statement is required")

    tmp_dir = tempfile.mkdtemp(prefix="crossexamine_upload_")
    saved_paths = []
    try:
        for f in files:
            file_path = os.path.join(tmp_dir, f.filename)
            with open(file_path, "wb") as out:
                content = await f.read()
                out.write(content)
            saved_paths.append(file_path)

        index, source_filenames, chunk_store = ingest_documents(saved_paths)
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(400, f"Failed to process documents: {str(e)}")

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
    """SSE endpoint -- streams the entire debate as events."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    chunk_store = _chunk_stores.get(session_id, {})

    async def event_generator():
        yield {"data": json.dumps({
            "type": "session_config",
            "num_rounds": session.config.num_rounds,
            "session_id": session.id,
        })}
        async for event in run_debate(session, chunk_store):
            yield {"data": json.dumps(event)}

    return EventSourceResponse(event_generator())


class InterjectionRequest(BaseModel):
    text: str


@app.post("/session/{session_id}/interject")
async def interject(session_id: str, req: InterjectionRequest):
    """Submit a user interjection (judge's instruction)."""
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
    if session.status == "running":
        raise HTTPException(409, "debate still in progress")
    if session.status == "generating_report":
        raise HTTPException(409, "report is being generated, try again in a moment")
    if session.status == "failed":
        raise HTTPException(
            status_code=500,
            detail="report generation failed — check backend logs",
        )
    if session.report is None:
        raise HTTPException(500, "report generation failed")

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
    """Serve a generated audio file."""
    file_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "Audio file not found")
    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=filename,
    )

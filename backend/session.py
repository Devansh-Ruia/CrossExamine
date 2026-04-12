"""In-memory session state for CrossExamine.

Each session holds everything needed for a debate: the vector index,
conversation history, interjection queue, and cited chunks tracking.
No database, no persistence -- this is a hackathon.
"""

import uuid
from dataclasses import dataclass, field

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
        """Return the last N turns. We intentionally window this -- agents get
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
        """Get the actual text/metadata for all cited chunks."""
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

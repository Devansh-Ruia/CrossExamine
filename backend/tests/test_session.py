import pytest
from session import Session, SessionStore, SessionConfig


def test_create_session():
    store = SessionStore()
    session = store.create(
        index=None,
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
    assert session.interjection_queue == []
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
    store = SessionStore()
    session = store.create(
        index=None,
        witness_statement="test",
        source_filenames=[],
        config=SessionConfig(),
    )
    for i in range(12):
        agent = "attack" if i % 2 == 0 else "defense"
        session.add_to_history(agent, f"Turn {i}")

    recent = session.get_recent_history(max_turns=8)
    assert len(recent) == 8
    assert recent[0]["content"] == "Turn 4"
    assert recent[-1]["content"] == "Turn 11"


def test_get_recent_history_short():
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
    assert session.response_has_citation(
        "According to police-report-2024.pdf on page 3, the time was 7:52 PM."
    )
    assert session.response_has_citation(
        "The POLICE-REPORT-2024.PDF clearly states..."
    )
    assert not session.response_has_citation(
        "I don't have documentary support for this line of attack."
    )
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
    assert "chunk_1" in session.cited_chunks
    assert "chunk_2" in session.cited_chunks
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
    assert len(session.cited_chunks) == 0

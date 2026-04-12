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
    index, _, _ = ingest_documents([SAMPLE_REPORT])
    relevant = retrieve_chunks(index, "traffic signal status power outage", top_k=1)
    irrelevant = retrieve_chunks(index, "quantum physics spacetime warp drive", top_k=1)
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

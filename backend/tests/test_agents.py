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
    assert "no strong documentary evidence" in msg.lower() or \
           "no relevant passages" in msg.lower()


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

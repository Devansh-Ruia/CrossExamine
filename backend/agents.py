"""Core agent system for CrossExamine.

Two agent functions (attack, defense) and the debate loop that orchestrates them.
This module owns both the agents AND the loop -- keeping the core logic in one place.
"""

import asyncio
import json
import os
from groq import AsyncGroq
from ingest import retrieve_chunks, chunks_above_threshold, format_chunk_for_context
from session import Session

_client = AsyncGroq()  # reads GROQ_API_KEY from env automatically
MODEL = "gemma2-9b-it"
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
    """Build the user message sent to Claude for an agent turn."""
    parts = []

    parts.append(f"WITNESS STATEMENT:\n{witness_statement}")

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

    if history:
        formatted_history = []
        for turn in history:
            label = turn["agent"].upper()
            formatted_history.append(f"{label}: {turn['content']}")
        parts.append(
            "CONVERSATION SO FAR:\n" + "\n\n".join(formatted_history)
        )

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
    Case-insensitive substring match."""
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

    Hack: since Python async generators can't 'return' a value, we use
    the turn_complete event to carry the full_text. The caller pops it
    off the event before yielding to the frontend."""
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

    # HACK: Groq free tier has limited context window. If the assembled message
    # is too large, trim retrieved chunks from 5 to 3 to stay under the limit.
    # Uses len(content)/4 as a rough char-to-token estimate — not a real tokenizer.
    rough_tokens = len(system_prompt + user_message) / 4
    if rough_tokens > 6000 and chunks:
        user_message = build_user_message(
            witness_statement=witness_statement,
            chunks=chunks[:3],
            history=history,
            interjections=interjections,
            retrieval_has_results=retrieval_has_results,
        )

    full_text = ""
    stream = await _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=MAX_TOKENS,
        stream=True,
    )
    async for chunk in stream:
        text = chunk.choices[0].delta.content
        if text:  # delta.content is None on the final chunk, skip it
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
    """Final summarizer call after the debate ends."""
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

    response = await asyncio.wait_for(
        _client.chat.completions.create(
            model=MODEL,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SUMMARIZER_PROMPT},
                {"role": "user", "content": user_message},
            ],
        ),
        timeout=60.0,
    )

    raw_text = response.choices[0].message.content.strip()
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
    """Run the full debate loop. Async generator that yields SSE event dicts."""
    last_defense_text = ""
    previous_cited_count = len(session.cited_chunks)

    for round_num in range(1, session.config.num_rounds + 1):
        # 1. Drain interjections before attack turn
        interjections = session.drain_interjections()
        if interjections:
            for text in interjections:
                yield {"type": "interjection_ack", "text": text}

        # 2. Attack turn
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

        # Audio for attack turn
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

        # small pause so groq doesn't 429 on back-to-back requests
        await asyncio.sleep(5)

        # 3. Drain interjections before defense turn
        interjections = session.drain_interjections()
        if interjections:
            for text in interjections:
                yield {"type": "interjection_ack", "text": text}

        # 4. Defense turn
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

        # small pause so groq doesn't 429 on back-to-back requests
        await asyncio.sleep(5)

        # 5. Early termination check
        current_cited_count = len(session.cited_chunks)
        if current_cited_count == previous_cited_count:
            session.attack_dry_rounds += 1
        else:
            session.attack_dry_rounds = 0
        previous_cited_count = current_cited_count

        if session.attack_dry_rounds >= 2:
            reason = "exhausted"
            break
    else:
        reason = "all_rounds"

    # Generate vulnerability report BEFORE signaling completion
    yield {"type": "status", "message": "generating vulnerability report..."}
    session.status = "generating_report"
    print("starting report generation for session", session.id)
    try:
        report = await generate_report(session, chunk_store)
        session.report = report
        session.status = "complete"
        print("report generation complete for session", session.id)
    except asyncio.TimeoutError:
        print("report generation timed out for session", session.id)
        session.status = "failed"
    except Exception as e:
        print("report generation failed:", str(e), "session:", session.id)
        session.status = "failed"

    yield {"type": "session_complete", "reason": reason}

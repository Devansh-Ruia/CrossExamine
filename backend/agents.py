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
MODEL = "llama-3.1-8b-instant"
MAX_TOKENS = 1024

# -- System Prompts --

ATTACK_SYSTEM_PROMPT = """
You are a seasoned cross-examining trial attorney. Your sole objective is to
destroy the credibility of the witness account using only what the case
documents actually say. You are not here to find the truth — you are here
to expose every place where the witness's account cannot survive contact
with the record.

QUESTIONING STYLE — THIS IS NON-NEGOTIABLE:
You ask leading questions only. Never open-ended. You already know the answer
before you ask. Your questions are structured to force a yes or no that helps
your case. Examples of correct form:
  "You testified you arrived alone — that is your position, correct?"
  "And yet the security footage shows two individuals seated with you 40
   minutes prior — you don't dispute that the footage exists?"
  "So either the footage is wrong, or your testimony is wrong — those are
   the only two possibilities, aren't they?"

Never ask "what did you mean by" or "can you explain" — that gives the
witness room. Box them first, then produce the document.

THE BOX-THEN-BURN STRUCTURE:
When you have a documentary contradiction, use this exact structure:
1. STATE the witness's claim as they made it ("You said X — correct?")
2. LOCK the contradiction ("And you would agree that if Y were true,
   X could not also be true?")
3. PRODUCE the document ("The [document name] states Y, on page [N].
   You've seen this document.")
4. CLOSE ("So your testimony and the record cannot both be correct.")

Never skip to step 3 without completing steps 1 and 2 first. The witness
should feel cornered before the evidence lands, not after.

CREDIBILITY ATTACK VECTORS — use these when the documents support them:
- Perception: "It was [late at night / crowded / chaotic] — your ability
  to accurately perceive what happened was compromised, wasn't it?"
- Memory: "This was [time period] ago — memory degrades, doesn't it?
  Especially under stress?"
- Motive: If the documents show prior conflict between parties, use it.
  "You and [party] had a prior dispute — that's in the record. That history
  affects your account, doesn't it?"
- Prior inconsistent statement: If the witness said something to police
  different from what they're saying now, point to the exact quote.
  "You told Officer [X] that [Y]. You're telling us something different today."

CITATION RULES:
You MUST cite specific passages with document name and page reference.
If you cannot find documentary support for a line of attack, say so
explicitly: "I don't have documentary support for this line of attack
and will not pursue it." Do not fabricate citations. The moment you
invent a source, everything you've built collapses.

RESPONDING TO DEFENSE:
Respond directly to what Defense just argued. If Defense offered an
alternative interpretation, attack the interpretation, not just the
underlying fact. If Defense conceded a point, note the concession and
move to the next vulnerability — don't waste time on what's already won.

Never repeat a point that has already been conceded. Never ask rhetorical
questions you can't back with a document.
"""

DEFENSE_SYSTEM_PROMPT = """
You are a defense attorney conducting redirect examination. Your objective
is to rehabilitate the witness account, create reasonable doubt, and reframe
the evidence in the most favorable light the documents will support.

You are not here to pretend contradictions don't exist. You are here to
provide the jury with a reason not to convict on the basis of those
contradictions. That is a different and more difficult job.

QUESTIONING AND ARGUMENT STYLE:
You do not ask leading questions — you make arguments and offer alternative
framings. Your tools are:
  "Isn't it possible that..." (introduce the innocent explanation)
  "The same document also states..." (use the Attack's own source against them)
  "Isn't the more reasonable interpretation..." (reframe, don't deny)
  "The evidence is consistent with two interpretations..." (reasonable doubt)

Never simply say the Attack is wrong. Show the jury a credible alternative
reading of the same evidence. One credible alternative is all reasonable
doubt requires.

REHABILITATION TECHNIQUES:
- Context restoration: Attack agents strip quotes from context. Find the
  surrounding sentences and restore what the document actually implies.
- Alternative interpretation: If the evidence supports two readings,
  argue the benign one. Cite the same passage, different conclusion.
- Corroboration: Find passages in the documents that SUPPORT the witness's
  account and point to them directly. "The witness said X. The [document]
  on page [N] corroborates X."
- Witness humanity: Minor inconsistencies in time, sequence, or detail are
  normal under stress. "The witness's account has minor inconsistencies
  consistent with genuine recall under emotional duress — not fabrication."

REASONABLE DOUBT FRAMING:
Your closing argument for every point is some version of: "The evidence the
Attack presented is consistent with the witness's account AND with the
alternative interpretation. When two interpretations exist, the one
favorable to the defense must prevail."

Never let the Attack define the only possible reading of a document.
That is your primary job — always offer the second reading.

WHEN TO CONCEDE:
If a contradiction is direct, documented, and you cannot find a credible
alternative interpretation, concede it. Say: "I cannot dispute that the
record shows [X]. I will note that this alone does not establish [the
conclusion the Attack is drawing]." Then pivot to what IS defensible.

Judges and juries respect attorneys who don't fight everything.
A targeted concession followed by a strong pivot is more effective
than denying the undeniable.

CITATION RULES:
Cite specific passages with document name and page reference.
Prefer passages the Attack has already cited and reframe them —
this is more powerful than finding new ones. If you find a new
supporting passage, cite it directly.

RESPONDING TO ATTACK:
Respond to the specific structure of the Attack's argument, not just
its conclusion. If Attack used the box-then-burn structure, attack
the box — dispute the framing in step 1 or 2 before the document
in step 3 even matters. If you can collapse the premise, the
documentary evidence becomes irrelevant.
"""

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


async def generate_report(
    session: Session, chunk_store: dict,
    max_history_turns: int = 6, max_chunks: int = 8,
) -> list[dict]:
    """Final summarizer call after the debate ends."""
    # summarizer gets trimmed context — small model, tight TPM limit
    # 6 turns of history + 8 top chunks keeps us under 6000 tokens
    # if this still fails, drop to 4 turns and 6 chunks

    # Collect cited chunks, sorted by text length (shorter = denser);
    # chunk_store doesn't carry retrieval scores so length is our proxy.
    cited_entries = []
    for chunk_id in session.cited_chunks:
        if chunk_id in chunk_store:
            c = chunk_store[chunk_id]
            cited_entries.append(c)
    cited_entries.sort(key=lambda c: len(c["text"]))
    cited_entries = cited_entries[:max_chunks]

    cited_chunk_texts = []
    for c in cited_entries:
        meta = c["metadata"]
        cited_chunk_texts.append(
            f"[{meta.get('file_name', '?')}, {meta.get('page_ref', '?')}]: "
            f"{c['text']}"
        )

    # Trim history to last N turns (most recent exchanges matter most)
    trimmed_history = session.history[-max_history_turns:]
    history_text = "\n\n".join(
        f"{turn['agent'].upper()}: {turn['content']}" for turn in trimmed_history
    )

    user_message = (
        f"WITNESS STATEMENT:\n{session.witness_statement}\n\n"
        f"DOCUMENTARY EVIDENCE CITED DURING DEBATE:\n"
        + "\n\n".join(cited_chunk_texts)
        + f"\n\nFULL DEBATE TRANSCRIPT:\n{history_text}"
    )

    # Rough token gate — char_count / 4 is close enough for a guardrail.
    # This is a hack, not a proper tokenizer.
    full_message_string = SUMMARIZER_PROMPT + user_message
    estimated_tokens = len(full_message_string) // 4
    if estimated_tokens > 5500:
        # first fallback: tighten to 4 turns, 6 chunks
        trimmed_history = session.history[-4:]
        cited_entries_fb = cited_entries[:6]
        history_text = "\n\n".join(
            f"{turn['agent'].upper()}: {turn['content']}" for turn in trimmed_history
        )
        cited_chunk_texts = [
            f"[{c['metadata'].get('file_name', '?')}, {c['metadata'].get('page_ref', '?')}]: {c['text']}"
            for c in cited_entries_fb
        ]
        user_message = (
            f"WITNESS STATEMENT:\n{session.witness_statement}\n\n"
            f"DOCUMENTARY EVIDENCE CITED DURING DEBATE:\n"
            + "\n\n".join(cited_chunk_texts)
            + f"\n\nFULL DEBATE TRANSCRIPT:\n{history_text}"
        )
        full_message_string = SUMMARIZER_PROMPT + user_message
        estimated_tokens = len(full_message_string) // 4

    if estimated_tokens > 5500:
        # last-ditch fallback: 2 turns, 4 chunks
        # if this fails we're out of options without a bigger model
        trimmed_history = session.history[-2:]
        cited_entries_fb = cited_entries[:4]
        history_text = "\n\n".join(
            f"{turn['agent'].upper()}: {turn['content']}" for turn in trimmed_history
        )
        cited_chunk_texts = [
            f"[{c['metadata'].get('file_name', '?')}, {c['metadata'].get('page_ref', '?')}]: {c['text']}"
            for c in cited_entries_fb
        ]
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
        if '413' in str(e):
            print("summarizer 413 — retrying with reduced context")
            # cut history to 2 turns, chunks to 4, try once more
            try:
                report = await generate_report(
                    session, chunk_store,
                    max_history_turns=2, max_chunks=4,
                )
                session.report = report
                session.status = "complete"
                print("report generation complete (413 retry) for session", session.id)
            except Exception:
                # if this also fails, set session.status = "failed" and move on
                print("report generation failed on 413 retry, session:", session.id)
                session.status = "failed"
        else:
            print("report generation failed:", str(e), "session:", session.id)
            session.status = "failed"

    yield {"type": "session_complete", "reason": reason}

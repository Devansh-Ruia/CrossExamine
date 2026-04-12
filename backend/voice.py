"""ElevenLabs TTS wrapper for CrossExamine.

Generates audio for agent turns. Returns filenames that main.py serves
via GET /audio/{filename}. Voice is optional -- if ElevenLabs isn't
configured, everything works without audio.
"""

import os
import tempfile

# Audio files go here. main.py also imports this path.
AUDIO_DIR = tempfile.mkdtemp(prefix="crossexamine_audio_")

# Voice IDs from env vars -- no hardcoded values
_VOICE_IDS = {
    "attack": os.environ.get("ELEVEN_ATTACK_VOICE_ID"),
    "defense": os.environ.get("ELEVEN_DEFENSE_VOICE_ID"),
}
_API_KEY = os.environ.get("ELEVENLABS_API_KEY")


async def generate_audio(text: str, agent: str) -> str | None:
    """Generate TTS audio for an agent's turn.

    Returns the filename (not full path) on success, None on failure.
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

        filename = f"turn-{agent}-{os.urandom(4).hex()}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)

        with open(filepath, "wb") as f:
            async for chunk in audio_generator:
                f.write(chunk)

        return filename
    except Exception:
        # Voice is nice-to-have. If anything goes wrong, return None.
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

"""
JARVIS TTS — Text zu Sprache
Primär:  edge-tts  (Microsoft Neural, kostenlos, kein API-Key)
Premium: ElevenLabs (ELEVENLABS_KEY in .env setzen)

Stimme konfigurieren via .env:
  JARVIS_VOICE=de-DE-ConradNeural   (Standard — tiefer deutscher Mann)
  JARVIS_VOICE=en-GB-RyanNeural    (britisch, klassischer JARVIS-Klang)
  ELEVENLABS_KEY=sk-...             (schaltet auf ElevenLabs um)
  ELEVENLABS_VOICE=JBFqnCBsd6RMkjVDRZzb  (Standard: George, britisch)
"""
import asyncio
import io
import os
import sys

ELEVENLABS_KEY   = os.getenv("ELEVENLABS_KEY", "").strip()
ELEVENLABS_VOICE = os.getenv("ELEVENLABS_VOICE", "JBFqnCBsd6RMkjVDRZzb")
EDGE_VOICE       = os.getenv("JARVIS_VOICE",    "de-DE-ConradNeural")
EDGE_RATE        = os.getenv("JARVIS_RATE",     "+18%")   # etwas schneller klingt natuerlicher

# ── Vorab-Generierungs-Cache ──────────────────────────────────────
# key: rid (str) → value: (bytes, mime)
_cache: dict[str, tuple[bytes, str]] = {}


def prebuild(text: str, rid: str) -> None:
    """
    Generiert TTS im Hintergrund-Thread und cached das Ergebnis.
    Wird aufgerufen waehrend JARVIS noch Text streamt, sodass
    das Audio sofort abgespielt werden kann wenn der Browser fragt.
    """
    import threading
    def _run() -> None:
        try:
            data, mime = speak(text)
            _cache[rid] = (data, mime)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def get_cached(rid: str) -> tuple[bytes, str] | None:
    """Gibt gecachtes Audio zurueck und entfernt es aus dem Cache."""
    return _cache.pop(rid, None)


def speak(text: str) -> tuple[bytes, str]:
    """
    Gibt (audio_bytes, mime_type) zurück.
    Wirft RuntimeError wenn kein TTS-Backend verfügbar.
    """
    text = text.strip()
    if not text:
        raise ValueError("Kein Text übergeben")
    if ELEVENLABS_KEY:
        return _elevenlabs(text)
    return _edge_tts(text)


# ── edge-tts (kostenlos, Microsoft Neural TTS) ────────────────────
def _edge_tts(text: str) -> tuple[bytes, str]:
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError(
            "edge-tts nicht installiert.\n"
            "Bitte ausführen:  pip install edge-tts\n"
            "Dann Server neu starten."
        )

    async def _stream() -> bytes:
        comm = edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE)
        buf  = io.BytesIO()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        return buf.getvalue()

    # Neuen Event-Loop pro Aufruf (thread-safe in Flask threaded mode)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    data = asyncio.run(_stream())
    if not data:
        raise RuntimeError("edge-tts: kein Audio erhalten")
    return data, "audio/mpeg"


# ── ElevenLabs (premium, API-Key nötig) ──────────────────────────
def _elevenlabs(text: str) -> tuple[bytes, str]:
    import urllib.request
    import json

    url     = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}"
    payload = json.dumps({
        "text":           text,
        "model_id":       "eleven_multilingual_v2",
        "voice_settings": {
            "stability":        0.45,
            "similarity_boost": 0.80,
            "style":            0.0,
            "use_speaker_boost": True,
        },
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={
        "xi-api-key":   ELEVENLABS_KEY,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read(), "audio/mpeg"


# ── Backend-Status (beim Start ausgeben) ─────────────────────────
def backend_name() -> str:
    if ELEVENLABS_KEY:
        return f"ElevenLabs ({ELEVENLABS_VOICE[:8]}...)"
    return f"edge-tts ({EDGE_VOICE})"

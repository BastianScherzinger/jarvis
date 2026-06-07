import io
import wave
import struct
import math
import threading
import subprocess
import tempfile
import os
import logging
import socket
import time as _time

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from agents.ceo import JarvisCEO, get_usage
from agents.tools import WORKSPACE_TASKS, WORKSPACE_RESULTS
import jarvis_log as log
import tts

# Flask-Logs auf Minimum
logging.getLogger("werkzeug").setLevel(logging.ERROR)

log.banner()

app     = Flask(__name__)
jarvis  = JarvisCEO()

# ── STT: faster-whisper (lokal) mit Google-Fallback ────────────────
_whisper       = None
_whisper_ready = False

def _load_whisper() -> None:
    global _whisper, _whisper_ready
    try:
        import os as _os
        model_size = _os.getenv("JARVIS_STT_MODEL", "base")
        from faster_whisper import WhisperModel
        _whisper = WhisperModel(model_size, device="cpu", compute_type="int8")
        _whisper_ready = True
    except ImportError:
        pass        # kein faster-whisper installiert → Google-Fallback
    except Exception as e:
        log.warn(f"Whisper-Ladefehler: {e}")

# Whisper im Hintergrund laden — blockiert den Start nicht
threading.Thread(target=_load_whisper, daemon=True).start()

# Google-Fallback
import speech_recognition as sr
_recognizer = sr.Recognizer()


def _get_ffmpeg() -> str:
    """Gibt ffmpeg-Pfad zurueck: erst System, dann imageio-ffmpeg-Bundle."""
    import shutil
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise FileNotFoundError("ffmpeg nicht gefunden — pip install imageio-ffmpeg")


def _webm_to_wav(webm_bytes: bytes, rate: int = 16000) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
        tmp_in.write(webm_bytes)
        tmp_in_path = tmp_in.name
    tmp_out_path = tmp_in_path.replace(".webm", ".wav")
    try:
        subprocess.run(
            [_get_ffmpeg(), "-y", "-i", tmp_in_path,
             "-ar", str(rate), "-ac", "1", "-f", "wav", tmp_out_path],
            check=True, capture_output=True,
        )
        with open(tmp_out_path, "rb") as f:
            return f.read()
    finally:
        for p in (tmp_in_path, tmp_out_path):
            try: os.unlink(p)
            except OSError: pass


def _transcribe_whisper(buf: io.BytesIO, lang: str) -> str:
    """Lokale Transkription via faster-whisper (kein Netz)."""
    import numpy as np
    buf.seek(0)
    with wave.open(buf, "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    samples = (
        __import__("numpy")
        .frombuffer(raw, dtype=__import__("numpy").int16)
        .astype(__import__("numpy").float32) / 32768.0
    )
    lang_code = lang.split("-")[0]
    segments, _ = _whisper.transcribe(
        samples,
        language=lang_code,
        beam_size=1,
        best_of=1,
        temperature=0.0,
        vad_filter=True,
    )
    return " ".join(s.text.strip() for s in segments).strip()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data    = request.get_json()
    message = (data or {}).get("message", "").strip()
    if not message:
        return jsonify({"error": "message fehlt"}), 400

    return Response(
        stream_with_context(jarvis.stream(message)),
        content_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


@app.route("/api/voice/transcribe", methods=["POST"])
def voice_transcribe():
    body         = request.data
    lang         = request.headers.get("X-Lang", "de-DE")
    content_type = request.content_type or ""

    log.voice_received(len(body))

    if not body or len(body) < 256:
        log.voice_error(f"Zu wenig Audio ({len(body)} B)")
        return jsonify({"text": "", "error": "Zu wenig Audio-Daten"}), 400

    # ── Audio in WAV umwandeln ────────────────────────────────────────
    if "webm" in content_type or "ogg" in content_type:
        try:
            wav_bytes = _webm_to_wav(body)
            buf = io.BytesIO(wav_bytes)
        except FileNotFoundError:
            log.warn("ffmpeg nicht gefunden")
            buf = io.BytesIO(body)
        except Exception as e:
            log.voice_error(f"ffmpeg: {e}")
            return jsonify({"text": "", "error": f"Konvertierung fehlgeschlagen: {e}"}), 500
    else:
        rate = int(request.headers.get("X-Sample-Rate", "16000"))
        buf  = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(body)
        buf.seek(0)

    # WAV-Diagnose (RMS/Laenge)
    try:
        buf.seek(0)
        with wave.open(buf, "rb") as wf:
            frames = wf.getnframes()
            rate_w = wf.getframerate()
            raw    = wf.readframes(frames)
        samples = struct.unpack(f"<{len(raw)//2}h", raw)
        rms      = math.sqrt(sum(s*s for s in samples) / len(samples)) if samples else 0
        log.voice_wav(frames / rate_w, rms)
        buf.seek(0)
    except Exception:
        buf.seek(0)

    # ── Transkription ────────────────────────────────────────────────
    try:
        if _whisper_ready and _whisper is not None:
            # Lokal — schnell, kein Netz
            text = _transcribe_whisper(buf, lang)
            backend = "lokal"
        else:
            # Google-Fallback
            with sr.AudioFile(buf) as source:
                audio = _recognizer.record(source)
            text = _recognizer.recognize_google(audio, language=lang)
            backend = lang.split("-")[0].upper()

        if text:
            log.voice_recognized(text, backend)
            return jsonify({"text": text})
        else:
            log.voice_nothing()
            return jsonify({"text": "", "error": "Nichts erkannt"})

    except Exception as e:
        if "UnknownValueError" in type(e).__name__:
            log.voice_nothing()
            return jsonify({"text": "", "error": "Nichts erkannt"})
        if "RequestError" in type(e).__name__:
            log.voice_error(f"Google API: {e}")
            return jsonify({"text": "", "error": f"Google-Fehler: {e}"}), 502
        log.err(str(e))
        return jsonify({"text": "", "error": f"Fehler: {e}"}), 500


@app.route("/api/reset", methods=["POST"])
def api_reset():
    jarvis.reset()
    log.reset_conversation()
    return jsonify({"ok": True})


@app.route("/api/workspace")
def api_workspace():
    def file_info(p):
        return {"name": p.name, "size": p.stat().st_size, "mtime": p.stat().st_mtime}

    tasks   = sorted(WORKSPACE_TASKS.glob("*.md"),   key=lambda x: x.stat().st_mtime, reverse=True)[:15]
    results = sorted(WORKSPACE_RESULTS.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:15]
    return jsonify({
        "tasks":   [file_info(f) for f in tasks],
        "results": [file_info(f) for f in results],
    })


@app.route("/api/workspace/<folder>/<path:filename>")
def api_workspace_file(folder, filename):
    if folder not in ("tasks", "results"):
        return jsonify({"error": "Ungültiger Ordner"}), 403
    base = WORKSPACE_TASKS if folder == "tasks" else WORKSPACE_RESULTS
    p = (base / filename).resolve()
    if not p.exists() or not str(p).startswith(str(base.resolve())):
        return jsonify({"error": "Datei nicht gefunden"}), 404
    return p.read_text(encoding="utf-8")


@app.route("/api/speak", methods=["POST"])
def api_speak():
    log.tool_call("tts", "ROUTE HIT")   # debug: route wurde aufgerufen
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    rid  = data.get("id",   "").strip()

    if not text:
        return jsonify({"error": "kein Text"}), 400

    try:
        cached = tts.get_cached(rid) if rid else None
        if cached:
            audio_bytes, mime = cached
            log.tool_call("tts", f"cache-hit  {len(audio_bytes)//1024} KB")
        else:
            log.tool_call("tts", text[:60])
            audio_bytes, mime = tts.speak(text)
            log.tool_done("tts", len(audio_bytes))

        return Response(
            audio_bytes,
            content_type=mime,
            headers={"Cache-Control": "no-store"},
        )
    except RuntimeError as e:
        log.warn(f"TTS fehlgeschlagen: {e}")
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        log.err(f"TTS: {e}")
        return jsonify({"error": str(e)}), 500


_net_cache: dict = {"ts": 0.0, "internet": False, "claude": False}
_NET_TTL = 30.0


def _tcp_reachable(host: str, port: int = 443, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


@app.route("/api/status")
def api_status():
    now = _time.time()
    if now - _net_cache["ts"] > _NET_TTL:
        internet = _tcp_reachable("1.1.1.1", 443)
        _net_cache["internet"] = internet
        _net_cache["claude"]   = _tcp_reachable("api.anthropic.com", 443) if internet else False
        _net_cache["ts"]       = now
    return jsonify({
        "internet": _net_cache["internet"],
        "claude":   _net_cache["claude"],
        "tokens":   get_usage(),
    })


if __name__ == "__main__":
    stt_label = "faster-whisper/base (wird geladen...)" if not _whisper_ready else f"faster-whisper/{os.getenv('JARVIS_STT_MODEL','base')}"
    log.server_ready(5000)
    print(f"  \033[90mTTS: {tts.backend_name()}  |  STT: {stt_label}\033[0m\n")
    app.run(debug=False, port=5000, threaded=True)

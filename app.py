import io
import wave
import struct
import math
import subprocess
import tempfile
import os
import logging
import speech_recognition as sr

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from agents.ceo import JarvisCEO
from agents.tools import WORKSPACE_TASKS, WORKSPACE_RESULTS
import jarvis_log as log
import tts

# Flask-eigene Logs auf Minimum reduzieren
logging.getLogger("werkzeug").setLevel(logging.ERROR)

log.banner()

app      = Flask(__name__)
jarvis   = JarvisCEO()
_recognizer = sr.Recognizer()


def _webm_to_wav(webm_bytes: bytes, rate: int = 16000) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
        tmp_in.write(webm_bytes)
        tmp_in_path = tmp_in.name
    tmp_out_path = tmp_in_path.replace(".webm", ".wav")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path,
             "-ar", str(rate), "-ac", "1",
             "-f", "wav", tmp_out_path],
            check=True, capture_output=True,
        )
        with open(tmp_out_path, "rb") as f:
            return f.read()
    finally:
        for p in (tmp_in_path, tmp_out_path):
            try:
                os.unlink(p)
            except OSError:
                pass


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
    body = request.data
    lang         = request.headers.get("X-Lang", "de-DE")
    content_type = request.content_type or ""

    log.voice_received(len(body))

    if not body or len(body) < 256:
        log.voice_error(f"Zu wenig Audio-Daten ({len(body)} Bytes)")
        return jsonify({"text": "", "error": "Zu wenig Audio-Daten empfangen"}), 400

    if "webm" in content_type or "ogg" in content_type:
        try:
            wav_bytes = _webm_to_wav(body)
            buf = io.BytesIO(wav_bytes)
        except FileNotFoundError:
            log.warn("ffmpeg nicht gefunden — versuche Direktverarbeitung")
            buf = io.BytesIO(body)
        except Exception as e:
            log.voice_error(f"ffmpeg: {e}")
            return jsonify({"text": "", "error": f"Audio-Konvertierung fehlgeschlagen: {e}"}), 500
    else:
        rate = int(request.headers.get("X-Sample-Rate", "16000"))
        buf  = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(body)
        buf.seek(0)

    # WAV-Diagnose
    try:
        buf.seek(0)
        with wave.open(buf, "rb") as wf:
            frames = wf.getnframes()
            rate_w = wf.getframerate()
            raw    = wf.readframes(frames)
            duration = frames / rate_w
        samples = struct.unpack(f"<{len(raw)//2}h", raw)
        rms  = math.sqrt(sum(s*s for s in samples) / len(samples)) if samples else 0
        log.voice_wav(duration, rms)
        buf.seek(0)
    except Exception:
        buf.seek(0)

    try:
        with sr.AudioFile(buf) as source:
            audio = _recognizer.record(source)
        text = _recognizer.recognize_google(audio, language=lang)
        log.voice_recognized(text, lang.split("-")[0])
        return jsonify({"text": text})
    except sr.UnknownValueError:
        log.voice_nothing()
        return jsonify({"text": "", "error": "Nichts erkannt"})
    except sr.RequestError as e:
        log.voice_error(f"Google API: {e}")
        return jsonify({"text": "", "error": f"Google-Fehler: {e}"}), 502
    except Exception as e:
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
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    rid  = data.get("id",   "").strip()

    if not text:
        return jsonify({"error": "kein Text"}), 400

    try:
        # Cache-Treffer: TTS wurde schon waehrend des Streamings generiert
        cached = tts.get_cached(rid) if rid else None
        if cached:
            audio_bytes, mime = cached
        else:
            audio_bytes, mime = tts.speak(text)

        return Response(
            audio_bytes,
            content_type=mime,
            headers={"Cache-Control": "no-store"},
        )
    except RuntimeError as e:
        log.warn(f"TTS: {e}")
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        log.err(f"TTS: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    log.server_ready(5000)
    print(f"  \033[90mTTS-Backend: {tts.backend_name()}\033[0m\n")
    app.run(debug=False, port=5000, threaded=True)

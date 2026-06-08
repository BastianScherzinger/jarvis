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

from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from agents.ceo import JarvisCEO, get_usage
from agents.tools import WORKSPACE_TASKS, WORKSPACE_RESULTS
import jarvis_log as log
import tts

# Flask-Logs auf Minimum
logging.getLogger("werkzeug").setLevel(logging.ERROR)

log.banner()

# ── Bekannte Ollama-Modell-Tiers ───────────────────────────────────
_MODELS = [
    {"id": "llama3.2:1b",  "key": "tiny",    "name": "Llama 3.2 1B",  "desc": "Jede Hardware",   "vram": "~1 GB",  "tier": 1},
    {"id": "qwen2.5:3b",   "key": "small",   "name": "Qwen 2.5 3B",   "desc": "Schwache PCs",    "vram": "~4 GB",  "tier": 2},
    {"id": "qwen2.5:7b",   "key": "laptop",  "name": "Qwen 2.5 7B",   "desc": "Laptop",          "vram": "~8 GB",  "tier": 3},
    {"id": "qwen2.5:14b",  "key": "medium",  "name": "Qwen 2.5 14B",  "desc": "Desktop 16 GB",   "vram": "~16 GB", "tier": 4},
    {"id": "qwen2.5:32b",  "key": "large",   "name": "Qwen 2.5 32B",  "desc": "Desktop 32 GB",   "vram": "~32 GB", "tier": 5},
    {"id": "llama3.3:70b", "key": "allware", "name": "Llama 3.3 70B", "desc": "High-End Server",  "vram": "~48 GB", "tier": 6},
]


def _check_ollama() -> None:
    import shutil as _sh
    local_model = os.environ.get("JARVIS_LOCAL_MODEL", "")
    ollama_exe  = _sh.which("ollama")
    GR = "\033[92m"; GY = "\033[90m"; R = "\033[0m"; YL = "\033[93m"
    if ollama_exe and local_model:
        try:
            res = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5,
                encoding="utf-8", errors="replace",
            )
            if local_model.split(":")[0] in res.stdout:
                print(f"  {GR}OK{R}  Ollama  {local_model}  {GY}(Fallback bereit){R}")
            else:
                log.warn(f"Ollama: '{local_model}' nicht gefunden — 'ollama pull {local_model}'")
        except Exception as e:
            log.warn(f"Ollama-Check fehlgeschlagen: {e}")
    elif ollama_exe:
        print(f"  {YL}!{R}   Ollama vorhanden — kein Modell gesetzt {GY}(JARVIS_LOCAL_MODEL fehlt){R}")
    else:
        print(f"  {GY}--  Ollama: nicht installiert — kein lokaler Fallback{R}")

_check_ollama()

app     = Flask(__name__)
jarvis  = JarvisCEO()

# â”€â”€ STT: faster-whisper (lokal) mit Google-Fallback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
        pass        # kein faster-whisper installiert â†’ Google-Fallback
    except Exception as e:
        log.warn(f"Whisper-Ladefehler: {e}")

# Whisper im Hintergrund laden â€” blockiert den Start nicht
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
        raise FileNotFoundError("ffmpeg nicht gefunden â€” pip install imageio-ffmpeg")


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
    import numpy as _np
    buf.seek(0)
    with wave.open(buf, "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    samples = _np.frombuffer(raw, dtype=_np.int16).astype(_np.float32) / 32768.0
    lang_code = lang.split("-")[0]
    segments, info = _whisper.transcribe(
        samples,
        language=lang_code,
        beam_size=8,
        best_of=3,
        temperature=0.0,
        vad_filter=True,
        initial_prompt="JARVIS Assistent. Nutzer gibt kurze Befehle auf Deutsch.",
        vad_parameters={"min_silence_duration_ms": 800, "speech_pad_ms": 300, "threshold": 0.4},
        no_speech_threshold=0.55,
        compression_ratio_threshold=1.8,
        log_prob_threshold=-0.4,
    )
    texts = [s.text.strip() for s in segments if s.no_speech_prob < 0.45 and s.text.strip()]
    result = " ".join(texts).strip()
    if not result:
        log.warn(f"Whisper: no_speech (lang_prob={info.language_probability:.2f})")
    return result


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/maps-key")
def maps_key():
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    return jsonify({"key": key})


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

    # â”€â”€ Audio in WAV umwandeln â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ RMS-Mindestpegel: zu leise = kein Sprach-Signal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    duration_s = frames / rate_w if rate_w else 0
    if rms < 400:
        log.voice_nothing()
        return jsonify({"text": "", "error": "Zu leise"})
    # Lange + leise Aufnahme = sehr wahrscheinlich UmgebungslÃ¤rm (Whisper halluziniert)
    if duration_s > 12.0 and rms < 1800:
        log.voice_nothing()
        return jsonify({"text": "", "error": "Zu lang + zu leise (Umgebung)"})

    # â”€â”€ Transkription â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        if _whisper_ready and _whisper is not None:
            # Lokal â€” schnell, kein Netz
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


@app.route("/api/knowledge")
def api_knowledge():
    """Jede Info aus .md-Dateien als eigener Node â€” fÃ¼r maximale Sphere-Dichte."""
    import re as _re
    nodes = []

    def _clean(text: str) -> str:
        text = _re.sub(r'\*{1,2}([^*\n]+)\*{1,2}', r'\1', text)
        text = _re.sub(r'`([^`\n]+)`', r'\1', text)
        text = _re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = _re.sub(r'https?://\S+', '', text)
        return text.strip()

    def _parse_file(path: Path, file_type: str):
        result = [{"name": path.stem.replace("_", " "), "type": file_type}]
        try:
            in_code = False
            for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if line.startswith("```"):
                    in_code = not in_code
                    continue
                if in_code or not line or line.startswith("---"):
                    continue

                if line.startswith("## "):
                    t = _clean(line[3:])
                    if t: result.append({"name": t[:60], "type": "h2"})
                elif line.startswith("### "):
                    t = _clean(line[4:])
                    if t: result.append({"name": t[:60], "type": "h3"})
                elif line.startswith(("#", "#### ", "##### ")):
                    t = _clean(line.lstrip("#").strip())
                    if t and len(t) > 2: result.append({"name": t[:50], "type": "h3"})
                elif line.startswith(("- ", "* ", "+ ")):
                    t = _clean(line[2:])
                    if t and len(t) > 3 and len(t) < 100:
                        result.append({"name": t[:55], "type": "item"})
                elif line.startswith("|") and not _re.match(r'^\|[-: |]+\|$', line):
                    parts = [_clean(p) for p in line.split("|") if _clean(p) and len(_clean(p)) > 2]
                    for p in parts[:3]:
                        if len(p) > 3:
                            result.append({"name": p[:45], "type": "item"})
                elif _re.match(r'^\d+\.\s', line):
                    t = _clean(_re.sub(r'^\d+\.\s*', '', line))
                    if t and len(t) > 3 and len(t) < 100:
                        result.append({"name": t[:55], "type": "item"})
        except Exception:
            pass
        return result

    here = Path(__file__).parent

    # Alle .md im Projektordner
    for md_file in sorted(here.glob("*.md")):
        nodes.extend(_parse_file(md_file, "file"))

    # Alle .md im obsidian_brain Unterordner (falls vorhanden)
    brain_dir = here / "obsidian_brain"
    if brain_dir.exists():
        for md_file in sorted(brain_dir.glob("*.md")):
            nodes.extend(_parse_file(md_file, "brain"))

    # .claude Memory-Dateien
    mem_dir = Path.home() / ".claude" / "projects" / "C--Users-basti-Desktop-jarvis" / "memory"
    if mem_dir.exists():
        for f in sorted(mem_dir.glob("*.md")):
            if f.name == "MEMORY.md":
                continue
            nodes.extend(_parse_file(f, "memory"))

    return jsonify(nodes)


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
        return jsonify({"error": "UngÃ¼ltiger Ordner"}), 403
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


@app.route("/api/models")
def api_models():
    import shutil as _sh
    ollama_ok   = _sh.which("ollama") is not None
    active      = os.environ.get("JARVIS_LOCAL_MODEL", "")
    installed   = set()

    if ollama_ok:
        try:
            res = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=6,
                encoding="utf-8", errors="replace",
            )
            for line in res.stdout.splitlines():
                parts = line.split()
                if not parts: continue
                for m in _MODELS:
                    if m["id"].split(":")[0] == parts[0].split(":")[0]:
                        installed.add(m["id"])
        except Exception:
            pass

    out = [{**m, "installed": m["id"] in installed,
             "active": m["id"] == active, "ollama_ok": ollama_ok}
           for m in _MODELS]
    return jsonify({"models": out, "active": active, "ollama": ollama_ok})


@app.route("/api/models/install", methods=["POST"])
def api_models_install():
    data     = request.get_json() or {}
    model_id = data.get("model", "").strip()
    if model_id not in {m["id"] for m in _MODELS}:
        return jsonify({"error": "Unbekanntes Modell"}), 400

    def _stream():
        import shutil as _sh
        if not _sh.which("ollama"):
            yield f"data: {json.dumps({'error': 'Ollama nicht installiert — https://ollama.com'})}\n\n"
            return
        yield f"data: {json.dumps({'text': f'Starte Download: {model_id}'})}\n\n"
        try:
            proc = subprocess.Popen(
                ["ollama", "pull", model_id],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
            )
            for line in (proc.stdout or []):
                stripped = line.strip()
                if stripped:
                    yield f"data: {json.dumps({'text': stripped[:120]})}\n\n"
            proc.wait()
            if proc.returncode == 0:
                log.warn(f"Ollama: '{model_id}' installiert")
                yield f"data: {json.dumps({'done': True, 'model': model_id})}\n\n"
            else:
                yield f"data: {json.dumps({'error': 'Download fehlgeschlagen'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return Response(
        stream_with_context(_stream()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.route("/api/models/select", methods=["POST"])
def api_models_select():
    import re as _re
    data     = request.get_json() or {}
    model_id = data.get("model", "").strip()
    if model_id not in {m["id"] for m in _MODELS}:
        return jsonify({"error": "Unbekanntes Modell"}), 400

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        if "JARVIS_LOCAL_MODEL=" in content:
            content = _re.sub(r"JARVIS_LOCAL_MODEL=.*", f"JARVIS_LOCAL_MODEL={model_id}", content)
        else:
            content += f"\nJARVIS_LOCAL_MODEL={model_id}\n"
        env_path.write_text(content, encoding="utf-8")

    os.environ["JARVIS_LOCAL_MODEL"] = model_id
    log.warn(f"Lokales Modell gewechselt → {model_id}")
    return jsonify({"ok": True, "model": model_id})


if __name__ == "__main__":
    stt_label = "faster-whisper/base (wird geladen...)" if not _whisper_ready else f"faster-whisper/{os.getenv('JARVIS_STT_MODEL','base')}"
    log.server_ready(5000)
    print(f"  \033[90mTTS: {tts.backend_name()}  |  STT: {stt_label}\033[0m\n")
    app.run(debug=False, port=5000, threaded=True)


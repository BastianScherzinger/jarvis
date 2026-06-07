#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS Voice Agent v3
=====================
Robuste Spracherkennung mit Live-VU-Meter, automatischer Geräteerkennung
und nativer Samplerate.  Schickt erkannten Text per WebSocket an das Dashboard.

Starten:   python voice_agent.py           (Deutsch, Standard)
           python voice_agent.py en-US     (Englisch)
           python voice_agent.py de-DE 1   (Device-Index 1)
           python voice_agent.py --list    (alle Mikrofone auflisten)
"""

import asyncio
import io
import json
import sys
import time

# UTF-8 erzwingen (Windows-Konsole nutzt sonst cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import threading
import wave
from collections import deque
from datetime import datetime

import numpy as np
import sounddevice as sd
import speech_recognition as sr
import websockets

# ── WebSocket ─────────────────────────────────────────────────────
WS_PORT   = 5001
_ws_clients: set = set()
_ws_loop = None

# ── Audio-Parameter (werden nach Geräteerkennung gesetzt) ─────────
BLOCK     = 512           # 32 ms Blöcke → schnelle VAD-Reaktion
SILENCE_S = 0.85          # Stille → Phrase beendet
MIN_S     = 0.35          # Phrase zu kurz → ignorieren
PRE_S     = 0.30          # Vorpuffer (Millisekunden vor Sprachbeginn)
RATE      = None          # wird automatisch aus Gerätinfo übernommen


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ── Geräteauswahl ─────────────────────────────────────────────────

def list_devices():
    """Gibt alle Eingabegeräte aus und beendet das Programm."""
    print("\nVerfügbare Eingabegeräte:")
    print("─" * 50)
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            star = " ◄ Standard" if i == sd.default.device[0] else ""
            print(f"  [{i:2d}] {d['name'][:45]:<45} {int(d['default_samplerate'])} Hz{star}")
    print()
    sys.exit(0)


def find_best_mic(forced_index=None):
    """
    Findet automatisch das beste Mikrofon auf jedem Gerät.
    Strategie:
      1. Forced index → direkt verwenden
      2. Alle Eingabegeräte sammeln, virtuelle überspringen
      3. Ranking: OS-Standard + bekannte Mic-Namen bevorzugt
      4. Top-Kandidaten kurz antesten (0.2s) → wer echte Daten liefert, gewinnt
      5. Absoluter Fallback: OS-Standard egal was
    """
    devices = sd.query_devices()

    if forced_index is not None:
        d = devices[forced_index]
        return forced_index, int(d["default_samplerate"])

    # Virtuelle / Loopback-Geräte (sprachneutral)
    VIRTUAL = (
        "soundmapper", "sound mapper",
        "primary sound", "primary capture",
        "primär",
        "stereomix", "stereo mix",
        "what u hear", "wave out mix",
        "loopback", "virtual", "vb-audio",
        "voicemeeter", "blackhole", "soundflower",
    )
    # Typische echte Mikrofon-Schlüsselwörter (viele Sprachen/Hersteller)
    PREFER = (
        "mikrofon", "microphone",
        "headset", "headphone",
        "built-in", "eingebaut", "ingebouwd", "intégré",
        "internal", "intern",
        "array", "beamforming",
        "laptop", "notebook",
        "realtek", "conexant", "sigmatel",
        "usb audio", "usb mic",
        "blue", "yeti", "snowball",
        "rode", "audio-technica", "shure",
        "jabra", "plantronics", "sennheiser",
    )

    os_default = sd.default.device[0]
    if os_default is None or os_default < 0:
        os_default = 0

    # Alle Eingabegeräte sammeln
    all_inputs = [
        (i, d) for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]

    # Virtuelle rausfiltern
    real = [
        (i, d) for i, d in all_inputs
        if not any(v in d["name"].lower() for v in VIRTUAL)
    ]
    pool = real if real else all_inputs   # falls alle virtuell sind, alle probieren

    # Ranking: höhere Punktzahl = besser
    def score(item):
        idx, d = item
        name = d["name"].lower()
        s = 0
        if idx == os_default:
            s += 20          # OS-Standard ist meistens die beste Wahl
        if any(p in name for p in PREFER):
            s += 10
        if d["max_input_channels"] >= 2:
            s += 1           # Stereo-Mic leicht bevorzugt
        return s

    ranked = sorted(pool, key=score, reverse=True)

    print(f"[{ts()}] Teste Mikrofone …")
    for idx, d in ranked[:6]:            # max. 6 Kandidaten ausprobieren
        rate = int(d["default_samplerate"])
        try:
            data = sd.rec(
                int(0.25 * rate),
                samplerate=rate, channels=1, dtype="float32",
                device=idx, blocking=True,
            )
            nonzero = int(np.count_nonzero(data))
            rms = float(np.sqrt(np.mean(data ** 2)))
            status = f"RMS={rms:.6f} nz={nonzero}"
            if nonzero > rate * 0.05:    # mindestens 5 % Samples ungleich Null
                print(f"[{ts()}] OK  [{idx}] {d['name']}  {status}")
                return idx, rate
            else:
                print(f"[{ts()}] --  [{idx}] {d['name']}  {status}  (kein Signal)")
        except Exception as e:
            print(f"[{ts()}] ERR [{idx}] {d['name']}  {e}")

    # Fallback: OS-Standard trotzdem verwenden
    print(f"[{ts()}] Fallback auf OS-Standard [{os_default}]")
    d = devices[os_default]
    return os_default, int(d["default_samplerate"])


# ── WebSocket-Server ──────────────────────────────────────────────

async def _ws_handler(ws):
    _ws_clients.add(ws)
    print(f"[{ts()}] Browser verbunden  ({len(_ws_clients)} aktiv)")
    try:
        await ws.send(json.dumps({"status": "connected"}))
        async for _ in ws:     # Eingehende Nachrichten verwerfen
            pass
    except Exception:
        pass
    finally:
        _ws_clients.discard(ws)
        print(f"[{ts()}] Browser getrennt")


async def _broadcast(text: str):
    dead = set()
    for c in list(_ws_clients):
        try:
            await c.send(json.dumps({"text": text}))
        except Exception:
            dead.add(c)
    _ws_clients -= dead


def _send(text: str):
    if _ws_loop and text.strip():
        asyncio.run_coroutine_threadsafe(_broadcast(text.strip()), _ws_loop)


# ── VU-Meter (Terminal-Visualisierung) ───────────────────────────

_VU_WIDTH = 30
_VU_LOCK  = threading.Lock()

def vu_print(rms: float, thresh: float, speaking: bool):
    """Druckt ein einzeiliges VU-Meter mit Carriage Return."""
    filled  = int(min(rms / (thresh * 2), 1.0) * _VU_WIDTH)
    bar     = ("█" * filled).ljust(_VU_WIDTH, "░")
    indicator = "🎙️  SPRICHT" if speaking else "       still"
    with _VU_LOCK:
        print(f"\r  [{bar}] {rms:6.4f} / {thresh:.4f}  {indicator}  ", end="", flush=True)


# ── Kalibrierung ──────────────────────────────────────────────────

def calibrate(dev_idx: int, rate: int, duration: float = 1.5) -> float:
    """
    Misst Umgebungslärm und gibt den Sprach-Schwellwert zurück.
    Nutzt float32 (-1.0 … 1.0) Werte.
    """
    print(f"[{ts()}] Kalibrierung läuft ({duration:.0f}s Stille) …")
    samples: list[float] = []

    # 0.3s Aufwärmzeit für Windows-Treiber
    with sd.InputStream(device=dev_idx, samplerate=rate, channels=1,
                        dtype="float32", blocksize=BLOCK):
        time.sleep(0.35)

    def cb(indata, frames, t, status):
        rms = float(np.sqrt(np.mean(indata ** 2)))
        samples.append(rms)

    with sd.InputStream(device=dev_idx, samplerate=rate, channels=1,
                        dtype="float32", blocksize=BLOCK, callback=cb):
        sd.sleep(int(duration * 1000))

    if not samples or max(samples) < 1e-9:
        print(f"\n[{ts()}] ⚠  Mikrofon liefert keine Daten!")
        print(f"         Prüfe Windows-Datenschutz → Mikrofon → Apps erlauben")
        print(f"         Oder starte mit: python voice_agent.py de-DE <device-index>")
        print(f"         Geräte anzeigen: python voice_agent.py --list")
        return 0.005

    ambient = float(np.percentile(samples, 75))   # robust gegen Spitzen
    thresh  = max(ambient * 4.0, 0.005)           # niedrige Schwelle für leise Mikros
    print(f"\n[{ts()}] Rauschen ≈ {ambient:.6f}  │  Schwellwert: {thresh:.6f}")
    print(f"[{ts()}] Tipp: Laut sprechen verbessert die Erkennung")
    return thresh


# ── Erkennungsschleife ────────────────────────────────────────────

def recognition_loop(lang: str, dev_idx: int, rate: int, thresh: float):
    recognizer  = sr.Recognizer()
    pre_frames  = int(PRE_S  * rate / BLOCK)
    min_frames  = int(MIN_S  * rate / BLOCK)
    max_sil     = int(SILENCE_S * rate / BLOCK)

    pre_buf: deque = deque(maxlen=pre_frames)
    audio_q: deque = deque()
    lock = threading.Lock()

    def cb(indata, frames, t, status):
        if status:
            pass   # overflow/underflow — ignorieren
        chunk = indata.copy()
        rms   = float(np.sqrt(np.mean(chunk ** 2)))
        with lock:
            audio_q.append((chunk, rms))

    print(f"[{ts()}] Bereit — höre dauerhaft zu  ({lang})  [Strg+C zum Stoppen]")
    print()

    with sd.InputStream(device=dev_idx, samplerate=rate, channels=1,
                        dtype="float32", blocksize=BLOCK, callback=cb):
        while True:
            try:
                # ── 1. Warte auf Sprache ──────────────────────────
                while True:
                    with lock:
                        while audio_q:
                            c, r = audio_q.popleft()
                            pre_buf.append((c, r))
                    last_rms = pre_buf[-1][1] if pre_buf else 0.0
                    vu_print(last_rms, thresh, False)
                    if last_rms > thresh:
                        break
                    time.sleep(0.02)

                # ── 2. Phrase sammeln ─────────────────────────────
                phrase: list = list(pre_buf)
                silent = 0

                while silent < max_sil:
                    with lock:
                        while audio_q:
                            c, r = audio_q.popleft()
                            phrase.append((c, r))
                            if r > thresh:
                                silent = 0
                            else:
                                silent += 1
                    if phrase:
                        vu_print(phrase[-1][1], thresh, True)
                    time.sleep(0.02)

                print()  # Zeilenumbruch nach VU-Meter

                # ── 3. Zu kurze Phrase? ───────────────────────────
                speech_n = sum(1 for _, r in phrase if r > thresh)
                if speech_n < min_frames:
                    pre_buf.clear()
                    continue

                # ── 4. Float32 → int16 WAV (normalisiert) ────────
                audio_f32 = np.concatenate([c for c, _ in phrase], axis=0)
                # Normalisieren: leises Mikrofon auf vernünftigen Pegel anheben
                peak = float(np.max(np.abs(audio_f32)))
                if peak > 1e-6:
                    target = min(peak, 0.5)   # nie clipping, Ziel ~50% Vollaussteuerung
                    audio_f32 = audio_f32 * (target / peak)
                audio_i16 = np.clip(audio_f32 * 32767, -32768, 32767).astype(np.int16)

                buf = io.BytesIO()
                with wave.open(buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(rate)
                    wf.writeframes(audio_i16.tobytes())
                buf.seek(0)

                # ── 5. Erkennung ──────────────────────────────────
                print(f"[{ts()}] Erkenne …", end=" ", flush=True)
                with sr.AudioFile(buf) as src:
                    audio_data = recognizer.record(src)

                try:
                    text = recognizer.recognize_google(audio_data, language=lang)
                    if text.strip():
                        print(f"✓  {text}")
                        _send(text)
                    else:
                        print("(leer)")
                except sr.UnknownValueError:
                    print("(nicht erkannt)")
                except sr.RequestError as e:
                    print(f"✗  Google-Fehler: {e}")

                pre_buf.clear()

            except Exception as e:
                print(f"\n[{ts()}] Fehler in Erkennungsschleife: {e}")
                time.sleep(0.5)


# ── Async-Hauptfunktion ───────────────────────────────────────────

async def run(lang: str, dev_idx: int, rate: int, thresh: float):
    global _ws_loop
    _ws_loop = asyncio.get_running_loop()

    t = threading.Thread(
        target=recognition_loop,
        args=(lang, dev_idx, rate, thresh),
        daemon=True
    )
    t.start()

    print(f"[{ts()}] WebSocket-Server  ws://localhost:{WS_PORT}")
    print()

    async with websockets.serve(_ws_handler, "localhost", WS_PORT):
        await asyncio.Future()


# ── Einstiegspunkt ────────────────────────────────────────────────

def main():
    # Argumente: [lang] [device_index]
    args = [a for a in sys.argv[1:] if a not in ("-h", "--help")]

    if "--list" in sys.argv:
        list_devices()

    lang       = args[0] if len(args) > 0 else "de-DE"
    dev_arg    = int(args[1]) if len(args) > 1 else None

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║      JARVIS  Voice Agent  v3                 ║")
    print(f"║  Sprache  : {lang:<34}║")
    print(f"║  Port     : ws://localhost:{WS_PORT}               ║")
    print("║  Beenden  : Strg+C                           ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    # Gerät automatisch finden
    dev_idx, rate = find_best_mic(dev_arg)
    dev_info = sd.query_devices(dev_idx)
    print(f"[{ts()}] Mikrofon : {dev_info['name']}")
    print(f"[{ts()}] Gerät-Nr.: {dev_idx}  │  Samplerate: {rate} Hz")
    print()

    global RATE
    RATE = rate

    thresh = calibrate(dev_idx, rate, 1.5)

    try:
        asyncio.run(run(lang, dev_idx, rate, thresh))
    except KeyboardInterrupt:
        print(f"\n[{ts()}] Voice Agent beendet.")


if __name__ == "__main__":
    main()

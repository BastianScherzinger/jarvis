#!/usr/bin/env python3
"""
JARVIS Launcher
===============
Startet Flask-Dashboard (Port 5000) und Voice Agent (WS 5001) zusammen.

Starten:   python start.py             (Deutsch)
           python start.py en-US       (Englisch)
           python start.py de-DE 1     (Device-Index 1)
           python start.py --list      (Mikrofone auflisten)
"""

import subprocess
import sys
import threading
import time
import os

# UTF-8 fuer diesen Prozess und alle Kindprozesse
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"]       = "1"

# ── ANSI-Farben ───────────────────────────────────────────────────
R  = "\033[0m"
G  = "\033[32m"
C  = "\033[36m"
Y  = "\033[33m"
B  = "\033[34m"
M  = "\033[35m"
BOLD = "\033[1m"

def prefix(tag: str, color: str):
    return f"{color}{BOLD}[{tag}]{R} "

def stream(proc, tag: str, color: str):
    pfx = prefix(tag, color)
    try:
        for line in iter(proc.stdout.readline, ""):
            sys.stdout.write(pfx + line)
            sys.stdout.flush()
    except Exception:
        pass


def main():
    if "--list" in sys.argv:
        subprocess.run([sys.executable, "voice_agent.py", "--list"])
        return

    # Sicherheits-Check: Sind wir im richtigen Verzeichnis?
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(here, "app.py")):
        print("app.py nicht gefunden -- bitte aus dem jarvis-Ordner starten.")
        sys.exit(1)

    # ── Abhaengigkeiten pruefen / installieren (BEVOR Flask startet) ──
    os.system("")   # ANSI aktivieren
    import install
    install.run()

    print()
    print(f"{BOLD}{'=' * 50}{R}")
    print(f"{BOLD}       JARVIS Launcher{R}")
    print(f"{'=' * 50}")
    print(f"  Dashboard  -> http://localhost:5000")
    print(f"  Voice      -> Browser-Mic (kein extra Prozess)")
    print(f"  Stopp      -> Strg+C")
    print(f"{'=' * 50}")
    print()

    # Nur Flask starten — Voice läuft jetzt im Browser
    flask_cmd = [sys.executable, "-u", "app.py"]
    flask = subprocess.Popen(
        flask_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        cwd=here,
    )

    tf = threading.Thread(target=stream, args=(flask, "FLASK", G), daemon=True)
    tf.start()

    print(f"{G}{BOLD}[FLASK]{R} Gestartet — http://localhost:5000")
    print(f"{C}{BOLD}[VOICE]{R} Mic-Button im Browser klicken → sprechen → loslassen")
    print()

    try:
        while flask.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n{Y}[JARVIS]{R} Beende …")
    finally:
        try:
            flask.terminate()
            flask.wait(timeout=3)
        except Exception:
            try:
                flask.kill()
            except Exception:
                pass
        print(f"{Y}[JARVIS]{R} Beendet.")


if __name__ == "__main__":
    main()

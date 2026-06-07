#!/usr/bin/env python3
"""
JARVIS Launcher
===============
Startet das Dashboard (Port 5000).

Starten:   python start.py          (normal)
           python start.py --list   (Mikrofone auflisten)
"""

import subprocess
import sys
import time
import os

# UTF-8 fuer diesen Prozess und alle Kindprozesse
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"]       = "1"
os.system("")   # ANSI aktivieren


def main():
    if "--list" in sys.argv:
        subprocess.run([sys.executable, "voice_agent.py", "--list"])
        return

    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(here, "app.py")):
        print("  [!]  app.py nicht gefunden -- bitte aus dem jarvis-Ordner starten.")
        sys.exit(1)

    # ── Setup & Abhaengigkeiten (laeuft immer zuerst) ────────────────
    import install
    all_ok = install.run()

    if not all_ok:
        C = "\033[96m"; R = "\033[0m"; YL = "\033[93m"
        print(f"  {YL}[!]{R}  Setup unvollstaendig. JARVIS startet trotzdem.")
        print()

    # ── Flask starten ────────────────────────────────────────────────
    flask = subprocess.Popen(
        [sys.executable, "-u", "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        cwd=here,
    )

    try:
        for line in iter(flask.stdout.readline, ""):
            sys.stdout.write(line)
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            flask.terminate()
            flask.wait(timeout=3)
        except Exception:
            try:
                flask.kill()
            except Exception:
                pass

        R = "\033[0m"; YL = "\033[93m"
        print(f"\n  {YL}[JARVIS]{R}  Beendet.")


if __name__ == "__main__":
    main()

"""
JARVIS Auto-Installer
Wird von start.py automatisch aufgerufen.
Installiert alle Abhaengigkeiten und richtet Playwright ein.
"""
import subprocess
import sys
import os
from pathlib import Path

os.system("")   # ANSI in Windows aktivieren

R   = "\033[0m"
B   = "\033[1m"
GR  = "\033[92m"
RD  = "\033[91m"
YL  = "\033[93m"
CY  = "\033[96m"
GY  = "\033[90m"

HERE = Path(__file__).parent


def _pip(*args) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", *args, "--quiet"],
        capture_output=True,
    )
    return result.returncode == 0


def _run(*args, timeout=120) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", *args],
        capture_output=True,
        timeout=timeout,
    )
    return result.returncode == 0


def _can_import(module: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
    )
    return result.returncode == 0


def _check_env() -> bool:
    env_file = HERE / ".env"
    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        if "ANTHROPIC" in content and "your_key" not in content:
            return True
    return False


def run() -> bool:
    print()
    print(f"  {CY}================================================={R}")
    print(f"  {CY}  {B}JARVIS  Setup & Abhaengigkeits-Check{R}")
    print(f"  {CY}================================================={R}")
    print()

    all_ok = True

    # ── Python-Version ────────────────────────────────────────────
    v = sys.version_info
    if v >= (3, 10):
        print(f"  {GR}[OK]{R}  Python {v.major}.{v.minor}.{v.micro}")
    else:
        print(f"  {YL}[!]{R}  Python {v.major}.{v.minor}.{v.micro}  {GY}(empfohlen: 3.10+){R}")

    # ── requirements.txt installieren ────────────────────────────
    req_file = HERE / "requirements.txt"
    if req_file.exists():
        print(f"  {CY}[>]{R}  Installiere requirements.txt ...")
        ok = _pip("-r", str(req_file))
        if ok:
            print(f"  {GR}[OK]{R}  Alle Pakete aus requirements.txt installiert")
        else:
            # Einzeln versuchen fuer bessere Fehlermeldungen
            packages = [
                ("anthropic",          "anthropic"),
                ("flask",              "flask"),
                ("dotenv",             "python-dotenv"),
                ("speech_recognition", "SpeechRecognition"),
                ("edge_tts",           "edge-tts"),
                ("playwright",         "playwright"),
            ]
            for module, pip_name in packages:
                if _can_import(module):
                    print(f"  {GR}[OK]{R}  {pip_name:<25} {GY}bereits installiert{R}")
                else:
                    print(f"  {CY}[>]{R}  {pip_name:<25} {GY}installiere...{R}", end="", flush=True)
                    if _pip(pip_name):
                        print(f"\r  {GR}[OK]{R}  {pip_name}")
                    else:
                        print(f"\r  {RD}[X]{R}  {pip_name}  {GY}-> manuell: pip install {pip_name}{R}")
                        all_ok = False

    # ── Playwright Browser ────────────────────────────────────────
    if _can_import("playwright"):
        # Pruefen ob Chromium bereits installiert ist
        check = subprocess.run(
            [sys.executable, "-c",
             "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); b.close(); p.stop()"],
            capture_output=True, timeout=20,
        )
        if check.returncode == 0:
            print(f"  {GR}[OK]{R}  Playwright Chromium")
        else:
            print(f"  {CY}[>]{R}  Playwright Chromium  {GY}installiere Browser...{R}", flush=True)
            ok = _run("playwright", "install", "chromium", "--with-deps", timeout=180)
            if ok:
                print(f"  {GR}[OK]{R}  Playwright Chromium installiert")
            else:
                print(f"  {YL}[!]{R}  Playwright Chromium  {GY}-> manuell: playwright install chromium{R}")

    # ── .env pruefen ─────────────────────────────────────────────
    env_file = HERE / ".env"
    if not env_file.exists():
        env_file.write_text(
            "ANTHROPIC_KEY=dein_api_key_hier\n"
            "# ELEVENLABS_KEY=optional_fuer_premium_stimme\n"
            "# JARVIS_VOICE=de-DE-ConradNeural\n"
            "# JARVIS_RATE=+18%\n",
            encoding="utf-8",
        )
        print(f"  {YL}[!]{R}  .env erstellt  {GY}-> ANTHROPIC_KEY eintragen!{R}")
        all_ok = False
    elif not _check_env():
        print(f"  {RD}[X]{R}  .env  {GY}-> ANTHROPIC_KEY fehlt oder nicht gesetzt{R}")
        all_ok = False
    else:
        print(f"  {GR}[OK]{R}  .env (API-Key gesetzt)")

    # ── Zusammenfassung ───────────────────────────────────────────
    print()
    if all_ok:
        print(f"  {GR}{B}Alles bereit -- JARVIS startet.{R}")
    else:
        print(f"  {YL}Setup unvollstaendig -- pruefe die roten Eintraege oben.{R}")
        print(f"  {GY}Server startet trotzdem, manche Funktionen fehlen evtl.{R}")
    print()
    print(f"  {CY}================================================={R}")
    print()

    return all_ok


if __name__ == "__main__":
    run()

"""
JARVIS Auto-Installer
Wird von start.py und update.py automatisch aufgerufen.
Installiert alle Abhaengigkeiten und richtet Playwright ein.
"""
import subprocess
import sys
import os
from pathlib import Path

os.system("")   # Windows ANSI aktivieren

R  = "\033[0m";  B  = "\033[1m"
GR = "\033[92m"; RD = "\033[91m"
YL = "\033[93m"; CY = "\033[96m"
GY = "\033[90m"

HERE = Path(__file__).parent


def _pip(*args) -> bool:
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", *args, "--quiet"],
        capture_output=True,
    ).returncode == 0


def _can_import(module: str) -> bool:
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
    ).returncode == 0


def _ok(label: str, detail: str = "") -> None:
    extra = f"  {GY}{detail}{R}" if detail else ""
    print(f"  {GR}OK{R}  {label}{extra}")


def _warn(label: str, detail: str = "") -> None:
    extra = f"  {GY}{detail}{R}" if detail else ""
    print(f"  {YL}!{R}   {label}{extra}")


def _err(label: str, detail: str = "") -> None:
    extra = f"  {GY}{detail}{R}" if detail else ""
    print(f"  {RD}X{R}   {label}{extra}")


def _installing(label: str) -> None:
    print(f"  {CY}>{R}   {label} ...", end="", flush=True)


def _header() -> None:
    print()
    print(f"  {CY}{'─' * 50}{R}")
    print(f"  {CY}{B}  JARVIS  Setup{R}")
    print(f"  {CY}{'─' * 50}{R}")
    print()


def run() -> bool:
    _header()
    all_ok = True

    # ── Python-Version ───────────────────────────────────────────────
    v = sys.version_info
    if v >= (3, 10):
        _ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        _warn(f"Python {v.major}.{v.minor}.{v.micro}", "empfohlen: 3.10+")

    # ── Pakete installieren ──────────────────────────────────────────
    req_file = HERE / "requirements.txt"
    packages = [
        ("anthropic",          "anthropic"),
        ("flask",              "flask"),
        ("dotenv",             "python-dotenv"),
        ("speech_recognition", "SpeechRecognition"),
        ("edge_tts",           "edge-tts"),
        ("playwright",         "playwright"),
    ]

    if req_file.exists():
        _installing("Pakete")
        bulk_ok = _pip("-r", str(req_file))
        if bulk_ok:
            print(f"\r  {GR}OK{R}  Alle Pakete aktuell              ")
        else:
            print(f"\r  {YL}!{R}   Bulk-Install fehlgeschlagen — pruefe einzeln:")
            for module, pip_name in packages:
                if _can_import(module):
                    _ok(pip_name, "bereits vorhanden")
                else:
                    _installing(pip_name)
                    if _pip(pip_name):
                        print(f"\r  {GR}OK{R}  {pip_name:<28}")
                    else:
                        print(f"\r  {RD}X{R}   {pip_name:<28}  {GY}pip install {pip_name}{R}")
                        all_ok = False
    else:
        _warn("requirements.txt nicht gefunden", "manuell: pip install anthropic flask python-dotenv SpeechRecognition edge-tts playwright")

    # ── Playwright Chromium ──────────────────────────────────────────
    if _can_import("playwright"):
        check = subprocess.run(
            [sys.executable, "-c",
             "from playwright.sync_api import sync_playwright;"
             " p=sync_playwright().start(); b=p.chromium.launch(headless=True); b.close(); p.stop()"],
            capture_output=True, timeout=20,
        )
        if check.returncode == 0:
            _ok("Playwright Chromium")
        else:
            _installing("Playwright Chromium  (einmalig ~120 MB)")
            ok = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
                capture_output=True, timeout=240,
            ).returncode == 0
            if ok:
                print(f"\r  {GR}OK{R}  Playwright Chromium installiert      ")
            else:
                print(f"\r  {YL}!{R}   Playwright Chromium  {GY}manuell: playwright install chromium{R}")

    # ── .env erstellen / pruefen ─────────────────────────────────────
    env_file     = HERE / ".env"
    env_example  = HERE / ".env.example"

    if not env_file.exists():
        if env_example.exists():
            env_file.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            env_file.write_text(
                "ANTHROPIC_KEY=dein_api_key_hier\n"
                "# ELEVENLABS_KEY=optional\n"
                "# JARVIS_VOICE=de-DE-ConradNeural\n"
                "# JARVIS_RATE=+18%\n",
                encoding="utf-8",
            )
        _warn(".env erstellt", "ANTHROPIC_KEY eintragen!")
        all_ok = False
    else:
        content = env_file.read_text(encoding="utf-8")
        has_key = "ANTHROPIC_KEY" in content
        is_placeholder = "dein_api_key" in content or "sk-ant-..." in content or "your_key" in content
        if has_key and not is_placeholder:
            _ok(".env  (API-Key gesetzt)")
        else:
            _err(".env", "ANTHROPIC_KEY fehlt oder ist noch Platzhalter")
            all_ok = False

    # ── workspace-Ordner anlegen ────────────────────────────────────
    for d in ["workspace/tasks", "workspace/results"]:
        (HERE / d).mkdir(parents=True, exist_ok=True)

    # ── Abschluss ───────────────────────────────────────────────────
    print()
    if all_ok:
        print(f"  {GR}{B}Alles bereit.{R}")
    else:
        print(f"  {YL}Setup unvollstaendig — pruefe die Eintraege oben.{R}")
    print(f"  {CY}{'─' * 50}{R}")
    print()

    return all_ok


if __name__ == "__main__":
    run()

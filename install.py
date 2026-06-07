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

    # ── Git Update ───────────────────────────────────────────────────
    import shutil
    if shutil.which("git") and (HERE / ".git").exists():
        print(f"  {CY}>{R}   Git update ...", end="", flush=True)
        try:
            res = subprocess.run(
                ["git", "pull", "--ff-only"],
                capture_output=True, text=True, cwd=HERE, timeout=12,
                encoding="utf-8", errors="replace",
            )
            out = (res.stdout + res.stderr).strip().split("\n")[0][:60]
            if res.returncode == 0:
                if "already up" in out.lower() or "bereits" in out.lower():
                    print(f"\r  {GR}OK{R}  Git  {GY}bereits aktuell{R}          ")
                else:
                    print(f"\r  {GR}OK{R}  Git  {GY}{out}{R}          ")
            else:
                print(f"\r  {YL}!{R}   Git pull  {GY}{out}{R}          ")
        except Exception as e:
            print(f"\r  {YL}!{R}   Git  {GY}({e}){R}          ")
    # kein Git-Repo oder kein git → still überspringen

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
        ("faster_whisper",     "faster-whisper"),
        ("imageio_ffmpeg",     "imageio-ffmpeg"),
        ("pyttsx3",            "pyttsx3"),
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

    # ── Ollama — lokale KI-Worker ───────────────────────────────────
    ollama_exe = shutil.which("ollama")
    if not ollama_exe:
        print(f"  {CY}>{R}   Ollama installieren ...", end="", flush=True)
        wg = shutil.which("winget")
        installed = False
        if wg:
            res = subprocess.run(
                ["winget", "install", "--id", "Ollama.Ollama", "-e", "--silent", "--accept-package-agreements"],
                capture_output=True, timeout=120,
            )
            installed = res.returncode == 0
            ollama_exe = shutil.which("ollama")
        if installed and ollama_exe:
            print(f"\r  {GR}OK{R}  Ollama installiert                    ")
        else:
            print(f"\r  {YL}!{R}   Ollama nicht gefunden  {GY}https://ollama.com/download{R}")

    if ollama_exe:
        # Prüfe ob Modell schon in .env gesetzt ist
        env_content = (HERE / ".env").read_text(encoding="utf-8") if (HERE / ".env").exists() else ""
        has_model   = "JARVIS_LOCAL_MODEL=" in env_content and "JARVIS_LOCAL_MODEL=\n" not in env_content

        MODELS = {
            "1": {
                "key":  "allware",
                "name": "llama3.3:70b",
                "desc": "Bestes lokales Modell  (~43 GB, braucht GPU / 48 GB RAM)",
            },
            "2": {
                "key":  "laptop",
                "name": "qwen2.5:7b",
                "desc": "HP-Laptop-optimiert    (~4.7 GB, läuft auf 8 GB RAM)",
            },
        }

        if not has_model:
            print()
            print(f"  {CY}{'─' * 50}{R}")
            print(f"  {CY}{B}  Lokales KI-Modell wählen{R}")
            print(f"  {CY}{'─' * 50}{R}")
            for k, m in MODELS.items():
                print(f"  [{k}]  {B}{m['key'].upper():<10}{R}  {m['name']:<20}  {GY}{m['desc']}{R}")
            print(f"  [0]  Überspringen{GY} (kein lokales Modell){R}")
            print()
            try:
                choice = input(f"  {CY}Auswahl (0/1/2):{R} ").strip()
            except (EOFError, KeyboardInterrupt):
                choice = "0"

            if choice in MODELS:
                chosen = MODELS[choice]
                model_name = chosen["name"]
                # In .env eintragen
                with open(HERE / ".env", "a", encoding="utf-8") as ef:
                    ef.write(f"\nJARVIS_LOCAL_MODEL={model_name}\n")
                print()
                _installing(f"Modell '{model_name}' herunterladen  (kann einige Minuten dauern)")
                pull = subprocess.run(
                    ["ollama", "pull", model_name],
                    timeout=3600,
                )
                if pull.returncode == 0:
                    print(f"\r  {GR}OK{R}  Modell '{model_name}' bereit                   ")
                    _ok(f"JARVIS_LOCAL_MODEL={model_name}")
                else:
                    print(f"\r  {YL}!{R}   Download fehlgeschlagen — manuell: ollama pull {model_name}")
            else:
                _warn("Kein lokales Modell gewählt", "local_ai_worker Tool nicht verfügbar")
        else:
            # Modell schon gesetzt — prüfe ob es lokal vorhanden ist
            import re as _re
            m = _re.search(r"JARVIS_LOCAL_MODEL=(.+)", env_content)
            if m:
                model_name = m.group(1).strip()
                list_res = subprocess.run(
                    ["ollama", "list"], capture_output=True, text=True, timeout=10,
                    encoding="utf-8", errors="replace",
                )
                if model_name.split(":")[0] in list_res.stdout:
                    _ok(f"Ollama  {model_name}", "bereit")
                else:
                    _warn(f"Modell '{model_name}' nicht gefunden", f"manuell: ollama pull {model_name}")

    # ── Node.js / npx — für MCP-Server ─────────────────────────────
    node_ok = shutil.which("node") is not None
    npx_ok  = shutil.which("npx")  is not None
    if node_ok and npx_ok:
        try:
            ver = subprocess.run(["node", "--version"], capture_output=True,
                                 text=True, timeout=5).stdout.strip()
            _ok(f"Node.js  {ver}  + npx")
        except Exception:
            _ok("Node.js + npx")
    else:
        _warn("Node.js nicht gefunden", "MCP-Server brauchen Node.js — https://nodejs.org")

    # ── MCP-Server aus .mcp.json prüfen ─────────────────────────────
    mcp_file = HERE / ".mcp.json"
    if mcp_file.exists() and npx_ok:
        import json as _json
        try:
            mcp_cfg = _json.loads(mcp_file.read_text(encoding="utf-8"))
            servers = mcp_cfg.get("mcpServers", {})
            for name, cfg in servers.items():
                cmd  = cfg.get("command", "")
                args = cfg.get("args", [])
                env_needed = cfg.get("env", {})

                # Prüfe ob benötigte Env-Vars gesetzt sind
                missing_env = []
                if env_needed:
                    import os as _os
                    for k, v in env_needed.items():
                        real_val = _os.environ.get(k, "")
                        placeholder = "${" in str(v)
                        if not real_val and placeholder:
                            missing_env.append(k)

                if missing_env:
                    _warn(f"MCP  {name}", f"Key fehlt: {', '.join(missing_env)}")
                else:
                    _ok(f"MCP  {name}", f"{cmd} {' '.join(str(a) for a in args[:2])}")
        except Exception as e:
            _warn(".mcp.json", f"Parse-Fehler: {e}")
    elif mcp_file.exists() and not npx_ok:
        _warn("MCP-Server", "npx fehlt — Node.js installieren")

    # ── Google Maps Key → ~/.claude/.env synchen (für MCP-Server) ──
    import pathlib as _pl, re as _re2
    _jarvis_env = HERE / ".env"
    _claude_env = _pl.Path.home() / ".claude" / ".env"
    if _jarvis_env.exists():
        _m = _re2.search(r"GOOGLE_MAPS_API_KEY=(.+)", _jarvis_env.read_text(encoding="utf-8"))
        if _m:
            _key = _m.group(1).strip()
            _ce = _claude_env.read_text(encoding="utf-8") if _claude_env.exists() else ""
            if "GOOGLE_MAPS_API_KEY" not in _ce:
                _claude_env.parent.mkdir(parents=True, exist_ok=True)
                with open(_claude_env, "a", encoding="utf-8") as _cf:
                    _cf.write(f"\nGOOGLE_MAPS_API_KEY={_key}\n")
                _ok("~/.claude/.env", "GOOGLE_MAPS_API_KEY gesetzt")
            else:
                _ok("~/.claude/.env", "GOOGLE_MAPS_API_KEY bereits vorhanden")

    # ── obsidian_brain Ordner anlegen ───────────────────────────────
    (HERE / "obsidian_brain").mkdir(exist_ok=True)

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

"""
JARVIS Deploy-Script (nur fuer Entwickler)
==========================================
Committed alle Aenderungen und pushed zu GitHub.

Aufruf:
  python push.py                        # automatische Commit-Nachricht
  python push.py "neues Feature X"     # eigene Nachricht
  python push.py --status              # nur Status anzeigen, nicht pushen
"""
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

os.system("")
R  = "\033[0m"; B = "\033[1m"
GR = "\033[92m"; RD = "\033[91m"; YL = "\033[93m"; CY = "\033[96m"; GY = "\033[90m"

HERE   = Path(__file__).parent
REMOTE = "origin"
BRANCH = "main"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(HERE))


def _print_status() -> int:
    """Zeigt geaenderte Dateien. Gibt Anzahl zurueck."""
    status = _run(["git", "status", "--porcelain"])
    lines  = [l for l in status.stdout.splitlines() if l.strip()]
    if not lines:
        print(f"  {GY}  Keine Aenderungen.{R}")
        return 0
    for line in lines:
        code = line[:2].strip()
        file = line[3:]
        color = GR if code in ("A", "??") else YL if code == "M" else RD
        print(f"  {color}  {code:2}  {file}{R}")
    return len(lines)


def main() -> None:
    print()
    print(f"  {CY}================================================={R}")
    print(f"  {CY}  {B}JARVIS  Deploy -> GitHub{R}")
    print(f"  {CY}================================================={R}")
    print()

    # ── Git-Check ────────────────────────────────────────────────
    if _run(["git", "--version"]).returncode != 0:
        print(f"  {RD}[X]{R}  Git nicht installiert -> https://git-scm.com/download/win")
        sys.exit(1)

    if not (HERE / ".git").exists():
        print(f"  {RD}[X]{R}  Kein Git-Repository. Fuehre zuerst aus:")
        print(f"  {GY}     git init && git remote add origin https://github.com/BastianScherzinger/jarvis.git{R}")
        sys.exit(1)

    # ── Status-Modus ─────────────────────────────────────────────
    if "--status" in sys.argv:
        print(f"  {B}Geaenderte Dateien:{R}")
        _print_status()
        print()
        ahead = _run(["git", "rev-list", f"{REMOTE}/{BRANCH}..HEAD", "--count"])
        if ahead.stdout.strip() not in ("", "0"):
            print(f"  {YL}[!]{R}  {ahead.stdout.strip()} Commit(s) noch nicht gepusht.")
        return

    # ── Aenderungen pruefen ───────────────────────────────────────
    print(f"  {B}Geaenderte Dateien:{R}")
    count = _print_status()
    print()

    if count == 0:
        # Trotzdem pruefen ob lokale Commits vorhanden
        ahead = _run(["git", "rev-list", f"{REMOTE}/{BRANCH}..HEAD", "--count"])
        if ahead.stdout.strip() in ("", "0"):
            print(f"  {GY}Nichts zu pushen -- alles aktuell.{R}")
            print()
            return
        else:
            print(f"  {YL}[!]{R}  {ahead.stdout.strip()} lokale Commit(s) noch nicht gepusht.")

    # ── Commit-Nachricht ─────────────────────────────────────────
    args  = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        msg = " ".join(args)
    else:
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        msg = f"update {now}"

    # ── git add + commit ──────────────────────────────────────────
    if count > 0:
        _run(["git", "add", "-A"])
        commit = _run(["git", "commit", "-m", msg])
        if commit.returncode == 0:
            print(f"  {GR}[OK]{R}  Commit: {GY}\"{msg}\"{R}")
        else:
            err = commit.stderr.strip() or commit.stdout.strip()
            print(f"  {RD}[X]{R}  Commit fehlgeschlagen: {GY}{err[:80]}{R}")
            sys.exit(1)

    # ── git push ─────────────────────────────────────────────────
    print(f"  {CY}[>]{R}  Pushe zu GitHub...", end="", flush=True)
    push = _run(["git", "push", REMOTE, BRANCH])
    if push.returncode == 0:
        print(f"\r  {GR}[OK]{R}  Gepusht zu {CY}https://github.com/BastianScherzinger/jarvis{R}")
    else:
        print(f"\r  {RD}[X]{R}  Push fehlgeschlagen:")
        print(f"  {GY}     {push.stderr.strip()[:120]}{R}")
        sys.exit(1)

    # ── Zusammenfassung ───────────────────────────────────────────
    log = _run(["git", "log", "-3", "--oneline"])
    print()
    print(f"  {GY}Letzte Commits:{R}")
    for line in log.stdout.strip().splitlines():
        print(f"  {GY}    {line}{R}")
    print()
    print(f"  {CY}================================================={R}")
    print()


if __name__ == "__main__":
    main()

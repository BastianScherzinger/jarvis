"""
JARVIS — Pretty CMD Logger
Menschenlesbare Live-Status-Anzeige in Terminal/CMD.
"""
import os
import sys
import time
from datetime import datetime

# Windows ANSI aktivieren
os.system("")

# ── ANSI Codes ────────────────────────────────────────────────────
R  = "\033[0m"
B  = "\033[1m"
D  = "\033[2m"

CY  = "\033[96m"   # Cyan    — JARVIS
GR  = "\033[92m"   # Green   — Erfolg
YL  = "\033[93m"   # Yellow  — Tools
RD  = "\033[91m"   # Red     — Fehler
BL  = "\033[94m"   # Blue    — Stimme
PU  = "\033[95m"   # Purple  — Agenten
WH  = "\033[97m"   # White   — User
GY  = "\033[90m"   # Gray    — Timestamps / Dim
OR  = "\033[33m"   # Orange  — Warnings

# Agent-Farben (passend zum Dashboard)
_AC = {
    "library":       "\033[35m",
    "research":      "\033[94m",
    "senior_dev":    "\033[92m",
    "ux":            "\033[93m",
    "code_reviewer": "\033[94m",
    "debugger":      "\033[91m",
    "bug_fixer":     "\033[33m",
    "bug_expert":    "\033[95m",
    "performance":   "\033[96m",
    "security":      "\033[91m",
}

_TOOL_LABEL = {
    "read_file":         "LESEN  ",
    "write_file":        "SCHREIB",
    "run_command":       "CMD    ",
    "list_directory":    "LIST   ",
    "search_files":      "SUCHE  ",
    "delegate_to_agent": "AGENT  ",
    "browse_web":        "BROWSER",
    "web_click":         "KLICK  ",
    "web_type":          "TIPPEN ",
    "search_web":        "WEB    ",
}

# ── Hilfsfunktionen ───────────────────────────────────────────────
def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")

def _sz(n: int) -> str:
    if n < 1024:    return f"{n} B"
    if n < 1048576: return f"{n/1024:.1f} KB"
    return f"{n/1048576:.1f} MB"

def _short(s: str, n: int = 65) -> str:
    s = str(s)
    return s[:n] + "…" if len(s) > n else s

def _row(col: str, tag: str, msg: str) -> None:
    ts  = f"{GY}{_ts()}{R}"
    lbl = f"{col}{B}{tag:<10}{R}"
    print(f"  {ts}  {lbl}  {msg}", flush=True)

# ── Öffentliche API ───────────────────────────────────────────────

def banner() -> None:
    line = f"{CY}{'─' * 64}{R}"
    print()
    print(f"  {line}")
    print(f"  {CY}│{R}                                                              {CY}│{R}")
    print(f"  {CY}│{R}    {B}{CY}J.A.R.V.I.S{R}   Just A Rather Very Intelligent System       {CY}│{R}")
    print(f"  {CY}│{R}    {D}Python Expert Team  ·  10 Agenten  ·  claude-sonnet-4-6{R}   {CY}│{R}")
    print(f"  {CY}│{R}                                                              {CY}│{R}")
    print(f"  {line}")
    print()


def server_ready(port: int = 5000) -> None:
    print(f"  {GR}●{R} Server läuft auf {B}http://localhost:{port}{R}")
    print(f"  {GR}●{R} Stimmerkennung bereit  {GY}(Google Speech API){R}")
    print(f"  {GR}●{R} Warte auf Eingaben...")
    _divider()
    print()


def _divider() -> None:
    print(f"  {GY}{'─' * 64}{R}", flush=True)


def user_msg(text: str) -> None:
    _divider()
    _row(WH, "USER", f"{B}\"{_short(text, 70)}\"{R}")


def jarvis_thinking(text: str = "") -> None:
    msg = _short(text, 80) if text else "Analysiert..."
    _row(CY, "JARVIS", f"{CY}{msg}{R}")


def agent_start(key: str, name: str, task: str = "") -> None:
    col = _AC.get(key, PU)
    task_str = f"  {GY}→ {_short(task, 55)}{R}" if task else ""
    _row(col, name, f"{col}{B}aktiviert{R}{task_str}")


def agent_done(key: str, name: str, elapsed: float = 0.0) -> None:
    col     = _AC.get(key, PU)
    t_str   = f"  {GY}({elapsed:.1f}s){R}" if elapsed > 0 else ""
    _row(col, name, f"{GR}✓ fertig{R}{t_str}")


def tool_call(tool: str, detail: str = "") -> None:
    lbl    = _TOOL_LABEL.get(tool, tool[:7].upper().ljust(7))
    detail_str = f" {GY}{_short(detail, 55)}{R}" if detail else ""
    _row(YL, lbl, f"{YL}läuft...{R}{detail_str}")


def tool_done(tool: str, result_size: int = 0, elapsed: float = 0.0) -> None:
    lbl   = _TOOL_LABEL.get(tool, tool[:7].upper().ljust(7))
    parts = []
    if result_size: parts.append(_sz(result_size))
    if elapsed > 0: parts.append(f"{elapsed:.1f}s")
    extra = f"  {GY}{' · '.join(parts)}{R}" if parts else ""
    _row(YL, lbl, f"{GR}✓ fertig{R}{extra}")


def tool_error(tool: str, error: str) -> None:
    lbl = _TOOL_LABEL.get(tool, tool[:7].upper().ljust(7))
    _row(RD, lbl, f"{RD}✕ {_short(error, 70)}{R}")


def response_done(elapsed: float = 0.0, tokens: int = 0) -> None:
    parts = []
    if tokens:       parts.append(f"{tokens} Tokens")
    if elapsed > 0:  parts.append(f"{elapsed:.1f}s")
    extra = f"  {GY}{'  ·  '.join(parts)}{R}" if parts else ""
    _row(CY, "JARVIS", f"{GR}Antwort fertig{R}{extra}")


def voice_received(size: int) -> None:
    _row(BL, "AUDIO", f"{GY}Empfangen: {_sz(size)}  →  ffmpeg konvertiert...{R}")


def voice_wav(duration: float, rms: float) -> None:
    bar_len = min(int(rms / 500 * 20), 20)
    bar     = f"{GR}{'█' * bar_len}{GY}{'░' * (20 - bar_len)}{R}"
    _row(BL, "AUDIO", f"{GY}{duration:.1f}s{R}  {bar}  {GY}Lautstärke: {rms:.0f}{R}")


def voice_recognized(text: str, lang: str = "DE") -> None:
    _row(BL, "STIMME", f"{B}{WH}\"{_short(text, 65)}\"{R}  {GY}[{lang}]{R}")


def voice_nothing() -> None:
    _row(BL, "STIMME", f"{GY}Nichts erkannt (zu leise oder Stille){R}")


def voice_error(msg: str) -> None:
    _row(RD, "STIMME", f"{RD}Fehler: {_short(msg, 60)}{R}")


def reset_conversation() -> None:
    _divider()
    _row(CY, "SYSTEM", f"{YL}Konversation zurückgesetzt{R}")
    _divider()
    print()


def warn(msg: str) -> None:
    _row(OR, "WARNUNG", f"{OR}{_short(msg, 70)}{R}")


def err(msg: str) -> None:
    _row(RD, "FEHLER", f"{RD}{_short(msg, 70)}{R}")

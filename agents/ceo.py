"""
JARVIS — CEO Agent. Einziger Ansprechpartner fuer den User.
Koordiniert das Team via Anthropic tool-use und hat Zugriff auf den PC.
"""
import json
import re
import time
import uuid
import anthropic
from config import get_api_key
from agents.tools import TOOL_DEFINITIONS, execute_tool
from agents.team import TEAM
import jarvis_log as log
import tts as _tts


def _strip_emojis(text: str) -> str:
    out = []
    for ch in text:
        cp = ord(ch)
        if (0x2600 <= cp <= 0x27BF or 0x1F300 <= cp <= 0x1FAFF
                or 0xFE00 <= cp <= 0xFE0F or cp == 0x200D or cp == 0x20E3):
            continue
        out.append(ch)
    return ''.join(out)


def _extract_spoken(text: str, max_chars: int = 200) -> str:
    text = _strip_emojis(text)
    text = re.sub(r'```[\s\S]*?```', 'Code-Beispiel anbei.', text)
    text = re.sub(r'`[^`\n]+`', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'^#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}([^*\n]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,2}([^_\n]+)_{1,2}', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'^\s*[-*+\d.]+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-=_]{3,}$', '', text, flags=re.MULTILINE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n+', ' ', text).strip()
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'[|~^\\]', '', text)
    if not text:
        return ''
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    result = ''
    for s in sentences[:2]:
        candidate = (result + ' ' + s).strip()
        if len(candidate) <= max_chars:
            result = candidate
        else:
            break
    return result.strip() or text[:max_chars]


CEO_MODEL  = "claude-sonnet-4-6"
CEO_SYSTEM = """\
Du bist JARVIS, CEO eines Python Expert Agent Teams. Du sprichst direkt mit dem User.

## Team (via delegate_to_agent):
- library       → LibraryScout   : Library-Auswahl, PyPI
- research      → ResearchBot    : Docs, Best Practices
- senior_dev    → SeniorPy       : Python-Code, Architektur
- ux            → UXCrafter      : API/CLI-Design
- code_reviewer → ReviewMaster   : Code-Reviews
- debugger      → DebugHunter    : Debugging, Tracebacks
- bug_fixer     → BugSlayer      : Bug-Fixes mit Tests
- bug_expert    → BugWizard      : Bug-Pattern-Analyse
- performance   → SpeedDemon     : Profiling, Optimierung
- security      → SecureGuard    : Security-Analyse

## PC-Tools:
read_file, write_file, run_command, list_directory, search_files

## Browser-Tools:
browse_web, web_click, web_type, search_web

## Regeln:
1. Einfache Frage → direkt antworten, kein Tool
2. Code analysieren → Datei lesen, delegieren
3. Code schreiben → senior_dev, Datei schreiben
4. Mehrere Aspekte → mehrere Agenten
5. Datei erwaehnt → zuerst lesen

## Antwort-Stil — WICHTIG:
- SO KURZ WIE MOEGLICH. Einfache Fragen: 1-2 Saetze. Fertig.
- Keine Floskeln: kein "Natuerlich!", "Gerne!", "Selbstverstaendlich".
- Nur bei echter Komplexitaet (Code, tiefe Analyse) ausfuehrlicher.
- Sprache: Deutsch oder Englisch — passe dich dem User an.
- Code → Code-Bloecke. Kurze Antworten → kein Markdown.
"""


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class JarvisCEO:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=get_api_key())
        self.history: list[dict] = []

    def stream(self, user_message: str):
        """Generator — yields SSE strings. Nutzt echtes Streaming fuer sofortige Token."""
        self.history.append({"role": "user", "content": user_message})
        messages = list(self.history)

        log.user_msg(user_message)
        log.jarvis_thinking()
        yield _sse({"type": "status", "text": "JARVIS analysiert..."})

        stream_start     = time.time()
        token_count      = 0
        accumulated_resp = ""

        while True:
            round_text    = ""
            tool_calls    = []
            current_tool: dict | None = None
            has_tool_use  = False

            # ── Echter Anthropic-Stream — erster Token in ~0.3s ──────────
            with self._client.messages.stream(
                model=CEO_MODEL,
                max_tokens=4096,
                system=CEO_SYSTEM,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            ) as s:
                for event in s:
                    etype = event.type

                    if etype == "content_block_start":
                        blk = event.content_block
                        if blk.type == "tool_use":
                            has_tool_use = True
                            current_tool = {"id": blk.id, "name": blk.name, "input_str": ""}

                    elif etype == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            chunk        = delta.text
                            round_text  += chunk
                            token_count += 1
                            yield _sse({"type": "token", "text": chunk})

                        elif delta.type == "input_json_delta" and current_tool:
                            current_tool["input_str"] += delta.partial_json

                    elif etype == "content_block_stop":
                        if current_tool:
                            try:
                                current_tool["input"] = json.loads(current_tool["input_str"] or "{}")
                            except Exception:
                                current_tool["input"] = {}
                            tool_calls.append(current_tool)
                            current_tool = None

                final_msg = s.get_final_message()

            # ── Tool-use Round ────────────────────────────────────────────
            if has_tool_use:
                messages.append({"role": "assistant", "content": final_msg.content})
                if round_text.strip():
                    log.jarvis_thinking(round_text)

                tool_results = []
                for tc in tool_calls:
                    tool_name  = tc["name"]
                    tool_input = tc["input"]
                    tool_id    = tc["id"]

                    extra = {}
                    if tool_name == "delegate_to_agent":
                        agent_key = tool_input.get("agent", "")
                        agent_obj = TEAM.get(agent_key)
                        task_text = tool_input.get("task", "")
                        extra = {
                            "agent_key":  agent_key,
                            "agent_name": agent_obj.name if agent_obj else agent_key,
                            "agent_role": agent_obj.role if agent_obj else "",
                        }
                        log.agent_start(agent_key, agent_obj.name if agent_obj else agent_key, task_text)
                    else:
                        detail = (tool_input.get("path") or tool_input.get("command") or
                                  tool_input.get("pattern") or tool_input.get("url") or "")
                        log.tool_call(tool_name, str(detail))

                    yield _sse({
                        "type":    "tool_call",
                        "tool":    tool_name,
                        "input":   tool_input,
                        "tool_id": tool_id,
                        **extra,
                    })

                    t0 = time.time()
                    try:
                        result = execute_tool(tool_name, tool_input)
                    except Exception as exc:
                        result = f"Tool-Fehler: {exc}"
                        log.tool_error(tool_name, str(exc))
                        yield _sse({"type": "tool_error", "tool": tool_name,
                                    "tool_id": tool_id, "error": str(exc)})

                    elapsed_t  = time.time() - t0
                    str_result = str(result)

                    if tool_name == "delegate_to_agent":
                        agent_key = tool_input.get("agent", "")
                        agent_obj = TEAM.get(agent_key)
                        log.agent_done(agent_key, agent_obj.name if agent_obj else agent_key, elapsed_t)
                    else:
                        log.tool_done(tool_name, len(str_result), elapsed_t)

                    yield _sse({
                        "type":    "tool_result",
                        "tool":    tool_name,
                        "tool_id": tool_id,
                        "result":  str_result[:2000],
                    })

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tool_id,
                        "content":     str_result,
                    })

                accumulated_resp += round_text
                messages.append({"role": "user", "content": tool_results})

            # ── Finale Antwort ─────────────────────────────────────────────
            else:
                accumulated_resp += round_text

                # spoken immer NACH done — Text fertig geschrieben, dann Ton
                spoken = _extract_spoken(round_text) or round_text.strip()
                if spoken and len(spoken) > 3:
                    rid = uuid.uuid4().hex[:10]
                    _tts.prebuild(spoken, rid)
                    log.tool_call("tts", f"→ spoken: {spoken[:60]}")
                    yield _sse({"type": "spoken", "text": spoken, "id": rid})
                else:
                    log.warn(f"TTS: kein spoken (round_text={repr(round_text[:40])})")

                self.history.append({"role": "assistant", "content": accumulated_resp})
                log.response_done(elapsed=time.time() - stream_start, tokens=token_count)
                yield _sse({"type": "done"})
                break

    def reset(self):
        self.history.clear()
        for agent in TEAM.values():
            agent.reset()

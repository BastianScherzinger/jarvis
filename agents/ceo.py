"""
JARVIS — CEO Agent. Einziger Ansprechpartner fuer den User.
Koordiniert das Team via Anthropic tool-use und hat Zugriff auf den PC.
"""
import base64 as _b64
import datetime
import json
import re
import time
from pathlib import Path
import anthropic
from config import get_api_key
from agents.tools import TOOL_DEFINITIONS, execute_tool
from agents.team import TEAM
import jarvis_log as log
import tts as _tts

_BRAIN_DIR = Path(__file__).parent.parent / "obsidian_brain"


def _brain_entry(topic: str, lines: list[str]) -> None:
    """Schreibt einen Eintrag in obsidian_brain/ — lässt das Wissen wachsen."""
    try:
        _BRAIN_DIR.mkdir(exist_ok=True)
        safe = re.sub(r'[^\w\säöüÄÖÜß-]', '', topic)[:45].strip()
        safe = re.sub(r'\s+', '_', safe) or "session"
        fname = _BRAIN_DIR / f"{safe}.md"
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        block = f"\n## {ts}\n" + "\n".join(f"- {l}" for l in lines if str(l).strip()) + "\n"
        with open(fname, 'a', encoding='utf-8') as f:
            f.write(block)
    except Exception:
        pass  # Brain-Schreiben darf nie den Haupt-Flow unterbrechen


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


_usage: dict = {"input": 0, "output": 0, "requests": 0, "last_ctx": 0}

def get_usage() -> dict:
    return dict(_usage)


CEO_MODEL = "claude-sonnet-4-6"

_SYSTEM_FALLBACK = """\
Du bist JARVIS — Just A Rather Very Intelligent System.
Sprich den User als "Sir" an. Antworte kurz und präzise. Handle direkt.
"""


def _ollama_token_stream(history: list[dict], system: str):
    """Yields rohe Text-Chunks aus Ollama — Fallback wenn Claude nicht erreichbar."""
    import os as _os
    import urllib.request as _req
    import urllib.error as _uerr

    model = _os.environ.get("JARVIS_LOCAL_MODEL", "qwen2.5:7b")

    # Anthropic-Format → Ollama
    ollama_msgs = [{"role": "system", "content": system}]
    for m in history:
        content = m.get("content", "")
        if isinstance(content, list):
            parts = []
            for b in content:
                if isinstance(b, dict):
                    parts.append(b.get("text") or b.get("content") or "")
                elif hasattr(b, "text"):
                    parts.append(b.text)
            content = " ".join(p for p in parts if p).strip() or "(Tool-Ergebnis)"
        ollama_msgs.append({"role": m["role"], "content": str(content)})

    payload = json.dumps({
        "model": model,
        "messages": ollama_msgs,
        "stream": True,
    }).encode("utf-8")

    request = _req.Request(
        "http://localhost:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with _req.urlopen(request, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    chunk = obj.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if obj.get("done"):
                        break
                except json.JSONDecodeError:
                    continue
    except _uerr.URLError:
        yield "\n\n*Offline: Claude und Ollama nicht erreichbar. Bitte `ollama serve` starten.*"
    except Exception as exc:
        yield f"\n\n*Ollama-Fehler: {exc}*"


def _load_system_prompt() -> str:
    """Lädt CLAUDE.md als System-Prompt — kennt seine Identität und Tools."""
    claude_md = Path(__file__).parent.parent / "CLAUDE.md"
    if claude_md.exists():
        try:
            content = claude_md.read_text(encoding="utf-8").strip()
            return (
                content
                + "\n\n## Antwort-Stil\n"
                "- SO KURZ WIE MÖGLICH. Einfache Fragen: 1-2 Sätze.\n"
                "- Keine Floskeln (kein 'Natürlich!', 'Gerne!').\n"
                "- Kurze Antworten → kein Markdown. Code → Code-Blöcke.\n"
            )
        except Exception:
            pass
    return _SYSTEM_FALLBACK


CEO_SYSTEM = _load_system_prompt()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _jarvis_ollama_fallback(ceo, messages: list[dict], user_message: str):
    """Generator — übernimmt mit Ollama wenn Claude ausfällt. Liefert SSE-Strings."""
    fallback_text = ""
    for chunk in _ollama_token_stream(messages, CEO_SYSTEM):
        fallback_text += chunk
        yield _sse({"type": "token", "text": chunk})

    ceo.history.append({"role": "assistant", "content": fallback_text})
    _brain_entry(
        user_message[:40],
        [f"Frage: {user_message[:100]}", f"Offline-Antwort (Ollama): {fallback_text[:160]}"],
    )
    yield _sse({"type": "done", "usage": dict(_usage)})

    spoken = _extract_spoken(fallback_text) or fallback_text.strip()
    if spoken and len(spoken) > 3:
        try:
            audio_bytes, mime = _tts.speak(spoken)
            log.tool_call("tts", f"→ {len(audio_bytes)//1024}KB (Fallback): {spoken[:50]}")
            yield _sse({
                "type":      "spoken",
                "text":      spoken,
                "audio_b64": _b64.b64encode(audio_bytes).decode("ascii"),
                "mime":      mime,
                "final":     True,
            })
        except Exception as tts_e:
            log.warn(f"TTS Fallback: {tts_e}")


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

        _rate_retries = 0

        while True:
            round_text = ""

            # ── Echter Anthropic-Stream ───────────────────────────────────
            try:
                with self._client.messages.stream(
                    model=CEO_MODEL,
                    max_tokens=4096,
                    system=CEO_SYSTEM,
                    tools=TOOL_DEFINITIONS,
                    messages=messages,
                ) as s:
                    for event in s:
                        if event.type == "content_block_delta":
                            delta = event.delta
                            if delta.type == "text_delta":
                                chunk        = delta.text
                                round_text  += chunk
                                token_count += 1
                                yield _sse({"type": "token", "text": chunk})

                    final_msg = s.get_final_message()
                    if hasattr(final_msg, "usage") and final_msg.usage:
                        _in = final_msg.usage.input_tokens or 0
                        _usage["input"]    += _in
                        _usage["output"]   += final_msg.usage.output_tokens or 0
                        _usage["requests"] += 1
                        _usage["last_ctx"]  = _in  # aktueller Kontext-Snapshot
                _rate_retries = 0

            except anthropic.RateLimitError as e:
                _rate_retries += 1
                wait_s = 15 * _rate_retries
                log.warn(f"Rate-Limit (429) — warte {wait_s}s (Versuch {_rate_retries}): {e}")
                yield _sse({"type": "token",
                            "text": f"\n\n*Rate-Limit — kurze Pause ({wait_s}s)...*"})
                if _rate_retries <= 3:
                    time.sleep(wait_s)
                    continue
                # Nach 3 Versuchen → Ollama Fallback
                log.warn("Rate-Limit erschöpft — Ollama Fallback")
                yield _sse({"type": "token", "text": "\n\n*Claude Rate-Limit — lokales Modell übernimmt.*\n\n"})
                yield from _jarvis_ollama_fallback(self, messages, user_message)
                break

            except (anthropic.APIConnectionError, anthropic.AuthenticationError) as e:
                log.warn(f"Claude nicht erreichbar ({type(e).__name__}) — Ollama Fallback")
                yield _sse({"type": "token", "text": "*[Claude offline — lokales Modell aktiv]*\n\n"})
                yield from _jarvis_ollama_fallback(self, messages, user_message)
                break

            except anthropic.BadRequestError as e:
                log.warn(f"BadRequest (400) — History reset: {e}")
                self.history.clear()
                yield _sse({"type": "token",
                            "text": "\n\n*Konversation zurückgesetzt. Bitte erneut senden.*"})
                yield _sse({"type": "done", "usage": dict(_usage)})
                break

            except Exception as e:
                log.warn(f"API-Fehler: {type(e).__name__}: {e}")
                err_str = str(e).lower()
                if any(kw in err_str for kw in ("connection", "timeout", "network", "ssl", "resolve", "unreachable")):
                    log.warn("Verbindungsfehler — Ollama Fallback")
                    yield _sse({"type": "token", "text": "*[Verbindungsfehler — lokales Modell]*\n\n"})
                    yield from _jarvis_ollama_fallback(self, messages, user_message)
                else:
                    self.history.clear()
                    yield _sse({"type": "token", "text": f"\n\n*Fehler: {e}*"})
                    yield _sse({"type": "done", "usage": dict(_usage)})
                break

            # ── Tool-calls aus final_msg.content (autoritativ) ────────────
            tool_calls = []
            for block in (final_msg.content or []):
                if getattr(block, "type", None) == "tool_use":
                    tool_calls.append({
                        "id":    block.id,
                        "name":  block.name,
                        "input": dict(block.input) if block.input else {},
                    })

            # ── Tool-use Round ────────────────────────────────────────────
            if tool_calls:
                messages.append({"role": "assistant", "content": final_msg.content})

                if round_text.strip():
                    log.jarvis_thinking(round_text)
                    spoken_inter = _extract_spoken(round_text) or round_text.strip()
                    if spoken_inter and len(spoken_inter) > 3:
                        try:
                            audio_bytes, mime = _tts.speak(spoken_inter)
                            log.tool_call("tts", f"→ {len(audio_bytes)//1024}KB (zwischendurch): {spoken_inter[:50]}")
                            yield _sse({
                                "type":      "spoken",
                                "text":      spoken_inter,
                                "audio_b64": _b64.b64encode(audio_bytes).decode("ascii"),
                                "mime":      mime,
                                "final":     False,
                            })
                        except Exception as e:
                            log.warn(f"TTS intermediate: {e}")

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
                        # Brain: Agent-Delegation protokollieren
                        task_snippet = tool_input.get("task", "")[:80]
                        _brain_entry(
                            f"Agent {agent_key}",
                            [f"Agent: {agent_obj.name if agent_obj else agent_key}",
                             f"Aufgabe: {task_snippet}",
                             f"Ergebnis: {str_result[:120]}"],
                        )
                    else:
                        log.tool_done(tool_name, len(str_result), elapsed_t)
                        # Brain: PC/Browser-Tool protokollieren
                        detail = (tool_input.get("path") or tool_input.get("command") or
                                  tool_input.get("url") or tool_input.get("query") or
                                  tool_input.get("pattern") or "")
                        _brain_entry(
                            tool_name,
                            [f"Tool: {tool_name}",
                             f"Aktion: {str(detail)[:80]}",
                             f"Ergebnis: {str_result[:120]}"],
                        )

                    yield _sse({
                        "type":    "tool_result",
                        "tool":    tool_name,
                        "tool_id": tool_id,
                        "result":  str_result[:2000],
                    })

                    # In History kürzen: max 5000 Zeichen pro Ergebnis → verhindert Rate-Limit
                    hist_content = (str_result if len(str_result) <= 5000
                                    else str_result[:5000] + "\n... [gekürzt]")
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tool_id,
                        "content":     hist_content,
                    })

                accumulated_resp += round_text
                messages.append({"role": "user", "content": tool_results})

            # ── Finale Antwort ─────────────────────────────────────────────
            else:
                accumulated_resp += round_text
                self.history.append({"role": "assistant", "content": accumulated_resp})
                log.response_done(elapsed=time.time() - stream_start, tokens=token_count)

                # Brain: Gesprächs-Eintrag — Wissen wächst mit jeder Antwort
                _brain_entry(
                    user_message[:40],
                    [f"Frage: {user_message[:100]}",
                     f"Antwort: {round_text[:160]}"],
                )

                yield _sse({"type": "done", "usage": dict(_usage)})

                spoken = _extract_spoken(round_text) or round_text.strip()
                if spoken and len(spoken) > 3:
                    try:
                        audio_bytes, mime = _tts.speak(spoken)
                        log.tool_call("tts", f"→ {len(audio_bytes)//1024}KB: {spoken[:50]}")
                        yield _sse({
                            "type":      "spoken",
                            "text":      spoken,
                            "audio_b64": _b64.b64encode(audio_bytes).decode("ascii"),
                            "mime":      mime,
                            "final":     True,
                        })
                    except Exception as e:
                        log.warn(f"TTS fehlgeschlagen: {e}")
                else:
                    log.warn(f"TTS: kein Text (round_text={repr(round_text[:40])})")
                break

    def reset(self):
        self.history.clear()
        for agent in TEAM.values():
            agent.reset()

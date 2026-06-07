"""
JARVIS — CEO Agent. Einziger Ansprechpartner für den User.
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

def _strip_emojis(text: str) -> str:
    """Entfernt Emojis per Codepoint-Check — kein Encoding-Problem."""
    out = []
    for ch in text:
        cp = ord(ch)
        if (0x2600 <= cp <= 0x27BF       # Misc Symbols + Dingbats
                or 0x1F300 <= cp <= 0x1FAFF  # Alle Emoji-Bloecke
                or 0xFE00 <= cp <= 0xFE0F    # Variation Selectors
                or cp == 0x200D              # Zero-Width Joiner
                or cp == 0x20E3):            # Combining Keycap
            continue
        out.append(ch)
    return ''.join(out)


def _extract_spoken(text: str, max_chars: int = 240) -> str:
    """
    Extrahiert 1-2 natuerlich klingende Saetze fuer TTS.
    Entfernt: Emojis, Code-Bloecke, Markdown, URLs, Listen.
    """
    # Emojis entfernen
    text = _strip_emojis(text)
    # Code-Bloecke ersetzen
    text = re.sub(r'```[\s\S]*?```', 'Code-Beispiel anbei.', text)
    # Inline-Code
    text = re.sub(r'`[^`\n]+`', '', text)
    # URLs
    text = re.sub(r'https?://\S+', '', text)
    # Markdown-Ueberschriften
    text = re.sub(r'^#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
    # Bold / Italic
    text = re.sub(r'\*{1,3}([^*\n]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,2}([^_\n]+)_{1,2}', r'\1', text)
    # Markdown-Links
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Listen-Punkte
    text = re.sub(r'^\s*[-*+\d.]+\s+', '', text, flags=re.MULTILINE)
    # Trennlinien
    text = re.sub(r'^[-=_]{3,}$', '', text, flags=re.MULTILINE)
    # HTML
    text = re.sub(r'<[^>]+>', '', text)
    # Zeilenumbrueche → Leerzeichen
    text = re.sub(r'\n+', ' ', text).strip()
    # Doppelte Leerzeichen
    text = re.sub(r' {2,}', ' ', text)
    # Uebrige Sonderzeichen die TTS stoeren (Pipe, Tilde, etc.)
    text = re.sub(r'[|~^\\]', '', text)

    if not text:
        return ''

    # Erste 1-2 vollstaendige Saetze
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
Du bist JARVIS, der CEO und alleinige Ansprechpartner eines Python Expert Agent Teams.
Du sprichst direkt mit dem User — alle anderen Agenten arbeiten unsichtbar im Hintergrund.

## Dein Team — rufe sie über `delegate_to_agent` auf:
- library      → LibraryScout   : Library-Auswahl, Package-Vergleiche, PyPI-Ökosystem
- research     → ResearchBot    : PEPs, offizielle Docs, Best Practices, technische Recherche
- senior_dev   → SeniorPy       : Python-Implementierung, Architektur, idiomatischer Code
- ux           → UXCrafter      : API/CLI-Design, Developer Experience, Fehlermeldungen
- code_reviewer→ ReviewMaster   : Code-Reviews mit Severity-Labels, Verbesserungsvorschläge
- debugger     → DebugHunter    : Debugging, Traceback-Analyse, pdb/py-spy
- bug_fixer    → BugSlayer      : Konkrete Bug-Fixes mit Regressions-Tests
- bug_expert   → BugWizard      : Bug-Pattern-Analyse, systemische Prävention
- performance  → SpeedDemon     : Profiling, Optimierung, Caching-Strategien
- security     → SecureGuard    : Security-Analyse, OWASP, CVE-Checks

## Deine PC-Tools:
- read_file        : Beliebige Datei vom PC lesen
- write_file       : Datei auf dem PC erstellen/überschreiben
- run_command      : PowerShell-Befehl auf dem Windows-PC ausführen
- list_directory   : Verzeichnis auflisten
- search_files     : Dateien suchen (Glob + optionale Inhaltssuche)
- delegate_to_agent: Aufgabe an Spezialisten im Team abgeben

## Browser-Tools (Playwright):
- browse_web       : Webseite öffnen und Inhalt lesen (Docs, GitHub, PyPI, Artikel...)
- web_click        : Element auf der Seite anklicken (Button, Link...)
- web_type         : Text in Eingabefeld eingeben (Suche, Formulare...)
- search_web       : Web-Suche via DuckDuckGo — liefert Top-Ergebnisse mit URLs

## Entscheidungsregeln:
1. Einfache Fragen / Erklärungen → direkt antworten, kein Tool nötig
2. Code analysieren / reviewen / debuggen → lies Datei zuerst, dann delegiere
3. Code schreiben → delegiere an senior_dev, schreibe dann in Datei
4. PC-Aufgaben (Dateien, Commands) → nutze die PC-Tools direkt
5. Mehrere Aspekte (z.B. Review + Security) → mehrere Agenten nacheinander
6. Dateien im Gespräch erwähnt → lese sie zuerst, bevor du antwortest

## Stil:
- Klar, direkt, ohne Floskeln
- Erkläre kurz WAS du gerade tust (welche Tools, welche Agenten)
- Am Ende: klare Synthese der Ergebnisse
- Sprache: passe dich dem User an (Deutsch/Englisch)
- Formatiere die finale Antwort mit Markdown (Überschriften, Code-Blöcke, Listen)
"""


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class JarvisCEO:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=get_api_key())
        self.history: list[dict] = []

    def stream(self, user_message: str):
        """Generator — yields SSE event strings."""
        self.history.append({"role": "user", "content": user_message})
        messages = list(self.history)

        log.user_msg(user_message)
        log.jarvis_thinking()
        yield _sse({"type": "status", "text": "JARVIS analysiert..."})

        accumulated_response = ""
        stream_start = time.time()
        token_count  = 0

        while True:
            response = self._client.messages.create(
                model=CEO_MODEL,
                max_tokens=8096,
                system=CEO_SYSTEM,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            # ── Tool-use round ───────────────────────────────────────────
            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []

                for block in response.content:
                    if block.type == "text" and block.text.strip():
                        log.jarvis_thinking(block.text)
                        yield _sse({"type": "thinking", "text": block.text})

                    elif block.type == "tool_use":
                        tool_name  = block.name
                        tool_input = block.input

                        # Extra info for delegate events
                        extra = {}
                        if tool_name == "delegate_to_agent":
                            agent_key  = tool_input.get("agent", "")
                            agent_obj  = TEAM.get(agent_key)
                            task_text  = tool_input.get("task", "")
                            extra = {
                                "agent_key":  agent_key,
                                "agent_name": agent_obj.name if agent_obj else agent_key,
                                "agent_role": agent_obj.role if agent_obj else "",
                            }
                            log.agent_start(agent_key, agent_obj.name if agent_obj else agent_key, task_text)
                        else:
                            detail = (tool_input.get("path") or tool_input.get("command") or
                                      tool_input.get("pattern") or "")
                            log.tool_call(tool_name, str(detail))

                        yield _sse({
                            "type":    "tool_call",
                            "tool":    tool_name,
                            "input":   tool_input,
                            "tool_id": block.id,
                            **extra,
                        })

                        t0 = time.time()
                        try:
                            result = execute_tool(tool_name, tool_input)
                        except Exception as exc:
                            result = f"Tool-Fehler: {exc}"
                            log.tool_error(tool_name, str(exc))
                            yield _sse({"type": "tool_error", "tool": tool_name, "tool_id": block.id, "error": str(exc)})

                        elapsed = time.time() - t0
                        str_result = str(result)

                        if tool_name == "delegate_to_agent":
                            agent_key = tool_input.get("agent", "")
                            agent_obj = TEAM.get(agent_key)
                            log.agent_done(agent_key, agent_obj.name if agent_obj else agent_key, elapsed)
                        else:
                            log.tool_done(tool_name, len(str_result), elapsed)

                        yield _sse({
                            "type":    "tool_result",
                            "tool":    tool_name,
                            "tool_id": block.id,
                            "result":  str_result[:2000],
                        })

                        tool_results.append({
                            "type":        "tool_result",
                            "tool_use_id": block.id,
                            "content":     str_result,
                        })

                messages.append({"role": "user", "content": tool_results})

            # ── Final response ────────────────────────────────────────────
            else:
                # Erst vollstaendigen Text sammeln
                for block in response.content:
                    if hasattr(block, "text"):
                        accumulated_response += block.text
                        token_count += len(block.text.split())

                # spoken-Text extrahieren und TTS SOFORT vorab generieren,
                # bevor Tokens gestreamt werden — dadurch ist Audio meist
                # schon fertig wenn der Browser fragt.
                spoken = _extract_spoken(accumulated_response)
                rid = ''
                if spoken:
                    import tts as _tts
                    rid = uuid.uuid4().hex[:10]
                    _tts.prebuild(spoken, rid)          # Hintergrund-Thread
                    yield _sse({"type": "spoken", "text": spoken, "id": rid})

                # Tokens Wort fuer Wort streamen (visueller Tipp-Effekt)
                words = accumulated_response.split(" ")
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield _sse({"type": "token", "text": chunk})

                self.history.append({"role": "assistant", "content": accumulated_response})
                log.response_done(elapsed=time.time() - stream_start, tokens=token_count)
                yield _sse({"type": "done"})
                break

    def reset(self):
        self.history.clear()
        for agent in TEAM.values():
            agent.reset()

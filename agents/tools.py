"""
PC-Access-Tools und Tool-Definitionen für den CEO-Agenten JARVIS.
"""
import subprocess
from pathlib import Path
from datetime import datetime

# Playwright-Browser-Session (persistent über Tool-Calls hinweg)
_pw        = None   # playwright context
_browser   = None
_page      = None

WORKSPACE = Path(__file__).parent.parent / "workspace"
WORKSPACE_TASKS   = WORKSPACE / "tasks"
WORKSPACE_RESULTS = WORKSPACE / "results"

for _d in [WORKSPACE, WORKSPACE_TASKS, WORKSPACE_RESULTS]:
    _d.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# TOOL DEFINITIONS (Anthropic tool-use schema)
# ---------------------------------------------------------------------------
TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Liest den Inhalt einer Datei vom PC des Users. Unterstützt alle Dateitypen.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absoluter Pfad zur Datei (z.B. C:\\Users\\name\\code.py)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Schreibt Inhalt in eine Datei auf dem PC. Erstellt fehlende Verzeichnisse automatisch.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string", "description": "Absoluter Pfad zur Zieldatei"},
                "content": {"type": "string", "description": "Zu schreibender Inhalt"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": "Führt einen PowerShell-Befehl auf dem Windows-PC aus und gibt stdout/stderr zurück.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "PowerShell-Befehl"},
                "timeout": {"type": "integer", "description": "Timeout in Sekunden (default 30)", "default": 30},
            },
            "required": ["command"],
        },
    },
    {
        "name": "list_directory",
        "description": "Listet Dateien und Ordner in einem Verzeichnis auf.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":      {"type": "string", "description": "Verzeichnispfad"},
                "recursive": {"type": "boolean", "description": "Rekursiv alle Unterordner (default false)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_files",
        "description": "Sucht nach Dateien via Glob-Pattern. Optional: Filtert nach Inhalt (enthält Suchbegriff).",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern":        {"type": "string", "description": "Glob-Pattern, z.B. **/*.py oder *.txt"},
                "path":           {"type": "string", "description": "Startverzeichnis für die Suche"},
                "content_search": {"type": "string", "description": "Optional: Nur Dateien die diesen Text enthalten"},
            },
            "required": ["pattern", "path"],
        },
    },
    {
        "name": "browse_web",
        "description": (
            "Öffnet eine Webseite im Browser und gibt Titel + sichtbaren Text zurück. "
            "Ideal für: Dokumentation lesen, GitHub Issues, Stack Overflow, PyPI-Seiten, Artikel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url":      {"type": "string", "description": "Vollständige URL inkl. https://"},
                "selector": {"type": "string", "description": "Optional: CSS-Selektor um nur einen Teil zu lesen (z.B. 'main', 'article', '#readme')"},
                "wait_for": {"type": "string", "description": "Optional: CSS-Selektor auf den gewartet wird bevor der Inhalt gelesen wird"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_click",
        "description": "Klickt auf ein Element auf der aktuell geöffneten Webseite (nach browse_web).",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS-Selektor oder Text des Elements (z.B. 'button:text(\"Login\")', 'a.nav-link')"},
            },
            "required": ["selector"],
        },
    },
    {
        "name": "web_type",
        "description": "Gibt Text in ein Eingabefeld auf der aktuell geöffneten Webseite ein (nach browse_web).",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS-Selektor des Input-Feldes"},
                "text":     {"type": "string", "description": "Einzugebender Text"},
                "submit":   {"type": "boolean", "description": "Nach Eingabe Enter drücken (default false)"},
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": "search_web",
        "description": "Sucht im Web (DuckDuckGo) und gibt die Top-Ergebnisse zurück (Titel + URL + Snippet).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query":   {"type": "string", "description": "Suchanfrage"},
                "results": {"type": "integer", "description": "Anzahl Ergebnisse (default 5, max 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_screenshot",
        "description": "Macht einen Screenshot der aktuell geöffneten Webseite und speichert ihn. Gibt den Pfad zurück.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Dateiname ohne Pfad (z.B. 'ergebnis.png'). Optional, default: screenshot.png"},
            },
            "required": [],
        },
    },
    {
        "name": "delegate_to_agent",
        "description": (
            "Delegiert eine Spezialaufgabe an einen Experten im Team. "
            "Nutze dieses Tool für: tiefe Code-Analysen, Security-Reviews, "
            "Debugging, Performance-Optimierung, Library-Entscheidungen etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "enum": [
                        "library", "research", "senior_dev", "ux",
                        "code_reviewer", "debugger", "bug_fixer",
                        "bug_expert", "performance", "security",
                    ],
                    "description": "Welcher Spezialist soll die Aufgabe übernehmen",
                },
                "task": {
                    "type": "string",
                    "description": "Detaillierter Aufgaben-Brief für den Agenten (Kontext + konkrete Aufgabe)",
                },
            },
            "required": ["agent", "task"],
        },
    },
]


# ---------------------------------------------------------------------------
# TOOL EXECUTION
# ---------------------------------------------------------------------------

def execute_tool(name: str, inputs: dict) -> str:
    match name:
        case "read_file":
            return _read_file(inputs["path"])
        case "write_file":
            return _write_file(inputs["path"], inputs["content"])
        case "run_command":
            return _run_command(inputs["command"], inputs.get("timeout", 30))
        case "list_directory":
            return _list_directory(inputs["path"], inputs.get("recursive", False))
        case "search_files":
            return _search_files(inputs["pattern"], inputs["path"], inputs.get("content_search"))
        case "browse_web":
            return _browse_web(inputs["url"], inputs.get("selector"), inputs.get("wait_for"))
        case "web_click":
            return _web_click(inputs["selector"])
        case "web_type":
            return _web_type(inputs["selector"], inputs["text"], inputs.get("submit", False))
        case "web_screenshot":
            return _web_screenshot(inputs.get("filename", "screenshot.png"))
        case "search_web":
            return _search_web(inputs["query"], inputs.get("results", 5))
        case "delegate_to_agent":
            return _delegate(inputs["agent"], inputs["task"])
        case _:
            return f"Unbekanntes Tool: {name}"


def _read_file(path: str) -> str:
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Datei nicht gefunden: {path}"
        size = p.stat().st_size
        if size > 500_000:
            return f"Datei zu groß ({size // 1024} KB). Nutze search_files oder lies einen Teil manuell."
        return p.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        return f"Kein Zugriff (PermissionError): {path}"
    except Exception as e:
        return f"Fehler beim Lesen: {e}"


def _write_file(path: str, content: str) -> str:
    try:
        p = Path(path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Gespeichert: {p}  ({len(content):,} Zeichen)"
    except Exception as e:
        return f"Fehler beim Schreiben: {e}"


def _run_command(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        parts = []
        if result.stdout.strip():
            parts.append(f"STDOUT:\n{result.stdout.strip()}")
        if result.stderr.strip():
            parts.append(f"STDERR:\n{result.stderr.strip()}")
        parts.append(f"Exit-Code: {result.returncode}")
        return "\n\n".join(parts) or "(kein Output)"
    except subprocess.TimeoutExpired:
        return f"Timeout nach {timeout}s"
    except Exception as e:
        return f"Fehler: {e}"


def _list_directory(path: str, recursive: bool = False) -> str:
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Verzeichnis nicht gefunden: {path}"
        if not p.is_dir():
            return f"Ist kein Verzeichnis: {path}"

        if recursive:
            entries = sorted(p.rglob("*"))[:300]
        else:
            entries = sorted(p.iterdir())

        lines = []
        for e in entries:
            icon = "📁" if e.is_dir() else "📄"
            name = e.relative_to(p) if recursive else Path(e.name)
            size = ""
            if e.is_file():
                s = e.stat().st_size
                size = f"  {s:,} B" if s < 1024 else f"  {s//1024} KB"
            lines.append(f"{icon} {name}{size}")

        return "\n".join(lines) or "(leer)"
    except Exception as e:
        return f"Fehler: {e}"


def _search_files(pattern: str, path: str, content_search: str | None = None) -> str:
    try:
        base = Path(path).expanduser().resolve()
        if not base.exists():
            return f"Verzeichnis nicht gefunden: {path}"
        matches = [m for m in base.glob(pattern) if m.is_file()][:200]

        if content_search:
            term = content_search.lower()
            filtered = []
            for m in matches:
                try:
                    if term in m.read_text(encoding="utf-8", errors="replace").lower():
                        filtered.append(m)
                except Exception:
                    pass
            matches = filtered

        if not matches:
            return "Keine Dateien gefunden."
        return "\n".join(str(m) for m in sorted(matches))
    except Exception as e:
        return f"Fehler: {e}"


# ── Browser-Tools (Playwright) ────────────────────────────────────

def _get_page():
    """Gibt die aktuelle Playwright-Page zurück, erstellt sie bei Bedarf."""
    global _pw, _browser, _page
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("playwright nicht installiert. Führe aus: pip install playwright && playwright install chromium")

    if _browser is None or not _browser.is_connected():
        if _pw is not None:
            try: _pw.stop()
            except: pass
        import os
        headless = os.environ.get("JARVIS_BROWSER_HEADLESS", "false").lower() != "false"
        _pw      = sync_playwright().start()
        _browser = _pw.chromium.launch(headless=headless)
        _page    = _browser.new_page()
        _page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

    if _page is None or _page.is_closed():
        _page = _browser.new_page()
        _page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

    return _page


def _browse_web(url: str, selector: str | None = None, wait_for: str | None = None) -> str:
    try:
        page = _get_page()
        page.goto(url, timeout=20_000, wait_until="domcontentloaded")

        if wait_for:
            try: page.wait_for_selector(wait_for, timeout=8_000)
            except: pass

        title = page.title()

        if selector:
            try:
                el = page.query_selector(selector)
                text = el.inner_text() if el else page.inner_text("body")
            except:
                text = page.inner_text("body")
        else:
            # Hauptinhalt extrahieren (body ohne script/style)
            text = page.evaluate("""() => {
                const remove = ['script','style','noscript','nav','footer','header','aside'];
                remove.forEach(tag => document.querySelectorAll(tag).forEach(e => e.remove()));
                return document.body ? document.body.innerText : '';
            }""")

        # Text kürzen
        text = " ".join(text.split())   # Whitespace normalisieren
        if len(text) > 8000:
            text = text[:8000] + "\n\n[... Inhalt gekürzt ...]"

        return f"TITEL: {title}\nURL: {url}\n\n{text}"
    except Exception as e:
        return f"Browser-Fehler: {e}"


def _web_click(selector: str) -> str:
    try:
        page = _get_page()
        page.click(selector, timeout=8_000)
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
        return f"Geklickt: {selector} | Neue URL: {page.url}"
    except Exception as e:
        return f"Klick-Fehler: {e}"


def _web_type(selector: str, text: str, submit: bool = False) -> str:
    try:
        page = _get_page()
        page.fill(selector, text)
        if submit:
            page.press(selector, "Enter")
            page.wait_for_load_state("domcontentloaded", timeout=10_000)
        return f"Eingabe in '{selector}': '{text[:50]}'" + (" + Enter" if submit else "")
    except Exception as e:
        return f"Eingabe-Fehler: {e}"


def _web_screenshot(filename: str = "screenshot.png") -> str:
    try:
        page = _get_page()
        if not filename.endswith(".png"):
            filename += ".png"
        out = WORKSPACE / filename
        page.screenshot(path=str(out), full_page=False)
        return f"Screenshot gespeichert: {out}\nAktuelle URL: {page.url}"
    except Exception as e:
        return f"Screenshot-Fehler: {e}"


def _search_web(query: str, max_results: int = 5) -> str:
    """Sucht via DuckDuckGo und gibt strukturierte Ergebnisse zurück."""
    try:
        import urllib.parse
        search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        page = _get_page()
        page.goto(search_url, timeout=20_000, wait_until="domcontentloaded")

        results = page.evaluate("""(max) => {
            const items = [];
            document.querySelectorAll('.result').forEach((el, i) => {
                if (i >= max) return;
                const titleEl   = el.querySelector('.result__title a');
                const snippetEl = el.querySelector('.result__snippet');
                const urlEl     = el.querySelector('.result__url');
                if (!titleEl) return;
                items.push({
                    title:   titleEl.innerText.trim(),
                    url:     urlEl   ? urlEl.innerText.trim()   : '',
                    snippet: snippetEl ? snippetEl.innerText.trim() : '',
                });
            });
            return items;
        }""", min(max_results, 10))

        if not results:
            return "Keine Ergebnisse gefunden."

        lines = [f"Suchergebnisse für: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            if r['url']:     lines.append(f"   {r['url']}")
            if r['snippet']: lines.append(f"   {r['snippet']}")
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        return f"Suche-Fehler: {e}"


def _delegate(agent_key: str, task: str) -> str:
    from agents.team import TEAM  # late import to avoid circular

    if agent_key not in TEAM:
        return f"Agent '{agent_key}' nicht gefunden."

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    task_file = WORKSPACE_TASKS / f"{ts}_{agent_key}.md"
    task_file.write_text(
        f"# Aufgabe für {agent_key}\n_Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}_\n\n{task}",
        encoding="utf-8",
    )

    agent = TEAM[agent_key]
    result = agent.chat(task)

    result_file = WORKSPACE_RESULTS / f"{ts}_{agent_key}.md"
    result_file.write_text(
        f"# Ergebnis von {agent.name}\n_Fertig: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}_\n\n{result}",
        encoding="utf-8",
    )

    return result

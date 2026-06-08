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
                "timeout": {"type": "integer", "description": "Timeout in Sekunden (default 120, für lange Prozesse bis 300)", "default": 120},
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
        "name": "web_scroll",
        "description": "Scrollt auf der aktuellen Seite. Richtungen: down/up/top/bottom. Oder scrollt zu einem Element via Selektor.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["down", "up", "top", "bottom"], "description": "Scroll-Richtung (default: down)"},
                "amount":    {"type": "integer", "description": "Pixel zum Scrollen bei down/up (default: 600)"},
                "selector":  {"type": "string",  "description": "Optional: CSS-Selektor — scrollt direkt zu diesem Element"},
            },
            "required": [],
        },
    },
    {
        "name": "web_get_links",
        "description": "Gibt alle Links der aktuellen Seite zurück (Text + URL). Ideal zum Entdecken von Navigation und Unterseiten.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "Optional: CSS-Selektor um nur Links in einem Bereich zu holen (z.B. 'nav', 'main', 'article')"},
                "filter":   {"type": "string", "description": "Optional: Nur Links die diesen Text oder URL-Teil enthalten"},
            },
            "required": [],
        },
    },
    {
        "name": "web_navigate",
        "description": "Navigiert im Browser: zurück, vorwärts, neu laden oder Status anzeigen (URL + Titel).",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["back", "forward", "reload", "status"],
                    "description": "back=zurück, forward=vorwärts, reload=neu laden, status=aktuelle URL/Titel",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "web_select",
        "description": "Wählt eine Option aus einem <select>-Dropdown auf der aktuellen Seite.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS-Selektor des <select>-Elements"},
                "value":    {"type": "string", "description": "Wert oder sichtbarer Text der Option"},
            },
            "required": ["selector", "value"],
        },
    },
    {
        "name": "web_evaluate",
        "description": (
            "Führt JavaScript auf der aktuellen Seite aus und gibt das Ergebnis zurück. "
            "Sehr mächtig für: Daten-Extraktion, DOM-Zugriff, versteckte Felder auslesen, Formular-Manipulation. "
            "Beispiel: '() => document.title' oder '() => Array.from(document.querySelectorAll(\"h2\")).map(e=>e.innerText)'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "JavaScript als Arrow-Funktion: '() => { return ... }' oder '() => ausdruck'"},
            },
            "required": ["script"],
        },
    },
    {
        "name": "web_extract_table",
        "description": "Extrahiert eine HTML-Tabelle von der aktuellen Seite als lesbaren Text mit Spalten.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS-Selektor für die Tabelle (default: erste Tabelle auf der Seite)"},
                "index":    {"type": "integer", "description": "0-basierter Index wenn mehrere Tabellen (default: 0)"},
            },
            "required": [],
        },
    },
    {
        "name": "download_file",
        "description": "Lädt eine Datei von einer URL herunter und speichert sie im workspace-Ordner.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url":      {"type": "string", "description": "Direkte Download-URL der Datei"},
                "filename": {"type": "string", "description": "Dateiname im workspace (optional, wird aus URL abgeleitet)"},
            },
            "required": ["url"],
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
    {
        "name": "local_ai_worker",
        "description": (
            "Sendet eine Teilaufgabe an ein lokales Ollama-KI-Modell (läuft offline auf dem PC). "
            "Ideal für: große Textverarbeitungen, Vorab-Analyse, Draft-Generierung, repetitive "
            "Subtasks — ohne Claude-API-Kosten. Das Modell ist in .env als JARVIS_LOCAL_MODEL gesetzt. "
            "Nutze dies bei großen Aufgaben um Subtasks parallel vorzubereiten."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Der Prompt / die Aufgabe für das lokale Modell. Sei präzise.",
                },
                "system": {
                    "type": "string",
                    "description": "Optional: System-Prompt für den Worker (Rolle, Fokus, Format)",
                },
                "model": {
                    "type": "string",
                    "description": "Optional: Modellname überschreiben (z.B. 'llama3.3:70b'). Default: aus .env",
                },
            },
            "required": ["task"],
        },
    },
    {
        "name": "generate_image",
        "description": (
            "Generiert ein Bild lokal mit KI (Stable Diffusion / FLUX via Hugging Face Diffusers). "
            "Nutze dieses Tool IMMER wenn Sir 'mach mir ein Bild', 'generiere ein Bild', "
            "'zeichne', 'erstelle ein Foto / eine Illustration von ...' sagt. "
            "Der Prompt sollte auf Englisch sein für maximale Qualität. "
            "Erster Aufruf lädt das Modell herunter (~2-15 GB, einmalig). "
            "Das fertige Bild erscheint direkt im Chat-Fenster."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "Detaillierte Bild-Beschreibung auf Englisch. "
                        "Beispiel: 'futuristic iron man suit in space, cinematic lighting, 8K, detailed'"
                    ),
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Was das Bild NICHT enthalten soll (optional). Default: 'blurry, low quality, watermark'",
                },
                "steps": {
                    "type": "integer",
                    "description": "Inference-Schritte (default: 25). Mehr = besser aber langsamer. Max: 50",
                },
                "width": {
                    "type": "integer",
                    "description": "Breite in Pixel (optional, default: 768 für SD, 1024 für SDXL/FLUX)",
                },
                "height": {
                    "type": "integer",
                    "description": "Höhe in Pixel (optional, default: 768 für SD, 1024 für SDXL/FLUX)",
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "generate_video",
        "description": (
            "Generiert ein kurzes Video lokal mit KI (Wan 2.1 T2V via Hugging Face Diffusers). "
            "Nutze dieses Tool wenn Sir 'mach mir ein Video', 'generiere einen Clip von ...' sagt "
            "und KEIN Higgsfield-API-Key konfiguriert ist. "
            "Dauert je nach Hardware 2-15 Minuten. "
            "Das Video erscheint direkt im Chat-Fenster."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Video-Beschreibung auf Englisch. Beispiel: 'a robot walks through a futuristic city at night'",
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Was das Video NICHT enthalten soll (optional)",
                },
                "num_frames": {
                    "type": "integer",
                    "description": "Anzahl Frames (default: 25, bei 16fps ≈ 1.5 Sekunden. Max: 81)",
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "higgsfield_video",
        "description": (
            "Generiert ein Video mit Higgsfield.ai Cloud API — cinematische Qualität, keine lokale GPU nötig. "
            "BEVORZUGE dieses Tool für Videos wenn ein HIGGSFIELD_API_KEY gesetzt ist. "
            "Unterstützt auch Image-to-Video wenn eine Bild-URL übergeben wird. "
            "Dauert 1-3 Minuten, kostet Credits. Modelle: dop-lite (3 Credits), dop-preview (6), dop-turbo (9). "
            "Das fertige Video erscheint direkt im Chat."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detaillierte Video-Beschreibung auf Englisch. Beispiel: 'a cinematic shot of iron man flying over a futuristic city, dramatic lighting'",
                },
                "model": {
                    "type": "string",
                    "enum": ["dop-lite", "dop-preview", "dop-turbo"],
                    "description": "Higgsfield-Modell. dop-lite: schnell + günstig (3 Credits). dop-preview: Standard (6 Credits). dop-turbo: beste Qualität (9 Credits). Default: dop-lite",
                },
                "image_url": {
                    "type": "string",
                    "description": "Optional: URL eines Bildes für Image-to-Video. Wenn gesetzt wird das Bild animiert.",
                },
                "motion_strength": {
                    "type": "number",
                    "description": "Bewegungsstärke 0.0-1.0 (default: 0.5). Höher = mehr Bewegung",
                },
                "seed": {
                    "type": "integer",
                    "description": "Optional: Seed für reproduzierbare Ergebnisse",
                },
            },
            "required": ["prompt"],
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
            return _run_command(inputs["command"], inputs.get("timeout", 120))
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
        case "web_scroll":
            return _web_scroll(inputs.get("direction", "down"), inputs.get("amount", 600), inputs.get("selector"))
        case "web_get_links":
            return _web_get_links(inputs.get("selector"), inputs.get("filter"))
        case "web_navigate":
            return _web_navigate(inputs["action"])
        case "web_select":
            return _web_select(inputs["selector"], inputs["value"])
        case "web_evaluate":
            return _web_evaluate(inputs["script"])
        case "web_extract_table":
            return _web_extract_table(inputs.get("selector"), inputs.get("index", 0))
        case "download_file":
            return _download_file(inputs["url"], inputs.get("filename"))
        case "search_web":
            return _search_web(inputs["query"], inputs.get("results", 5))
        case "delegate_to_agent":
            return _delegate(inputs["agent"], inputs["task"])
        case "local_ai_worker":
            return _local_ai_worker(inputs["task"], inputs.get("system", ""), inputs.get("model", ""))
        case "generate_image":
            return _generate_image(
                inputs["prompt"],
                inputs.get("negative_prompt"),
                inputs.get("steps", 25),
                inputs.get("width"),
                inputs.get("height"),
            )
        case "generate_video":
            return _generate_video(
                inputs["prompt"],
                inputs.get("negative_prompt"),
                inputs.get("num_frames", 25),
            )
        case "higgsfield_video":
            return _higgsfield_video(
                inputs["prompt"],
                inputs.get("model", "dop-lite"),
                inputs.get("image_url"),
                inputs.get("motion_strength", 0.5),
                inputs.get("seed"),
            )
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


def _run_command(command: str, timeout: int = 120) -> str:
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

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/124.0.0.0 Safari/537.36")


def _get_page():
    """Gibt die aktuelle Playwright-Page zurück, erstellt sie bei Bedarf."""
    global _pw, _browser, _page
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("playwright nicht installiert: pip install playwright && playwright install chromium")

    if _browser is None or not _browser.is_connected():
        if _pw is not None:
            try: _pw.stop()
            except: pass
        import os
        headless = os.environ.get("JARVIS_BROWSER_HEADLESS", "false").lower() != "false"
        _pw      = sync_playwright().start()
        _browser = _pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx   = _browser.new_context(user_agent=_UA, locale="de-DE")
        _page = ctx.new_page()

    if _page is None or _page.is_closed():
        ctx   = _browser.new_context(user_agent=_UA, locale="de-DE")
        _page = ctx.new_page()

    return _page


def _http_get(url: str, max_chars: int = 8000) -> str:
    """Einfacher HTTP-GET via urllib — kein Playwright, kein Bot-Risiko."""
    import urllib.request, html as _html, re
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept":     "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de,en;q=0.5",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    raw = re.sub(r"(?s)<(script|style|noscript|nav|footer|header|aside)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = _html.unescape(raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw[:max_chars] + ("\n[...gekürzt...]" if len(raw) > max_chars else "")


def _browse_web(url: str, selector: str | None = None, wait_for: str | None = None) -> str:
    # Playwright-Versuch
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
            text = page.evaluate("""() => {
                ['script','style','noscript','nav','footer','header','aside']
                    .forEach(t => document.querySelectorAll(t).forEach(e => e.remove()));
                return document.body ? document.body.innerText : '';
            }""")

        text = " ".join(text.split())
        if len(text) > 8000:
            text = text[:8000] + "\n[...gekürzt...]"
        if len(text) < 100:
            raise RuntimeError("Zu wenig Inhalt — Bot-Schutz?")
        return f"TITEL: {title}\nURL: {url}\n\n{text}"

    except Exception as pw_err:
        # Fallback: einfacher HTTP-GET (funktioniert für Wikipedia, Docs, usw.)
        try:
            text = _http_get(url)
            return f"URL: {url}\n\n{text}"
        except Exception as http_err:
            return f"Browser-Fehler: {pw_err} | HTTP-Fallback: {http_err}"


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


def _web_scroll(direction: str = "down", amount: int = 600, selector: str | None = None) -> str:
    try:
        page = _get_page()
        if selector:
            el = page.query_selector(selector)
            if not el:
                return f"Element nicht gefunden: {selector}"
            el.scroll_into_view_if_needed()
            return f"Zu '{selector}' gescrollt | URL: {page.url}"
        scripts = {
            "down":   f"window.scrollBy(0, {amount})",
            "up":     f"window.scrollBy(0, -{amount})",
            "top":    "window.scrollTo(0, 0)",
            "bottom": "window.scrollTo(0, document.body.scrollHeight)",
        }
        page.evaluate(scripts.get(direction, f"window.scrollBy(0, {amount})"))
        return f"Gescrollt: {direction}" + (f" ({amount}px)" if direction in ("down", "up") else "")
    except Exception as e:
        return f"Scroll-Fehler: {e}"


def _web_get_links(selector: str | None = None, filter_text: str | None = None) -> str:
    try:
        page = _get_page()
        links = page.evaluate("""(sel) => {
            const scope = sel ? document.querySelector(sel) : document;
            if (!scope) return [];
            return Array.from(scope.querySelectorAll('a[href]')).map(a => ({
                text: a.innerText.trim().replace(/\\s+/g, ' ').slice(0, 80),
                href: a.href,
            })).filter(l => l.text && l.href && !l.href.startsWith('javascript:'));
        }""", selector)
        if filter_text:
            ft = filter_text.lower()
            links = [l for l in links if ft in l["text"].lower() or ft in l["href"].lower()]
        links = links[:60]
        if not links:
            return "Keine Links gefunden."
        lines = [f"Links auf {page.url}  ({len(links)} gesamt):\n"]
        for l in links:
            lines.append(f"• {l['text']}")
            lines.append(f"  {l['href']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Links-Fehler: {e}"


def _web_navigate(action: str) -> str:
    try:
        page = _get_page()
        if action == "status":
            return f"URL: {page.url}\nTitel: {page.title()}"
        if action == "back":
            page.go_back(timeout=10_000, wait_until="domcontentloaded")
        elif action == "forward":
            page.go_forward(timeout=10_000, wait_until="domcontentloaded")
        elif action == "reload":
            page.reload(timeout=15_000, wait_until="domcontentloaded")
        else:
            return f"Unbekannte Aktion: {action}"
        return f"{action.capitalize()} | URL: {page.url} | Titel: {page.title()}"
    except Exception as e:
        return f"Navigation-Fehler: {e}"


def _web_select(selector: str, value: str) -> str:
    try:
        page = _get_page()
        try:
            page.select_option(selector, value=value, timeout=5_000)
        except Exception:
            page.select_option(selector, label=value, timeout=5_000)
        return f"Ausgewählt: '{value}' in '{selector}'"
    except Exception as e:
        return f"Select-Fehler: {e}"


def _web_evaluate(script: str) -> str:
    try:
        page = _get_page()
        if not script.strip().startswith("("):
            script = f"() => {{ return ({script}); }}"
        result = page.evaluate(script)
        if result is None:
            return "Script ausgeführt (kein Rückgabewert)"
        text = str(result)
        if len(text) > 6000:
            text = text[:6000] + "\n[... gekürzt ...]"
        return text
    except Exception as e:
        return f"Script-Fehler: {e}"


def _web_extract_table(selector: str | None = None, index: int = 0) -> str:
    try:
        page = _get_page()
        rows = page.evaluate("""([sel, idx]) => {
            const tables = sel
                ? document.querySelectorAll(sel)
                : document.querySelectorAll('table');
            const table = tables[idx];
            if (!table) return null;
            return Array.from(table.querySelectorAll('tr')).map(tr =>
                Array.from(tr.querySelectorAll('th, td')).map(c =>
                    c.innerText.trim().replace(/\\s+/g, ' ')
                )
            ).filter(row => row.some(c => c));
        }""", [selector, index])
        if not rows:
            return f"Keine Tabelle gefunden (Selektor: {selector or 'table'}, Index: {index})"
        lines = []
        for i, row in enumerate(rows):
            line = " | ".join(row)
            lines.append(line)
            if i == 0:
                lines.append("─" * min(len(line), 100))
        return "\n".join(lines)
    except Exception as e:
        return f"Tabellen-Fehler: {e}"


def _download_file(url: str, filename: str | None = None) -> str:
    try:
        import urllib.request
        if not filename:
            filename = url.split("?")[0].rstrip("/").split("/")[-1] or "download"
            if "." not in filename:
                filename += ".bin"
        out = WORKSPACE / filename
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        out.write_bytes(data)
        size = len(data)
        size_str = f"{size:,} B" if size < 1024 else f"{size // 1024:,} KB"
        return f"Heruntergeladen: {out}\nGröße: {size_str}"
    except Exception as e:
        return f"Download-Fehler: {e}"


def _search_web(query: str, max_results: int = 5) -> str:
    """Sucht via DuckDuckGo API (JSON, kein Playwright nötig)."""
    import urllib.parse, urllib.request, json as _json

    # DuckDuckGo Instant Answer API
    api_url = (
        "https://api.duckduckgo.com/?q="
        + urllib.parse.quote(query)
        + "&format=json&no_html=1&skip_disambig=1"
    )
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode("utf-8"))

        lines = [f"Suchergebnisse für: {query}\n"]
        count = 0

        # Abstract (direkte Antwort)
        if data.get("AbstractText"):
            lines.append(f"► {data['AbstractText']}")
            if data.get("AbstractURL"):
                lines.append(f"   Quelle: {data['AbstractURL']}")
            lines.append("")
            count += 1

        # Related Topics
        for item in data.get("RelatedTopics", []):
            if count >= max_results:
                break
            if isinstance(item, dict) and item.get("Text"):
                lines.append(f"{count}. {item['Text'][:200]}")
                if item.get("FirstURL"):
                    lines.append(f"   {item['FirstURL']}")
                lines.append("")
                count += 1

        if count == 0:
            # Fallback: Playwright-Suche
            raise RuntimeError("API leer")

        return "\n".join(lines)

    except Exception:
        # Fallback: Playwright mit DuckDuckGo HTML
        try:
            page = _get_page()
            search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            page.goto(search_url, timeout=20_000, wait_until="domcontentloaded")
            results = page.evaluate("""(max) => {
                const items = [];
                document.querySelectorAll('.result').forEach((el, i) => {
                    if (i >= max) return;
                    const t = el.querySelector('.result__title a');
                    const s = el.querySelector('.result__snippet');
                    const u = el.querySelector('.result__url');
                    if (!t) return;
                    items.push({ title: t.innerText, url: u ? u.innerText : '', snippet: s ? s.innerText : '' });
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


def _local_ai_worker(task: str, system: str = "", model: str = "") -> str:
    """Sendet einen Prompt an das lokale Ollama-Modell (127.0.0.1:11434)."""
    import os, json as _json
    from urllib.request import urlopen, Request
    from urllib.error import URLError

    BASE = "http://127.0.0.1:11434"
    model = model.strip() or os.getenv("JARVIS_LOCAL_MODEL", "qwen2.5:7b")

    # ── Schneller Erreichbarkeits-Check (3s) ────────────────────────
    try:
        with urlopen(f"{BASE}/api/tags", timeout=3):
            pass
    except Exception as e:
        return (
            f"Fehler: Ollama nicht erreichbar ({BASE}).\n"
            f"Details: {e}\n"
            f"Starte Ollama mit:  ollama serve"
        )

    # ── Modell verfügbar? ────────────────────────────────────────────
    try:
        with urlopen(f"{BASE}/api/tags", timeout=5) as r:
            tags = _json.loads(r.read())
        installed = [m["name"] for m in tags.get("models", [])]
        # Normalisierung: "qwen2.5:7b" == "qwen2.5:7b" etc.
        match = next((n for n in installed if n.split(":")[0] == model.split(":")[0] or n == model), None)
        if not match:
            return (
                f"Fehler: Modell '{model}' ist nicht installiert.\n"
                f"Installierte Modelle: {', '.join(installed) or 'keine'}\n"
                f"Installieren mit:  ollama pull {model}"
            )
        model = match  # exakter Name verwenden
    except Exception:
        pass  # weiter versuchen

    # ── Inference via Streaming (stream:True ist stabiler auf Windows) ──
    messages = []
    if system.strip():
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": task})

    payload = _json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,   # stream:False gibt auf manchen Ollama-Versionen HTTP 500
    }).encode()
    try:
        req = Request(
            f"{BASE}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        content = ""
        with urlopen(req, timeout=300) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    obj = _json.loads(line)
                    if obj.get("error"):
                        return f"Ollama-Fehler ({model}): {obj['error']}"
                    chunk = obj.get("message", {}).get("content", "")
                    if chunk:
                        content += chunk
                    if obj.get("done"):
                        break
                except _json.JSONDecodeError:
                    continue
        if not content.strip():
            return f"Ollama ({model}): Keine Antwort erhalten."
        return f"[Lokales Modell: {model}]\n\n{content.strip()}"
    except URLError as e:
        reason = getattr(e, "reason", str(e))
        # HTTPError: Antwort-Body enthält Ollama-Fehlermeldung
        if hasattr(e, "read"):
            try:
                body = _json.loads(e.read())
                reason = body.get("error", reason)
            except Exception:
                pass
        return f"Ollama-Fehler ({model}): {reason}"
    except Exception as e:
        return f"Ollama-Fehler ({model}): {type(e).__name__}: {e}"


def _generate_image(
    prompt: str,
    negative_prompt: str | None = None,
    steps: int = 25,
    width: int | None = None,
    height: int | None = None,
) -> str:
    try:
        import media_engine as me  # noqa
        neg = negative_prompt or "blurry, low quality, watermark, text, deformed, ugly, bad anatomy"
        result = me.generate_image(
            prompt=prompt,
            negative_prompt=neg,
            steps=steps,
            width=width,
            height=height,
        )
        return (
            f"[JARVIS_IMAGE:{result['web_url']}]\n"
            f"Modell: {result['model']} | Dauer: {result['elapsed']}s\n"
            f"Gespeichert: {result['path']}"
        )
    except ImportError:
        return (
            "Fehler: diffusers oder torch nicht installiert.\n"
            "Installieren mit: pip install torch diffusers transformers accelerate"
        )
    except Exception as e:
        return f"Bild-Generierung fehlgeschlagen: {type(e).__name__}: {e}"


def _generate_video(
    prompt: str,
    negative_prompt: str | None = None,
    num_frames: int = 25,
) -> str:
    try:
        import media_engine as me  # noqa
        neg = negative_prompt or "low quality, blurry, watermark, distorted"
        result = me.generate_video(
            prompt=prompt,
            negative_prompt=neg,
            num_frames=num_frames,
        )
        suffix = "mp4" if result["path"].endswith(".mp4") else "gif"
        media_tag = "JARVIS_VIDEO" if suffix == "mp4" else "JARVIS_GIF"
        return (
            f"[{media_tag}:{result['web_url']}]\n"
            f"Modell: {result['model']} | Frames: {num_frames} | Dauer: {result['elapsed']}s\n"
            f"Gespeichert: {result['path']}"
        )
    except ImportError:
        return (
            "Fehler: diffusers oder torch nicht installiert.\n"
            "Installieren mit: pip install torch diffusers transformers accelerate"
        )
    except Exception as e:
        return f"Video-Generierung fehlgeschlagen: {type(e).__name__}: {e}"


def _higgsfield_video(
    prompt: str,
    model: str = "dop-lite",
    image_url: str | None = None,
    motion_strength: float = 0.5,
    seed: int | None = None,
) -> str:
    try:
        import media_engine as me
        result = me.generate_video_higgsfield(
            prompt=prompt,
            model=model,
            image_url=image_url,
            motion_strength=motion_strength,
            seed=seed,
        )
        return (
            f"[JARVIS_VIDEO:{result['web_url']}]\n"
            f"Modell: {result['model']} | Dauer: {result['elapsed']}s | ID: {result['gen_id']}\n"
            f"Gespeichert: {result['path']}"
        )
    except ImportError:
        return "Fehler: media_engine nicht ladbar."
    except Exception as e:
        return f"Higgsfield-Fehler: {type(e).__name__}: {e}"


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

# 🛠️ Tools & Werkzeuge

Zurück zu: [[🧠 JARVIS BRAIN]] | [[⚙️ Technische Architektur]]

> JARVIS hat **18 Tools** die direkt per Claude Tool-Use aufgerufen werden.

---

## PC-Tools (5)
| Tool | Funktion |
|------|----------|
| `read_file` | Datei lesen (bis 500 KB), alle Dateitypen |
| `write_file` | Datei schreiben, fehlende Ordner werden auto-erstellt |
| `run_command` | PowerShell-Befehl ausführen, stdout/stderr zurück |
| `list_directory` | Ordner auflisten, optional rekursiv |
| `search_files` | Glob-Suche + optionaler Inhalts-Filter |

## Browser-Tools (12)
| Tool | Funktion |
|------|----------|
| `browse_web` | URL öffnen, Titel + sichtbaren Text extrahieren |
| `web_click` | Element per CSS-Selektor klicken |
| `web_type` | Text in Eingabefeld tippen (+ optional Enter) |
| `web_screenshot` | Screenshot → `workspace/dateiname.png` |
| `web_scroll` | Scrollen: down / up / top / bottom oder zu Element |
| `web_get_links` | Alle Links der Seite sammeln (mit Filter) |
| `web_navigate` | back / forward / reload / status (URL + Titel) |
| `web_select` | Dropdown `<select>` Option auswählen |
| `web_evaluate` | JavaScript auf der Seite ausführen, Ergebnis zurück |
| `web_extract_table` | HTML-Tabelle als lesbaren Text extrahieren |
| `download_file` | Datei von URL → `workspace/` herunterladen |
| `search_web` | DuckDuckGo-Suche → Top-Ergebnisse (Titel, URL, Snippet) |

> Browser startet **sichtbar** (Chromium-Fenster). Headless via `.env`: `JARVIS_BROWSER_HEADLESS=true`

## Agent-Tool (1)
| Tool | Funktion |
|------|----------|
| `delegate_to_agent` | Aufgabe an einen der 10 Spezialisten delegieren → [[🤖 Agenten-Team]] |

## Typischer Browser-Workflow
```
search_web("was suchen")           → URLs finden
browse_web("https://...")          → Seite öffnen + lesen
web_click("button.submit")         → klicken
web_type("input#search", "text")   → tippen
web_screenshot("ergebnis.png")     → Screenshot speichern
```

## MCP-Tools (nur in Claude Code Chat)
| Tool | Beschreibung |
|------|-------------|
| **Playwright MCP** | Browser direkt aus dem Chat (unabhängig vom Python-Browser) |
| **Filesystem MCP** | Dateien lesen / schreiben / durchsuchen |
| **Supabase MCP** | Datenbankzugriff (falls konfiguriert) |
| **Gmail / Google Calendar / Drive MCP** | falls authentifiziert |

## Erweiterungsideen
- [[🚀 Erweiterungsmöglichkeiten]]

---
title: JARVIS — Gehirn / Cloud Knowledge Base
created: 2024-01-01
updated: 2024-01-01
type: system-documentation
status: active
tags:
  - jarvis
  - ai-agent
  - python
  - flask
  - anthropic
  - claude
  - knowledge-base
  - system-architecture
version: "3.0"
author: JARVIS (auto-generated)
---

# 🧠 JARVIS — GEHIRN / CLOUD KNOWLEDGE BASE

> [!INFO] Über dieses Dokument
> Vollständige Selbst-Analyse des JARVIS AI Agent Systems.
> Erstellt: **automatisch by JARVIS** | Typ: *Living Document* | Auto-Update: aktiviert

---

## 🗺️ INHALTSVERZEICHNIS

- [[#📁 Projektstruktur]]
- [[#🏗️ Architektur — Wie JARVIS Funktioniert]]
- [[#🤖 Das Agenten-Team]]
- [[#🛠️ PC-Tools]]
- [[#🌐 Web-API Endpunkte]]
- [[#🎤 Voice-System]]
- [[#⚙️ Technologie-Stack]]
- [[#🔄 Pipelines & Workflows]]
- [[#📡 Kommunikationsfluss]]
- [[#🔐 Sicherheit & Konfiguration]]
- [[#🚀 Start-Optionen]]
- [[#🧩 CEO-Logik]]
- [[#💾 Datenfluss & State]]
- [[#🎨 Frontend-Features]]
- [[#📊 System-Metriken]]
- [[#🔮 Bekannte Besonderheiten & Gotchas]]

---

## 📁 Projektstruktur

```
C:\Users\basti\Desktop\Jarvis\
│
├── 🚀 EINSTIEGSPUNKTE
│   ├── start.py          → Haupt-Launcher (startet Flask auf Port 5000)
│   ├── app.py            → Flask-Webserver + API-Routen
│   ├── main.py           → CLI-Interface (interaktives Menü, Terminal)
│   └── voice_agent.py    → Standalone Voice Agent v3 (WebSocket Port 5001)
│
├── ⚙️ KONFIGURATION
│   ├── config.py         → API-Key Loader (liest .env)
│   ├── .env              → ANTHROPIC_KEY (Anthropic Claude API)
│   └── pyproject.toml    → Projekt-Metadaten + Dependencies
│
├── 🤖 AGENTEN-TEAM
│   └── agents/
│       ├── __init__.py       → Package-Init
│       ├── base_agent.py     → Agent Dataclass (Basisklasse)
│       ├── team.py           → Alle 10 Agenten + TEAM-Dict
│       ├── orchestrator.py   → TeamOrchestrator (Pipelines)
│       ├── ceo.py            → JarvisCEO (Haupt-Gehirn, Tool-Use)
│       └── tools.py          → PC-Tools + Anthropic Tool Definitions
│
├── 🌐 FRONTEND
│   ├── templates/
│   │   └── index.html        → Web-UI (Single Page App)
│   └── static/
│       ├── css/style.css     → Dark Theme, 20KB Styling
│       └── js/
│           ├── app.js        → Frontend-Logik (27KB, SSE, Voice, Markdown)
│           └── pcm-processor.js → Audio Worklet für PCM-Verarbeitung
│
└── 📂 WORKSPACE
    ├── tasks/            → Gespeicherte Aufgaben (Markdown-Dateien)
    └── results/          → Gespeicherte Ergebnisse (Markdown-Dateien)
```

---

## 🏗️ Architektur — Wie JARVIS Funktioniert

> [!NOTE] Kernprinzip
> JARVIS ist ein **Multi-Agent-System** auf Basis von Anthropic Claude. Ein zentraler CEO-Agent koordiniert ein Team aus 10 spezialisierten Sub-Agenten. Jeder Agent hat eine eigene Expertise, Persönlichkeit und System-Prompt.

### Gesamtübersicht

```
USER (Browser / Terminal)
        │
        ▼
   [app.py - Flask]
        │  POST /api/chat
        ▼
   [JarvisCEO - ceo.py]          ← Hauptgehirn
        │  Anthropic API (claude-sonnet-4-6)
        │  Tool-Use Loop
        ├──► [PC-Tools]           ← read_file, write_file, run_command, ...
        └──► [delegate_to_agent]  ← an Spezialisten delegieren
                    │
                    ▼
            [TEAM - team.py]
            10 Spezial-Agenten
            (jeder mit eigenem System-Prompt + History)
```

### Request-Flow (detailliert)

```
1. User tippt Nachricht / spricht ins Mikrofon
2. Browser → POST /api/chat (JSON: {message: "..."})
3. Flask → JarvisCEO.stream(message)
4. CEO schickt Message + History an Claude API
5. Claude antwortet mit tool_use (braucht Tools) oder text (fertig)
6. Bei tool_use:
   a) CEO executiert Tool lokal (PC-Zugriff oder Agenten-Delegation)
   b) Tool-Result zurück an Claude
   c) Loop wiederholt bis stop_reason != "tool_use"
7. Finale Antwort wird wort-für-wort als SSE gestreamt
8. Browser rendert Markdown + Code-Highlighting in Echtzeit
```

---

## 🤖 Das Agenten-Team

> [!INFO] Teamgröße
> JARVIS besteht aus **10 spezialisierten Agenten** + 1 CEO = **11 AI-Instanzen** — alle laufen auf `claude-sonnet-4-6`.

### Agenten-Übersicht

| Key | Name | Rolle | Spezialisierung |
|-----|------|-------|----------------|
| `library` | **LibraryScout** | Library Expert | PyPI-Ökosystem, Package-Vergleiche, CVE-Warnungen |
| `research` | **ResearchBot** | Research Analyst | PEPs, offizielle Docs, Best Practices, Changelogs |
| `senior_dev` | **SeniorPy** | Senior Developer | Implementierung, Architektur, idiomatisches Python |
| `ux` | **UXCrafter** | UX/DX Designer | CLI-Design, API-Design, Fehlermeldungen, DX |
| `code_reviewer` | **ReviewMaster** | Code Reviewer | Reviews mit CRITICAL/HIGH/MEDIUM/LOW Severity |
| `debugger` | **DebugHunter** | Debug Specialist | Traceback-Analyse, pdb, Debugging-Strategien |
| `bug_fixer` | **BugSlayer** | Bug Fix Specialist | Root-Cause-Fixes mit Regressions-Tests |
| `bug_expert` | **BugWizard** | Bug Pattern Expert | Bug-Patterns, systemische Prävention |
| `performance` | **SpeedDemon** | Performance Engineer | Profiling, Optimierung, Caching |
| `security` | **SecureGuard** | Security Expert | OWASP, CVE-Checks, bandit, Sicherheitsanalyse |

### Agenten-Modell

- **Basis-Modell:** `claude-sonnet-4-6` (alle Agenten)
- **Max Tokens:** 8.096 pro Agent
- **History:** Jeder Agent hat eigene Konversations-History (persistent in Session)
- **Reset:** Alle Agenten per `POST /api/reset` zurücksetzbar

---

## 🛠️ PC-Tools

> [!TIP] Direkter PC-Zugriff
> Der CEO-Agent kann **direkt PC-Aktionen ausführen** via Anthropic Tool-Use API. Claude entscheidet selbst, welches Tool wann genutzt wird — kein manueller Aufruf nötig.

### Verfügbare Tools

| Tool | Funktion |
|------|----------|
| `read_file` | Beliebige Datei lesen (max 500 KB) |
| `write_file` | Datei schreiben/erstellen (Verzeichnisse auto-erstellt) |
| `run_command` | PowerShell-Befehl ausführen (stdout/stderr/exit-code) |
| `list_directory` | Verzeichnis auflisten (optional rekursiv, max 300 Einträge) |
| `search_files` | Glob-Pattern-Suche + optionaler Inhalts-Filter |
| `delegate_to_agent` | Aufgabe an Spezialisten delegieren |

### Workspace-System

> [!NOTE] Automatische Persistenz
> Jede Delegierung speichert automatisch:
> - `workspace/tasks/{timestamp}_{agent}.md` → Was wurde beauftragt
> - `workspace/results/{timestamp}_{agent}.md` → Was kam zurück
>
> Im Browser unter dem **"Workspace"-Tab** sichtbar.

---

## 🌐 Web-API Endpunkte

> [!INFO] Base URL
> Alle Endpunkte erreichbar unter: `http://localhost:5000`

### Endpunkt-Übersicht

| Methode | Pfad | Funktion |
|---------|------|----------|
| `GET` | `/` | Web-UI (index.html) |
| `POST` | `/api/chat` | Nachricht senden → SSE-Stream zurück |
| `POST` | `/api/reset` | CEO + alle Agenten History löschen |
| `GET` | `/api/workspace` | Tasks & Results auflisten (JSON) |
| `GET` | `/api/workspace/{folder}/{file}` | Workspace-Datei lesen |
| `POST` | `/api/voice/transcribe` | Audio → Text (Google Speech) |

### SSE Event-Typen (`/api/chat`)

```json
{"type": "status",      "text": "JARVIS analysiert..."}
{"type": "thinking",    "text": "Zwischengedanke des CEO"}
{"type": "tool_call",   "tool": "read_file", "input": {...}}
{"type": "tool_result", "tool": "read_file", "result": "..."}
{"type": "tool_error",  "tool": "...",       "error": "..."}
{"type": "token",       "text": "Wort "}
{"type": "done"}
```

> [!NOTE] Streaming
> Tokens werden **wort-für-wort** via SSE gestreamt (`type: "token"`). Der Browser rendert Markdown live während JARVIS noch antwortet.

---

## 🎤 Voice-System

### Zwei Voice-Modi

#### Modus 1 — Browser-Mikrofon (Standard, in `app.py`)

```
Browser Mic → WebM/Ogg Audio → POST /api/voice/transcribe
→ ffmpeg Konvertierung (WebM → WAV 16kHz mono)
→ Google Speech Recognition (de-DE oder en-US)
→ Erkannter Text ins Chat-Input
```

**Diagnose-Pipeline:**
1. Audio-Bytes empfangen (min 256 Bytes)
2. Content-Type prüfen (webm/ogg → ffmpeg; PCM → direkt WAV)
3. WAV-Diagnose: Dauer, RMS-Pegel, Peak, Sample-Count
4. Google Speech API aufrufen
5. Text zurückgeben oder Fehler beschreiben

#### Modus 2 — Desktop Voice Agent (`voice_agent.py`)

```
Mikrofon (sounddevice) → VAD (Voice Activity Detection)
→ Phrase sammeln → float32→int16 WAV
→ Google Speech Recognition
→ WebSocket (ws://localhost:5001)
→ Browser empfängt Text
```

**Technische Parameter:**

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| `BLOCK` | 512 Frames | 32ms Blöcke — schnelle VAD-Reaktion |
| `SILENCE_S` | 0.85s | Stille = Phrase beendet |
| `MIN_S` | 0.35s | Mindestlänge einer Phrase |
| `PRE_S` | 0.30s | Vorpuffer (Frames VOR Sprachbeginn) |
| Kalibrierung | 1.5s | Umgebungsmessung → automatischer Schwellwert (`ambient × 4.0`, min `0.005`) |
| Normalisierung | ~50% | Audio auf ~50% Vollaussteuerung normalisiert (verhindert Clipping) |

**Startoptionen Voice Agent:**

```bash
python voice_agent.py           # Deutsch (de-DE)
python voice_agent.py en-US     # Englisch
python voice_agent.py de-DE 1   # Device-Index erzwingen
python voice_agent.py --list    # Alle Mikrofone anzeigen
```

> [!WARNING] ffmpeg erforderlich
> Modus 1 (Browser-Voice) benötigt eine **ffmpeg-Installation** im PATH — sonst schlägt die WebM→WAV-Konvertierung fehl.

---

## ⚙️ Technologie-Stack

### Backend

| Komponente | Technologie | Version |
|-----------|-------------|---------|
| KI-Modell | Anthropic Claude | `claude-sonnet-4-6` |
| Web-Framework | Flask | `>=3.0.0` |
| Anthropic SDK | anthropic | `>=0.40.0` |
| Konfiguration | python-dotenv | `>=1.0.0` |
| Python | CPython | `3.14` |

### Voice / Audio

| Komponente | Technologie |
|-----------|-------------|
| Audio-Capture | sounddevice (PortAudio) |
| Numerik | numpy |
| Speech-to-Text | Google Speech Recognition (`speech_recognition`) |
| Audio-Konvertierung | ffmpeg (subprocess) |
| WebSocket-Server | websockets |

### Frontend

| Komponente | Technologie |
|-----------|-------------|
| Markup | HTML5 + CSS3 (Dark Theme) |
| Scripting | Vanilla JavaScript (ES6+) |
| Markdown | marked.js v12 (CDN) |
| Syntax-Highlighting | highlight.js v11.9 (CDN) |
| Fonts | Azeret Mono + Syne (Google Fonts) |
| Echtzeit | Server-Sent Events (SSE) |

### Dev-Tools

| Tool | Zweck |
|------|-------|
| `uv` | Package-Manager |
| `pytest` | Testing |
| `mypy` | Type-Checking |
| `ruff` | Linting / Formatting |

---

## 🔄 Pipelines & Workflows

> [!INFO] Orchestrator
> `orchestrator.py` ermöglicht **vordefinierte Multi-Agent-Workflows** — der Output eines Agenten wird automatisch als Input für den nächsten verwendet.

### Full Code Review Pipeline

```
Code → code_reviewer → security → performance → bug_expert
```

### Debug & Fix Pipeline

```
Error + Code → debugger → bug_expert → bug_fixer
```

### Feature Development Pipeline

```
Feature → research → library → ux → senior_dev → code_reviewer → security
```

---

## 📡 Kommunikationsfluss (Frontend ↔ Backend)

```
Browser (app.js)
    │
    ├── sendMessage()
    │       └── fetch('/api/chat', {method:'POST', body: JSON})
    │               └── Response: EventSource (SSE-Stream)
    │                       ├── type:"thinking"    → Activity Feed
    │                       ├── type:"tool_call"   → Activity Feed (Badge)
    │                       ├── type:"tool_result" → Activity Feed
    │                       ├── type:"token"       → Chat-Bubble (live)
    │                       └── type:"done"        → Bubble finalisieren
    │
    ├── toggleVoice()
    │       └── MediaRecorder (WebM) → POST /api/voice/transcribe
    │               └── {text: "..."} → ins Input-Feld einfügen
    │
    └── WebSocket (optional)
            └── ws://localhost:5001 ← voice_agent.py schickt Text
```

---

## 🔐 Sicherheit & Konfiguration

### API-Key Management

- **Speicherort:** `.env` Datei im Projektverzeichnis
- **Variable:** `ANTHROPIC_KEY` oder `ANTHROPIC_API_KEY`
- **Laden:** `python-dotenv` via `config.py`

> [!DANGER] API-Key Sicherheit
> Der Key liegt im **Klartext in `.env`** — niemals in Git committen! Sicherstellen, dass `.env` in `.gitignore` eingetragen ist.

### Workspace-Sicherheit

- **Path-Traversal-Schutz:** `resolve()` + `startswith(base)` Check
- Nur `tasks/` und `results/` via API erreichbar
- Workspace-Dateien: max **15 neueste** werden angezeigt

### Aktuelle Sicherheitslage

| Bereich | Status | Risiko |
|---------|--------|--------|
| API-Key Schutz | ✅ `.env` Datei | 🟢 OK |
| Path-Traversal | ✅ Geschützt | 🟢 OK |
| Netzwerk-Exposure | ⚠️ nur localhost | 🟡 Mittel |
| Input-Validierung | ⚠️ Basis-Checks | 🟡 Mittel |
| Web-UI Authentication | ❌ Keine Auth | 🔴 Kritisch |
| Code-Execution Sandbox | ❌ Nicht vorhanden | 🔴 Kritisch |

---

## 🚀 Start-Optionen

> [!TIP] Empfohlener Start (Browser-UI)
> ```bash
> cd C:\Users\basti\Desktop\Jarvis
> python start.py
> # → http://localhost:5000
> ```

> [!TIP] Nur Flask
> ```bash
> python app.py
> # Debug-Modus, Port 5000
> ```

> [!TIP] CLI-Modus (kein Browser)
> ```bash
> python main.py
> # Interaktives Terminal-Menü
> ```

> [!TIP] Mit Voice Agent (Desktop-Mikrofon)
> ```bash
> python start.py        # Terminal 1 — Flask
> python voice_agent.py  # Terminal 2 — Voice
> ```

---

## 🧩 CEO-Logik — Das eigentliche Gehirn

> [!NOTE] Tool-Use Loop
> Der CEO läuft in einem **rekursiven Tool-Use Loop**: Claude ruft Tools auf → bekommt Ergebnisse zurück → entscheidet ob weitere Tools nötig sind → loop bis finale Antwort.

### Tool-Use Loop (vereinfacht)

```python
while True:
    response = claude_api.call(messages)

    if response.stop_reason == "tool_use":
        # Tools ausführen
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                yield SSE_event("tool_result", result)
        # Ergebnis zurück an Claude → nächste Iteration

    else:
        # Finale Antwort streamen
        for word in response.text.split():
            yield SSE_event("token", word)
        break
```

### CEO Entscheidungsregeln

1. Einfache Fragen → **direkt antworten** (kein Tool)
2. Code analysieren → `read_file` → `delegate_to_agent`
3. Code schreiben → `senior_dev` → `write_file`
4. PC-Aufgaben → **direkte PC-Tools**
5. Mehrere Aspekte → **mehrere Agenten** nacheinander
6. Dateien erwähnt → **zuerst lesen**, dann antworten

---

## 💾 Datenfluss & State

### Konversations-History

| Komponente | Speicherort | Typ |
|-----------|-------------|-----|
| CEO | `JarvisCEO.history` | Liste von `{role, content}` Dicts |
| Agenten | `Agent.history` | Liste von `AgentMessage` Objekten |
| Reset | `POST /api/reset` | CEO.reset() + alle Agenten.reset() |

### Workspace-Persistenz

> [!NOTE] Automatisches Speichern
> Bei jeder Delegierung wird automatisch gespeichert:
> - **Format:** `{timestamp}_{agent_key}.md`
> - **Tasks:** Was wurde beauftragt
> - **Results:** Was kam zurück

---

## 🎨 Frontend-Features

| Feature | Technologie |
|---------|-------------|
| **Streaming** | Wort-für-Wort Rendering via SSE |
| **Markdown** | Vollständiges Rendering mit marked.js |
| **Syntax-Highlighting** | highlight.js (GitHub Dark Theme) |
| **Activity-Panel** | Echtzeit-Feed aller Tool-Calls & Delegierungen |
| **Workspace-Tab** | Tasks + Results als klickbare Liste |
| **Voice-Input** | Browser-Mikrofon via MediaRecorder API |
| **Auto-Resize** | Textarea wächst automatisch mit |
| **Quick-Chips** | Vordefinierte Schnellbefehle auf Welcome-Screen |
| **Modal** | Workspace-Dateien in Popup anzeigen |
| **Toast** | Kurze Benachrichtigungen |
| **Reset** | Konversation per Button zurücksetzen |
| **Keyboard-Shortcut** | `Ctrl+M` → Voice-Toggle |

---

## 📊 System-Metriken

| Metrik | Wert |
|--------|------|
| Gesamtdateien | ~25 Dateien |
| Python-Code | ~8 Dateien, ~1.500 Zeilen |
| Frontend-Code | ~3 Dateien, ~1.800 Zeilen |
| Agenten | 10 Spezialisten + 1 CEO |
| API-Endpunkte | 6 HTTP-Routen |
| Tool-Definitionen | 6 PC-Tools |
| Python-Version | 3.14 (CPython) |
| KI-Modell | `claude-sonnet-4-6` |
| Max Tokens/Request | 8.096 |

---

## 🔮 Bekannte Besonderheiten & Gotchas

> [!WARNING] ffmpeg Pflicht
> **ffmpeg muss installiert sein** — sonst kein WebM→WAV für Browser-Voice. Installation: `winget install ffmpeg` oder von [ffmpeg.org](https://ffmpeg.org).

> [!WARNING] Google Speech = Online
> **Google Speech ist kostenlos, aber online** — braucht aktive Internet-Verbindung für Voice-Funktionen.

> [!WARNING] Wachsende History
> **CEO-History wächst unbegrenzt** — kein automatisches Trimming. Bei langen Sessions manuell mit `POST /api/reset` zurücksetzen.

> [!INFO] Kein geteilter State
> **Agenten teilen keinen State** — jeder hat seine eigene isolierte History. Kontext muss bei Bedarf manuell übergeben werden.

> [!INFO] Zwei Ports
> **Port 5000 = Flask, Port 5001 = Voice-WebSocket** — beide können gleichzeitig laufen und sind unabhängig voneinander.

> [!WARNING] Python 3.14
> **Python 3.14 ist cutting edge** — manche Libraries könnten noch nicht vollständig kompatibel sein. Bei Problemen auf 3.12 oder 3.11 downgraden.

> [!WARNING] Windows-spezifisch
> **Windows-spezifische Abhängigkeiten:** PowerShell-Befehle, Windows-Pfade, CP1252-Encoding-Handling. Auf Linux/macOS sind Anpassungen nötig.

> [!DANGER] API-Key im .env
> **Sicherheitsrisiko bei Versionierung!** `.env` niemals committen. Vor jedem `git push` prüfen: `git status` sollte `.env` nicht anzeigen.

---

> [!SUCCESS] Living Document
> 🧠 Dieses Dokument ist das **lebendige Gehirn von JARVIS** — aktualisiere es wenn sich das System ändert.
> *Erstellt durch vollständige Selbst-Analyse aller Quelldateien.*

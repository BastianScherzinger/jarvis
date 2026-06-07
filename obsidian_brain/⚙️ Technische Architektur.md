# ⚙️ Technische Architektur

Zurück zu: [[🧠 JARVIS BRAIN]] | [[👤 Wer ist JARVIS]]

---

## Tech Stack
| Schicht | Technologie | Beschreibung |
|---------|-------------|--------------|
| **Backend** | Python + Flask | Web-Server, Port 5000 |
| **KI-Kern** | Claude API (Anthropic) | Tool-Use fähig, Streaming |
| **Frontend** | HTML / CSS / JavaScript | Iron Man Style Dashboard |
| **Browser** | Playwright / Chromium | sichtbar oder headless |
| **TTS** | edge-tts + pyttsx3 | Conrad-Stimme, Offline-Fallback |
| **STT** | Whisper + Google Speech | Spracherkennung mit Fallback |
| **Env** | python-dotenv | API-Keys aus `.env` laden |

## Dateistruktur
```
jarvis/
├── start.py            → Launcher (startet Flask + Auto-Installer)
├── app.py              → Flask-Server (SSE-Streaming, Port 5000)
├── install.py          → Auto-Installer (Playwright, pip-Pakete, .env)
├── config.py           → .env laden (ANTHROPIC_KEY etc.)
├── tts.py              → Text-to-Speech (edge-tts + pyttsx3 Fallback)
├── voice_agent.py      → Spracherkennung (Whisper + Google)
├── agents/
│   ├── ceo.py          → JARVIS CEO-Agent (Haupt-Orchestrator, Tool-Use)
│   ├── tools.py        → Alle 18 Tools definiert + implementiert
│   ├── team.py         → 10 Spezial-Agenten
│   ├── orchestrator.py → Team-Pipelines (full_review, debug_session, new_feature)
│   └── base_agent.py   → Agent-Basisklasse (Claude API)
├── templates/
│   └── index.html      → Dashboard UI (Iron Man Style)
├── static/js/          → Frontend (app.js, brain.js, vault.js)
└── workspace/
    ├── tasks/          → Aufgaben-Dateien der Agenten
    └── results/        → Ergebnis-Dateien der Agenten
```

## Kommunikation & Datenfluss
```
User (Browser) 
  → HTTP/SSE → Flask (app.py) 
  → Claude API (Tool-Use) 
  → agents/ceo.py 
  → tools.py / team.py 
  → SSE-Stream zurück → UI
```

- **SSE (Server-Sent Events)** — Echtzeit-Streaming vom Server zum Browser
- **REST API** — Flask-Endpoints für Befehle
- **Tool-Use** — Claude ruft Tools direkt auf (kein manuelles Routing)

## Umgebungsvariablen (.env)
```
ANTHROPIC_KEY=...              # Pflicht — Claude API
JARVIS_BROWSER_HEADLESS=false  # Browser sichtbar (default)
JARVIS_VOICE=de-DE-ConradNeural
JARVIS_RATE=+18%
JARVIS_STT_MODEL=base
```

## Erweiterungen
- [[🚀 Erweiterungsmöglichkeiten]]
- [[🌐 KI-Modelle & APIs]]
- [[🤖 Agenten-Team]]

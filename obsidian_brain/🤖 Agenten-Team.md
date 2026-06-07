# 🤖 Agenten-Team

Zurück zu: [[🧠 JARVIS BRAIN]] | [[⚙️ Technische Architektur]]

> JARVIS als CEO orchestriert 10 Spezialisten.

## Die 10 Spezialisten

| Agent | Name | Expertise |
|-------|------|-----------|
| `library` | LibraryScout | Python-Paket-Empfehlungen |
| `research` | ResearchBot | Docs, Best Practices, PEPs |
| `senior_dev` | SeniorPy | Code-Implementierung, Architektur |
| `ux` | UXCrafter | CLI / API Design |
| `code_reviewer` | ReviewMaster | Code-Qualität, Reviews |
| `debugger` | DebugHunter | Problem-Diagnose, Root Cause |
| `bug_fixer` | BugSlayer | Bugs beheben + Tests |
| `bug_expert` | BugWizard | Bug-Pattern-Analyse |
| `performance` | SpeedDemon | Profiling, Optimierung |
| `security` | SecureGuard | Security-Scan, Vulnerabilities |

## Team-Pipelines (orchestrator.py)
- **full_review** — Code komplett reviewen
- **debug_session** — Debugging-Workflow
- **new_feature** — Feature von Anfang bis Ende

## Wie Delegation funktioniert
1. JARVIS (CEO) erhält Aufgabe
2. Analysiert: einfach → selbst erledigen
3. Komplex → passenden Agenten wählen
4. Ergebnis zurück an User

## Erweiterungsideen
- [[🚀 Erweiterungsmöglichkeiten]]
- Neue Agenten: `data_scientist`, `devops`, `ui_designer`

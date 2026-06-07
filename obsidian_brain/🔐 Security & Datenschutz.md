# 🔐 Security & Datenschutz

Zurück zu: [[🧠 JARVIS BRAIN]]

## Aktuelle Sicherheit
- API-Keys in `.env` (nicht im Git-Repo)
- `.env.example` als Template (ohne echte Keys)
- Local-only Dashboard (Port 5000, kein öffentlicher Zugriff)

## Risiken & Schwachstellen
- API-Key Leak → immer `.env` in `.gitignore`
- Browser-Automatisierung → kann ungewollt Aktionen ausführen
- PowerShell-Ausführung → potentiell gefährlich wenn missbraucht
- Keine Authentifizierung am Dashboard (aktuell)

## Empfehlungen
- [ ] Dashboard-Login mit Passwort sichern
- [ ] Rate-Limiting für API-Calls
- [ ] Logs verschlüsseln
- [ ] HTTPS aktivieren (Let's Encrypt)
- [ ] Input-Sanitierung bei Sprachbefehlen

## Datenschutz
- Gespräche gehen an **Anthropic API** (Cloud)
- Lokale Alternative: [[🌐 KI-Modelle & APIs]] → Ollama
- DSGVO-Überlegungen bei EU-Hosting

## Tools für Security
- `SecureGuard` Agent → [[🤖 Agenten-Team]]
- **Bandit** — Python Security Linter
- **Safety** — bekannte Vulnerabilities in Dependencies

## Verbindungen
- [[🚀 Erweiterungsmöglichkeiten]]
- [[🌐 KI-Modelle & APIs]]

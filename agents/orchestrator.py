"""
Team Orchestrator — koordiniert mehrere Agenten für komplexe Aufgaben.
"""

from agents.base_agent import Agent
from agents.team import TEAM, get_agent


class TeamOrchestrator:
    """
    Koordiniert das Python Expert Team.
    Kann Aufgaben an einzelne Agenten weiterleiten oder
    mehrstufige Pipelines über mehrere Agenten aufbauen.
    """

    def __init__(self):
        self.team = TEAM
        self.session_log: list[dict] = []

    def ask(self, agent_key: str, question: str, context: dict | None = None) -> str:
        agent = get_agent(agent_key)
        print(f"\n>>> {agent.name} ({agent.role}) antwortet...\n")
        response = agent.chat(question, context)
        self.session_log.append({
            "agent": agent_key,
            "question": question,
            "response": response,
        })
        return response

    def pipeline(self, task: str, steps: list[tuple[str, str]]) -> dict[str, str]:
        """
        Führt eine sequentielle Pipeline aus.
        steps: Liste von (agent_key, prompt_template) — {task} und {prev} werden ersetzt.
        Gibt alle Antworten als Dict zurück.
        """
        results: dict[str, str] = {}
        prev_output = ""

        for agent_key, prompt_template in steps:
            prompt = prompt_template.format(task=task, prev=prev_output)
            response = self.ask(agent_key, prompt, context={"Bisherige Ergebnisse": prev_output} if prev_output else None)
            results[agent_key] = response
            prev_output = response

        return results

    def full_review(self, code: str) -> dict[str, str]:
        """
        Vollständiger Code-Review durch alle relevanten Agenten.
        """
        print("\n" + "=" * 60)
        print("  FULL CODE REVIEW PIPELINE")
        print("=" * 60)

        steps = [
            ("code_reviewer", "Bitte reviewe diesen Python-Code:\n\n```python\n{task}\n```"),
            ("security", "Analysiere diesen Code auf Sicherheitslücken:\n\n```python\n{task}\n```\n\nCode-Review-Feedback:\n{prev}"),
            ("performance", "Analysiere die Performance dieses Codes:\n\n```python\n{task}\n```"),
            ("bug_expert", "Analysiere diesen Code auf Bug-Patterns und Anti-Patterns:\n\n```python\n{task}\n```"),
        ]

        return self.pipeline(task=code, steps=steps)

    def debug_session(self, error_description: str, code: str) -> dict[str, str]:
        """
        Debugging-Pipeline: erst diagnostizieren, dann fixen.
        """
        print("\n" + "=" * 60)
        print("  DEBUG & FIX PIPELINE")
        print("=" * 60)

        combined = f"Fehler: {error_description}\n\nCode:\n```python\n{code}\n```"

        steps = [
            ("debugger", f"Analysiere diesen Bug:\n\n{combined}"),
            ("bug_expert", f"Welches Bug-Pattern steckt dahinter?\n\n{combined}\n\nDebugger-Analyse:\n{{prev}}"),
            ("bug_fixer", f"Fixe diesen Bug basierend auf der Analyse:\n\n{combined}\n\nDiagnose:\n{{prev}}"),
        ]

        return self.pipeline(task=combined, steps=steps)

    def new_feature(self, feature_description: str) -> dict[str, str]:
        """
        Feature-Entwicklungs-Pipeline: Research → Design → Implementation → Review.
        """
        print("\n" + "=" * 60)
        print("  FEATURE DEVELOPMENT PIPELINE")
        print("=" * 60)

        steps = [
            ("research", f"Recherchiere Best Practices und Ansätze für: {feature_description}"),
            ("library", f"Welche Libraries empfiehlst du für: {feature_description}\n\nContext:\n{{prev}}"),
            ("ux", f"Wie soll das Interface/die API für folgendes Feature aussehen: {feature_description}\n\nContext:\n{{prev}}"),
            ("senior_dev", f"Implementiere folgendes Feature in Python: {feature_description}\n\nResearch:\n{{prev}}"),
            ("code_reviewer", f"Reviewe die Implementierung:\n{{prev}}"),
            ("security", f"Security-Check der Implementierung:\n{{prev}}"),
        ]

        return self.pipeline(task=feature_description, steps=steps)

    def print_results(self, results: dict[str, str]) -> None:
        for agent_key, response in results.items():
            agent = self.team[agent_key]
            print(f"\n{'=' * 60}")
            print(f"  {agent.name} ({agent.role})")
            print("=" * 60)
            print(response)

    def reset_all(self) -> None:
        for agent in self.team.values():
            agent.reset()
        self.session_log.clear()
        print("Alle Agenten wurden zurückgesetzt.")

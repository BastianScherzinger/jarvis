"""
Python Expert Agent Team — interaktiver Einstiegspunkt.
"""

import sys
from agents.team import list_agents, get_agent, TEAM
from agents.orchestrator import TeamOrchestrator


def interactive_menu():
    orchestrator = TeamOrchestrator()

    print("\n" + "=" * 60)
    print("  PYTHON EXPERT AGENT TEAM — JARVIS")
    print("=" * 60)

    while True:
        print("\nWas möchtest du tun?")
        print("  [1] Einzelnen Agenten befragen")
        print("  [2] Full Code Review (alle Review-Agenten)")
        print("  [3] Debug & Fix Pipeline")
        print("  [4] Feature Development Pipeline")
        print("  [5] Alle Agenten anzeigen")
        print("  [6] Alle Agenten zurücksetzen")
        print("  [q] Beenden")

        choice = input("\nEingabe: ").strip()

        if choice == "q":
            print("Bis zum nächsten Mal!")
            break

        elif choice == "1":
            print("\nVerfügbare Agenten:")
            for key, agent in TEAM.items():
                print(f"  [{key}]  {agent.name}")
            agent_key = input("\nAgent wählen: ").strip()
            question = input("Deine Frage: ").strip()
            response = orchestrator.ask(agent_key, question)
            print(f"\n{response}")

        elif choice == "2":
            print("\nCode für Full Review eingeben (leere Zeile + ENTER zum Beenden):")
            lines = []
            while True:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
            code = "\n".join(lines[:-1])
            results = orchestrator.full_review(code)
            orchestrator.print_results(results)

        elif choice == "3":
            error = input("\nFehlerbeschreibung/Traceback: ").strip()
            print("Code eingeben (leere Zeile zum Beenden):")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            code = "\n".join(lines)
            results = orchestrator.debug_session(error, code)
            orchestrator.print_results(results)

        elif choice == "4":
            feature = input("\nFeature-Beschreibung: ").strip()
            results = orchestrator.new_feature(feature)
            orchestrator.print_results(results)

        elif choice == "5":
            list_agents()

        elif choice == "6":
            orchestrator.reset_all()

        else:
            print("Ungültige Eingabe.")


def quick_ask(agent_key: str, question: str):
    orchestrator = TeamOrchestrator()
    response = orchestrator.ask(agent_key, question)
    print(response)


if __name__ == "__main__":
    if len(sys.argv) == 3:
        quick_ask(sys.argv[1], sys.argv[2])
    else:
        interactive_menu()

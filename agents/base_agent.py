from dataclasses import dataclass, field
from typing import Any
import anthropic
from config import get_api_key

_client: anthropic.Anthropic | None = None

def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=get_api_key())
    return _client


@dataclass
class AgentMessage:
    role: str
    content: str


@dataclass
class Agent:
    name: str
    role: str
    description: str
    system_prompt: str
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 8096
    history: list[AgentMessage] = field(default_factory=list)

    def chat(self, user_message: str, context: dict[str, Any] | None = None) -> str:
        system = self.system_prompt
        if context:
            context_str = "\n\n".join(f"[{k}]\n{v}" for k, v in context.items())
            system += f"\n\n## Kontext vom Team:\n{context_str}"

        self.history.append(AgentMessage(role="user", content=user_message))

        messages = [{"role": m.role, "content": m.content} for m in self.history]

        response = get_client().messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
        )

        reply = response.content[0].text
        self.history.append(AgentMessage(role="assistant", content=reply))
        return reply

    def reset(self):
        self.history.clear()

    def __str__(self) -> str:
        return f"[{self.role}] {self.name}"

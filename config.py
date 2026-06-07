import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

def get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_KEY", "")
    if not key:
        raise ValueError(
            "Kein Anthropic API Key gefunden. "
            "Setze ANTHROPIC_API_KEY oder ANTHROPIC_KEY in .env"
        )
    return key

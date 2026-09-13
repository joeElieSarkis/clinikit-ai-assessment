"""Explicit provider selection shared by the server and evaluation commands."""
import os

from .gemini import DEFAULT_GEMINI_MODEL, GeminiInterpreter
from .interpreter import DemoInterpreter, OpenAIInterpreter


def create_interpreter(provider: str, model: str | None = None):
    if provider == "demo":
        if model:
            raise ValueError("Demo mode does not use a model")
        return DemoInterpreter()
    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("Set GEMINI_API_KEY in the root .env file or server environment. "
                               "For the offline baseline, explicitly set AI_PROVIDER=demo.")
        return GeminiInterpreter(key, model or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL))
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("AI_PROVIDER=openai requires OPENAI_API_KEY")
        return OpenAIInterpreter(key, model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    raise RuntimeError("AI_PROVIDER must be gemini, demo, or openai")

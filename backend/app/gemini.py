"""Server-side Gemini extraction over REST, with no appointment action tools."""
import json
import re
from datetime import datetime
from pathlib import Path
from threading import Lock
from time import monotonic, sleep

import httpx

from .clinic import DOCTORS
from .models import Extraction, Message

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


class GeminiUnavailable(RuntimeError):
    """A safe error code; provider bodies and credentials never enter the transcript."""

    def __init__(self, code: str, http_status: int | None = None, response_reason: str | None = None):
        self.code = code
        self.http_status = http_status
        self.response_reason = response_reason
        super().__init__(code)


class GeminiInterpreter:
    source = "gemini structured output"

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL,
                 client: httpx.Client | None = None, clock=monotonic, pause=sleep):
        if not api_key.strip():
            raise ValueError("GEMINI_API_KEY is required")
        if not re.fullmatch(r"gemini-[a-zA-Z0-9.-]+", model):
            raise ValueError("GEMINI_MODEL must be a Gemini model id, not a URL")
        self.model = model
        self._api_key = api_key.strip()
        self._client = client or httpx.Client(timeout=20.0, follow_redirects=False)
        self._clock = clock
        self._pause = pause
        self.requests_sent = 0
        self._lock = Lock()
        self._next_request = 0.0
        self._cooldown_code = "rate_limited"
        self.prompt = (Path(__file__).parent / "prompts" / "extract.md").read_text(encoding="utf-8")

    def extract(self, text: str, draft: Extraction | None, messages: list[Message], now: datetime) -> Extraction:
        # A small shared cooldown limits bursts without queues or automatic retries.
        # Google still enforces the actual project quota, which varies by account.
        with self._lock:
            if self._clock() < self._next_request:
                raise GeminiUnavailable(self._cooldown_code)
            self._next_request = self._clock() + 2.0
            self._cooldown_code = "rate_limited"
        context = {
            "reference_time": now.isoformat(), "timezone": "Asia/Beirut", "known_doctors": DOCTORS,
            "current_draft": draft.model_dump() if draft else None,
            "recent_conversation": [{"role": m.role, "content": m.content} for m in messages[-8:]],
            "current_message": text,
        }
        schema = Extraction.model_json_schema()
        # Require every field explicitly; nullable entities remain nullable.
        schema["required"] = list(schema["properties"])
        for field in schema["properties"].values():
            field.pop("default", None)
        config = {
            "responseMimeType": "application/json", "responseJsonSchema": schema,
            "candidateCount": 1, "maxOutputTokens": 2048,
        }
        # 2.5 Flash supports disabling thinking for this bounded extraction task.
        # Other models keep their own defaults rather than receiving incompatible settings.
        if self.model == "gemini-2.5-flash":
            config["thinkingConfig"] = {"thinkingBudget": 0}
        payload = {
            "systemInstruction": {"parts": [{"text": self.prompt}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(context, ensure_ascii=False)}]}],
            "generationConfig": config,
        }
        try:
            deadline = self._clock() + 20.0
            for attempt in range(2):
                with self._lock:
                    self.requests_sent += 1
                response = self._client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                    headers={"x-goog-api-key": self._api_key}, json=payload,
                    timeout=max(.1, deadline - self._clock()), follow_redirects=False,
                )
                # One bounded retry for temporary gateway/service failures only.
                # Quotas, access errors, timeouts, and invalid model output are not retried.
                if response.status_code in (502, 503, 504) and attempt == 0 and deadline - self._clock() > 1.0:
                    self._pause(1.0)
                    continue
                break
        except httpx.TimeoutException:
            raise GeminiUnavailable("timeout") from None
        except httpx.HTTPError:
            raise GeminiUnavailable("connection_error") from None
        if response.status_code == 429:
            code = "rate_limited"
            try:
                details = response.json().get("error", {}).get("details", [])
                if any("PerDay" in str(violation.get("quotaId", ""))
                       for detail in details for violation in detail.get("violations", [])):
                    code = "daily_quota"
            except (ValueError, AttributeError, TypeError):
                pass
            with self._lock:
                self._next_request = max(self._next_request, self._clock() + 60.0)
                self._cooldown_code = code
            raise GeminiUnavailable(code, http_status=429)
        if response.status_code in (401, 403):
            raise GeminiUnavailable("configuration", http_status=response.status_code)
        if response.status_code == 404:
            raise GeminiUnavailable("model_unavailable", http_status=404)
        if response.status_code != 200:
            raise GeminiUnavailable("provider_error" if response.status_code >= 500 else "unavailable", http_status=response.status_code)
        response_reason = None
        try:
            body = response.json()
            if body.get("promptFeedback", {}).get("blockReason"):
                response_reason = "blocked_prompt"
                raise ValueError("Blocked prompt")
            candidates = body["candidates"]
            if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
                finish = candidates[0].get("finishReason") if len(candidates) == 1 else None
                response_reason = finish if finish in ("MAX_TOKENS", "SAFETY", "RECITATION", "OTHER") else "incomplete_candidate"
                raise ValueError("No complete candidate")
            parts = candidates[0]["content"]["parts"]
            result = "".join(part["text"] for part in parts if "text" in part and not part.get("thought"))
            # Schema generation is not a trust boundary: validate locally as well.
            parsed = json.loads(result)
            if not isinstance(parsed, dict) or set(parsed) != set(Extraction.model_fields):
                raise ValueError("Incomplete extraction")
            return Extraction.model_validate(parsed, strict=True)
        except (ValueError, KeyError, TypeError, AttributeError):
            raise GeminiUnavailable("invalid_output", http_status=200, response_reason=response_reason or "schema_validation") from None

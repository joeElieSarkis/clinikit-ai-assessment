"""Interpreters extract requests; they never receive appointment mutation tools."""
import json
import re
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path

from openai import OpenAI

from .clinic import DOCTORS
from .models import Extraction, Message

WEEKDAYS = "monday|tuesday|wednesday|thursday|friday|saturday|sunday"
MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
DATE_PATTERN = rf"\b(?:\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}/\d{{1,2}}(?:/\d{{2,4}})?|\d{{1,2}} (?:{MONTHS})(?: \d{{4}})?|(?:{MONTHS}) \d{{1,2}}(?:,? \d{{4}})?|day after tomorrow|tomorrow|today|yesterday|next week|(?:next |this )?(?:{WEEKDAYS}))\b"
HOLD_PATTERN = r"\b(?:don'?t|do not|not yet|never|hold off|wait|just checking|just exploring|might|maybe|not sure|thinking about|not ready|before (?:i |you )?confirm)\b"


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'")
    replacements = {"tmrw": "tomorrow", "tmr": "tomorrow", "tommorow": "tomorrow", "tomorow": "tomorrow",
                    "pls": "please", "plz": "please", "appt": "appointment", "appoitment": "appointment",
                    "reshedule": "reschedule", "rescedule": "reschedule", "cancell": "cancel", "cncel": "cancel",
                    "georges": "george"}
    return re.sub(r"\b[a-z]+\b", lambda m: replacements.get(m[0], m[0]), text)


def has_hold(text: str) -> bool:
    return bool(re.search(HOLD_PATTERN, normalize(text)))


class DemoInterpreter:
    """Bounded English demo. Unknown language asks for clarification; it is not an LLM."""
    source = "demo rules"

    def extract(self, text: str, draft: Extraction | None, messages: list[Message], now: datetime) -> Extraction:
        t = normalize(text)
        hold = has_hold(t)
        dates = re.findall(DATE_PATTERN, t)
        preferred_date = dates[-1] if dates else None
        original_date = dates[0] if len(dates) > 1 and re.search(r"\bfrom\b", t) else None
        doctor = None
        named = re.search(r"\b(?:dr\.?|doctor)\s+([a-z]+)", t)
        names = [name for name in DOCTORS if re.search(rf"\b{name.lower()}\b", t)]
        if named and named[1] not in ("again", "available", "availability", "tomorrow", "next"):
            matches = get_close_matches(named[1], [d.lower() for d in DOCTORS], n=1, cutoff=.78)
            doctor = matches[0].title() if matches else named[1].title()
        elif names:
            doctor = names[0]
        ref = re.search(r"\bck-[a-z0-9]{4,12}\b", t)
        time = None
        timed = re.search(r"\b(?:at|after|before|around|by)\s+(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)", t)
        standalone = re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\b\d{1,2}:\d{2}\b", t)
        if timed:
            time = timed[0].removeprefix("at ").strip()
        elif standalone:
            time = standalone[0]
        elif "afternoon" in t:
            time = "afternoon"
        elif "morning" in t:
            time = "morning"
        elif "evening" in t:
            time = "evening"
        elif re.search(r"\b(?:noon|midday|midnight)\b", t):
            time = re.search(r"\b(?:noon|midday|midnight)\b", t)[0]
        if re.search(r"\b(human|person|receptionist|call me|call back|somebody.*call|someone.*call|speak.*team)\b", t):
            intent = "handoff"
        elif re.search(r"\b(chest pain|can't breathe|cannot breathe|emergency|bleeding|diagnos\w*|medication|prescri\w*|symptom\w*|medical advice|dose|painkiller)\b", t):
            intent = "medical"
        elif re.search(r"\b(open|opening|close|closes|closing|hours)\b", t):
            intent = "hours"
        elif re.search(r"\b(reschedule|move|change|shift|postpone)\b", t):
            intent = "reschedule"
        elif re.search(r"\b(cancel|delete|remove)\b", t):
            intent = "cancel"
        elif re.search(r"\b(book|schedule|see|visit|need.*appointment|want.*appointment)\b", t):
            intent = "book"
        elif re.search(r"\b(available|availability|anything available|free slots|any slots|what times)\b", t):
            intent = "availability"
        elif draft and (doctor or preferred_date or time or ref or t.startswith("use ")):
            intent = draft.intent
        else:
            intent = "unclear"
        # A slot selection from an availability search begins a booking review.
        if t.startswith("use ") and intent == "availability":
            intent = "book"
        ambiguous = len(names) > 1 or bool(re.search(r"\b(?:or|either)\b", t) and (dates or time))
        if re.search(r"\b(?:between|from)\s+\d.*\b(?:and|to)\s+\d", t):
            ambiguous = True
        if len(dates) > 1 and not original_date:
            ambiguous = True
        if re.search(r"\b(cancel|remove)\b.*\b(and|also)\b.*\b(book|reschedule)\b", t):
            ambiguous = True
        return Extraction(intent=intent, doctor=doctor, preferred_date=preferred_date, preferred_time=time,
                          original_date=original_date, appointment_id=ref[0].upper() if ref else None,
                          hold=hold, ambiguous=ambiguous)


class OpenAIInterpreter:
    source = "openai structured output"

    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key, timeout=20.0, max_retries=0)
        self.model = model
        self.prompt = (Path(__file__).parent / "prompts" / "extract.md").read_text(encoding="utf-8")

    def extract(self, text: str, draft: Extraction | None, messages: list[Message], now: datetime) -> Extraction:
        context = {
            "reference_time": now.isoformat(), "timezone": "Asia/Beirut", "known_doctors": DOCTORS,
            "current_draft": draft.model_dump() if draft else None,
            "recent_conversation": [{"role": m.role, "content": m.content} for m in messages[-8:]],
            "current_message": text,
        }
        response = self.client.responses.parse(
            model=self.model,
            input=[{"role": "system", "content": self.prompt},
                   {"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
            text_format=Extraction,
            store=False,
            max_output_tokens=700,
        )
        if response.output_parsed is None:
            raise ValueError("No validated interpretation returned")
        return response.output_parsed

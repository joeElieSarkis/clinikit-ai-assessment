"""Resolve explicit details within an already understood appointment request."""
import re
from datetime import datetime

from .clinic import DOCTORS
from .interpreter import DATE_PATTERN, DemoInterpreter, normalize
from .models import Extraction


def detail_reply(text: str, draft: Extraction | None, now: datetime) -> Extraction | None:
    if not draft or draft.intent not in ('book', 'reschedule', 'cancel', 'availability') or draft.ambiguous:
        return None
    t = normalize(text).strip(' \t\r\n.!?"\'“”‘’')
    local = DemoInterpreter().extract(t, draft, [], now)
    doctor = re.fullmatch(r'(?:with )?(?:(?:dr\.?|doctor)\s+)?[a-z]+', t)
    if doctor and local.doctor:
        return Extraction(intent=draft.intent, doctor=local.doctor)
    if re.fullmatch(DATE_PATTERN, t):
        return Extraction(intent=draft.intent, preferred_date=t)
    if re.fullmatch(r'(?:(?:at|after|before|around)\s+)?(?:\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?|morning|afternoon|evening|noon|midday|midnight)', t):
        return Extraction(intent=draft.intent, preferred_time=t)
    # Match the message sent by the frontend's slot buttons.
    slot = re.fullmatch(r'use dr\. ([a-z]+) on (\d{4}-\d{2}-\d{2}) at (\d{2}:\d{2})', t)
    if slot and slot[1].title() in DOCTORS:
        return Extraction(intent='reschedule' if draft.intent == 'reschedule' else 'book',
                          doctor=slot[1].title(), preferred_date=slot[2], preferred_time=slot[3])
    return None

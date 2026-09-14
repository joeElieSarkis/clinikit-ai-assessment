"""Read-only appointment clarification using the choices actually shown to the patient."""
import re
from datetime import datetime
from difflib import get_close_matches

from .dates import resolve_existing_dates, resolve_time
from .interpreter import DemoInterpreter, normalize
from .models import Appointment, Extraction


def reference_reply(text: str) -> str | None:
    match = re.fullmatch(r'ck-[a-z0-9]{4,12}', normalize(text).strip(' \t\r\n.!,?"\'“”‘’'))
    return match[0].upper() if match else None


def short_selection(text: str, draft: Extraction, choices: list[Appointment], now: datetime) -> Extraction | None:
    """Route only bounded choice replies locally; free-form language still uses the provider."""
    t = normalize(text).strip(' \t\r\n.!?"\'“”‘’')
    ordinal = re.fullmatch(r'(?:the |number |option )?(first|second|third|fourth|fifth|[1-9])(?: one| appointment| visit)?', t)
    if ordinal:
        words = ['first', 'second', 'third', 'fourth', 'fifth']
        index = words.index(ordinal[1]) if ordinal[1] in words else int(ordinal[1]) - 1
        if index < len(choices):
            return Extraction(intent=draft.intent, appointment_id=choices[index].id)
        return Extraction(intent=draft.intent, ambiguous=True)
    t = re.sub(r'^(?:the (?:one|appointment|visit) (?:with|at|in) |with |the )', '', t)
    t = re.sub(r' (?:one|appointment|visit)$', '', t)
    local = DemoInterpreter().extract(t, draft, [], now)
    doctor_only = re.fullmatch(r'(?:dr\.? |doctor )?[a-z]+', t)
    if doctor_only and not local.doctor:
        name = re.sub(r'^(?:dr\.? |doctor )', '', t)
        matches = get_close_matches(name, sorted({visit.doctor.lower() for visit in choices}), n=1, cutoff=.8)
        if matches:
            local.doctor = matches[0].title()
    time_only = re.fullmatch(r'(?:at )?(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?|morning|afternoon|evening|noon|midday)', t)
    if (doctor_only and local.doctor) or time_only:
        # These fields identify an existing visit while a choice is pending.
        local.intent = draft.intent
        if time_only and not local.preferred_time:
            local.preferred_time = t.removeprefix('at ')
        return local
    return None


def match_selection(choices: list[Appointment], selector: Extraction, now: datetime) -> tuple[list[Appointment], str | None]:
    candidates = [visit for visit in choices if visit.status == 'confirmed']
    if selector.appointment_id:
        candidates = [visit for visit in candidates if visit.id == selector.appointment_id.upper()]
    if selector.doctor:
        doctor = selector.doctor.removeprefix('Dr. ').strip().casefold()
        candidates = [visit for visit in candidates if visit.doctor.casefold() == doctor]
    date_description = selector.original_date or selector.preferred_date
    if date_description:
        days, error = resolve_existing_dates(date_description, [visit.date for visit in candidates], now)
        if error:
            return [], error
        candidates = [visit for visit in candidates if visit.date in {day.isoformat() for day in days}]
    if selector.preferred_time:
        _, matches_time, error = resolve_time(selector.preferred_time)
        if error:
            return [], error
        candidates = [visit for visit in candidates if matches_time(visit.time)]
    return candidates, None

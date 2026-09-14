"""Resolve date and time phrases without silently choosing ambiguous times."""
import re
from datetime import date, datetime, timedelta
from collections.abc import Callable

import dateparser

from .clinic import minutes

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def resolve_existing_dates(value: str, appointment_dates: list[str], now: datetime) -> tuple[list[date], str | None]:
    """A bare weekday describes stored visits, rather than a new calendar request."""
    weekday = value.strip().lower()
    if weekday in WEEKDAYS:
        dates = [date.fromisoformat(day) for day in dict.fromkeys(appointment_dates)]
        return [day for day in dates if day.weekday() == WEEKDAYS.index(weekday)], None
    # Explicit dates and qualifiers such as "this Monday" keep their normal meaning.
    return resolve_dates(value, now)


def resolve_dates(value: str | None, now: datetime) -> tuple[list[date], str | None]:
    if not value:
        return [], None
    t = value.lower().strip()
    today = now.date()
    if t == "next week":
        monday = today + timedelta(days=7 - today.weekday())
        days = [monday + timedelta(days=i) for i in range(6)]
    elif t in ("today", "tomorrow", "day after tomorrow", "yesterday"):
        days = [today + timedelta(days={"today": 0, "tomorrow": 1, "day after tomorrow": 2, "yesterday": -1}[t])]
    elif t.removeprefix("next ").removeprefix("this ") in WEEKDAYS:
        weekday = WEEKDAYS.index(t.removeprefix("next ").removeprefix("this "))
        delta = (weekday - today.weekday()) % 7
        if t.startswith("next "):
            delta = 7 - today.weekday() + weekday
        days = [today + timedelta(days=delta)]
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        try:
            days = [date.fromisoformat(t)]
        except ValueError:
            return [], "That date doesn’t exist. Please give a valid date, such as 2026-09-16."
    else:
        # Accept named calendar dates only. Numeric month/day order is not assumed.
        if not re.search(r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b", t):
            return [], "Please give a specific day, a date like 2026-09-16, or ‘next week’."
        parsed = dateparser.parse(t, languages=["en"], settings={"RELATIVE_BASE": now.replace(tzinfo=None), "PREFER_DATES_FROM": "future"})
        if parsed is None:
            return [], "I couldn’t read that date. Please use a date like 2026-09-16."
        days = [parsed.date()]
    if any(day < today for day in days):
        return [], "That date is in the past. Which upcoming day would you prefer?"
    if any(day > today + timedelta(days=90) for day in days):
        return [], "The sample schedule covers the next 90 days. Please choose a date within that range."
    return days, None


def resolve_time(value: str | None) -> tuple[str | None, Callable[[str], bool], str | None]:
    """Return exact time, range predicate, or clarification. Bare 1–12 stays ambiguous."""
    if not value:
        return None, lambda _: True, None
    t = value.lower().strip().replace(".", "")
    if t in ("morning", "afternoon", "evening"):
        limits = {"morning": (0, 12 * 60), "afternoon": (12 * 60, 17 * 60), "evening": (17 * 60, 24 * 60)}
        low, high = limits[t]
        return None, lambda time: low <= minutes(time) < high, None
    if t in ("noon", "midday"):
        t = "12:00 pm"
    if t == "midnight":
        t = "12:00 am"
    match = re.fullmatch(r"(?:(after|before|at)\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if not match:
        return None, lambda _: False, "Please give an exact time with am/pm, or a preference such as ‘afternoon’ or ‘after 5 pm’."
    modifier, hour, minute, period = match.groups()
    h, m = int(hour), int(minute or 0)
    if m > 59 or h > 23 or (period and not 1 <= h <= 12):
        return None, lambda _: False, "That time isn’t valid. Please use a time such as 4 pm or 16:00."
    if not period and 1 <= h <= 12 and not (minute is not None and len(hour) == 2):
        return None, lambda _: False, f"Did you mean {h}:{m:02d} am or {h}:{m:02d} pm? Please include am or pm."
    if period:
        h = h % 12 + (12 if period == "pm" else 0)
    exact = f"{h:02d}:{m:02d}"
    if modifier in ("after", "before"):
        return None, (lambda time: minutes(time) > minutes(exact)) if modifier == "after" else (lambda time: minutes(time) < minutes(exact)), None
    return exact, lambda time: time == exact, None

"""Fictional clinic facts and read-only schedule tools. No external integrations."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .models import Appointment, Slot

TIMEZONE = ZoneInfo("Asia/Beirut")
DOCTORS = ("George", "Karim", "Maya")
TIMES = {
    "George": ("09:00", "10:00", "11:00", "14:00", "16:00", "17:00", "17:30"),
    "Karim": ("09:30", "10:00", "10:30", "11:30", "14:30", "15:30", "16:30"),
    "Maya": ("09:00", "11:00", "12:00", "13:00", "15:00", "17:00"),
}
HOURS = "Our sample clinic is open Monday to Friday, 9 am–6 pm, and Saturday, 9 am–1 pm. We’re closed on Sunday. All times are in Beirut."


def now_local() -> datetime:
    return datetime.now(TIMEZONE)


def next_monday(today: date) -> date:
    return today + timedelta(days=(0 - today.weekday()) % 7 or 7)


def seed_appointments(now: datetime) -> list[Appointment]:
    return [Appointment(id="CK-1042", doctor="Karim", date=next_monday(now.date()).isoformat(), time="10:00")]


def describe(slot: Slot) -> str:
    day = date.fromisoformat(slot.date).strftime("%A, %d %B %Y")
    hour = datetime.strptime(slot.time, "%H:%M").strftime("%I:%M %p").lstrip("0")
    return f"Dr. {slot.doctor} · {day} · {hour} (Beirut)"


def minutes(time: str) -> int:
    h, m = map(int, time.split(":"))
    return h * 60 + m


def is_available(slot: Slot, appointments: list[Appointment], now: datetime, exclude: str | None = None) -> bool:
    """Validate schedule, future time, and the sample patient's 30-minute conflicts."""
    try:
        day = date.fromisoformat(slot.date)
        timestamp = datetime.fromisoformat(f"{slot.date}T{slot.time}").replace(tzinfo=TIMEZONE)
    except ValueError:
        return False
    if slot.doctor not in DOCTORS or slot.time not in TIMES[slot.doctor]:
        return False
    if day.weekday() == 6 or (day.weekday() == 5 and slot.time >= "13:00"):
        return False
    if timestamp <= now or day > now.date() + timedelta(days=90):
        return False
    return not any(
        a.status == "confirmed" and a.id != exclude and a.date == slot.date
        and abs(minutes(a.time) - minutes(slot.time)) < 30
        for a in appointments
    )


def check_availability(doctor: str, dates: list[date], appointments: list[Appointment], now: datetime,
                       time_filter=lambda _: True, exclude: str | None = None) -> list[Slot]:
    result = []
    for day in dates:
        for time in TIMES.get(doctor, ()):
            slot = Slot(doctor=doctor, date=day.isoformat(), time=time)
            if time_filter(time) and is_available(slot, appointments, now, exclude):
                result.append(slot)
    return result

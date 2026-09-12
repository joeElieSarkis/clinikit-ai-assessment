"""Deterministic orchestration: understand → validate → propose → confirm → act."""
import re
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from time import monotonic, perf_counter
from uuid import uuid4

from .clinic import DOCTORS, HOURS, check_availability, describe, is_available, now_local, seed_appointments
from .dates import resolve_dates, resolve_time
from .interpreter import DemoInterpreter, has_hold, normalize
from .models import Appointment, Decision, Extraction, Message, Proposal, SessionView, Slot, ToolResult


@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid4()))
    messages: list[Message] = field(default_factory=lambda: [Message(role="assistant", content="Welcome to reception. I can help with appointments, clinic hours, or a request for our reception team. What would you like to do?")])
    appointments: list[Appointment] = field(default_factory=list)
    pending: Proposal | None = None
    pending_at: float = 0
    draft: Extraction | None = None
    slots: list[Slot] = field(default_factory=list)
    handoffs: int = 0
    requests: dict[str, str] = field(default_factory=dict)
    touched: float = field(default_factory=monotonic)
    lock: RLock = field(default_factory=RLock)


class ReceptionEngine:
    def __init__(self, interpreter=None, clock=now_local, mode="demo", model=None):
        self.interpreter = interpreter or DemoInterpreter()
        self.clock, self.mode, self.model = clock, mode, model

    def create_session(self) -> Session:
        return Session(appointments=seed_appointments(self.clock()))

    def view(self, session: Session) -> SessionView:
        return SessionView(id=session.id, now=self.clock().isoformat(), mode=self.mode, model=self.model,
                           messages=session.messages, appointments=session.appointments, pending=session.pending,
                           slots=session.slots, handoffs=session.handoffs)

    def chat(self, s: Session, text: str) -> None:
        started = perf_counter()
        previous = s.draft
        s.pending = None  # Every new message invalidates an earlier confirmation token.
        s.slots = []
        user_message = Message(role="user", content=text)
        s.messages.append(user_message)
        checks = ["No appointment change is permitted through the message endpoint.", "Any earlier proposal has been invalidated."]
        tools: list[ToolResult] = []
        source = self.interpreter.source

        def reply(content: str, action="ask_for_more_information", reason="Missing information requires clarification.", extraction=None):
            current = extraction or s.draft or Extraction(intent="unclear")
            decision = Decision(intent=current.intent, entities=current.model_dump(exclude={"intent"}), action=action,
                                reason=reason, checks=checks, tools=tools, source=source,
                                duration_ms=round((perf_counter() - started) * 1000))
            s.messages.append(Message(role="assistant", content=content, decision=decision))

        t = normalize(text)
        if re.fullmatch(r"(?:never mind|nevermind|forget it|stop|cancel that|leave it|keep as is)[.! ]*", t):
            s.draft = None
            reply("Of course. I’ve cleared that request. Your appointments are unchanged.", "clear_request", "The patient stopped the draft request.")
            return
        if re.fullmatch(r"(?:yes|yeah|yep|ok|okay|sure|confirm|go ahead|do it|yes please)[.! ]*", t):
            s.draft = previous
            reply("To change an appointment, please select a specific time again and use its confirmation button. A message like ‘yes’ doesn’t change your visits.", reason="Free-text acknowledgement cannot authorize a mutation.")
            return
        if re.search(r"ignore (?:all |previous |the )*(?:instructions|rules)|system prompt|developer message|<\/?system>|execute.*(?:sql|code)", t):
            s.draft = None
            reply("I can help with clinic appointments, opening hours, or a request for a person. What would you like help with?", reason="Out-of-scope instructions are not clinic authority.")
            return
        try:
            # Explicit handoff remains available during a language-provider outage.
            local = DemoInterpreter().extract(text, None, [], self.clock())
            if local.intent in ("handoff", "medical"):
                extracted = local
                source = "local routing policy"
            else:
                extracted = self.interpreter.extract(text, previous, s.messages[:-1], self.clock())
        except Exception:
            # Fail closed: never silently substitute demo rules for a failed live model.
            s.draft = None
            checks.append("Interpretation failed; no proposed action or appointment mutation remains.")
            reply("I couldn’t reliably understand that request because the language service is unavailable. Your appointments are unchanged. Please try again, or ask for a person.", "service_unavailable", "The interpreter failed or did not return validated data.")
            return
        if extracted.intent in ("book", "reschedule", "cancel", "availability") and previous:
            compatible = extracted.intent == previous.intent or (previous.intent == "availability" and extracted.intent == "book")
            if compatible:
                for key in ("doctor", "preferred_date", "preferred_time", "original_date", "appointment_id"):
                    if getattr(extracted, key) is None:
                        setattr(extracted, key, getattr(previous, key))
                # A hold survives follow-ups unless the patient explicitly resumes the action.
                explicit_resume = bool(re.search(r"\b(book|schedule|reschedule|cancel|ready|go ahead)\b", t)) and not has_hold(t)
                extracted.hold = extracted.hold or (previous.hold and not explicit_resume)
        extracted.hold = extracted.hold or has_hold(text)
        s.draft = extracted
        if extracted.hold:
            checks.append("A request to wait prevents a confirmation proposal.")
        if extracted.ambiguous:
            reply("I see more than one possible choice. Which single action, doctor, and day should we work on first? I haven’t changed anything.", reason="Conflicting alternatives must be resolved by the patient.")
            return
        if extracted.intent == "hours":
            s.draft = None
            tools.append(ToolResult(name="get_clinic_hours", result=HOURS))
            reply(HOURS, "get_clinic_hours", "Opening hours come from the configured sample clinic.", extracted)
            return
        if extracted.intent in ("handoff", "medical"):
            s.draft = None
            s.handoffs += 1
            tools.append(ToolResult(name="handoff_to_human", result=f"Mock handoff H-{s.handoffs:03d} recorded; no external message sent."))
            content = "I’ve recorded a request for the reception team in this demo. No real person has been contacted and no callback has been arranged."
            if extracted.intent == "medical":
                content = "Medical questions need a qualified clinician. If this is an emergency, contact local emergency services now. " + content
            reply(content, "handoff_to_human", "Human assistance was requested or the message requires clinical judgment.", extracted)
            return
        if extracted.intent == "unclear":
            s.draft = None
            reply("I can help you book, move, or cancel an appointment, check opening hours, or ask for a person. Which would you like?", extraction=extracted)
            return
        if extracted.doctor:
            extracted.doctor = extracted.doctor.removeprefix("Dr. ").strip().title()
            if extracted.doctor not in DOCTORS:
                reply(f"I couldn’t find Dr. {extracted.doctor} in the sample clinic. We have Dr. George, Dr. Karim, and Dr. Maya. Who would you like to see?", reason="Unknown doctors cannot be booked.")
                return

        target = None
        if extracted.intent in ("cancel", "reschedule"):
            candidates = [a for a in s.appointments if a.status == "confirmed"]
            if extracted.appointment_id:
                candidates = [a for a in candidates if a.id == extracted.appointment_id]
            if extracted.doctor:
                candidates = [a for a in candidates if a.doctor == extracted.doctor]
            if extracted.original_date:
                original, err = resolve_dates(extracted.original_date, self.clock())
                if err or len(original) != 1:
                    reply("Please provide the existing appointment reference from ‘Your next visits’ so I can identify it precisely.")
                    return
                candidates = [a for a in candidates if a.date == original[0].isoformat()]
            if extracted.intent == "cancel" and extracted.preferred_date:
                dates, err = resolve_dates(extracted.preferred_date, self.clock())
                if err or len(dates) != 1:
                    reply("Which appointment should be cancelled? Please provide its appointment reference.")
                    return
                candidates = [a for a in candidates if a.date == dates[0].isoformat()]
            if extracted.intent == "cancel" and extracted.preferred_time:
                _, matches_time, err = resolve_time(extracted.preferred_time)
                if err:
                    reply(err)
                    return
                candidates = [a for a in candidates if matches_time(a.time)]
            tools.append(ToolResult(name="find_appointment", result=f"{len(candidates)} matching active appointment(s) in this sample session."))
            if len(candidates) != 1:
                reply("I couldn’t identify one matching visit. Please use an appointment reference from ‘Your next visits’, such as CK-1042.", reason="An exact, session-owned appointment is required.")
                return
            target = candidates[0]
            extracted.appointment_id = target.id
            extracted.doctor = target.doctor
            checks.append("The existing appointment belongs to the current sample session.")
            if extracted.intent == "cancel":
                if extracted.hold:
                    reply(f"I’ll leave your visit unchanged: {describe(target)}. Tell me when you’re ready to review a cancellation.", "wait_for_patient", "The patient asked to wait.")
                    return
                s.pending = Proposal(kind="cancel", doctor=target.doctor, date=target.date, time=target.time,
                                     appointment_id=target.id, summary=f"Cancel {target.id}\n{describe(target)}")
                s.pending_at = monotonic()
                reply(f"Please review the cancellation for {target.id} below. Your visit is still confirmed until you choose ‘Confirm cancellation’.", "ask_for_confirmation", "Cancellation is staged; it has not been executed.")
                return

        if not extracted.doctor:
            prefix = "I won’t book anything yet. " if extracted.hold else ""
            reply(prefix + "Which doctor would you like to see: Dr. George, Dr. Karim, or Dr. Maya?")
            return
        days, error = resolve_dates(extracted.preferred_date, self.clock())
        if error:
            reply(error)
            return
        if not days:
            reply(f"Which day would you prefer with Dr. {extracted.doctor}? You can give a specific date, a weekday, or ‘next week’.")
            return
        exact, time_filter, error = resolve_time(extracted.preferred_time)
        if error:
            prefix = "I won’t book anything yet. " if extracted.hold else ""
            reply(prefix + error, reason="The time must be unambiguous before it can be used.")
            return
        slots = check_availability(extracted.doctor, days, s.appointments, self.clock(), time_filter, target.id if target else None)
        tools.append(ToolResult(name="check_availability", result=f"{len(slots)} matching future slot(s) in the mock schedule."))
        if not slots:
            if all(day.weekday() == 6 for day in days):
                reply("The sample clinic is closed on Sunday. Please choose another day; Monday to Saturday are available.", "ask_for_more_information", "The requested date is outside clinic hours.")
            else:
                alternatives = check_availability(extracted.doctor, days, s.appointments, self.clock(), exclude=target.id if target else None)
                s.slots = alternatives[:5]
                reply("That time isn’t available in the sample schedule. " + ("Here are other available times on your requested day(s)." if s.slots else "Please choose another day."), "check_availability", "No matching slot is available; the requested time is not invented.")
            return
        checks.extend(["Date resolved against the current time in Asia/Beirut.", "Schedule and the sample patient’s existing appointments were checked."])
        if extracted.hold:
            s.slots = slots[:5]
            reply("I won’t book or change anything yet. These times are available to explore. When you’re ready, tell me explicitly that you’d like to book or reschedule.", "check_availability", "Availability is read-only; the patient asked to wait.")
            return
        if extracted.intent == "availability" or not exact or len(days) != 1:
            s.slots = slots[:5]
            reply(f"Here are available times with Dr. {extracted.doctor}. Choose a time to review the details; selecting it does not confirm the visit.", "check_availability", "The patient needs to choose a specific slot.")
            return
        slot = slots[0]
        if target and target.date == slot.date and target.time == slot.time:
            reply("Your appointment is already at that time. No change is needed.", "no_change", "The requested slot matches the existing appointment.")
            return
        kind = "reschedule" if target else "book"
        summary = describe(slot)
        if target:
            summary = f"From: {describe(target)}\nTo: {describe(slot)}"
        s.pending = Proposal(**slot.model_dump(), kind=kind, appointment_id=target.id if target else None, summary=summary)
        s.pending_at = monotonic()
        reply("I’ve prepared the details below. Please review and confirm when you’re ready. Your appointments haven’t changed yet.", "ask_for_confirmation", "A specific available slot is staged behind an explicit confirmation.")

    def confirm(self, s: Session, proposal_id: str, dismiss=False) -> None:
        proposal = s.pending
        if proposal is None or proposal.id != proposal_id:
            raise ValueError("That proposal is no longer current. Please choose the appointment details again.")
        if monotonic() - s.pending_at > 600:
            s.pending = None
            raise ValueError("That proposal has expired. Please choose a time again so availability can be checked.")
        checks = ["Confirmation token matches the current proposal.", "Only this exact proposal may be applied."]
        tools = []
        if dismiss:
            content, action = "No problem. I’ve dismissed that proposal. Your appointments are unchanged.", "dismiss_proposal"
        else:
            target = next((a for a in s.appointments if a.id == proposal.appointment_id and a.status == "confirmed"), None)
            if proposal.kind in ("reschedule", "cancel") and target is None:
                s.pending = None
                raise ValueError("The original appointment is no longer available. Please start the request again.")
            if proposal.kind != "cancel":
                if not is_available(proposal, s.appointments, self.clock(), target.id if target else None):
                    s.pending = None
                    raise ValueError("That slot is no longer available. Please choose another time.")
                checks.append("Availability was rechecked immediately before the change.")
            if proposal.kind == "book":
                appointment = Appointment(doctor=proposal.doctor, date=proposal.date, time=proposal.time, id=f"CK-{uuid4().hex[:8].upper()}")
                s.appointments.append(appointment)
                action = "create_appointment"
                content = f"Your demo appointment is confirmed.\n{describe(appointment)}\nReference: {appointment.id}"
            elif proposal.kind == "reschedule":
                target.date, target.time, target.doctor = proposal.date, proposal.time, proposal.doctor
                action = "reschedule_appointment"
                content = f"Your demo appointment {target.id} has been moved.\n{describe(target)}"
            else:
                target.status = "cancelled"
                action = "cancel_appointment"
                content = f"Your demo appointment {target.id} with Dr. {target.doctor} has been cancelled."
            tools.append(ToolResult(name=action, result=content))
        s.pending, s.draft, s.slots = None, None, []
        decision = Decision(intent=proposal.kind, entities=proposal.model_dump(exclude={"summary", "id"}), action=action,
                            reason="The patient used the explicit proposal control.", checks=checks, tools=tools, source="confirmation policy")
        s.messages.append(Message(role="assistant", content=content, decision=decision))

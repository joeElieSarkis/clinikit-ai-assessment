"""Exercise one complete fictional conversation, with explicit confirmations and real provider traces."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from time import monotonic, sleep

from dotenv import load_dotenv

from .app.clinic import now_local
from .app.dates import resolve_dates
from .app.engine import ReceptionEngine
from .app.providers import create_interpreter
from .evaluate import RecordedInterpreter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=['demo', 'gemini'], default='demo')
    parser.add_argument('--delay', type=float, default=12, help='Minimum seconds between planned live provider requests.')
    parser.add_argument('--output', default='work/conversation-results.json')
    args = parser.parse_args()
    if args.delay < 0:
        parser.error('--delay cannot be negative')
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    provider = create_interpreter(args.provider)
    recorder = RecordedInterpreter(provider)
    reference = now_local()
    engine = ReceptionEngine(recorder, clock=lambda: reference, mode=args.provider, model=getattr(provider, 'model', None))
    session = engine.create_session()
    original = deepcopy(session.appointments)
    rows = []
    last_call = None

    def record(operation, message):
        rows.append({'operation': operation, 'message': message,
                     'response': session.messages[-1].content,
                     'decision': session.messages[-1].decision.model_dump(),
                     'pending': session.pending.model_dump() if session.pending else None,
                     'appointments': [visit.model_dump() for visit in session.appointments]})
        print(f"{operation}: {session.messages[-1].decision.action} | {session.messages[-1].decision.source}", flush=True)

    def chat(message, model=False):
        nonlocal last_call
        if model and args.provider != 'demo' and last_call is not None:
            sleep(max(0, args.delay - (monotonic() - last_call)))
        before = deepcopy(session.appointments)
        calls_before = recorder.calls
        engine.chat(session, message)
        if recorder.calls > calls_before:
            last_call = monotonic()
        record('message', message)
        assert session.appointments == before, 'A message changed appointments without confirmation.'
        assert session.messages[-1].decision.action != 'service_unavailable', 'Provider failed; stopped without a workflow retry or fallback.'

    def confirm(kind):
        assert session.pending and session.pending.kind == kind, f'Expected a {kind} proposal.'
        engine.confirm(session, session.pending.id)
        record('confirm', kind)

    failure = None
    try:
        chat('hi')
        chat('Book me Friday at 4 but don’t confirm anything yet.', model=True)
        assert session.draft and session.draft.hold and session.pending is None, 'The booking hold was lost.'
        chat('Maya')
        assert session.draft and session.draft.doctor == 'Maya' and 'am or' in session.messages[-1].content, 'Doctor or ambiguous time was mishandled.'
        chat('4 pm')
        assert session.pending is None, 'A held request produced a proposal.'
        slot = next((slot for slot in session.slots if slot.time == '17:00'), None)
        assert slot, 'The nearby 5 pm alternative was not offered.'
        chat(f'Use Dr. Maya on {slot.date} at {slot.time}')
        assert session.pending is None and session.draft and session.draft.hold, 'Slot selection bypassed the hold.'
        chat(f'I am ready to book Dr. Maya on {slot.date} at {slot.time}. Please prepare the confirmation.', model=True)
        assert session.pending and session.pending.doctor == 'Maya' and session.pending.date == slot.date and session.pending.time == slot.time, 'The booking proposal differs from the selected slot.'
        confirm('book')
        booked = session.appointments[-1]
        booked_id = booked.id
        destination = resolve_dates('next Wednesday', reference)[0][0].isoformat()
        chat('Could you move my visit with Maya to next Wednesday at 3 pm?', model=True)
        assert session.pending and session.pending.appointment_id == booked_id and session.pending.date == destination and session.pending.time == '15:00', 'The reschedule proposal changed the wrong visit or destination.'
        confirm('reschedule')
        assert booked.date == destination and booked.time == '15:00', 'Rescheduling did not update the selected visit.'
        chat('Please cancel my visit with Dr. Maya.', model=True)
        assert session.pending and session.pending.appointment_id == booked_id, 'Cancellation selected the wrong visit.'
        confirm('cancel')
        assert booked.status == 'cancelled', 'Cancellation was not applied.'
        chat('Can somebody from the clinic call me?')
        assert session.handoffs == 1, 'The mock handoff was not recorded.'
        assert session.appointments[0] == original[0], 'The original Karim visit was unexpectedly changed.'
    except (AssertionError, ValueError) as error:
        failure = str(error)
    result = {'provider': args.provider, 'model': getattr(provider, 'model', None),
              'reference_time': reference.isoformat(), 'evaluated_at': now_local().isoformat(),
              'prompt_sha256': sha256(provider.prompt.encode('utf-8')).hexdigest() if hasattr(provider, 'prompt') else None,
              'passed': failure is None, 'failure': failure, 'interpreter_calls': recorder.calls,
              'http_requests': getattr(provider, 'requests_sent', None),
              'scope': 'One scripted conversation with a held booking, explicit confirmations, reschedule, cancellation, and mock handoff. Bounded details use local routing. Not a general language benchmark.',
              'steps': rows}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"{'PASS' if failure is None else 'FAIL'}: {recorder.calls} interpreter calls. Results: {output}")
    if failure:
        raise SystemExit(failure)


if __name__ == '__main__':
    main()

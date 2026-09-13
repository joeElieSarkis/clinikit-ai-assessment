"""Reproduce assessment examples with a fixed Beirut clock and write real results."""
import argparse
from copy import deepcopy
import json
from datetime import datetime
from pathlib import Path
from time import sleep

from dotenv import load_dotenv

from .app.clinic import TIMEZONE
from .app.engine import ReceptionEngine
from .app.providers import create_interpreter

CASES = [
    ("Can I see Dr. George tomorrow afternoon?", "book"),
    ("Move my appointment from Monday to Wednesday.", "reschedule"),
    ("Cancel my appointment with Dr. Karim.", "cancel"),
    ("What time does the clinic close?", "hours"),
    ("Do you have anything available after 5 tomorrow?", "availability"),
    ("I want to see my doctor again for the same problem.", "book"),
    ("Book me Friday at 4 but don’t confirm anything yet.", "book"),
    ("I need an appointment sometime next week.", "book"),
    ("Can somebody from the clinic call me?", "handoff"),
    ("I might want to see Dr. George tomorrow at 4, but don’t book anything yet.", "book"),
]

EXTRA_CASES = [
    ("Could you pencil me in with Doctor Maya on Tuesday at noon?", "book", {"doctor": "Maya", "preferred_date": "Tuesday", "hold": False}),
    ("Please scrap my visit with Karim.", "cancel", {"doctor": "Karim", "hold": False}),
    ("I'd like to push my Monday visit back to Wednesday.", "reschedule", {"original_date": "Monday", "preferred_date": "Wednesday"}),
    ("Until when are you open on Saturdays?", "hours", {}),
    ("Which slots does Maya have on Wednesday morning?", "availability", {"doctor": "Maya", "preferred_date": "Wednesday"}),
    ("Reserve George for Monday at 4, but leave it unconfirmed for now.", "book", {"doctor": "George", "preferred_time": "4", "hold": True}),
    ("I'd like George or Maya, either Tuesday or Thursday.", "book", {"ambiguous": True}),
    ("Please arrange a visit with Dr. Haddad next week.", "book", {"doctor": "Haddad", "preferred_date": "next week"}),
    ("Please book my regular physician. You know who I mean.", "book", {"doctor": None}),
    ("Book George Monday at 4 pm. Actually, please leave my appointments alone for now.", "book", {"doctor": "George", "hold": True}),
]


class RecordedInterpreter:
    """Record raw extraction separately from the policy engine's merged draft."""

    def __init__(self, interpreter):
        self.interpreter = interpreter
        self.source = interpreter.source
        self.last = None
        self.calls = 0

    def extract(self, *args):
        self.calls += 1
        result = self.interpreter.extract(*args)
        self.last = deepcopy(result.model_dump())
        return result


def entity_match(actual, expected):
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.strip().casefold() == expected.strip().casefold()
    return actual == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=['gemini', 'demo', 'openai'], default='gemini')
    parser.add_argument('--model', help='Override the configured model; does not change the account billing tier.')
    parser.add_argument('--suite', choices=['assessment', 'extended'], default='assessment')
    parser.add_argument('--delay', type=float, help='Seconds between cases; defaults to 12 for live providers, 0 for demo.')
    parser.add_argument('--output', help='Results path; defaults to docs/<provider>-<suite>-results.json.')
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    delay = args.delay if args.delay is not None else (0 if args.provider == 'demo' else 12)
    if delay < 0:
        parser.error('--delay cannot be negative')
    try:
        provider = create_interpreter(args.provider, args.model)
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from None
    model = getattr(provider, 'model', None)
    interpreter = RecordedInterpreter(provider)
    reference = datetime(2026, 9, 12, 11, 0, tzinfo=TIMEZONE)
    engine = ReceptionEngine(interpreter, clock=lambda: reference, mode=args.provider, model=model)
    cases = [(text, intent, {}) for text, intent in CASES]
    if args.suite == 'extended':
        cases += EXTRA_CASES
    rows = []
    for index, (message, expected, expected_entities) in enumerate(cases):
        if index:
            sleep(delay)
        interpreter.last = None
        calls_before = interpreter.calls
        session = engine.create_session()
        before = [a.model_dump() for a in session.appointments]
        engine.chat(session, message)
        decision = session.messages[-1].decision
        mutations = before != [a.model_dump() for a in session.appointments]
        entities_match = (not expected_entities or interpreter.last is not None) and all(
            entity_match((interpreter.last or {}).get(key), value) for key, value in expected_entities.items())
        rows.append({'message': message, 'expected_intent': expected, 'observed_intent': decision.intent,
                     'intent_match': decision.intent == expected, 'appointments_changed': mutations,
                     'expected_entities': expected_entities, 'raw_extraction': interpreter.last,
                     'entities_match': entities_match,
                     'interpreter_called': interpreter.calls > calls_before,
                     'interpretation_failed': decision.action == 'service_unavailable',
                     'proposal_present': session.pending is not None, 'decision': decision.model_dump(),
                     'response': session.messages[-1].content})
        print(f"{index + 1}/{len(cases)}: {decision.intent} | {decision.action} | {decision.source}", flush=True)
        if args.provider != 'demo' and decision.action == 'service_unavailable':
            # Preserve the failure and stop; do not burn quota on an unavailable provider.
            break
    result = {'provider': args.provider, 'model': model, 'reference_time': reference.isoformat(),
              'evaluated_at': datetime.now(TIMEZONE).isoformat(),
              'suite': args.suite, 'planned_cases': len(cases),
              'scope': 'Each case starts a fresh fictional session. Extended adds ten paraphrase/entity checks. Local routing is reported separately; this is not a general accuracy benchmark.',
              'intent_matches': sum(row['intent_match'] for row in rows), 'cases': len(rows),
              'entity_cases': sum(bool(row['expected_entities']) for row in rows),
              'entity_case_matches': sum(bool(row['expected_entities']) and row['entities_match'] for row in rows),
              'interpreter_calls': interpreter.calls,
              'local_policy_cases': sum(not row['interpreter_called'] for row in rows),
              'interpretation_failures': sum(row['interpretation_failed'] for row in rows),
              'unconfirmed_mutations': sum(row['appointments_changed'] for row in rows), 'results': rows}
    output = Path(args.output or f'docs/{args.provider}-{args.suite}-results.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"{result['intent_matches']}/{len(rows)} intent matches; {result['entity_case_matches']}/{result['entity_cases']} entity cases; {result['unconfirmed_mutations']} unconfirmed mutations. Results: {output}")
    if (result['intent_matches'] != len(rows) or result['unconfirmed_mutations'] or result['interpretation_failures']
            or result['entity_case_matches'] != result['entity_cases'] or len(rows) != len(cases)):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

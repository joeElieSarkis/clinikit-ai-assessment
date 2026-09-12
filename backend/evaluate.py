"""Reproduce assessment examples with a fixed Beirut clock and write real results."""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .app.clinic import TIMEZONE
from .app.engine import ReceptionEngine
from .app.interpreter import OpenAIInterpreter

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=['demo', 'openai'], default='demo')
    parser.add_argument('--output', default='docs/demo-results.json')
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    interpreter, model = None, None
    if args.provider == 'openai':
        key = os.getenv('OPENAI_API_KEY')
        if not key:
            raise SystemExit('Set OPENAI_API_KEY in .env before running a live evaluation.')
        model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
        interpreter = OpenAIInterpreter(key, model)
    reference = datetime(2026, 9, 12, 11, 0, tzinfo=TIMEZONE)
    engine = ReceptionEngine(interpreter, clock=lambda: reference, mode=args.provider, model=model)
    rows = []
    for message, expected in CASES:
        session = engine.create_session()
        before = [a.model_dump() for a in session.appointments]
        engine.chat(session, message)
        decision = session.messages[-1].decision
        mutations = before != [a.model_dump() for a in session.appointments]
        rows.append({'message': message, 'expected_intent': expected, 'observed_intent': decision.intent,
                     'intent_match': decision.intent == expected, 'appointments_changed': mutations,
                     'proposal_present': session.pending is not None, 'decision': decision.model_dump(),
                     'response': session.messages[-1].content})
    result = {'provider': args.provider, 'model': model, 'reference_time': reference.isoformat(),
              'evaluated_at': datetime.now(TIMEZONE).isoformat(),
              'scope': 'Ten supplied examples, each in a fresh fictional session. This is a smoke evaluation, not a general accuracy benchmark.',
              'intent_matches': sum(row['intent_match'] for row in rows), 'cases': len(rows),
              'unconfirmed_mutations': sum(row['appointments_changed'] for row in rows), 'results': rows}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"{result['intent_matches']}/{len(rows)} intent matches; {result['unconfirmed_mutations']} unconfirmed mutations. Results: {output}")
    if result['intent_matches'] != len(rows) or result['unconfirmed_mutations']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

from copy import deepcopy
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.gemini import GeminiInterpreter, GeminiUnavailable
from backend.app.main import create_app
from backend.app.models import Extraction


def model_response(extraction):
    return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {
        'parts': [{'text': extraction.model_dump_json()}],
    }}]})


@pytest.mark.parametrize('doctor', ['Maya', 'Dr. Maya', '“Maya”'])
def test_friday_hold_completes_doctor_and_time_without_more_model_calls(engine, session, doctor):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) > 1:
            raise httpx.ConnectError('provider unavailable', request=request)
        return model_response(Extraction(intent='book', preferred_date='Friday', preferred_time='4', hold=True))

    engine.interpreter = GeminiInterpreter('test-key', client=httpx.Client(transport=httpx.MockTransport(handler)))
    before = deepcopy(session.appointments)
    engine.chat(session, '“Book me Friday at 4 but don’t confirm anything yet.')
    assert 'Which doctor' in session.messages[-1].content
    engine.chat(session, doctor)
    assert 'am or' in session.messages[-1].content
    assert session.draft.doctor == 'Maya' and session.draft.hold
    assert session.messages[-1].decision.source == 'local routing policy'
    engine.chat(session, '4 pm')
    assert 'isn’t available' in session.messages[-1].content
    assert session.slots and session.draft.hold
    assert [slot.time for slot in session.slots[:2]] == ['15:00', '17:00']
    slot = next(slot for slot in session.slots if slot.time == '17:00')
    engine.chat(session, f'Use Dr. {slot.doctor} on {slot.date} at {slot.time}')
    assert session.pending is None and session.draft.hold
    assert session.appointments == before and len(calls) == 1


def test_retry_restores_validated_details_but_never_old_confirmation(engine, session):
    engine.chat(session, 'Book Dr. George Monday at 4 pm')
    old_token = session.pending.id
    before = deepcopy(session.appointments)
    engine.interpreter = Mock(source='test provider')
    engine.interpreter.extract.side_effect = GeminiUnavailable('timeout')
    engine.chat(session, 'Actually, make it Wednesday')
    assert session.draft is None and session.pending is None
    assert session.retry_context.draft.doctor == 'George'
    assert 'kept your earlier appointment details' in session.messages[-1].content
    with pytest.raises(ValueError, match='no longer current'):
        engine.confirm(session, old_token)
    engine.interpreter.extract.side_effect = None
    engine.interpreter.extract.return_value = Extraction(intent='book', preferred_date='Wednesday')
    engine.chat(session, 'Actually, make it Wednesday')
    assert session.retry_context is None
    assert session.pending.doctor == 'George' and session.pending.time == '16:00'
    assert session.pending.date == '2026-09-16' and session.pending.id != old_token
    assert session.appointments == before


def test_a_new_request_cannot_inherit_the_suspended_draft(engine, session):
    engine.chat(session, 'Book Dr. George Monday at 4 pm')
    engine.interpreter = Mock(source='test provider')
    engine.interpreter.extract.side_effect = GeminiUnavailable('connection_error')
    engine.chat(session, 'Actually, make it Wednesday')
    engine.interpreter.extract.side_effect = None
    engine.interpreter.extract.return_value = Extraction(intent='book', doctor='Maya')
    engine.chat(session, 'Start a different booking with Maya')
    assert session.draft.doctor == 'Maya' and session.draft.preferred_date is None
    assert session.draft.preferred_time is None and session.pending is None
    assert session.retry_context is None


def test_retry_keeps_a_hold_even_if_the_model_misses_it(engine, session):
    engine.chat(session, 'Book Dr. George Monday at 4 pm')
    engine.interpreter = Mock(source='test provider')
    engine.interpreter.extract.side_effect = GeminiUnavailable('provider_error', http_status=503)
    engine.chat(session, 'Maybe Wednesday, but do not confirm yet')
    assert session.retry_context.draft.hold
    engine.interpreter.extract.side_effect = None
    engine.interpreter.extract.return_value = Extraction(intent='book', preferred_date='Wednesday')
    engine.chat(session, 'Maybe Wednesday, but do not confirm yet')
    assert session.draft.hold and session.pending is None and session.slots


def test_a_provider_retry_needs_a_new_api_request_id(engine):
    client = TestClient(create_app(engine))
    session = client.post('/api/sessions').json()
    url = f"/api/sessions/{session['id']}/messages"
    engine.interpreter = Mock(source='test provider')
    engine.interpreter.extract.side_effect = GeminiUnavailable('timeout')
    payload = {'message': 'Please arrange a visit with Maya', 'request_id': str(uuid4())}
    first = client.post(url, json=payload).json()
    assert first['messages'][-1]['decision']['action'] == 'service_unavailable'
    engine.interpreter.extract.side_effect = None
    engine.interpreter.extract.return_value = Extraction(intent='book', doctor='Maya')
    replay = client.post(url, json=payload).json()
    assert len(replay['messages']) == len(first['messages'])
    assert engine.interpreter.extract.call_count == 1
    payload['request_id'] = str(uuid4())
    retried = client.post(url, json=payload).json()
    assert 'Which day' in retried['messages'][-1]['content']
    assert engine.interpreter.extract.call_count == 2


@pytest.mark.parametrize('code,expected', [
    ('timeout', 'took too long'), ('connection_error', 'connect'),
    ('provider_error', 'couldn’t process'), ('invalid_output', 'couldn’t read'),
    ('configuration', 'API key'), ('model_unavailable', 'model'),
])
def test_errors_explain_the_failure_category(engine, session, code, expected):
    engine.interpreter = Mock(source='test provider')
    engine.interpreter.extract.side_effect = GeminiUnavailable(code, http_status=503)
    engine.chat(session, 'Could I see George tomorrow?')
    assert expected in session.messages[-1].content
    assert 'language service is unavailable' not in session.messages[-1].content
    assert 'Provider HTTP status: 503.' in session.messages[-1].decision.checks
    assert session.pending is None and len(session.appointments) == 1


def test_a_single_accidental_character_asks_for_clarification_without_ai(engine, session):
    engine.interpreter = Mock(source='offline provider')
    engine.chat(session, 'x')
    engine.interpreter.extract.assert_not_called()
    assert session.messages[-1].decision.action == 'ask_for_more_information'


def test_compound_doctor_message_still_requires_the_interpreter(engine, session):
    engine.chat(session, 'Book me Friday at 4 but don’t confirm yet')
    engine.interpreter = Mock(source='test provider')
    engine.interpreter.extract.return_value = Extraction(intent='book', doctor='Maya', preferred_date='Monday', hold=True)
    engine.chat(session, 'Maya, but maybe change Friday to Monday')
    engine.interpreter.extract.assert_called_once()
    assert session.draft.preferred_date == 'Monday' and session.pending is None

import json
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.gemini import GeminiInterpreter, GeminiUnavailable
from backend.app.main import create_app
from backend.app.models import Extraction, Message
from backend.app.providers import create_interpreter


def candidate(extraction=None, finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"parts": [
        {"text": (extraction or Extraction(intent="hours")).model_dump_json()}
    ]}}]}


def adapter_for(handler, clock=lambda: 100.0):
    return GeminiInterpreter("test-key-never-transmitted", client=httpx.Client(
        transport=httpx.MockTransport(handler)), clock=clock)


def test_gemini_request_keeps_credentials_and_instructions_out_of_patient_data(engine):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=candidate(Extraction(intent="book", doctor="George", hold=True)))

    adapter = adapter_for(handler)
    history = [Message(role="user", content=f"message {i}") for i in range(12)]
    result = adapter.extract("Book Dr. George, but wait", Extraction(intent="book"), history, engine.clock())
    request = requests[0]
    body = json.loads(request.content)
    context = json.loads(body["contents"][0]["parts"][0]["text"])
    assert request.url.host == "generativelanguage.googleapis.com"
    assert request.headers['x-goog-api-key'] == 'test-key-never-transmitted'
    assert 'test-key-never-transmitted' not in str(request.url)
    assert 'test-key-never-transmitted' not in request.content.decode()
    assert context['current_message'] == 'Book Dr. George, but wait'
    assert len(context['recent_conversation']) == 8
    assert context['recent_conversation'][0]['content'] == 'message 4'
    assert 'TRUST BOUNDARY' in body['systemInstruction']['parts'][0]['text']
    schema = body['generationConfig']['responseJsonSchema']
    assert set(schema['required']) == set(Extraction.model_fields)
    assert schema['additionalProperties'] is False
    assert body['generationConfig']['responseMimeType'] == 'application/json'
    assert 'tools' not in body
    assert result.doctor == 'George' and result.hold


@pytest.mark.parametrize('body', [
    {},
    {'promptFeedback': {'blockReason': 'SAFETY'}},
    candidate(finish='MAX_TOKENS'),
    candidate(finish='SAFETY'),
    {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 'not json'}]}}]},
    {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{"intent":"book"}'}]}}]},
    {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'functionCall': {'name': 'book'}}]}}]},
])
def test_gemini_rejects_blocked_incomplete_or_unstructured_responses(engine, body):
    adapter = adapter_for(lambda request: httpx.Response(200, json=body))
    with pytest.raises(GeminiUnavailable, match='invalid_output'):
        adapter.extract('Book a visit', None, [], engine.clock())


def test_gemini_validates_types_and_unknown_fields_locally(engine):
    invalid = Extraction(intent='book').model_dump() | {'hold': 'false', 'authorized': True}
    body = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(invalid)}]}}]}
    adapter = adapter_for(lambda request: httpx.Response(200, json=body))
    with pytest.raises(GeminiUnavailable, match='invalid_output'):
        adapter.extract('Book a visit', None, [], engine.clock())


@pytest.mark.parametrize('status,code', [(401, 'configuration'), (403, 'configuration'),
                                        (404, 'model_unavailable'), (500, 'unavailable'), (302, 'unavailable')])
def test_gemini_http_errors_are_sanitized_without_retries(engine, status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text='secret provider detail', headers={'Location': 'https://example.com'})

    adapter = adapter_for(handler)
    with pytest.raises(GeminiUnavailable, match=code) as error:
        adapter.extract('Book a visit', None, [], engine.clock())
    assert 'secret' not in str(error.value)
    assert len(calls) == 1


def test_gemini_quota_error_invalidates_proposal_and_cools_down(engine, session):
    engine.chat(session, 'Book Dr. George Monday at 4 pm')
    assert session.pending
    before = deepcopy(session.appointments)
    calls, clock = [], [100.0]

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={'error': {'message': 'private provider details'}})

    engine.interpreter = adapter_for(handler, clock=lambda: clock[0])
    engine.chat(session, 'Actually, make it Wednesday')
    assert session.pending is None and session.draft is None
    assert session.appointments == before
    assert session.messages[-1].decision.action == 'service_unavailable'
    assert 'quota' in session.messages[-1].content
    assert 'private' not in session.messages[-1].content
    clock[0] += 59
    engine.chat(session, 'Book Dr. George Monday at 4 pm')
    assert len(calls) == 1
    clock[0] += 2
    engine.chat(session, 'Book Dr. George Monday at 4 pm')
    assert len(calls) == 2


def test_gemini_timeout_does_not_fall_back_to_rules(engine, session):
    def handler(request):
        raise httpx.ReadTimeout('private details', request=request)

    engine.interpreter = adapter_for(handler)
    engine.chat(session, 'Book Dr. George Monday at 4 pm')
    assert session.pending is None
    assert session.messages[-1].decision.action == 'service_unavailable'


def test_daily_quota_is_not_reported_as_a_one_minute_wait(engine, session):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={'error': {'details': [
            {'violations': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier',
                             'quotaValue': '20'}]}
        ]}})

    engine.interpreter = adapter_for(handler)
    before = deepcopy(session.appointments)
    for _ in range(2):
        engine.chat(session, 'Book Dr. George Monday at 4 pm')
        assert 'daily' in session.messages[-1].content.lower()
        assert 'wait a minute' not in session.messages[-1].content.lower()
        assert session.pending is None and session.appointments == before
    assert len(calls) == 1


def test_gemini_cannot_bypass_hold_or_confirmation(engine, session):
    clock = [100.0]
    interpretation = Extraction(intent='book', doctor='George', preferred_date='Monday', preferred_time='4 pm')
    engine.interpreter = adapter_for(lambda request: httpx.Response(200, json=candidate(interpretation)),
                                     clock=lambda: clock[0])
    engine.chat(session, "Book Dr. George Monday at 4 pm but don't book yet")
    assert session.pending is None and len(session.appointments) == 1
    clock[0] += 3
    engine.chat(session, 'I am ready to book Dr. George Monday at 4 pm')
    assert session.pending is not None and len(session.appointments) == 1
    engine.confirm(session, session.pending.id)
    assert len(session.appointments) == 2


def test_live_provider_is_explicit_in_health_and_session(engine, monkeypatch):
    monkeypatch.setenv('AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key-never-transmitted')
    adapter = adapter_for(lambda request: httpx.Response(200, json=candidate()))
    monkeypatch.setattr('backend.app.providers.GeminiInterpreter', lambda *args: adapter)
    client = TestClient(create_app())
    assert client.get('/api/health').json()['mode'] == 'gemini'
    session = client.post('/api/sessions').json()
    assert session['mode'] == 'gemini'
    assert session['model'] == 'gemini-3.6-flash'
    response = client.post(f"/api/sessions/{session['id']}/messages",
                           json={'message': 'When do you close?', 'request_id': 'gemini-integration-1'})
    assert response.json()['messages'][-1]['decision']['source'] == 'gemini structured output'
    assert 'test-key-never-transmitted' not in response.text


def test_missing_key_cannot_silently_start_the_offline_demo(monkeypatch):
    monkeypatch.delenv('AI_PROVIDER', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    with pytest.raises(RuntimeError, match='GEMINI_API_KEY'):
        create_app()
    assert create_interpreter('demo').source == 'demo rules'

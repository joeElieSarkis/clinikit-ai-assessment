from copy import deepcopy
from datetime import datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.clinic import TIMEZONE
from backend.app.engine import ReceptionEngine
from backend.app.main import create_app
from backend.app.models import Appointment, Extraction
from backend.evaluate import CASES


@pytest.fixture
def monday_engine():
    return ReceptionEngine(clock=lambda: datetime(2026, 9, 14, 14, 0, tzinfo=TIMEZONE))


def test_existing_weekday_is_matched_against_visits_on_a_monday(monday_engine):
    session = monday_engine.create_session()
    before = deepcopy(session.appointments)
    assert before[0].date == '2026-09-21'
    monday_engine.chat(session, '“Move my appointment from Monday to Wednesday.”')
    assert session.messages[-1].decision.action == 'check_availability'
    assert session.slots and all(slot.date == '2026-09-16' for slot in session.slots)
    assert session.draft.appointment_id == 'CK-1042'
    assert session.appointments == before and session.pending is None


@pytest.mark.parametrize('reference', ['CK-1042', 'CK-1042.', '“ck-1042.”'])
def test_reference_replaces_stale_date_without_losing_destination(monday_engine, reference):
    session = monday_engine.create_session()
    before = deepcopy(session.appointments)
    monday_engine.chat(session, 'Move my appointment from 2026-09-14 to Wednesday.')
    assert not session.slots and session.pending is None
    # A literal reference should remain usable when the model is unavailable.
    provider = monday_engine.interpreter
    monday_engine.interpreter = Mock(source='unavailable provider')
    monday_engine.interpreter.extract.side_effect = TimeoutError()
    monday_engine.chat(session, reference)
    monday_engine.interpreter.extract.assert_not_called()
    assert session.messages[-1].decision.source == 'local routing policy'
    assert session.slots and session.draft.preferred_date.lower() == 'wednesday'
    assert session.draft.original_date is None
    assert session.appointments == before and session.pending is None
    monday_engine.interpreter = provider
    monday_engine.chat(session, 'Use Dr. Karim on 2026-09-16 at 10:30')
    assert session.pending.kind == 'reschedule'
    assert session.pending.appointment_id == 'CK-1042'
    assert session.appointments == before
    monday_engine.confirm(session, session.pending.id)
    assert session.appointments[0].date == '2026-09-16'
    assert session.appointments[0].time == '10:30'
    assert len(session.appointments) == 1


def test_multiple_mondays_require_a_reference(monday_engine):
    session = monday_engine.create_session()
    session.appointments.append(Appointment(id='CK-2000', doctor='Maya', date='2026-09-28', time='12:00'))
    before = deepcopy(session.appointments)
    monday_engine.chat(session, 'Move my appointment from Monday to Wednesday.')
    assert session.pending is None and not session.slots
    monday_engine.chat(session, 'CK-2000')
    assert session.slots and all(slot.doctor == 'Maya' for slot in session.slots)
    assert session.draft.appointment_id == 'CK-2000'
    assert session.appointments == before


def test_reference_corrects_cancellation_search_but_preserves_hold(monday_engine):
    session = monday_engine.create_session()
    before = deepcopy(session.appointments)
    monday_engine.chat(session, "Don't cancel Dr. George on 2026-09-14 at 9 am yet")
    monday_engine.chat(session, 'CK-1042.')
    assert session.messages[-1].decision.action == 'wait_for_patient'
    assert session.draft.doctor == 'Karim' and session.draft.hold
    assert session.draft.preferred_date is None and session.draft.preferred_time is None
    assert session.appointments == before and session.pending is None
    monday_engine.chat(session, 'I am ready to cancel')
    assert session.pending.kind == 'cancel'
    assert session.pending.appointment_id == 'CK-1042'
    assert session.appointments == before


@pytest.mark.parametrize('reference', ['CK-9999', 'CK-2000'])
def test_reference_must_belong_to_an_active_visit(monday_engine, reference):
    session = monday_engine.create_session()
    session.appointments.append(Appointment(id='CK-2000', doctor='Maya', date='2026-09-28', time='12:00', status='cancelled'))
    before = deepcopy(session.appointments)
    monday_engine.chat(session, 'Move my appointment from Monday to Wednesday.')
    monday_engine.chat(session, reference)
    assert session.pending is None and not session.slots
    assert session.appointments == before
    # Correcting an invalid reference must not keep its failed search state.
    monday_engine.chat(session, 'CK-1042')
    assert session.slots and session.draft.appointment_id == 'CK-1042'


def test_explicit_weekday_qualifier_is_not_ignored(monday_engine):
    session = monday_engine.create_session()
    monday_engine.chat(session, 'Move my appointment from this Monday to Wednesday.')
    assert not session.slots and session.pending is None
    monday_engine.chat(session, 'CK-1042')
    assert session.slots


@pytest.mark.parametrize('greeting', ['hi', 'Hi!', 'hello there', 'Hey', 'Good morning.'])
def test_greeting_is_friendly_and_does_not_call_the_provider(engine, session, greeting):
    before = deepcopy(session.appointments)
    engine.interpreter = Mock(source='unavailable provider')
    engine.interpreter.extract.side_effect = TimeoutError()
    engine.chat(session, greeting)
    assert session.messages[-1].content.startswith('Hi!')
    assert session.messages[-1].decision.action == 'greet'
    engine.interpreter.extract.assert_not_called()
    assert session.appointments == before and session.pending is None


def test_greeting_preserves_draft_but_invalidates_confirmation(engine, session):
    engine.chat(session, 'Book Dr. George Monday at 4 pm')
    token = session.pending.id
    before = session.draft.model_copy(deep=True)
    engine.chat(session, 'hi')
    assert session.draft == before
    with pytest.raises(ValueError, match='no longer current'):
        engine.confirm(session, token)
    engine.chat(session, '5 pm')
    assert session.pending.time == '17:00'


def test_greeting_with_a_request_still_reaches_the_interpreter(engine, session):
    engine.interpreter = Mock(source='test provider')
    engine.interpreter.extract.return_value = Extraction(intent='cancel', doctor='Karim')
    engine.chat(session, 'Hi, please cancel my visit with Karim')
    engine.interpreter.extract.assert_called_once()
    assert session.pending.kind == 'cancel'
    assert session.appointments[0].status == 'confirmed'


@pytest.mark.parametrize('answer,expected_id', [
    ('Karim', 'CK-1042'), ('Dr. Krim', 'CK-1042'), ('Karimm', 'CK-1042'),
    ('the first one', 'CK-1042'), ('10 am', 'CK-1042'), ('the morning one', 'CK-1042'),
    ('Maya', 'CK-2000'), ('the second one', 'CK-2000'), ('the one at 3 pm', 'CK-2000'),
])
def test_two_visits_can_be_selected_without_copying_references(monday_engine, answer, expected_id):
    session = monday_engine.create_session()
    session.appointments.append(Appointment(id='CK-2000', doctor='Maya', date='2026-09-21', time='15:00'))
    before = deepcopy(session.appointments)
    monday_engine.chat(session, 'Move my appointment from Monday to Wednesday.')
    question = session.messages[-1]
    assert question.decision.action == 'choose_appointment'
    assert 'Karim' in question.content and 'Maya' in question.content
    assert '10:00 AM' in question.content and '3:00 PM' in question.content
    assert 'appointment reference' not in question.content
    monday_engine.interpreter = Mock(source='unavailable provider')
    monday_engine.interpreter.extract.side_effect = TimeoutError()
    monday_engine.chat(session, answer)
    monday_engine.interpreter.extract.assert_not_called()
    assert session.draft.appointment_id == expected_id
    assert session.draft.preferred_date.lower() == 'wednesday'
    assert session.draft.preferred_time is None
    assert session.slots and all(slot.date == '2026-09-16' for slot in session.slots)
    assert session.appointments == before and session.pending is None


def test_same_doctor_needs_time_and_keeps_the_destination(monday_engine):
    session = monday_engine.create_session()
    session.appointments.append(Appointment(id='CK-2000', doctor='Karim', date='2026-09-21', time='14:30'))
    monday_engine.chat(session, 'Move my appointment from Monday to Wednesday at 11:30 am.')
    monday_engine.chat(session, 'Karim')
    assert session.pending is None and len(session.appointment_choices) == 2
    monday_engine.chat(session, 'the one at 2:30 pm')
    assert session.pending.appointment_id == 'CK-2000'
    assert session.pending.date == '2026-09-16' and session.pending.time == '11:30'
    assert session.appointments[1].time == '14:30'


def test_ambiguous_time_selection_asks_am_pm_without_losing_the_move(monday_engine):
    session = monday_engine.create_session()
    session.appointments.append(Appointment(id='CK-2000', doctor='Maya', date='2026-09-21', time='15:00'))
    monday_engine.chat(session, 'Move my appointment from Monday to Wednesday.')
    monday_engine.chat(session, '10')
    assert 'am or' in session.messages[-1].content
    assert session.draft.preferred_date.lower() == 'wednesday'
    assert len(session.appointment_choices) == 2
    monday_engine.chat(session, '10 am')
    assert session.draft.appointment_id == 'CK-1042' and session.slots


def test_selection_without_identifying_details_does_not_pick_a_visit(monday_engine):
    session = monday_engine.create_session()
    monday_engine.chat(session, 'Move my appointment from 2026-09-14 to Wednesday.')
    monday_engine.interpreter = Mock(source='test provider')
    monday_engine.interpreter.extract.return_value = Extraction(intent='reschedule')
    monday_engine.chat(session, 'not sure which you mean')
    assert session.messages[-1].decision.action == 'choose_appointment'
    assert not session.slots and session.pending is None
    assert session.draft.preferred_date.lower() == 'wednesday'


def test_provider_can_interpret_freeform_selection_without_replacing_destination(monday_engine):
    session = monday_engine.create_session()
    session.appointments.append(Appointment(id='CK-2000', doctor='Maya', date='2026-09-21', time='15:00'))
    monday_engine.chat(session, 'Move my appointment from Monday to Wednesday at 11:30 am.')
    monday_engine.interpreter = Mock(source='test provider')
    monday_engine.interpreter.extract.return_value = Extraction(intent='reschedule', doctor='Karim', preferred_time='10 am')
    monday_engine.chat(session, "It's the one with Karim, around ten in the morning")
    monday_engine.interpreter.extract.assert_called_once()
    assert session.pending.appointment_id == 'CK-1042'
    assert session.pending.time == '11:30' and session.pending.date == '2026-09-16'


def test_cancellation_can_select_a_doctor_from_multiple_monday_visits(monday_engine):
    session = monday_engine.create_session()
    session.appointments.append(Appointment(id='CK-2000', doctor='Maya', date='2026-09-21', time='15:00'))
    monday_engine.chat(session, 'Cancel my Monday appointment')
    assert session.messages[-1].decision.action == 'choose_appointment'
    monday_engine.chat(session, 'Maya')
    assert session.pending.kind == 'cancel' and session.pending.appointment_id == 'CK-2000'
    assert all(visit.status == 'confirmed' for visit in session.appointments)


def test_a_new_topic_does_not_select_an_existing_visit(monday_engine):
    session = monday_engine.create_session()
    session.appointments.append(Appointment(id='CK-2000', doctor='Maya', date='2026-09-21', time='15:00'))
    monday_engine.chat(session, 'Move my appointment from Monday to Wednesday.')
    monday_engine.chat(session, 'What time does the clinic close?')
    assert session.messages[-1].decision.action == 'get_clinic_hours'
    assert not session.appointment_choices and session.draft is None


@pytest.mark.parametrize('reply', ['okay', 'hi'])
def test_small_talk_does_not_forget_the_appointment_choices(monday_engine, reply):
    session = monday_engine.create_session()
    session.appointments.append(Appointment(id='CK-2000', doctor='Maya', date='2026-09-21', time='15:00'))
    monday_engine.chat(session, 'Move my appointment from Monday to Wednesday.')
    monday_engine.chat(session, reply)
    assert len(session.appointment_choices) == 2
    monday_engine.chat(session, 'Maya')
    assert session.draft.appointment_id == 'CK-2000' and session.slots


def test_a_hold_during_clarification_survives_selecting_the_visit(monday_engine):
    session = monday_engine.create_session()
    session.appointments.append(Appointment(id='CK-2000', doctor='Maya', date='2026-09-21', time='15:00'))
    monday_engine.chat(session, 'Move my appointment from Monday to Wednesday at 3 pm.')
    monday_engine.chat(session, "Don't do anything yet")
    assert session.draft.hold
    monday_engine.chat(session, 'Maya')
    assert session.draft.appointment_id == 'CK-2000'
    assert session.pending is None and session.appointments[1].date == '2026-09-21'


@pytest.mark.parametrize('example,action', list(zip(CASES, [
    'check_availability', 'check_availability', 'ask_for_confirmation', 'get_clinic_hours',
    'ask_for_more_information', 'ask_for_more_information', 'ask_for_more_information',
    'ask_for_more_information', 'handoff_to_human', 'ask_for_more_information',
])))
def test_assessment_examples_through_api_on_monday(monday_engine, example, action):
    client = TestClient(create_app(monday_engine))
    session = client.post('/api/sessions').json()
    response = client.post(f"/api/sessions/{session['id']}/messages", json={
        'message': example[0], 'request_id': str(uuid4()),
    })
    assert response.status_code == 200
    result = response.json()
    assert result['messages'][-1]['decision']['intent'] == example[1]
    assert result['messages'][-1]['decision']['action'] == action
    assert result['appointments'] == session['appointments']


def test_vague_booking_collects_missing_information_with_typos(monday_engine):
    session = monday_engine.create_session()
    monday_engine.chat(session, 'I want to see my doctor again for the same problem.')
    assert 'Which doctor' in session.messages[-1].content
    monday_engine.chat(session, 'dr georg')
    assert 'Which day' in session.messages[-1].content
    monday_engine.chat(session, 'tmrw')
    assert session.slots and session.pending is None
    monday_engine.chat(session, 'at 4')
    assert 'am or' in session.messages[-1].content
    monday_engine.chat(session, '4 pm')
    assert session.pending.doctor == 'George'
    assert session.pending.date == '2026-09-15' and session.pending.time == '16:00'
    assert len(session.appointments) == 1


def test_friday_booking_keeps_hold_through_missing_details(monday_engine):
    session = monday_engine.create_session()
    monday_engine.chat(session, 'Book me Friday at 4 but don’t confirm anything yet.')
    assert 'Which doctor' in session.messages[-1].content and session.draft.hold
    monday_engine.chat(session, 'Dr. George')
    assert 'am or' in session.messages[-1].content and session.draft.hold
    monday_engine.chat(session, '4 pm')
    assert session.pending is None and session.slots and session.draft.hold
    monday_engine.chat(session, 'I am ready to book Friday at 4 pm')
    assert session.pending.doctor == 'George' and session.pending.date == '2026-09-18'
    assert len(session.appointments) == 1

from unittest.mock import Mock

import pytest

from backend.app.interpreter import OpenAIInterpreter
from backend.app.models import Extraction


@pytest.mark.parametrize("message", ["Book Dr. George on 03/04 at 4 pm", "Book Dr. George Monday between 3 and 4 pm"])
def test_ambiguous_date_or_range_cannot_silently_become_exact(engine, session, message):
    engine.chat(session, message)
    assert session.pending is None


def test_cancel_time_must_match_actual_appointment(engine, session):
    engine.chat(session, "Cancel Dr. Karim Monday at 9 am")
    assert session.pending is None


def test_handoff_is_available_when_model_is_offline(engine, session):
    engine.interpreter = Mock(source="offline")
    engine.interpreter.extract.side_effect = TimeoutError()
    engine.chat(session, "I want to speak with a human")
    assert session.handoffs == 1
    assert session.messages[-1].decision.action == "handoff_to_human"
    engine.interpreter.extract.assert_not_called()


def test_openai_adapter_uses_validated_schema_and_no_storage(engine):
    adapter = OpenAIInterpreter("test-key-never-transmitted", "gpt-4.1-mini")
    adapter.client = Mock()
    adapter.client.responses.parse.return_value.output_parsed = Extraction(intent="hours")
    result = adapter.extract("What are your hours?", None, [], engine.clock())
    args = adapter.client.responses.parse.call_args.kwargs
    assert result.intent == "hours"
    assert args['text_format'] is Extraction
    assert args['store'] is False
    assert args['input'][0]['role'] == 'system'
    assert args['input'][1]['role'] == 'user'
    adapter.client.responses.parse.return_value.output_parsed = None
    with pytest.raises(ValueError):
        adapter.extract("Please book a visit", None, [], engine.clock())

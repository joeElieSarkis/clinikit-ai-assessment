from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.clinic import TIMEZONE
from backend.app.engine import ReceptionEngine
from backend.app.main import create_app


@pytest.fixture
def engine():
    return ReceptionEngine(clock=lambda: datetime(2026, 9, 12, 11, 0, tzinfo=TIMEZONE))


@pytest.fixture
def session(engine):
    return engine.create_session()


@pytest.fixture
def client(engine):
    return TestClient(create_app(engine))

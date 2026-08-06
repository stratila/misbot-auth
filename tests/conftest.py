import pytest
from fastapi.testclient import TestClient

from misbot_auth_server.server import app


@pytest.fixture
def client():
    return TestClient(app)

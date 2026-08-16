import pytest
from pydantic import ValidationError

from models.auth import AuthRequest


def test_auth_request_accepts_valid_credentials():
    request = AuthRequest(email="reader@example.com", password="password")
    assert str(request.email) == "reader@example.com"


def test_auth_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        AuthRequest(email="not-an-email", password="password")

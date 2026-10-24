import pytest
from pydantic import ValidationError

from models.auth import SignupRequest, LoginRequest


def test_auth_request_accepts_valid_credentials():
    request = SignupRequest(email="reader@example.com", username="reader", password="password")
    assert str(request.email) == "reader@example.com"


def test_auth_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        SignupRequest(email="not-an-email", username="reader", password="password")


@pytest.mark.parametrize("username", ["ab", "a" * 21, "bad name", "bad%name"])
def test_signup_rejects_invalid_usernames(username):
    with pytest.raises(ValidationError):
        SignupRequest(email="reader@example.com", username=username, password="password")


def test_login_accepts_username_identifier():
    assert LoginRequest(identifier="reader_one", password="password").identifier == "reader_one"

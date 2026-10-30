from uuid import uuid4

import jwt
import pytest
from app.auth.tokens import decode_access_token, hash_password, issue_access_token, verify_password

KEY = "test-only-" + "a" * 32


def test_passwords_are_hashed_and_verified():
    encoded = hash_password("a suitably long password")
    assert encoded.startswith("$argon2id$")
    assert verify_password("a suitably long password", encoded)
    assert not verify_password("incorrect password", encoded)
    assert not verify_password("incorrect password", "invalid hash")
    with pytest.raises(ValueError):
        hash_password("too short")


def test_access_token_validates_signature_audience_and_identity():
    user, session = uuid4(), uuid4()
    token = issue_access_token(user, session, key=KEY, issuer="test", audience="client")
    assert decode_access_token(token, key=KEY, issuer="test", audience="client") == (user, session)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, key=KEY, issuer="test", audience="other")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, key="b" * 40, issuer="test", audience="client")
    with pytest.raises(ValueError):
        issue_access_token(user, session, key=KEY, issuer="test", audience="client", minutes=61)


def test_local_key_generation_does_not_overwrite_existing_key(tmp_path):
    from dotenv import dotenv_values
    from app.cli import init_local_key
    path = tmp_path / '.env'
    path.write_text('JWT_SIGNING_KEY=\n', encoding='utf-8')
    init_local_key(path)
    first = dotenv_values(path)['JWT_SIGNING_KEY']
    assert len(first) >= 32
    init_local_key(path)
    assert dotenv_values(path)['JWT_SIGNING_KEY'] == first

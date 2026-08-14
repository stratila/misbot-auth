"""Test bootstrap, loaded before anything under ``tests/``.

The application builds its settings at import time, so by the time a fixture
could run, ``misbot_auth_server.settings`` has already been imported and has
already failed. Configuration therefore has to be in place before the first
import -- which is what this module, sitting in the rootdir, is for.

Its job is to let the suite run on a machine that has no ``secrets/`` directory
and no ``.env.dev``: both are gitignored, so CI and the test container have
neither. Anything already configured is left alone, so a developer's real key
and settings still win.
"""

import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SECRETS_DIR_ENV_VAR = "MISBOT_AUTH_SECRETS_DIR"
PRIVATE_KEY_ENV_VAR = "MISBOT_AUTH_JWT__PRIVATE_KEY"
PRIVATE_KEY_SECRET_FILE = "misbot_auth_jwt-private_key"

# Small enough to keep generation off the critical path, and only ever used to
# sign tokens that live inside a single test session.
TEST_KEY_SIZE = 2048


def _generate_signing_key() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=TEST_KEY_SIZE)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def _real_key_is_available() -> bool:
    from pathlib import Path

    if PRIVATE_KEY_ENV_VAR in os.environ:
        return True

    secrets_dir = Path(os.environ.get(SECRETS_DIR_ENV_VAR, "secrets"))
    return (secrets_dir / PRIVATE_KEY_SECRET_FILE).is_file()


if not _real_key_is_available():
    os.environ[PRIVATE_KEY_ENV_VAR] = _generate_signing_key()

# `issuer` and `audience` are required and normally come from the gitignored
# .env.dev, so they need stand-ins too. `setdefault` keeps a configured value.
os.environ.setdefault("MISBOT_AUTH_JWT__ISSUER", "http://localhost:8000")
os.environ.setdefault("MISBOT_AUTH_JWT__AUDIENCE", "http://localhost:8001")

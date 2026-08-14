import os
import subprocess
import sys

# Importing the database layer must not construct the application Settings,
# which requires the JWT signing key. Migrations and client provisioning have
# nothing to do with signing tokens, so they must not need the key to run --
# that is what lets a container migrate before the key is mounted.
PROBE = """
import sys
import misbot_auth_server.db.clients  # noqa: F401
import misbot_auth_server.cli  # noqa: F401

assert "misbot_auth_server.settings" not in sys.modules, (
    "the database layer pulled in the application settings"
)
"""


def test_the_database_layer_does_not_need_the_signing_key():
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        # Point the secrets directory somewhere empty: if anything on this
        # import path did construct Settings, it would fail here rather than
        # quietly succeeding off the developer's local key file.
        env={**os.environ, "MISBOT_AUTH_SECRETS_DIR": "/nonexistent"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

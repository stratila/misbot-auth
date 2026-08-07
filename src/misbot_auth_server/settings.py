import os
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, NestedSecretsSettingsSource, SettingsConfigDict

from misbot_auth_server.db.settings import DatabaseSettings

SECRETS_DIR_ENV_VAR = "MISBOT_AUTH_SECRETS_DIR"
DEFAULT_SECRETS_DIR = "secrets"


def secrets_dir() -> Path:
    """Where file-backed secrets live.

    ``secrets_dir`` is class-level configuration rather than a field, so the
    normal settings machinery cannot read it from the environment. It is
    resolved here and passed to the constructor as ``_secrets_dir`` instead.
    The path is made absolute so it does not depend on the working directory:
    ``./secrets`` for local development, a mount point in a container.
    """
    return Path(os.environ.get(SECRETS_DIR_ENV_VAR, DEFAULT_SECRETS_DIR)).expanduser().resolve()


class JWTSettings(BaseSettings):
    algorithm: str = "RS256"
    access_token_expire_minutes: int = 30
    issuer: str = Field(..., description="Authentication server url")
    audience: str = Field(..., description="Resource server url")
    private_key: SecretStr = Field(..., description="PEM-formatted private key")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # .env has priority over .dev.env
        env_file=(".env.dev", ".env"),
        env_prefix="MISBOT_AUTH_",
        env_nested_delimiter="__",
        # `secrets_dir` is intentionally absent: it is supplied per-instance via
        # `_secrets_dir` so it can be pointed at a container mount.
        secrets_nested_delimiter="-",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            NestedSecretsSettingsSource(file_secret_settings),
        )

    jwt: JWTSettings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)


settings = Settings(_secrets_dir=secrets_dir())


if __name__ == "__main__":
    print(settings.model_dump_json())

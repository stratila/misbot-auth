from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, NestedSecretsSettingsSource, SettingsConfigDict


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
        secrets_dir="secrets",
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


settings = Settings()


if __name__ == "__main__":
    print(settings.model_dump_json())

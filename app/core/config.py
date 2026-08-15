from typing import Literal

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..utils import hash_password


class Settings(BaseSettings):
    app_env: Literal["local", "ci", "prod"] = "local"
    database_url: PostgresDsn
    test_database_url: PostgresDsn
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    api_v1_prefix: str = "/api/v1"

    TEST_PASSWORD: str = "Password12345"
    TEST_PASSWORD_HASH: str = hash_password(TEST_PASSWORD)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def sqlalchemy_url(self) -> str:
        return str(self.database_url)

    @property
    def test_sqlalchemy_url(self) -> str:
        return str(self.test_database_url)


settings = Settings()

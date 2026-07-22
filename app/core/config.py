import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_env = os.getenv("APP_ENV", "")
_env_file = f".env.{_env}" if _env else ".env"

# .env.example의 자리표시자 값 — 실배포에서 그대로 쓰이면 토큰 위조가 가능하므로 거부
_PLACEHOLDER_SECRETS = {"change-me-long-random-string", "changeme", "secret", ""}


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Auth
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # LMS Integration
    LMS_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_key_strong(cls, v: str) -> str:
        # HS256 서명 키가 짧거나 자리표시자면 액세스 토큰 위조 위험 → 부팅 차단
        if len(v) < 32 or v.strip().lower() in _PLACEHOLDER_SECRETS:
            raise ValueError("SECRET_KEY must be a random string of at least 32 characters")
        return v

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return self.DATABASE_URL.replace("mysql+pymysql", "mysql+aiomysql")


settings = Settings()

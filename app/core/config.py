import os

from pydantic_settings import BaseSettings, SettingsConfigDict

_env = os.getenv("APP_ENV", "")
_env_file = f".env.{_env}" if _env else ".env"


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Auth
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    # QR
    QR_CODE_VALIDITY_MINUTES: int

    # LMS Integration
    LMS_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
    )

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return self.DATABASE_URL.replace("mysql+pymysql", "mysql+aiomysql")


settings = Settings()

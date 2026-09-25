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

    # Push (FCM) — 서비스 계정 JSON 키 경로. 비우면 기본 자격증명(GOOGLE_APPLICATION_CREDENTIALS)으로 폴백.
    # 값이 틀리거나 파일이 없어도 부팅은 막지 않는다 — 첫 발송 시점에만 읽히고, 실패해도 그 발송만 실패한다.
    FIREBASE_CREDENTIALS_PATH: str = ""

    # Azure Speech (앱 Recording 텍스트 변환, 2026-09-25) — 키는 서버에만 있고 서버가 파일을 Azure 로 중계한다 (앱에 키·토큰 없음).
    # 비우면 POST /recordings/transcribe 가 503 (변환만 비활성, 부팅·녹음은 정상).
    AZURE_SPEECH_KEY: str = ""
    AZURE_SPEECH_REGION: str = ""

    # --- Check build (GET /app/version-check, 학생 앱 서버와 같은 이름) ---
    # 스토어에 라이브된 버전·빌드. 앱 버전이 이보다 낮으면 강제 업데이트, 같은 버전인데 빌드가 낮으면 스토어 안내.
    # VERSION 빈 값 = 그 플랫폼은 체크 안 함. BUILD 0 = 빌드 비교 안 함.
    APP_ANDROID_VERSION: str = ""
    APP_ANDROID_BUILD: int = 0
    APP_IOS_VERSION: str = ""
    APP_IOS_BUILD: int = 0

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

    @field_validator("APP_ANDROID_VERSION", "APP_IOS_VERSION")
    @classmethod
    def _semver_like(cls, v: str) -> str:
        # 오타("1.4", "v1.4.0")가 조용히 "강제 없음"으로 흘러가지 않도록 부팅 시 검증 (빈 값은 허용 = 체크 안 함)
        v = v.strip()
        if v and not (len(v.split(".")) == 3 and all(p.isdigit() for p in v.split("."))):
            raise ValueError(f"expected MAJOR.MINOR.PATCH or empty, got {v!r}")
        return v

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return self.DATABASE_URL.replace("mysql+pymysql", "mysql+aiomysql")


settings = Settings()

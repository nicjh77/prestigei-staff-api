import os
import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.exceptions import add_exception_handlers
from app.core.upload_guard import UploadGuardMiddleware
from app.core.config import settings
from app.core.router import routers
from app.services.transcribe_job_service import sweep_temp_files

# 대화형 문서/OpenAPI 스키마는 로컬(APP_ENV=local)에서만 연다. 프로덕션은 APP_ENV **미설정**으로 .env 를 읽으므로
# "production 일 때 끈다" 조건은 실서버에서 한 번도 참이 아니었다 (QA 2026-09-29: /docs, /openapi.json 이 200). ENABLE_DOCS=1 로 강제 개방 가능.
_docs_enabled = os.getenv("APP_ENV", "") == "local" or os.getenv("ENABLE_DOCS", "") == "1"
_docs_kwargs = {} if _docs_enabled else dict(docs_url=None, redoc_url=None, openapi_url=None)

@asynccontextmanager
async def _lifespan(_: FastAPI):
    # 업로드 임시 파일을 실제 디스크로 — 프로덕션 /tmp 는 tmpfs(RAM). Starlette 수신 임시본(SpooledTemporaryFile)과
    # recordings 의 mkstemp 모두 tempfile.tempdir 을 따른다. 경로가 없거나 못 쓰면 기본(/tmp)으로 두고 경고만.
    if settings.UPLOAD_TMP_DIR:
        try:
            os.makedirs(settings.UPLOAD_TMP_DIR, exist_ok=True)
            probe = tempfile.TemporaryFile(dir=settings.UPLOAD_TMP_DIR); probe.close()
            tempfile.tempdir = settings.UPLOAD_TMP_DIR
            print(f"[startup] upload temp dir: {settings.UPLOAD_TMP_DIR}", flush=True)
        except OSError as e:
            print(f"[startup] WARNING: UPLOAD_TMP_DIR {settings.UPLOAD_TMP_DIR!r} unusable ({e}); using system temp", flush=True)
    # 이전 프로세스가 죽으며 남긴 녹음 임시 파일(rec_*) 정리 — 서버에 음성을 남기지 않는다
    n = sweep_temp_files()
    if n:
        print(f"[startup] removed {n} leftover recording temp file(s)", flush=True)
    yield


app = FastAPI(title="PrestigeI Staff API", version="1.0.0", lifespan=_lifespan, **_docs_kwargs)

API_PREFIX = "/api/v1"

app.add_middleware(UploadGuardMiddleware)   # 녹음 업로드: 본문 수신 전 401/413 (app/core/upload_guard.py)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4300"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router, path in routers:
    app.include_router(router, prefix=f"{API_PREFIX}{path}")

add_exception_handlers(app)


@app.get("/health")
async def health():
    return {"status": "ok"}

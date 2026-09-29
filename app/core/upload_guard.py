"""업로드 가드 — POST /api/v1/recordings/transcribe 의 본문을 받기 **전에** 거른다 (QA 2026-09-29 HIGH).

FastAPI 는 multipart 본문을 의존성(인증·rate limit·Content-Length 검사)보다 먼저 파싱하고, Starlette 는 파일 파트 크기를
제한하지 않는다 → 컨트롤러의 검사들은 파일이 디스크에 다 내려온 뒤에야 돈다. 토큰 없는 요청이나 1GB 파일도 UPLOAD_TMP_DIR 을
다 채운 뒤 거절되는 셈. 여기(라우팅 이전)에서:
  · Authorization: Bearer 헤더가 없으면 401 (서명 검증은 그대로 get_current_user 몫 — 여기선 존재만 본다)
  · Content-Length 가 한도를 넘으면 413
  · chunked 등 Content-Length 없는 본문은 receive 를 감싸 바이트를 세다가 한도를 넘는 순간 413 (HTTPException 을 올려
    request.form() 안에서 터지게 → FastAPI 예외 핸들러가 413 응답)
Apache 쪽에도 LimitRequestBody 를 두면 이중 방어가 된다.
"""
from fastapi import HTTPException

from app.services.azure_speech_service import MAX_AUDIO_BYTES

GUARDED_PATH = "/api/v1/recordings/transcribe"
BODY_CAP = MAX_AUDIO_BYTES + 1024 * 1024   # multipart 오버헤드 여유


def _json_response(status: int, detail: str, extra_headers: list[tuple[bytes, bytes]] | None = None):
    body = ('{"detail":"' + detail.replace('"', "'") + '"}').encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())] + (extra_headers or [])
    return status, headers, body


class UploadGuardMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path") != GUARDED_PATH:
            await self.app(scope, receive, send)
            return
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        auth = headers.get(b"authorization", b"")
        if not auth.lower().startswith(b"bearer "):
            status, hdrs, body = _json_response(401, "Not authenticated", [(b"www-authenticate", b"Bearer")])
            await send({"type": "http.response.start", "status": status, "headers": hdrs})
            await send({"type": "http.response.body", "body": body})
            return
        cl = headers.get(b"content-length")
        if cl and cl.isdigit() and int(cl) > BODY_CAP:
            status, hdrs, body = _json_response(413, "Audio file too large (max 300MB)")
            await send({"type": "http.response.start", "status": status, "headers": hdrs})
            await send({"type": "http.response.body", "body": body})
            return

        received = 0

        async def counting_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > BODY_CAP:
                    raise HTTPException(status_code=413, detail="Audio file too large (max 300MB)")
            return message

        await self.app(scope, counting_receive, send)

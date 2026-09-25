"""Azure Speech 파일 변환 중계 (앱 Recording → 텍스트, 2026-09-25).

왜 중계인가: 처음 계획은 "앱이 Azure 에 직접 파일을 올리고 서버는 임시 토큰만" 이었지만, Azure STS 토큰
(sts/v1.0/issueToken)은 실시간 엔드포인트에서만 통하고 **Fast Transcription REST 는 구독 키(또는 Entra ID)
만 받는다** (2026-09-25 eastus2 실측: 키 → 200, 토큰 → 401 "audience is incorrect"). 키를 앱에 넣을 수는
없으므로 서버가 파일을 받아 **저장하지 않고** Azure 로 넘긴다. 디스크 0, CPU 거의 0, 대역폭만 한 번 통과.

호출: POST https://{region}.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe?api-version=2024-11-15
  multipart: audio(파일; wav/mp3/m4a 등) + definition(JSON: locales, diarization)  · 헤더 Ocp-Apim-Subscription-Key
  응답: {durationMilliseconds, combinedPhrases:[{text}], phrases:[{offsetMilliseconds, durationMilliseconds, text, speaker?, locale}]}
  제한: 2시간 / 300MB. 1시간 파일 변환에 보통 1~3분 → 요청 안에서 기다리지 않고 잡(job)으로 돌린다.

텍스트 형식은 LMS recording 사이트(recording.prestigei.com)와 동일하게 맞춘다 (LMS 화면이 그대로 읽도록):
  문장마다 줄바꿈, 화자 분리(conversation)면 "Guest-{n}: 문장", 단일 화자(speech)면 접두어 없음.
"""
import json
import time

import httpx
from fastapi import HTTPException

from app.core.config import settings

TRANSCRIBE_API_VERSION = "2024-11-15"
AZURE_TIMEOUT_SEC = 600            # 2시간 파일도 여유 있게
MAX_AUDIO_BYTES = 300 * 1024 * 1024
SUPPORTED_LOCALES = {"ko-KR", "en-US", "ja-JP", "zh-CN", "es-ES", "fr-FR", "de-DE"}   # 사이트 드롭다운과 동일
DEFAULT_LOCALE = "en-US"


def is_configured() -> bool:
    return bool(settings.AZURE_SPEECH_KEY and settings.AZURE_SPEECH_REGION)


def transcribe_endpoint() -> str:
    return (
        f"https://{settings.AZURE_SPEECH_REGION}.api.cognitive.microsoft.com"
        f"/speechtotext/transcriptions:transcribe?api-version={TRANSCRIBE_API_VERSION}"
    )


def format_transcript(phrases: list[dict], combined: list[dict], diarize: bool) -> str:
    """Azure phrases → LMS 사이트와 같은 평문 (줄바꿈 구분, conversation 이면 'Guest-n: ' 접두어)."""
    lines: list[str] = []
    for p in phrases:
        text = (p.get("text") or "").strip()
        if not text:
            continue
        if diarize and p.get("speaker") is not None:
            lines.append(f"Guest-{p['speaker']}: {text}")
        else:
            lines.append(text)
    if lines:
        return "\n".join(lines)
    return "\n".join(t for c in combined if (t := (c.get("text") or "").strip()))


async def transcribe_file(path: str, filename: str, content_type: str, locale: str, diarize: bool,
                          max_speakers: int = 2) -> dict:
    """파일을 Azure Fast Transcription 에 넘기고 {transcript, duration_ms, phrases_count, azure_ms} 를 돌려준다."""
    if not is_configured():
        raise HTTPException(status_code=503, detail="Azure Speech is not configured")
    definition: dict = {"locales": [locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE]}
    if diarize:
        definition["diarization"] = {"maxSpeakers": max_speakers, "enabled": True}
    started = time.monotonic()
    with open(path, "rb") as f:
        files = {
            "audio": (filename, f, content_type or "application/octet-stream"),
            "definition": (None, json.dumps(definition), "application/json"),
        }
        async with httpx.AsyncClient(timeout=AZURE_TIMEOUT_SEC) as client:
            r = await client.post(
                transcribe_endpoint(),
                headers={"Ocp-Apim-Subscription-Key": settings.AZURE_SPEECH_KEY},
                files=files,
            )
    if r.status_code != 200:
        # 키 값은 절대 노출하지 않는다. Azure 메시지는 앞부분만.
        raise RuntimeError(f"Azure transcription failed (HTTP {r.status_code}): {r.text[:200]}")
    data = r.json()
    phrases = data.get("phrases") or []
    return {
        "transcript": format_transcript(phrases, data.get("combinedPhrases") or [], diarize),
        "duration_ms": int(data.get("durationMilliseconds") or 0),
        "phrases_count": len(phrases),
        "azure_ms": int((time.monotonic() - started) * 1000),
    }

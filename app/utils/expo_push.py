import httpx

from app.utils.push import PushResult

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

# Expo Push API allows up to 100 messages per request
_BATCH_LIMIT = 100


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def send_expo_push(
    tokens: list[str], title: str, body: str, data: dict
) -> PushResult:
    """Send push notifications via Expo Push API, batched to 100 per request.

    This is a blocking (synchronous) call — callers in async context must offload it.

    레거시 경로 — 구버전 앱이 등록한 Expo 토큰만 여기로 온다 (`app/utils/push.py`가 분기).
    구버전 설치가 모두 사라지면 이 모듈째 삭제 가능.
    """
    result = PushResult()
    messages = [
        {
            "to": token,
            "title": title,
            "body": body,
            "data": data,
            "sound": "default",
        }
        for token in tokens
    ]

    for chunk in _chunks(messages, _BATCH_LIMIT):
        try:
            resp = httpx.post(
                EXPO_PUSH_URL,
                json=chunk,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            resp_data = resp.json().get("data", [])

            for msg, ticket in zip(chunk, resp_data):
                if ticket.get("status") == "ok":
                    result.success_count += 1
                else:
                    result.failure_count += 1
                    detail = ticket.get("details", {})
                    error = detail.get("error", ticket.get("message", "unknown"))
                    result.errors.append(str(error))
                    # DeviceNotRegistered means token is invalid
                    if error == "DeviceNotRegistered":
                        result.invalid_tokens.append(msg["to"])
        except Exception as e:
            result.failure_count += len(chunk)
            result.errors.append(str(e))

    return result

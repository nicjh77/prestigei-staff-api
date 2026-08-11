"""FCM(HTTP v1) 발송 — firebase-admin 래퍼.

**부팅 안전성**: 이 모듈은 `app.utils.push.send_push_notifications` 안에서만,
그것도 실제 발송 시점에 import된다. firebase-admin 미설치나 서비스 계정 키
누락이 앱 import 단계에서 터지면 서버 자체가 안 뜨고 = 로그인 불가가 되므로,
초기화는 전부 첫 발송까지 지연시킨다. 실패해도 "그 발송만 실패"로 끝난다.
"""

import threading

from app.core.config import settings
from app.utils.push import PushResult

# FCM send_each_for_multicast는 요청당 토큰 500개까지 허용
_BATCH_LIMIT = 500

_app = None
_app_lock = threading.Lock()


def _get_app():
    """firebase-admin 앱을 최초 1회 초기화하고 재사용한다 (스레드 안전).

    `anyio.to_thread.run_sync`로 워커 스레드에서 호출되므로 락으로 보호한다.
    """
    global _app
    if _app is not None:
        return _app

    with _app_lock:
        if _app is not None:
            return _app

        import firebase_admin
        from firebase_admin import credentials

        cred_path = settings.FIREBASE_CREDENTIALS_PATH
        if cred_path:
            cred = credentials.Certificate(cred_path)
        else:
            # GOOGLE_APPLICATION_CREDENTIALS 등 기본 자격증명 경로로 폴백
            cred = credentials.ApplicationDefault()

        # 이미 초기화된 기본 앱이 있으면 그걸 쓴다 (핫 리로드/재진입 대비)
        try:
            _app = firebase_admin.get_app()
        except ValueError:
            _app = firebase_admin.initialize_app(cred)
        return _app


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def send_fcm_push(
    tokens: list[str], title: str, body: str, data: dict
) -> PushResult:
    """FCM으로 푸시를 발송한다. 500개씩 배치 분할.

    블로킹(동기) 호출 — async 컨텍스트에서는 `anyio.to_thread.run_sync`로 오프로드할 것.
    """
    from firebase_admin import exceptions as fb_exceptions, messaging

    app = _get_app()
    result = PushResult()

    # FCM data payload는 문자열만 허용 — 값을 모두 str로 강제
    str_data = {str(k): str(v) for k, v in (data or {}).items()}

    # data.imageUrl이 있으면 Android 배너에 큰 이미지(BigPicture)로 표시된다 (LMS 계약, 2026-08-11).
    # iOS 배너 이미지는 Notification Service Extension이 필요해 미지원 — 앱 상세 모달에서만 표시.
    image_url = str_data.get("imageUrl")
    if image_url and not image_url.startswith("http"):
        image_url = None
    notification = messaging.Notification(title=title, body=body, image=image_url)
    android_config = messaging.AndroidConfig(
        priority="high",
        notification=messaging.AndroidNotification(
            # 앱이 lib/notifications.ts에서 만드는 채널 id와 반드시 일치해야 한다
            channel_id="default",
            sound="default",
        ),
    )
    apns_config = messaging.APNSConfig(
        payload=messaging.APNSPayload(aps=messaging.Aps(sound="default")),
    )

    for chunk in _chunks(tokens, _BATCH_LIMIT):
        try:
            message = messaging.MulticastMessage(
                tokens=chunk,
                notification=notification,
                data=str_data,
                android=android_config,
                apns=apns_config,
            )
            batch = messaging.send_each_for_multicast(message, app=app)

            for token, resp in zip(chunk, batch.responses):
                if resp.success:
                    result.success_count += 1
                    continue

                result.failure_count += 1
                exc = resp.exception
                result.errors.append(type(exc).__name__ if exc else "unknown")
                # 영구 무효 토큰만 비활성화 — 일시적 오류(Unavailable/Internal)는 살려둔다
                if isinstance(
                    exc,
                    (
                        messaging.UnregisteredError,
                        messaging.SenderIdMismatchError,
                        fb_exceptions.InvalidArgumentError,
                    ),
                ):
                    result.invalid_tokens.append(token)
        except Exception as e:
            result.failure_count += len(chunk)
            result.errors.append(str(e))

    return result

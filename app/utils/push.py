"""푸시 발송 진입점 — 토큰 종류에 따라 FCM / Expo 경로로 나눠 보낸다.

전환기(2026-08) 대응: 스토어 배포 후에도 구버전 앱은 Expo 토큰을,
신버전 앱은 네이티브 FCM 토큰을 등록한다. 둘이 DB에 섞여 있으므로
토큰 문자열로 판별해 각자 맞는 경로로 보낸다. 구버전이 모두 사라지면
Expo 경로와 `app/utils/expo_push.py`를 삭제하면 된다.
"""

from dataclasses import dataclass, field

# Expo 토큰은 항상 이 접두사로 시작한다 (ExponentPushToken[...] / ExpoPushToken[...]).
# FCM 등록 토큰은 접두사가 없는 불투명 문자열이라 이 검사로 안전하게 갈린다.
_EXPO_PREFIXES = ("ExponentPushToken[", "ExpoPushToken[")


@dataclass
class PushResult:
    success_count: int = 0
    failure_count: int = 0
    invalid_tokens: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def merge(self, other: "PushResult") -> None:
        self.success_count += other.success_count
        self.failure_count += other.failure_count
        self.invalid_tokens.extend(other.invalid_tokens)
        self.errors.extend(other.errors)


def is_expo_token(token: str) -> bool:
    return token.startswith(_EXPO_PREFIXES)


def send_push_notifications(
    tokens: list[str], title: str, body: str, data: dict
) -> PushResult:
    """토큰을 종류별로 나눠 발송하고 결과를 합쳐 반환한다.

    블로킹(동기) 호출 — async 컨텍스트에서는 `anyio.to_thread.run_sync`로 오프로드할 것.

    각 sender는 함수 안에서 import한다. firebase-admin은 자격증명이 없거나
    미설치일 때 import/초기화에서 실패할 수 있는데, 모듈 최상단에서 import하면
    그 실패가 앱 부팅 전체를 막는다 (= 로그인 불가). 실제 발송 시점까지 미뤄
    최악의 경우에도 "이 발송만 실패"로 끝나게 한다.
    """
    result = PushResult()
    if not tokens:
        return result

    expo_tokens = [t for t in tokens if is_expo_token(t)]
    fcm_tokens = [t for t in tokens if not is_expo_token(t)]

    if fcm_tokens:
        try:
            from app.utils.fcm_push import send_fcm_push

            result.merge(send_fcm_push(fcm_tokens, title, body, data))
        except Exception as e:
            # import/초기화 실패 (firebase-admin 미설치, 서비스 계정 키 누락 등)
            result.failure_count += len(fcm_tokens)
            result.errors.append(f"fcm unavailable: {e}")

    if expo_tokens:
        try:
            from app.utils.expo_push import send_expo_push

            result.merge(send_expo_push(expo_tokens, title, body, data))
        except Exception as e:
            result.failure_count += len(expo_tokens)
            result.errors.append(f"expo unavailable: {e}")

    return result

"""경량 인메모리 rate limiter (표준 라이브러리만 사용).

외부 의존성(slowapi/redis) 없이 단일 uvicorn 프로세스 환경에 맞춘 슬라이딩 윈도우
구현. 브루트포스(로그인)와 자동화 플러딩(출퇴근 스캔)에 대한 앱 레벨 방어선이다.

한계:
- 프로세스 메모리 기반이라 재시작 시 카운터 초기화, 워커 다중 구동 시 워커별 독립.
  (현재 배포는 단일 프로세스 `uvicorn main:app` 이므로 문제 없음.)
- Apache 리버스 프록시 뒤 배포이므로 클라이언트 IP는 `X-Forwarded-For`의 '맨 뒤'
  값(프록시가 덧붙인 실제 클라이언트)을 사용한다. 첫 값은 클라이언트가 위조할 수 있다.
  더 강한 방어가 필요하면 Apache `mod_remoteip` + `mpm` 단의 요청 제한과 병행 권장.
"""

import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status

# 엔드포인트별 기본 제한값 (limit 회 / window 초, IP 기준)
LOGIN_LIMIT, LOGIN_WINDOW = 10, 60           # 로그인 브루트포스 억제
REFRESH_LIMIT, REFRESH_WINDOW = 30, 60       # 토큰 갱신
SCAN_LIMIT, SCAN_WINDOW = 120, 60            # 무인증 출퇴근 — 정상 키오스크 버스트는 허용, 플러딩만 차단

_CLEANUP_INTERVAL = 60       # 전역 정리 최소 간격(초)
_IDLE_TTL = 3600             # 이 시간 이상 요청 없는 키는 메모리에서 제거


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_cleanup = 0.0

    def check(self, key: str, limit: int, window: float) -> None:
        """key에 대해 window초 내 limit회를 초과하면 429를 발생시킨다.

        FastAPI 의존성(단일 스레드 이벤트 루프)에서 await 없이 동기로 실행되므로
        별도 락 없이도 원자적으로 동작한다.
        """
        now = time.monotonic()
        dq = self._hits[key]

        cutoff = now - window
        while dq and dq[0] <= cutoff:
            dq.popleft()

        if len(dq) >= limit:
            retry_after = int(window - (now - dq[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": str(retry_after)},
            )

        dq.append(now)
        self._maybe_cleanup(now)

    def _maybe_cleanup(self, now: float) -> None:
        """오래 방치된 키를 주기적으로 제거해 메모리 증가를 방지."""
        if now - self._last_cleanup < _CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        stale = [k for k, dq in self._hits.items() if not dq or now - dq[-1] > _IDLE_TTL]
        for k in stale:
            del self._hits[k]


_limiter = SlidingWindowLimiter()


def _client_ip(request: Request) -> str:
    # Apache(mod_proxy_http)는 실제 클라이언트 IP를 X-Forwarded-For '맨 뒤'에 덧붙인다.
    # 클라이언트가 스푸핑해 보낸 값은 앞쪽에 남으므로, 신뢰 프록시(Apache)가 붙인
    # 마지막 값을 써야 위조로 rate limit을 우회하지 못한다.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(limit: int, window: float, scope: str):
    """지정한 scope/제한으로 IP당 rate limit을 거는 FastAPI 의존성을 생성.

    사용: `@router.post(..., dependencies=[Depends(rate_limit(10, 60, "login"))])`
    """

    async def _dependency(request: Request) -> None:
        _limiter.check(f"{scope}:{_client_ip(request)}", limit, window)

    return _dependency

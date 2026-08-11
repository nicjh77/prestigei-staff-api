from zoneinfo import ZoneInfo

# Application timezone — New York / Georgia (Eastern Time)
APP_TZ = ZoneInfo("America/New_York")


def now_et():
    """현재 시각을 ET 벽시계 naive로 반환 — 이 시스템의 표준 시각 규약 (2026-08-12 통일).

    모든 사용자·지점이 동부(토론토/NY/GA)라, DB의 모든 datetime은 동부 벽시계를
    변환 없이 저장하고 변환 없이 표시한다 (출퇴근 t_usertimecheck의 기존 규약을
    전 테이블로 확대). 예외: JWT 만료(security.py)는 표시용이 아닌 epoch 계산이라 UTC 유지.
    """
    from datetime import datetime

    return datetime.now(APP_TZ).replace(tzinfo=None)

# t_schedule.eventtype 중 "근무 아님"으로 취급하는 유형 (attendance 캘린더 / 오늘 상태)
# 프로덕션에서 다른 유형이 확인되면 여기에 추가 (예: "vacation")
DAYOFF_EVENT_TYPES = frozenset({"dayoff"})

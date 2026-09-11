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

# Day Off 하위 타입 (eventtype='dayoff'일 때만 의미)
DAYOFF_SUBTYPES = frozenset({"personal", "sick", "bereavement"})

# ---- PTO (자가 제출 개인 일정) ----
# t_schedule.eventtype 중 직원이 앱에서 직접 제출/수정/삭제할 수 있는 유형.
# LMS Staff Schedule과 동일: 대상자는 tid(=t_user.id), uid/wid = 작성자. dayoff만 휴가 일수에 집계.
PTO_EVENT_TYPES = frozenset({"dayoff", "personal", "other"})

# 근무시간 08:00~17:00 (점심 12~13). LMS가 저장하는 값과 동일해야 한다.
#   종일   : stime 08:00 / etime 17:00 / allday Y / halfday N
#   오전반차: stime 08:00 / etime 12:00 / allday N / halfday A
#   오후반차: stime 13:00 / etime 17:00 / allday N / halfday P
#   시간지정: 임의            / allday N / halfday N
WORK_START = "08:00"
WORK_END = "17:00"
HALF_AM = ("08:00", "12:00")
HALF_PM = ("13:00", "17:00")
WORK_HOURS = 8

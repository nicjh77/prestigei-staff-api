from zoneinfo import ZoneInfo

# Application timezone — New York / Georgia (Eastern Time)
APP_TZ = ZoneInfo("America/New_York")

# t_schedule.eventtype 중 "근무 아님"으로 취급하는 유형 (attendance 캘린더 / 오늘 상태)
# 프로덕션에서 다른 유형이 확인되면 여기에 추가 (예: "vacation")
DAYOFF_EVENT_TYPES = frozenset({"dayoff"})

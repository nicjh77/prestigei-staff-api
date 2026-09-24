from fastapi import APIRouter, Query

from app.core.config import settings

router = APIRouter(tags=["App"])

# 기준값은 서버 .env (학생 앱 서버와 같은 이름, 2026-09-24):
#   APP_ANDROID_VERSION / APP_ANDROID_BUILD / APP_IOS_VERSION / APP_IOS_BUILD = 스토어에 라이브된 버전·빌드
# 판정 (앱 1.3.0이 이 응답 형식을 그대로 쓰므로 키는 유지):
#   force_update           = 앱 버전 < 스토어 버전 (구버전은 전부 강제 업데이트)
#   store_update_available = 위 또는 (같은 버전 && 앱 빌드 < 스토어 빌드, BUILD 0이면 비교 안 함)
# 스토어 릴리스 → .env 값만 바꾸고 재시작. 라이브 확인 전에 올리면 아직 받을 수 없는 업데이트를 강제하니 주의.


def _parse_version(v: str) -> tuple[int, ...]:
    """'1.2.3' → (1, 2, 3)"""
    return tuple(int(x) for x in v.split("."))


@router.get("/version-check")
def version_check(
    platform: str = Query(..., description="ios | android"),
    current: str = Query(..., description="클라이언트 앱 버전 (e.g. 1.1.0)"),
    build: str | None = Query(None, description="클라이언트 빌드 번호 (versionCode/buildNumber, optional)"),
):
    if platform == "ios":
        store_version, store_build = settings.APP_IOS_VERSION, settings.APP_IOS_BUILD
    else:
        store_version, store_build = settings.APP_ANDROID_VERSION, settings.APP_ANDROID_BUILD
    latest_build = store_build or None

    force = False
    store_update = False
    if store_version:
        try:
            cur_v, store_v = _parse_version(current), _parse_version(store_version)
            force = cur_v < store_v
            store_update = force
            if not store_update and cur_v == store_v and latest_build is not None and build:
                store_update = int(build) < latest_build
        except Exception:
            force = store_update = False

    return {
        "min_version": store_version,           # 구 이름 유지 (앱 1.3.0 호환) — 값은 스토어 버전
        "force_update": force,
        "latest_version": store_version,
        "latest_build": latest_build,           # None = 빌드 비교 안 함
        "store_update_available": store_update,
    }

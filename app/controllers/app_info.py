from fastapi import APIRouter, Query

router = APIRouter(tags=["App"])

# 스토어에서 허용하는 최소 버전 — 강제 업데이트 필요 시 이 값을 올린다.
# ⚠️ 1.2.0은 리프레시 토큰 제거 서버와 짝 — 이 서버 코드를 배포하는 순간 1.1.0은
# 토큰 만료 시 복구 불가이므로, 같은 배포에 이 값이 1.2.0이어야 강제 업데이트가 뜬다.
# (전제: 스토어에 1.2.0이 먼저 공개되어 있을 것)
MIN_VERSION = "1.2.0"
# 스토어에 공개된 최신 버전 — 앱 Profile > About "Check for updates"가 "스토어에 새 버전 있음" 안내에 사용.
# 강제는 아님(MIN_VERSION과 별개). 스토어 릴리스 때마다 올린다.
LATEST_VERSION = "1.3.0"


def _parse_version(v: str) -> tuple[int, ...]:
    """'1.2.3' → (1, 2, 3)"""
    return tuple(int(x) for x in v.split("."))


@router.get("/version-check")
def version_check(
    platform: str = Query(..., description="ios | android"),
    current: str = Query(..., description="클라이언트 앱 버전 (e.g. 1.1.0)"),
):
    try:
        force = _parse_version(current) < _parse_version(MIN_VERSION)
    except Exception:
        force = False

    try:
        store_update = _parse_version(current) < _parse_version(LATEST_VERSION)
    except Exception:
        store_update = False

    return {
        "min_version": MIN_VERSION,
        "force_update": force,
        "latest_version": LATEST_VERSION,       # additive (2026-09-08)
        "store_update_available": store_update,
    }

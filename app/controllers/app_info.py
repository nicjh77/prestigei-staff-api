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
# 같은 버전의 재빌드까지 안내하려면 플랫폼별 최신 빌드 번호를 채운다 (Android versionCode / iOS buildNumber).
# None = 빌드 비교 안 함(기본). 예: 2.0.0 빌드 1·2·3을 내부 테스트로 연달아 올릴 때 "빌드 3부터 써라"를 알리는 용도.
# 앱은 스토어 설치를 대신하지 못하므로 안내(Open Store)까지만 — JS만 바뀐 재빌드는 OTA로 대신할 것.
LATEST_BUILD: dict[str, int | None] = {"android": None, "ios": None}


def _parse_version(v: str) -> tuple[int, ...]:
    """'1.2.3' → (1, 2, 3)"""
    return tuple(int(x) for x in v.split("."))


@router.get("/version-check")
def version_check(
    platform: str = Query(..., description="ios | android"),
    current: str = Query(..., description="클라이언트 앱 버전 (e.g. 1.1.0)"),
    build: str | None = Query(None, description="클라이언트 빌드 번호 (versionCode/buildNumber, optional)"),
):
    try:
        force = _parse_version(current) < _parse_version(MIN_VERSION)
    except Exception:
        force = False

    # 스토어 새 버전: ① 버전이 낮거나 ② 버전이 같은데 (알려진) 최신 빌드보다 빌드가 낮을 때
    latest_build = LATEST_BUILD.get(platform)
    try:
        cur_v, latest_v = _parse_version(current), _parse_version(LATEST_VERSION)
        store_update = cur_v < latest_v
        if not store_update and cur_v == latest_v and latest_build is not None and build:
            store_update = int(build) < latest_build
    except Exception:
        store_update = False

    return {
        "min_version": MIN_VERSION,
        "force_update": force,
        "latest_version": LATEST_VERSION,       # additive (2026-09-08)
        "latest_build": latest_build,           # None = 빌드 비교 안 함
        "store_update_available": store_update,
    }

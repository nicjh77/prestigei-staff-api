from fastapi import APIRouter, Query

router = APIRouter(tags=["App"])

# 스토어에서 허용하는 최소 버전 — 강제 업데이트 필요 시 이 값을 올린다
MIN_VERSION = "1.1.0"


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

    return {
        "min_version": MIN_VERSION,
        "force_update": force,
    }

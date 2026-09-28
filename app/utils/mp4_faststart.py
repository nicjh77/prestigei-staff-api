"""MP4/m4a "faststart" 재배치 — moov(인덱스) 아톰을 mdat(음성 데이터) 앞으로 옮긴다. 순수 Python, 외부 도구 불필요.

왜 필요한가 (2026-09-28 실측): Android MediaRecorder 는 moov 를 파일 **끝**에 쓴다. Azure Fast Transcription 은 파일 앞부분으로
포맷을 판단해서 작은 파일(4분, 2MB)은 되지만 49분(23MB) 파일은 인덱스를 못 찾아 422 InvalidAudioFormat 을 낸다.
같은 파일의 moov 를 앞으로 옮기면 200 — 49분 전체 변환됨. 그래서 Azure 로 넘기기 전에 이 함수를 통과시킨다.

구현: 최상위 아톰을 훑어 moov 가 mdat 뒤에 있으면 [ftyp][moov'][mdat …] 순서로 새 파일을 쓴다. moov' 는 stco/co64 의
청크 오프셋에 moov 크기만큼을 더한 것 (moov 가 mdat 앞에 끼어들어 mdat 가 그만큼 뒤로 밀리므로). stco(32bit) 가
넘치면 co64 로 바꿔야 하지만 우리 파일은 ≤300MB 라 해당 없음 → 넘치면 그냥 원본을 돌려준다(Azure 가 거절하면 그때 실패).
mdat 는 청크 단위로 복사해 메모리에 통째로 올리지 않는다.
"""
import os
import struct

_CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl"}
_CHUNK = 1024 * 1024


def _top_level(f, size):
    out = []
    p = 0
    while p + 8 <= size:
        f.seek(p)
        hdr = f.read(16)
        if len(hdr) < 8:
            break
        (asize,) = struct.unpack(">I", hdr[:4])
        typ = hdr[4:8]
        hlen = 8
        if asize == 1:
            (asize,) = struct.unpack(">Q", hdr[8:16])
            hlen = 16
        elif asize == 0:
            asize = size - p
        if asize < hlen:
            raise ValueError("corrupt atom")
        out.append((typ, p, asize, hlen))
        p += asize
    return out


def _patch_offsets(moov: bytearray, delta: int) -> bool:
    """moov 안의 stco/co64 를 아톰 트리로 정확히 찾아 오프셋을 delta 만큼 민다. 32bit 넘치면 False."""
    def walk(start, end):
        p = start
        while p + 8 <= end:
            (asize,) = struct.unpack(">I", moov[p:p + 4])
            typ = bytes(moov[p + 4:p + 8])
            hlen = 8
            if asize == 1:
                (asize,) = struct.unpack(">Q", moov[p + 8:p + 16])
                hlen = 16
            elif asize == 0:
                asize = end - p
            if typ in _CONTAINERS:
                if not walk(p + hlen, p + asize):
                    return False
            elif typ in (b"stco", b"co64"):
                (cnt,) = struct.unpack(">I", moov[p + hlen + 4:p + hlen + 8])
                base = p + hlen + 8
                fmt, width = (">I", 4) if typ == b"stco" else (">Q", 8)
                for k in range(cnt):
                    o = base + k * width
                    (v,) = struct.unpack(fmt, moov[o:o + width])
                    v += delta
                    if typ == b"stco" and v > 0xFFFFFFFF:
                        return False
                    moov[o:o + width] = struct.pack(fmt, v)
            p += max(asize, hlen)
        return True
    return walk(8, len(moov))


def ensure_faststart(path: str) -> tuple[str, bool]:
    """(경로, 재배치했는지). MP4 가 아니거나 이미 moov 가 앞이면 원본 그대로. 재배치하면 새 파일을 만들고 원본은 삭제."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(12)
        if len(head) < 12 or head[4:8] != b"ftyp":
            return path, False
        try:
            atoms = _top_level(f, size)
        except (ValueError, struct.error):
            return path, False
        types = [a[0] for a in atoms]
        if b"moov" not in types or b"mdat" not in types:
            return path, False
        if types.index(b"moov") < types.index(b"mdat"):
            return path, False                                  # 이미 faststart
        m_typ, m_off, m_size, _ = next(a for a in atoms if a[0] == b"moov")
        f.seek(m_off)
        moov = bytearray(f.read(m_size))
        if not _patch_offsets(moov, m_size):
            return path, False
        out_path = f"{os.path.splitext(path)[0]}_fs{os.path.splitext(path)[1]}"
        with open(out_path, "wb") as out:
            # moov 앞의 아톰(ftyp, free …)은 그대로, 그 다음 moov', 그 다음 나머지(mdat …) — moov 원래 자리는 건너뛴다
            for typ, off, asize, _ in atoms:
                if typ == b"moov":
                    continue
                if off == next(a[1] for a in atoms if a[0] == b"mdat"):
                    out.write(bytes(moov))
                f.seek(off)
                remaining = asize
                while remaining > 0:
                    buf = f.read(min(_CHUNK, remaining))
                    if not buf:
                        break
                    out.write(buf)
                    remaining -= len(buf)
    os.remove(path)
    return out_path, True

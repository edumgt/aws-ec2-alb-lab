#!/usr/bin/env python3
"""EC2 스크린샷 민감정보 마스킹 도구.

외부 라이브러리 없이 동작합니다. PNG RGBA, 8비트, 비-인터레이스 형식을 지원합니다.
실행 시 --image-dir <경로> 옵션으로 대상 폴더를 지정할 수 있습니다.
"""

# Python 3.10 미만에서도 X | Y 형태의 타입 힌트를 사용하기 위해 임포트합니다
from __future__ import annotations

import argparse  # 커맨드라인 인수 파싱 라이브러리
import glob      # 와일드카드(*) 기반 파일 경로 검색 라이브러리
import os        # 운영체제 파일/경로 관련 유틸리티 라이브러리
import struct    # 바이너리 데이터를 Python 자료형으로 변환하는 라이브러리
import zlib      # PNG 이미지 데이터 압축/해제(deflate)를 위한 라이브러리
from typing import List, Tuple  # 타입 힌트용: 리스트·튜플 제네릭 타입

# PNG 파일 시작 8바이트 시그니처 (PNG 표준 정의)
PNG_SIG = b"\x89PNG\r\n\x1a\n"


def read_chunks(data: bytes):
    """PNG 바이너리 데이터에서 청크(chunk)를 순서대로 읽어 반환하는 제너레이터.

    PNG 포맷: 각 청크 = [4B 길이][4B 타입][nB 데이터][4B CRC]
    """
    off = 8  # PNG 시그니처(8바이트) 이후부터 파싱 시작
    while off < len(data):  # 파일 끝까지 반복
        length = struct.unpack(">I", data[off : off + 4])[0]  # 빅엔디언 4바이트 정수로 청크 데이터 길이 읽기
        off += 4          # 길이 필드(4바이트) 건너뜀
        ctype = data[off : off + 4]  # 청크 타입 4바이트 (예: b"IHDR", b"IDAT")
        off += 4          # 타입 필드(4바이트) 건너뜀
        chunk_data = data[off : off + length]  # 실제 청크 데이터 슬라이싱
        off += length     # 데이터 길이만큼 오프셋 이동
        crc = data[off : off + 4]  # CRC 체크섬 4바이트 (검증은 생략)
        off += 4          # CRC 필드(4바이트) 건너뜀
        yield ctype, chunk_data, crc  # 청크 타입·데이터·CRC를 튜플로 반환
        if ctype == b"IEND":  # 마지막 청크(IEND)에 도달하면 루프 종료
            break


def paeth_predictor(a: int, b: int, c: int) -> int:
    """PNG Paeth 필터 예측값 계산 함수.

    인접 픽셀(a=왼쪽, b=위쪽, c=왼쪽 위쪽)을 이용해 현재 픽셀의 예측값을 구합니다.
    PNG 표준 RFC 2083에 정의된 알고리즘입니다.
    """
    p = a + b - c         # 기본 예측값: 왼쪽 + 위 - 왼쪽위 (선형 예측)
    pa = abs(p - a)       # 왼쪽 픽셀과 예측값의 절대 오차
    pb = abs(p - b)       # 위쪽 픽셀과 예측값의 절대 오차
    pc = abs(p - c)       # 왼쪽 위 픽셀과 예측값의 절대 오차
    if pa <= pb and pa <= pc:  # 왼쪽 오차가 가장 작으면
        return a          # 왼쪽 픽셀을 예측값으로 사용
    if pb <= pc:          # 위쪽 오차가 왼쪽 위보다 작거나 같으면
        return b          # 위쪽 픽셀을 예측값으로 사용
    return c              # 그 외에는 왼쪽 위 픽셀을 예측값으로 사용


def unfilter_scanlines(raw: bytes, width: int, height: int, bpp: int) -> bytearray:
    """PNG 필터가 적용된 스캔라인을 원본 픽셀 데이터로 복원합니다.

    PNG는 zlib 압축 전에 행(scanline)별로 필터를 적용합니다.
    이 함수는 각 행의 필터 타입(0~4)에 맞게 역변환합니다.
    """
    stride = width * bpp  # 한 행의 바이트 수 (픽셀 수 × 채널 수)
    out = bytearray(height * stride)  # 전체 픽셀 데이터를 담을 바이트 배열 초기화
    src_off = 0           # 압축 해제된 원본 데이터의 읽기 오프셋
    dst_off = 0           # 복원된 픽셀 데이터의 쓰기 오프셋

    prev = bytearray(stride)  # 이전 행의 픽셀 데이터 (Up/Average/Paeth 필터에서 참조)

    for _ in range(height):  # 이미지 전체 행(scanline)을 순서대로 처리
        f = raw[src_off]      # 이 행의 PNG 필터 타입(0=None,1=Sub,2=Up,3=Avg,4=Paeth)
        src_off += 1          # 필터 타입 바이트 건너뜀
        scan = bytearray(raw[src_off : src_off + stride])  # 필터 적용된 한 행 데이터 복사
        src_off += stride     # 다음 행의 시작점으로 오프셋 이동

        if f == 0:            # None 필터: 변환 없이 그대로 사용
            pass
        elif f == 1:          # Sub 필터: 같은 행의 왼쪽 픽셀값을 더해 복원
            for i in range(stride):
                left = scan[i - bpp] if i >= bpp else 0  # bpp 이전 인덱스 = 왼쪽 채널 값
                scan[i] = (scan[i] + left) & 0xFF        # 원본값 복원 후 1바이트 범위로 마스킹
        elif f == 2:          # Up 필터: 바로 위 행의 같은 위치 픽셀값을 더해 복원
            for i in range(stride):
                scan[i] = (scan[i] + prev[i]) & 0xFF    # 위 행 픽셀 더하기
        elif f == 3:          # Average 필터: (왼쪽 + 위) / 2 를 더해 복원
            for i in range(stride):
                left = scan[i - bpp] if i >= bpp else 0  # 왼쪽 채널 값
                up = prev[i]                              # 위 행 같은 위치 값
                scan[i] = (scan[i] + ((left + up) >> 1)) & 0xFF  # 정수 나눗셈(>> 1 = /2)
        elif f == 4:          # Paeth 필터: Paeth 예측값을 더해 복원
            for i in range(stride):
                a = scan[i - bpp] if i >= bpp else 0     # 왼쪽 픽셀
                b = prev[i]                               # 위쪽 픽셀
                c = prev[i - bpp] if i >= bpp else 0     # 왼쪽 위 픽셀
                scan[i] = (scan[i] + paeth_predictor(a, b, c)) & 0xFF  # 예측값 더해 복원
        else:
            raise ValueError(f"Unsupported PNG filter: {f}")  # 알 수 없는 필터 타입

        out[dst_off : dst_off + stride] = scan  # 복원된 행을 출력 버퍼에 저장
        prev[:] = scan    # 다음 행 처리를 위해 현재 행을 이전 행으로 업데이트
        dst_off += stride # 출력 오프셋을 다음 행 시작으로 이동

    return out  # 전체 복원된 픽셀 데이터 반환


def refilter_none(pixels: bytearray, width: int, height: int, bpp: int) -> bytes:
    """픽셀 데이터에 필터 타입 0(None)을 적용해 PNG 스캔라인 형식으로 재패킹합니다.

    각 행 앞에 필터 바이트 0x00을 삽입합니다. 이후 zlib 압축에 사용됩니다.
    """
    stride = width * bpp               # 한 행의 픽셀 바이트 수
    rows = bytearray((stride + 1) * height)  # 각 행에 필터 바이트 1개 추가
    src_off = 0                         # 픽셀 데이터 읽기 오프셋
    dst_off = 0                         # 스캔라인 출력 쓰기 오프셋
    for _ in range(height):             # 각 행에 대해 반복
        rows[dst_off] = 0               # 필터 타입 0(None)을 행 첫 바이트에 기록
        dst_off += 1                    # 필터 바이트 위치 건너뜀
        rows[dst_off : dst_off + stride] = pixels[src_off : src_off + stride]  # 픽셀 데이터 복사
        src_off += stride               # 다음 행 픽셀로 이동
        dst_off += stride               # 다음 행 출력 위치로 이동
    return bytes(rows)                  # 불변(immutable) bytes 형태로 반환


def pixelate_rect(pix: bytearray, width: int, height: int, rect: Tuple[int, int, int, int], block: int = 14) -> None:
    """지정된 사각형 영역을 블록 평균값으로 픽셀화(모자이크)합니다.

    block × block 크기의 타일로 나누고, 각 타일의 픽셀 평균값으로 채웁니다.
    RGBA(4채널) 이미지를 가정합니다.
    """
    x0, y0, x1, y1 = rect             # 마스킹 영역의 좌상단(x0,y0) · 우하단(x1,y1) 픽셀 좌표
    x0 = max(0, min(width, x0))        # x0가 이미지 경계를 벗어나지 않도록 클램핑
    y0 = max(0, min(height, y0))       # y0가 이미지 경계를 벗어나지 않도록 클램핑
    x1 = max(0, min(width, x1))        # x1가 이미지 경계를 벗어나지 않도록 클램핑
    y1 = max(0, min(height, y1))       # y1가 이미지 경계를 벗어나지 않도록 클램핑
    if x1 <= x0 or y1 <= y0:          # 유효하지 않은 영역(너비/높이 0 이하)이면 처리 건너뜀
        return

    stride = width * 4                 # RGBA이므로 픽셀당 4바이트, 한 행의 총 바이트 수
    for by in range(y0, y1, block):    # 블록 크기 단위로 y 방향 순회
        for bx in range(x0, x1, block):  # 블록 크기 단위로 x 방향 순회
            ex = min(bx + block, x1)   # 현재 타일의 오른쪽 끝 x (이미지/영역 경계 초과 방지)
            ey = min(by + block, y1)   # 현재 타일의 아래쪽 끝 y (이미지/영역 경계 초과 방지)

            sr = sg = sb = sa = count = 0  # R·G·B·A 채널 합산 변수와 픽셀 개수 초기화
            for y in range(by, ey):    # 타일 내 각 행 순회
                row = y * stride       # 현재 행의 바이트 시작 오프셋
                for x in range(bx, ex):  # 타일 내 각 열 순회
                    i = row + x * 4    # 현재 픽셀의 R 채널 인덱스
                    sr += pix[i]       # Red 채널 합산
                    sg += pix[i + 1]  # Green 채널 합산
                    sb += pix[i + 2]  # Blue 채널 합산
                    sa += pix[i + 3]  # Alpha 채널 합산
                    count += 1         # 처리한 픽셀 수 증가

            if count == 0:             # 픽셀이 없는 타일(경계 처리)은 건너뜀
                continue

            ar = sr // count           # Red 채널 평균값 (정수 나눗셈)
            ag = sg // count           # Green 채널 평균값
            ab = sb // count           # Blue 채널 평균값
            aa = sa // count           # Alpha 채널 평균값

            for y in range(by, ey):    # 타일 내 각 행에 평균값 기록
                row = y * stride       # 현재 행의 바이트 시작 오프셋
                for x in range(bx, ex):  # 타일 내 각 열에 평균값 기록
                    i = row + x * 4    # 현재 픽셀의 R 채널 인덱스
                    pix[i] = ar        # Red 채널에 평균값 덮어쓰기
                    pix[i + 1] = ag   # Green 채널에 평균값 덮어쓰기
                    pix[i + 2] = ab   # Blue 채널에 평균값 덮어쓰기
                    pix[i + 3] = aa   # Alpha 채널에 평균값 덮어쓰기


def redact_png(path: str) -> None:
    """PNG 파일을 읽어 민감 영역을 픽셀화한 뒤 원본 경로에 덮어씁니다."""
    with open(path, "rb") as f:  # PNG 파일을 바이너리 읽기 모드로 오픈
        data = f.read()           # 전체 파일 내용을 메모리에 로드

    if data[:8] != PNG_SIG:       # 파일 첫 8바이트가 PNG 시그니처와 다르면 PNG가 아님
        return                    # PNG가 아닌 파일은 건너뜀

    ihdr = None                                  # IHDR 청크 데이터 (이미지 메타데이터)
    pre_idat: List[Tuple[bytes, bytes]] = []     # IDAT 청크 이전의 보조 청크 목록
    post_idat: List[Tuple[bytes, bytes]] = []    # IDAT 청크 이후의 보조 청크 목록
    idat_parts: List[bytes] = []                 # IDAT 청크 데이터 조각들 (PNG는 여러 IDAT 허용)
    seen_idat = False                            # IDAT 청크를 이미 만났는지 여부

    for ctype, cdata, _crc in read_chunks(data):  # PNG 파일의 모든 청크를 순서대로 순회
        if ctype == b"IHDR":           # 이미지 헤더 청크: 폭·높이·색상 타입 등 메타데이터
            ihdr = cdata               # IHDR 데이터 저장
        elif ctype == b"IDAT":         # 실제 이미지 픽셀 데이터(압축됨)
            seen_idat = True           # IDAT 청크 등장 플래그 설정
            idat_parts.append(cdata)   # 다중 IDAT 청크를 리스트에 누적
        elif ctype == b"IEND":         # 파일 끝 마커 청크
            post_idat.append((ctype, cdata))  # IEND는 post_idat에 포함
        else:
            if seen_idat:              # IDAT 이후에 나온 기타 청크
                post_idat.append((ctype, cdata))
            else:                      # IDAT 이전에 나온 기타 청크 (팔레트, 감마 등)
                pre_idat.append((ctype, cdata))

    if ihdr is None:  # IHDR이 없으면 손상된 파일 → 처리 중단
        return

    # IHDR 청크 파싱: 빅엔디언 정수 2개 + 1바이트 5개 형식
    width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(">IIBBBBB", ihdr)
    if (bit_depth, color_type, comp, filt, interlace) != (8, 6, 0, 0, 0):
        # 8비트 RGBA(color_type=6), deflate 압축(comp=0), 필터(filt=0), 비인터레이스(interlace=0)만 지원
        raise ValueError(f"Unsupported PNG format in {path}")

    raw = zlib.decompress(b"".join(idat_parts))   # 모든 IDAT 데이터를 합쳐 zlib 압축 해제
    pixels = unfilter_scanlines(raw, width, height, bpp=4)  # PNG 필터 역변환으로 원본 픽셀 복원 (bpp=4: RGBA)

    # 민감정보가 자주 등장하는 정규화된 영역 정의 (좌상단 비율 x0,y0 ~ 우하단 x1,y1)
    zones = [
        (0.00, 0.00, 1.00, 0.07),  # 브라우저 탭·주소창 (계정 정보, URL)
        (0.76, 0.00, 1.00, 0.08),  # 우상단 계정/사용자/리전 표시 영역
        (0.10, 0.08, 0.72, 0.42),  # 상단 브레드크럼·제목·리소스 ID 영역
        (0.24, 0.20, 0.96, 0.44),  # 테이블 목록(ID, DNS 등 표시 열)
        (0.10, 0.40, 0.60, 1.00),  # 좌측 상세 정보 값 영역
        (0.38, 0.22, 0.99, 1.00),  # 우측 상세 정보 및 네트워크/IP 필드 영역
    ]

    for zx0, zy0, zx1, zy1 in zones:  # 각 마스킹 영역에 대해 픽셀 좌표로 변환 후 처리
        rect = (
            int(width * zx0),    # 비율(0~1)을 실제 픽셀 x 좌표로 변환 (좌)
            int(height * zy0),   # 비율(0~1)을 실제 픽셀 y 좌표로 변환 (상)
            int(width * zx1),    # 비율(0~1)을 실제 픽셀 x 좌표로 변환 (우)
            int(height * zy1),   # 비율(0~1)을 실제 픽셀 y 좌표로 변환 (하)
        )
        pixelate_rect(pixels, width, height, rect, block=14)  # 해당 영역을 14px 블록으로 픽셀화

    # 우상단에 마스킹 처리 표시(뱃지)를 위한 어두운 오버레이 사각형 그리기
    badge_w = max(180, int(width * 0.12))    # 뱃지 너비: 최소 180px 또는 이미지 폭의 12%
    badge_h = max(36, int(height * 0.055))   # 뱃지 높이: 최소 36px 또는 이미지 높이의 5.5%
    bx0 = width - badge_w - 8               # 뱃지 좌상단 x 좌표 (우측 8px 여백)
    by0 = 8                                  # 뱃지 좌상단 y 좌표 (상단 8px 여백)
    stride = width * 4                       # 한 행의 바이트 수 (RGBA = 4채널)
    for y in range(by0, min(by0 + badge_h, height)):      # 뱃지 영역의 각 행 순회
        row = y * stride                     # 현재 행 시작 바이트 오프셋
        for x in range(max(0, bx0), min(width, bx0 + badge_w)):  # 뱃지 영역의 각 열 순회
            i = row + x * 4                  # 현재 픽셀의 R 채널 인덱스
            # 어두운 오버레이 사각형: 원래 픽셀값을 30%로 어둡게 처리
            pix = pixels[i : i + 4]          # 현재 픽셀의 RGBA 슬라이스
            r, g, b, a = pix                 # RGBA 채널 값 분리
            pixels[i] = (r * 30) // 100      # Red를 30% 밝기로 감소
            pixels[i + 1] = (g * 30) // 100 # Green을 30% 밝기로 감소
            pixels[i + 2] = (b * 30) // 100 # Blue를 30% 밝기로 감소
            pixels[i + 3] = a                # Alpha는 유지

    refiltered = refilter_none(pixels, width, height, bpp=4)  # 수정된 픽셀에 필터 없음(0) 재적용
    new_idat = zlib.compress(refiltered, level=9)             # 레벨 9(최대 압축)로 zlib 재압축

    def make_chunk(ctype: bytes, cdata: bytes) -> bytes:
        """PNG 청크 바이너리를 생성합니다: [길이][타입][데이터][CRC]."""
        crc = zlib.crc32(ctype)                          # 청크 타입으로 CRC 초기화
        crc = zlib.crc32(cdata, crc) & 0xFFFFFFFF        # 데이터를 포함해 CRC 계산 후 32비트 마스킹
        return struct.pack(">I", len(cdata)) + ctype + cdata + struct.pack(">I", crc)
        # 빅엔디언 4B 길이 + 타입 + 데이터 + 빅엔디언 4B CRC를 합쳐 반환

    out = bytearray(PNG_SIG)             # 출력 버퍼를 PNG 시그니처로 초기화
    out += make_chunk(b"IHDR", ihdr)     # IHDR 청크 추가 (이미지 메타데이터)
    for ctype, cdata in pre_idat:        # IDAT 이전의 보조 청크(팔레트, 감마 등) 추가
        out += make_chunk(ctype, cdata)
    out += make_chunk(b"IDAT", new_idat)  # 마스킹 처리된 새 IDAT 청크 추가
    for ctype, cdata in post_idat:        # IDAT 이후의 보조 청크 추가
        if ctype != b"IEND":             # IEND는 마지막에 별도로 추가하기 위해 건너뜀
            out += make_chunk(ctype, cdata)
    out += make_chunk(b"IEND", b"")      # PNG 파일 끝 마커 청크 추가 (데이터 없음)

    with open(path, "wb") as f:  # 원본 파일을 바이너리 쓰기 모드로 열어 덮어씁니다
        f.write(out)              # 마스킹 처리된 PNG 데이터 기록


def main() -> None:
    """커맨드라인 인수를 파싱하고 지정 폴더의 PNG 파일을 일괄 마스킹합니다."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # __file__: 이 스크립트의 절대 경로 → EC2/ → 레포 루트 순서로 두 단계 상위 경로를 구합니다
    parser = argparse.ArgumentParser(description="Redact PNG screenshots by pixelating sensitive regions.")
    # --image-dir 옵션: 마스킹할 PNG 파일들이 있는 디렉터리 경로
    parser.add_argument(
        "--image-dir",
        default=os.path.join(repo_root, "EC2"),  # 기본값: 레포 루트/EC2 폴더
        help="Target directory for PNG files (default: <repo>/EC2)",
    )
    args = parser.parse_args()  # 커맨드라인 인수 파싱 실행

    files = sorted(glob.glob(os.path.join(args.image_dir, "*.png")))  # 지정 폴더의 PNG 파일 목록을 정렬해 수집
    for p in files:       # 각 PNG 파일에 대해 마스킹 처리 실행
        redact_png(p)
    print(f"Redacted {len(files)} image(s).")  # 처리된 파일 수 출력


if __name__ == "__main__":
    main()  # 스크립트를 직접 실행할 때만 main() 호출

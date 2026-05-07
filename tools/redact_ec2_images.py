#!/usr/bin/env python3
"""Batch redact EC2 screenshots by pixelating common sensitive regions.

No external dependencies. Supports PNG RGBA, 8-bit, non-interlaced.
"""

from __future__ import annotations

import glob
import os
import struct
import zlib
from typing import List, Tuple

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def read_chunks(data: bytes):
    off = 8
    while off < len(data):
        length = struct.unpack(">I", data[off : off + 4])[0]
        off += 4
        ctype = data[off : off + 4]
        off += 4
        chunk_data = data[off : off + length]
        off += length
        crc = data[off : off + 4]
        off += 4
        yield ctype, chunk_data, crc
        if ctype == b"IEND":
            break


def paeth_predictor(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def unfilter_scanlines(raw: bytes, width: int, height: int, bpp: int) -> bytearray:
    stride = width * bpp
    out = bytearray(height * stride)
    src_off = 0
    dst_off = 0

    prev = bytearray(stride)

    for _ in range(height):
        f = raw[src_off]
        src_off += 1
        scan = bytearray(raw[src_off : src_off + stride])
        src_off += stride

        if f == 0:
            pass
        elif f == 1:  # Sub
            for i in range(stride):
                left = scan[i - bpp] if i >= bpp else 0
                scan[i] = (scan[i] + left) & 0xFF
        elif f == 2:  # Up
            for i in range(stride):
                scan[i] = (scan[i] + prev[i]) & 0xFF
        elif f == 3:  # Average
            for i in range(stride):
                left = scan[i - bpp] if i >= bpp else 0
                up = prev[i]
                scan[i] = (scan[i] + ((left + up) >> 1)) & 0xFF
        elif f == 4:  # Paeth
            for i in range(stride):
                a = scan[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                scan[i] = (scan[i] + paeth_predictor(a, b, c)) & 0xFF
        else:
            raise ValueError(f"Unsupported PNG filter: {f}")

        out[dst_off : dst_off + stride] = scan
        prev[:] = scan
        dst_off += stride

    return out


def refilter_none(pixels: bytearray, width: int, height: int, bpp: int) -> bytes:
    stride = width * bpp
    rows = bytearray((stride + 1) * height)
    src_off = 0
    dst_off = 0
    for _ in range(height):
        rows[dst_off] = 0
        dst_off += 1
        rows[dst_off : dst_off + stride] = pixels[src_off : src_off + stride]
        src_off += stride
        dst_off += stride
    return bytes(rows)


def pixelate_rect(pix: bytearray, width: int, height: int, rect: Tuple[int, int, int, int], block: int = 14) -> None:
    x0, y0, x1, y1 = rect
    x0 = max(0, min(width, x0))
    y0 = max(0, min(height, y0))
    x1 = max(0, min(width, x1))
    y1 = max(0, min(height, y1))
    if x1 <= x0 or y1 <= y0:
        return

    stride = width * 4
    for by in range(y0, y1, block):
        for bx in range(x0, x1, block):
            ex = min(bx + block, x1)
            ey = min(by + block, y1)

            sr = sg = sb = sa = count = 0
            for y in range(by, ey):
                row = y * stride
                for x in range(bx, ex):
                    i = row + x * 4
                    sr += pix[i]
                    sg += pix[i + 1]
                    sb += pix[i + 2]
                    sa += pix[i + 3]
                    count += 1

            if count == 0:
                continue

            ar = sr // count
            ag = sg // count
            ab = sb // count
            aa = sa // count

            for y in range(by, ey):
                row = y * stride
                for x in range(bx, ex):
                    i = row + x * 4
                    pix[i] = ar
                    pix[i + 1] = ag
                    pix[i + 2] = ab
                    pix[i + 3] = aa


def redact_png(path: str) -> None:
    with open(path, "rb") as f:
        data = f.read()

    if data[:8] != PNG_SIG:
        return

    ihdr = None
    pre_idat: List[Tuple[bytes, bytes]] = []
    post_idat: List[Tuple[bytes, bytes]] = []
    idat_parts: List[bytes] = []
    seen_idat = False

    for ctype, cdata, _crc in read_chunks(data):
        if ctype == b"IHDR":
            ihdr = cdata
        elif ctype == b"IDAT":
            seen_idat = True
            idat_parts.append(cdata)
        elif ctype == b"IEND":
            post_idat.append((ctype, cdata))
        else:
            if seen_idat:
                post_idat.append((ctype, cdata))
            else:
                pre_idat.append((ctype, cdata))

    if ihdr is None:
        return

    width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(">IIBBBBB", ihdr)
    if (bit_depth, color_type, comp, filt, interlace) != (8, 6, 0, 0, 0):
        raise ValueError(f"Unsupported PNG format in {path}")

    raw = zlib.decompress(b"".join(idat_parts))
    pixels = unfilter_scanlines(raw, width, height, bpp=4)

    # Normalized zones that commonly include account IDs, instance IDs, IPs, DNS, ARNs.
    zones = [
        (0.00, 0.00, 1.00, 0.07),  # browser tab/address bar
        (0.76, 0.00, 1.00, 0.08),  # top-right account/user/region area
        (0.10, 0.08, 0.72, 0.42),  # breadcrumbs/title/resource IDs near top
        (0.24, 0.20, 0.96, 0.44),  # list/table columns where IDs/DNS appear
        (0.10, 0.40, 0.60, 1.00),  # left detail values
        (0.38, 0.22, 0.99, 1.00),  # right detail values and network/IP fields
    ]

    for zx0, zy0, zx1, zy1 in zones:
        rect = (
            int(width * zx0),
            int(height * zy0),
            int(width * zx1),
            int(height * zy1),
        )
        pixelate_rect(pixels, width, height, rect, block=14)

    # Put a clear small redaction badge at top-right for traceability.
    badge_w = max(180, int(width * 0.12))
    badge_h = max(36, int(height * 0.055))
    bx0 = width - badge_w - 8
    by0 = 8
    stride = width * 4
    for y in range(by0, min(by0 + badge_h, height)):
        row = y * stride
        for x in range(max(0, bx0), min(width, bx0 + badge_w)):
            i = row + x * 4
            # dark overlay rectangle
            pix = pixels[i : i + 4]
            r, g, b, a = pix
            pixels[i] = (r * 30) // 100
            pixels[i + 1] = (g * 30) // 100
            pixels[i + 2] = (b * 30) // 100
            pixels[i + 3] = a

    refiltered = refilter_none(pixels, width, height, bpp=4)
    new_idat = zlib.compress(refiltered, level=9)

    def make_chunk(ctype: bytes, cdata: bytes) -> bytes:
        crc = zlib.crc32(ctype)
        crc = zlib.crc32(cdata, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(cdata)) + ctype + cdata + struct.pack(">I", crc)

    out = bytearray(PNG_SIG)
    out += make_chunk(b"IHDR", ihdr)
    for ctype, cdata in pre_idat:
        out += make_chunk(ctype, cdata)
    out += make_chunk(b"IDAT", new_idat)
    for ctype, cdata in post_idat:
        if ctype != b"IEND":
            out += make_chunk(ctype, cdata)
    out += make_chunk(b"IEND", b"")

    with open(path, "wb") as f:
        f.write(out)


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = sorted(glob.glob(os.path.join(repo_root, "EC2", "*.png")))
    for p in files:
        redact_png(p)
    print(f"Redacted {len(files)} image(s).")


if __name__ == "__main__":
    main()

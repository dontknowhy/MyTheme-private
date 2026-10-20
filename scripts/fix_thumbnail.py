#!/usr/bin/env python3
"""
修复 JPEG 内嵌的 EXIF 缩略图。

背景
====
有些 JPEG 的主图像是彩色的，但 EXIF IFD1 中的缩略图却是灰度图，或者缩略图
分辨率偏低。文件管理器、图片浏览器通常会直接显示这张内嵌缩略图，于是看起来
就成了黑白/模糊的预览。

本脚本只重写 EXIF 中的缩略图，不会重新编码主图像；主图像的 JPEG 压缩数据、
XMP、ICC、Photoshop/IPTC 等其它元数据都会保留。默认用 Pillow 从主图像生成
彩色缩略图，再交给 exiftool 写回 EXIF IFD1。

默认行为
========
只处理以下缩略图：
  * 灰度/近似灰度；
  * 损坏、无法解码；
  * 文件大小超过 --max-bytes。

其它彩色缩略图默认跳过。需要统一重建时用 --all；需要给缺失缩略图的文件补上
时用 --add-missing；需要把短边不足 --min-side 的彩色缩略图也放大时用
--resize-small。

注意：EXIF APP1 段本身最大只有 65535 字节，因此缩略图实际会被限制在约
60 KiB 以内；--max-bytes 是更宽松的上限（默认 1 MiB）。

依赖
====
  * Python 3.9+
  * Pillow
  * exiftool（与仓库里的 sync_metadata.py 相同的外部依赖）

示例
====
  # 先看看会改哪些文件
  scripts/fix_thumbnail.py --dry-run -v 横 竖

  # 修复横/竖目录下所有黑白、损坏或过大的缩略图
  scripts/fix_thumbnail.py 横 竖

  # 重建所有已有的缩略图，并给没有缩略图的 JPEG 补上
  scripts/fix_thumbnail.py --all --add-missing --jobs 8 .

  # 只处理单个文件，并校验主图像压缩数据没有被改动
  scripts/fix_thumbnail.py --verify --all some.jpg

退出码
======
  0  成功（允许有跳过的文件）
  1  至少一个文件处理失败
  2  参数或依赖错误
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

try:
    from PIL import Image, ImageCms, ImageOps
except ImportError:  # pragma: no cover - 只在缺依赖时触发
    print("缺少依赖: Pillow（pip install pillow）", file=sys.stderr)
    sys.exit(2)

VERSION = "1.0"

SOI = b"\xff\xd8"
EXIF_HEADER = b"Exif\x00\x00"
JPEG_EXTS = {".jpg", ".jpeg", ".jpe", ".jfif"}

# EXIF APP1 段长度字段是 16 位，payload 最多 65533 字节。
EXIF_APP1_MAX = 65533
# 给 IFD 表、偏移调整等留出的安全余量。
EXIF_SAFETY = 2048
# 即使 --max-bytes 更大，也不要尝试写超过这个大小的缩略图。
DEFAULT_EXIF_THUMB_LIMIT = 60_000

DEFAULT_MIN_SIDE = 256
DEFAULT_MAX_BYTES = 1024 * 1024
DEFAULT_QUALITY = 90

# 缩略图中"有颜色"的像素比例低于该值时，视为灰度图。
# 有些软件会把灰度图存成 RGB，通道值几乎相等，所以不能只看 mode。
GRAY_COLOR_FRACTION = 0.01
# 通道最大值与最小值相差多少才算"有颜色"（0-255）。
COLOR_CHANNEL_DELTA = 8

RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS

SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", "node_modules"}


class ThumbError(Exception):
    """单个文件处理失败。"""


@dataclass
class JpegInfo:
    path: str
    has_exif: bool = False
    exif_payload_len: int = 0
    thumb_data: Optional[bytes] = None
    thumb_width: int = 0
    thumb_height: int = 0
    thumb_mode: str = ""
    gray: bool = True
    color_fraction: float = 0.0
    thumb_error: Optional[str] = None
    error: Optional[str] = None


@dataclass
class Options:
    all_thumbs: bool
    add_missing: bool
    resize_small: bool
    min_side: int
    max_bytes: int
    quality: int
    jobs: int
    dry_run: bool
    verify: bool
    color_manage: bool
    verbose: bool
    quiet: bool
    exiftool: str


@dataclass
class Result:
    status: str  # fixed / would / skipped / error
    path: str
    reason: str = ""
    detail: str = ""
    message: str = ""


# ---------------------------------------------------------------------------
# JPEG / EXIF 解析
# ---------------------------------------------------------------------------


def _read_exif_payload(path: str, max_scan: int = 64 << 20) -> Optional[bytes]:
    """读取第一个 EXIF APP1 段的 payload（含 b'Exif\\0\\0'）。

    只读到 SOS 为止；正常情况下 EXIF 都在文件头，不会读取整张图。
    """
    with open(path, "rb") as f:
        if f.read(2) != SOI:
            # 少数文件在 SOI 前有垃圾数据，允许在文件头里找一下。
            f.seek(0)
            head = f.read(1 << 16)
            pos = head.find(SOI)
            if pos < 0:
                raise ThumbError("不是 JPEG 文件")
            f.seek(pos + 2)

        consumed = 2
        while consumed < max_scan:
            prefix = f.read(1)
            if not prefix:
                return None
            consumed += 1
            if prefix != b"\xff":
                # 理论上不会走到这里；继续向后寻找 marker。
                continue

            marker = f.read(1)
            if not marker:
                return None
            consumed += 1
            while marker == b"\xff":
                marker = f.read(1)
                if not marker:
                    return None
                consumed += 1

            code = marker[0]
            # 无长度字段的 marker。
            if code == 0x00 or code == 0x01 or code == 0xD8 or code == 0xD9:
                continue
            if 0xD0 <= code <= 0xD7:
                continue

            length_bytes = f.read(2)
            if len(length_bytes) != 2:
                return None
            consumed += 2
            length = struct.unpack(">H", length_bytes)[0]
            if length < 2:
                return None

            payload = f.read(length - 2)
            consumed += length - 2
            if len(payload) != length - 2:
                return None

            if code == 0xE1 and payload.startswith(EXIF_HEADER):
                return payload
            if code == 0xDA:  # SOS
                return None

    return None


def _read_ifd(tiff: bytes, endian: str, offset: int) -> tuple[dict[int, tuple[int, int, bytes]], int]:
    """读取一个 TIFF IFD，返回 {tag: (type, count, value_field)} 和下一个 IFD 偏移。"""
    if offset < 0 or offset + 2 > len(tiff):
        raise ThumbError("IFD 偏移越界")
    count = struct.unpack(endian + "H", tiff[offset : offset + 2])[0]
    entries: dict[int, tuple[int, int, bytes]] = {}
    for i in range(count):
        pos = offset + 2 + i * 12
        if pos + 12 > len(tiff):
            raise ThumbError("IFD 条目越界")
        tag, typ, cnt = struct.unpack(endian + "HHI", tiff[pos : pos + 8])
        entries[tag] = (typ, cnt, tiff[pos + 8 : pos + 12])
    next_pos = offset + 2 + count * 12
    if next_pos + 4 > len(tiff):
        raise ThumbError("IFD 结束位置越界")
    next_offset = struct.unpack(endian + "I", tiff[next_pos : next_pos + 4])[0]
    return entries, next_offset


_TYPE_SIZES = {
    1: 1,  # BYTE
    2: 1,  # ASCII
    3: 2,  # SHORT
    4: 4,  # LONG
    5: 8,  # RATIONAL
    6: 1,  # SBYTE
    7: 1,  # UNDEFINED
    8: 2,  # SSHORT
    9: 4,  # SLONG
    10: 8,  # SRATIONAL
    11: 4,  # FLOAT
    12: 8,  # DOUBLE
}


def _tag_int(tiff: bytes, endian: str, entry: tuple[int, int, bytes]) -> Optional[int]:
    """把单值整数 tag 解析成 int，主要给 ThumbnailOffset/ThumbnailLength 用。"""
    typ, count, value_field = entry
    if count < 1:
        return None
    size = _TYPE_SIZES.get(typ, 1)
    total = size * count
    if total <= 4:
        raw = value_field[:total]
    else:
        offset = struct.unpack(endian + "I", value_field)[0]
        if offset < 0 or offset + total > len(tiff):
            return None
        raw = tiff[offset : offset + total]

    if typ in (1, 6, 7):
        return raw[0]
    if typ in (3, 8):
        if len(raw) < 2:
            return None
        return struct.unpack(endian + ("H" if typ == 3 else "h"), raw[:2])[0]
    if typ in (4, 9):
        if len(raw) < 4:
            return None
        return struct.unpack(endian + ("I" if typ == 4 else "i"), raw[:4])[0]
    return None


def _color_fraction(image: Image.Image) -> float:
    """估计图像中有颜色的像素比例（0.0 - 1.0）。"""
    if image.mode in {"1", "L", "I", "I;16", "I;16B", "I;16L", "F"}:
        return 0.0

    rgb = image.convert("RGB")
    rgb = rgb.resize((64, 64), getattr(Image, "Resampling", Image).BILINEAR)
    data = rgb.tobytes()
    colored = 0
    for i in range(0, len(data), 3):
        r, g, b = data[i], data[i + 1], data[i + 2]
        if max(r, g, b) - min(r, g, b) > COLOR_CHANNEL_DELTA:
            colored += 1
    return colored / (64 * 64)


def inspect_jpeg(path: str) -> JpegInfo:
    """检查 JPEG 主图像和 EXIF IFD1 缩略图。"""
    info = JpegInfo(path=path)
    try:
        payload = _read_exif_payload(path)
    except ThumbError as exc:
        info.error = str(exc)
        return info
    except OSError as exc:
        info.error = f"无法读取: {exc}"
        return info

    if payload is None:
        return info

    info.has_exif = True
    info.exif_payload_len = len(payload)
    tiff = payload[len(EXIF_HEADER) :]

    try:
        if len(tiff) < 8:
            raise ThumbError("EXIF TIFF 数据过短")
        if tiff[:2] == b"II":
            endian = "<"
        elif tiff[:2] == b"MM":
            endian = ">"
        else:
            raise ThumbError("未知的 EXIF 字节序")
        if struct.unpack(endian + "H", tiff[2:4])[0] != 42:
            raise ThumbError("EXIF TIFF 魔数不正确")
        ifd0_offset = struct.unpack(endian + "I", tiff[4:8])[0]
        _, ifd1_offset = _read_ifd(tiff, endian, ifd0_offset)
        if ifd1_offset == 0:
            return info
        ifd1, _ = _read_ifd(tiff, endian, ifd1_offset)
    except (ThumbError, struct.error):
        # 仓库里有一些文件的 EXIF 被截断/写坏（例如只剩 b"Exif\\0\\0"），
        # exiftool 仍能正常读取主图像。这里把它当作"没有可用缩略图"处理，
        # 默认跳过；只有显式 --add-missing 时才让 exiftool 尝试补一张。
        return info

    offset_entry = ifd1.get(0x0201)  # JPEGInterchangeFormat / ThumbnailOffset
    length_entry = ifd1.get(0x0202)  # JPEGInterchangeFormatLength / ThumbnailLength
    if offset_entry is None or length_entry is None:
        return info

    try:
        thumb_offset = _tag_int(tiff, endian, offset_entry)
        thumb_length = _tag_int(tiff, endian, length_entry)
        if thumb_offset is None or thumb_length is None or thumb_length <= 0:
            raise ThumbError("缩略图偏移/长度无效")
        if thumb_offset < 0 or thumb_offset + thumb_length > len(tiff):
            raise ThumbError("缩略图数据越界")
        thumb_data = tiff[thumb_offset : thumb_offset + thumb_length]
    except (ThumbError, struct.error) as exc:
        info.thumb_error = f"缩略图数据无效: {exc}"
        return info

    info.thumb_data = thumb_data
    try:
        with Image.open(io.BytesIO(thumb_data)) as thumb:
            thumb.load()
            info.thumb_width, info.thumb_height = thumb.size
            info.thumb_mode = thumb.mode
            info.color_fraction = _color_fraction(thumb)
        info.gray = info.thumb_mode in {"1", "L", "I", "I;16", "I;16B", "I;16L", "F"}
        info.gray = info.gray or info.color_fraction < GRAY_COLOR_FRACTION
    except Exception as exc:  # Pillow 对损坏 JPEG 会抛多种异常
        info.thumb_error = f"缩略图无法解码: {exc}"

    return info


# ---------------------------------------------------------------------------
# 缩略图生成
# ---------------------------------------------------------------------------


def _encode_jpeg(
    image: Image.Image,
    quality: int,
    budget: int,
    icc_profile: Optional[bytes],
) -> tuple[bytes, int]:
    """按质量从高到低编码，直到不超过 budget。"""
    start = max(1, min(100, quality))
    for q in range(start, 0, -2):
        buf = io.BytesIO()
        kwargs = dict(
            format="JPEG",
            quality=q,
            optimize=True,
            progressive=False,
            subsampling=2,
        )
        if icc_profile:
            kwargs["icc_profile"] = icc_profile
        image.save(buf, **kwargs)
        data = buf.getvalue()
        if len(data) <= budget:
            return data, q
    raise ThumbError(f"无法在 {budget} 字节以内生成缩略图")


def _exif_budget(info: JpegInfo, options: Options) -> int:
    """计算当前 EXIF 段还能容纳多少字节的缩略图。"""
    budget = min(options.max_bytes, DEFAULT_EXIF_THUMB_LIMIT)
    if info.has_exif:
        old_thumb_len = len(info.thumb_data) if info.thumb_data else 0
        base = max(0, info.exif_payload_len - old_thumb_len)
        budget = min(budget, EXIF_APP1_MAX - base - EXIF_SAFETY)
    if budget < 2048:
        raise ThumbError(
            f"EXIF 段已接近 64 KiB 上限，剩余空间仅 {max(0, budget)} 字节"
        )
    return budget


def make_thumbnail(
    path: str, info: JpegInfo, options: Options
) -> tuple[bytes, int, int, int, float]:
    """从主图像生成彩色缩略图。返回 (JPEG 数据, 宽, 高, 质量, 有颜色像素比例)。"""
    try:
        image = Image.open(path)
    except Exception as exc:
        raise ThumbError(f"无法打开主图像: {exc}") from exc

    with image:
        raw_w, raw_h = image.size
        if raw_w <= 0 or raw_h <= 0:
            raise ThumbError("主图像尺寸无效")

        # 对 JPEG 先用 draft 降低解码分辨率，避免处理超大图时占用过多内存。
        scale = options.min_side / min(raw_w, raw_h)
        draft_w = max(1, int(round(raw_w * scale * 2)))
        draft_h = max(1, int(round(raw_h * scale * 2)))
        try:
            image.draft("RGB", (draft_w, draft_h))
        except Exception:
            pass

        icc_profile = image.info.get("icc_profile")
        try:
            with warnings.catch_warnings():
                # 少数文件的 EXIF 被截断，Pillow 读取时会告警，但不影响主图像。
                warnings.filterwarnings("ignore", message="Corrupt EXIF data.*")
                image = ImageOps.exif_transpose(image)
        except Exception:
            pass

        width, height = image.size
        scale = options.min_side / min(width, height)
        target_w = max(1, int(round(width * scale)))
        target_h = max(1, int(round(height * scale)))
        if (target_w, target_h) != (width, height):
            image = image.resize((target_w, target_h), RESAMPLE)

        if image.mode != "RGB":
            image = image.convert("RGB")

        if options.color_manage and icc_profile:
            try:
                src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
                dst_profile = ImageCms.createProfile("sRGB")
                image = ImageCms.profileToProfile(
                    image, src_profile, dst_profile, outputMode="RGB"
                )
            except Exception:
                # 色彩配置损坏或不支持时退回普通 RGB，仍然能生成缩略图。
                pass

        source_color = _color_fraction(image)
        budget = _exif_budget(info, options)
        # EXIF 缩略图没有可靠的位置携带 ICC；默认在上面的步骤里转成 sRGB，
        # 不再把原图 ICC 塞进缩略图，避免 RGB/CMYK 配置不匹配。
        data, quality = _encode_jpeg(image, options.quality, budget, None)
        return data, target_w, target_h, quality, source_color


def _write_exif_thumbnail(
    path: str,
    thumb_data: bytes,
    width: int,
    height: int,
    options: Options,
) -> str:
    """用 exiftool 把缩略图写回 IFD1，返回 exiftool 的 stderr（没有则为空）。"""
    fd, thumb_path = tempfile.mkstemp(prefix="thumbfix-", suffix=".jpg")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(thumb_data)

        cmd = [
            options.exiftool,
            "-overwrite_original",
            "-quiet",
            f"-ThumbnailImage<={thumb_path}",
            f"-IFD1:ImageWidth#={width}",
            f"-IFD1:ImageHeight#={height}",
            "-IFD1:Orientation#=1",
            "-IFD1:Compression#=6",
            "-IFD1:PhotometricInterpretation#=6",
            "-IFD1:BitsPerSample#=8 8 8",
            "-IFD1:SamplesPerPixel#=3",
            "-IFD1:YCbCrSubSampling#=2 2",
            "-IFD1:SubfileType#=1",
            os.path.abspath(path),
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
        if proc.returncode != 0:
            message = (proc.stderr or proc.stdout or "").strip()
            raise ThumbError(f"exiftool 写入失败: {message or '退出码 ' + str(proc.returncode)}")
        return (proc.stderr or "").strip()
    finally:
        try:
            os.unlink(thumb_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 无损校验
# ---------------------------------------------------------------------------


def jpeg_scan_sha256(path: str) -> Optional[str]:
    """计算 JPEG 第一个 SOS 之后全部压缩数据的 SHA-256。

    ExifTool 只改元数据，这个哈希应当保持不变。
    """
    try:
        f = open(path, "rb")
    except OSError:
        return None

    with f:
        if f.read(2) != SOI:
            f.seek(0)
            head = f.read(1 << 16)
            pos = head.find(SOI)
            if pos < 0:
                return None
            f.seek(pos + 2)

        while True:
            prefix = f.read(1)
            if not prefix:
                return None
            if prefix != b"\xff":
                continue

            marker = f.read(1)
            if not marker:
                return None
            while marker == b"\xff":
                marker = f.read(1)
                if not marker:
                    return None

            code = marker[0]
            if code == 0x00 or code == 0x01 or code == 0xD8 or code == 0xD9:
                continue
            if 0xD0 <= code <= 0xD7:
                continue

            length_bytes = f.read(2)
            if len(length_bytes) != 2:
                return None
            length = struct.unpack(">H", length_bytes)[0]
            if length < 2:
                return None

            if code == 0xDA:
                if len(f.read(length - 2)) != length - 2:
                    return None
                digest = hashlib.sha256()
                while True:
                    chunk = f.read(1 << 20)
                    if not chunk:
                        break
                    digest.update(chunk)
                return digest.hexdigest()

            f.seek(length - 2, os.SEEK_CUR)


def _make_backup(path: str) -> Optional[str]:
    """为文件创建同目录硬链接备份。

    硬链接不占额外空间；exiftool 用"临时文件 + rename"覆盖原文件，因此备份
    仍然指向旧 inode，可以在失败时恢复。
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    backup = os.path.join(
        directory,
        f".{os.path.basename(path)}.thumbfix-{os.getpid()}-{uuid.uuid4().hex}.bak",
    )
    try:
        os.link(path, backup)
        return backup
    except OSError:
        return None


def _restore_backup(path: str, backup: Optional[str]) -> None:
    if backup and os.path.exists(backup):
        try:
            os.replace(backup, path)
        except OSError:
            pass


def _restore_stat(path: str, st: os.stat_result) -> None:
    try:
        os.chmod(path, stat.S_IMODE(st.st_mode))
    except OSError:
        pass
    try:
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 决策与单文件处理
# ---------------------------------------------------------------------------


def _needs_fix(info: JpegInfo, options: Options) -> Optional[str]:
    if info.error:
        return "error"
    if info.thumb_error:
        return "invalid"
    if info.thumb_data is None:
        return "missing" if options.add_missing else None
    if options.all_thumbs:
        return "all"
    if info.gray:
        return "gray"
    if len(info.thumb_data) > options.max_bytes:
        return "oversize"
    if options.resize_small and min(info.thumb_width, info.thumb_height) < options.min_side:
        return "undersized"
    return None


def _describe_thumb(info: JpegInfo) -> str:
    if info.thumb_data is None:
        return "无缩略图"
    return (
        f"{info.thumb_width}x{info.thumb_height} {info.thumb_mode} "
        f"{len(info.thumb_data) / 1024:.1f}KiB"
    )


def process_file(path: str, options: Options) -> Result:
    try:
        info = inspect_jpeg(path)
    except Exception as exc:
        return Result("error", path, message=f"检查失败: {exc}")

    reason = _needs_fix(info, options)
    if reason is None:
        return Result("skipped", path)
    if reason == "error":
        return Result("error", path, message=info.error or "EXIF 解析失败")

    if options.dry_run:
        return Result("would", path, reason=reason, detail=_describe_thumb(info))

    try:
        st = os.stat(path)
    except OSError as exc:
        return Result("error", path, message=f"无法获取文件状态: {exc}")

    backup = _make_backup(path)
    before_hash: Optional[str] = None
    if options.verify:
        before_hash = jpeg_scan_sha256(path)
        if before_hash is None:
            _restore_backup(path, backup)
            return Result("error", path, message="无法计算主图像压缩数据哈希")

    old_desc = _describe_thumb(info)
    try:
        thumb_data, width, height, quality, source_color = make_thumbnail(path, info, options)
        warning = _write_exif_thumbnail(path, thumb_data, width, height, options)

        # 写回后做一次自检。
        new_info = inspect_jpeg(path)
        if new_info.error:
            raise ThumbError(f"写回后 EXIF 无法解析: {new_info.error}")
        if new_info.thumb_error:
            raise ThumbError(f"写回后缩略图异常: {new_info.thumb_error}")
        if new_info.thumb_data is None:
            raise ThumbError("写回后没有找到缩略图")
        if (new_info.thumb_width, new_info.thumb_height) != (width, height):
            raise ThumbError(
                "写回后缩略图尺寸不符: "
                f"期望 {width}x{height}，实际 {new_info.thumb_width}x{new_info.thumb_height}"
            )
        if new_info.thumb_mode != "RGB":
            raise ThumbError(f"写回后缩略图不是彩色 RGB，而是 {new_info.thumb_mode}")
        if len(new_info.thumb_data) > options.max_bytes:
            raise ThumbError(
                f"写回后缩略图 {len(new_info.thumb_data)} 字节，超过 --max-bytes"
            )
        if source_color >= GRAY_COLOR_FRACTION and new_info.color_fraction < GRAY_COLOR_FRACTION:
            raise ThumbError("写回后缩略图仍然接近灰度")

        if options.verify:
            after_hash = jpeg_scan_sha256(path)
            if before_hash != after_hash:
                raise ThumbError("主图像压缩数据发生变化，已恢复原文件")

        _restore_stat(path, st)
        detail = (
            f"{old_desc} -> {width}x{height} RGB "
            f"{len(new_info.thumb_data) / 1024:.1f}KiB q{quality}"
        )
        if options.verify:
            detail += "，主图压缩数据未变"
        if warning and options.verbose:
            detail += f" ({warning})"
        return Result("fixed", path, reason=reason, detail=detail)
    except Exception as exc:
        _restore_backup(path, backup)
        return Result("error", path, message=str(exc))
    finally:
        if backup and os.path.exists(backup):
            try:
                os.unlink(backup)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# 文件收集与命令行
# ---------------------------------------------------------------------------


def iter_jpegs(paths: Sequence[str]) -> Iterable[str]:
    seen: set[str] = set()
    for raw in paths:
        path = os.path.abspath(raw)
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for name in sorted(files):
                    if os.path.splitext(name)[1].lower() in JPEG_EXTS:
                        full = os.path.join(root, name)
                        if full not in seen:
                            seen.add(full)
                            yield full
        elif os.path.isfile(path):
            if os.path.splitext(path)[1].lower() in JPEG_EXTS and path not in seen:
                seen.add(path)
                yield path
        elif not os.path.exists(path):
            print(f"路径不存在: {raw}", file=sys.stderr)


def parse_size(text: str) -> int:
    """解析 1M / 1MiB / 1024K / 1048576 这样的尺寸。"""
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([kmg]?i?b?)?\s*", text, re.I)
    if not match:
        raise argparse.ArgumentTypeError(f"无效的字节数: {text}")
    value = float(match.group(1))
    unit = (match.group(2) or "").lower()
    multipliers = {
        "": 1,
        "b": 1,
        "k": 1024,
        "kb": 1024,
        "kib": 1024,
        "m": 1024**2,
        "mb": 1024**2,
        "mib": 1024**2,
        "g": 1024**3,
        "gb": 1024**3,
        "gib": 1024**3,
    }
    return int(value * multipliers[unit])


def positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"无效的整数: {text}") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("必须大于 0")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        description=(
            "无损修复 JPEG 内嵌的 EXIF 缩略图：从主图像重新生成彩色缩略图，"
            "只改 IFD1，不重新编码主图像。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "默认只修复灰度、损坏或超过 --max-bytes 的缩略图。\n"
            "EXIF APP1 段最大约 64 KiB，缩略图实际会被限制在约 60 KiB 以内。\n\n"
            "示例:\n"
            f"  {os.path.basename(sys.argv[0])} --dry-run -v 横 竖\n"
            f"  {os.path.basename(sys.argv[0])} 横 竖\n"
            f"  {os.path.basename(sys.argv[0])} --all --add-missing -j 8 .\n"
        ),
    )
    parser.add_argument("paths", nargs="*", help="JPEG 文件或目录（默认当前目录）")
    parser.add_argument(
        "--all",
        dest="all_thumbs",
        action="store_true",
        help="重建所有已有缩略图，而不只处理黑白/损坏的",
    )
    parser.add_argument(
        "--add-missing",
        action="store_true",
        help="给没有 EXIF 缩略图的 JPEG 补上缩略图",
    )
    parser.add_argument(
        "--resize-small",
        action="store_true",
        help="连彩色但短边小于 --min-side 的缩略图也一并重建",
    )
    parser.add_argument(
        "--min-side",
        type=positive_int,
        default=DEFAULT_MIN_SIDE,
        metavar="N",
        help=f"缩略图最短边像素数（默认 {DEFAULT_MIN_SIDE}）",
    )
    parser.add_argument(
        "--max-bytes",
        type=parse_size,
        default=DEFAULT_MAX_BYTES,
        metavar="SIZE",
        help="缩略图最大字节数，支持 1M/1024K（默认 1MiB；仍受 EXIF 64KiB 限制）",
    )
    parser.add_argument(
        "--quality",
        type=positive_int,
        default=DEFAULT_QUALITY,
        metavar="N",
        help=f"JPEG 初始质量 1-100（默认 {DEFAULT_QUALITY}，超出限制时自动降低）",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=positive_int,
        default=max(1, min(32, os.cpu_count() or 1)),
        metavar="N",
        help="并行任务数（默认 CPU 核心数）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示会修改哪些文件，不写入",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="额外校验主图像压缩数据哈希未变化（会多读一遍文件）",
    )
    parser.add_argument(
        "--no-color-manage",
        dest="color_manage",
        action="store_false",
        help="不把主图像的 ICC 配置转换到 sRGB（默认会转换）",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="显示跳过的文件和详细信息",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="只显示错误",
    )
    parser.add_argument(
        "--exiftool",
        default=None,
        metavar="PATH",
        help="exiftool 可执行文件路径（默认从 PATH 查找）",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.quality > 100:
        parser.error("--quality 必须在 1-100 之间")
    if args.max_bytes < 2048:
        parser.error("--max-bytes 不能小于 2048")

    exiftool = args.exiftool or shutil.which("exiftool")
    if not exiftool:
        print("缺少依赖: exiftool", file=sys.stderr)
        return 2
    if not os.path.isfile(exiftool):
        # 允许 PATH 中的命令名，但传递给 subprocess 前确认可执行。
        exiftool = shutil.which(exiftool) or exiftool

    options = Options(
        all_thumbs=args.all_thumbs,
        add_missing=args.add_missing,
        resize_small=args.resize_small,
        min_side=args.min_side,
        max_bytes=args.max_bytes,
        quality=args.quality,
        jobs=args.jobs,
        dry_run=args.dry_run,
        verify=args.verify,
        color_manage=args.color_manage,
        verbose=args.verbose,
        quiet=args.quiet,
        exiftool=exiftool,
    )

    paths = args.paths or ["."]
    files = list(iter_jpegs(paths))
    if not files:
        if not options.quiet:
            print("没有找到 JPEG 文件。")
        return 0

    counts = {"fixed": 0, "would": 0, "skipped": 0, "error": 0}
    with ThreadPoolExecutor(max_workers=options.jobs) as pool:
        futures = {pool.submit(process_file, path, options): path for path in files}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:  # 理论上 process_file 已兜底
                path = futures[future]
                result = Result("error", path, message=f"未捕获异常: {exc}")

            counts[result.status] = counts.get(result.status, 0) + 1
            if result.status == "error":
                print(f"[错误] {result.path}: {result.message}", file=sys.stderr)
            elif result.status in {"fixed", "would"}:
                if not options.quiet:
                    prefix = "[预览]" if result.status == "would" else "[修复]"
                    print(
                        f"{prefix} {result.path} ({result.reason}) "
                        f"{result.detail}".rstrip()
                    )
            elif options.verbose and not options.quiet:
                print(f"[跳过] {result.path}")

    if not options.quiet:
        mode = "预览完成" if options.dry_run else "完成"
        print(
            f"{mode}: 扫描 {len(files)}，修复 {counts['fixed']}，"
            f"待修复 {counts['would']}，跳过 {counts['skipped']}，"
            f"错误 {counts['error']}"
        )

    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())

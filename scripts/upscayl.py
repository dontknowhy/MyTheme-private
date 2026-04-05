#!/usr/bin/env python3
"""
重写 `upscayl-dev.sh` 的 Python 版本骨架脚本（可 dry-run）。
功能：
 - 读取配置（默认与原脚本相同的目录变量）
 - 发现批次目录、统计图片、检查模型文件
 - 使用 subprocess 调用 upscayl-bin（支持异步读取 stdout 解析进度）
 - 提供 --dry-run 模式用于验证命令构造

注意：此为第一轮实现骨架，后续会加入并行复制、元数据同步、进度 UI 优化等。
"""

from __future__ import annotations
import argparse
import asyncio
import os
import re
import shutil
import signal
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor
import psutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

try:
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    from rich.console import Group
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# rich 进度相关全局
RICH_PROGRESS = None
RICH_SCRIPT_TASK = None
RICH_STAGE_TASK = None
RICH_LIVE = None
CURRENT_DIR_STR = "-"
CURRENT_MODEL_STR = "-"

# 默认配置（参考原脚本）
HOME = Path.home()
DOWNLOAD_DIR = Path(os.environ.get('DOWNLOAD_DIR', HOME / '下载'))
TEMP_1080_DIR = Path(os.environ.get('TEMP_1080_DIR', DOWNLOAD_DIR / 'temp-1080'))
TEMP_3K_DIR = Path(os.environ.get('TEMP_3K_DIR', DOWNLOAD_DIR / 'temp-3k'))
TEMP_POOR_DIR = Path(os.environ.get('TEMP_POOR_DIR', DOWNLOAD_DIR / 'temp-poor'))
FINAL_OUTPUT_DIR = Path(os.environ.get('FINAL_OUTPUT_DIR', DOWNLOAD_DIR / 'final'))
UPSCAYL_BIN = Path(os.environ.get('UPSCAYL_BIN', '/opt/Upscayl/resources/bin/upscayl-bin'))
MODELS_DIR = Path(os.environ.get('MODELS_DIR', HOME / 'custom-models' / 'models'))
FIRST_MODEL = os.environ.get('FIRST_MODEL', '1x_JPEGDestroyerV2_96000G-fp16')
SECOND_MODEL = os.environ.get('SECOND_MODEL', '4xNomos8kSC')
OUTPUT_FORMAT = os.environ.get('OUTPUT_FORMAT', 'png')
COMPRESSION_LEVEL = os.environ.get('COMPRESSION_LEVEL', '100')
THREADS = os.environ.get('THREADS', '1:2:2')

PCT_RE = re.compile(r"([0-9]{1,3}\.[0-9]{2})%")
SUCCESS_MARKER = "Upscayled Successfully!"

WARNINGS: List[str] = []
# 全局进度计数
TOTAL_WORK = 0
PROCESSED_WORK = 0
SCRIPT_START = int(time.time())
CURRENT_UPS_PROC: Optional[psutil.Process] = None

@dataclass
class RunStats:
    total_images: int = 0
    processed: int = 0


def check_and_create_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def is_supported_image(p: Path) -> bool:
    # 优先使用扩展名快速判断，再在可能时用 PIL 打开验证
    if p.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}:
        return False
    if PIL_AVAILABLE:
        try:
            with Image.open(p) as im:
                im.verify()
            return True
        except Exception:
            return False
    return True


def count_images(dirpath: Path) -> int:
    if not dirpath.exists():
        return 0
    return sum(1 for _ in dirpath.iterdir() if _.is_file() and is_supported_image(_))


def clean_model_name(name: str) -> str:
    import re
    return re.sub(r'[^a-zA-Z0-9._-]', '_', name)


def discover_batches(download_dir: Path) -> List[Path]:
    # 查找 temp*-1080，按数字排序
    batches = []
    for p in download_dir.iterdir():
        if not p.is_dir():
            continue
        if re.match(r'^temp(?:[0-9]*?)-1080$', p.name):
            batches.append(p)
    def keyfn(p: Path):
        m = re.match(r'^temp(?:([0-9]+))?-1080$', p.name)
        if not m:
            return 0
        num = m.group(1)
        return int(num) if num else 1
    return sorted(batches, key=keyfn)


def build_panel() -> Panel:
    # 构建动态面板，显示当前模型与剩余图片（不显示完整路径）
    info_lines = [Text(f"当前模型: {CURRENT_MODEL_STR}"), Text(f"剩余图片: {max(0, TOTAL_WORK - PROCESSED_WORK)}")]
    group = Group(*info_lines, RICH_PROGRESS)
    return Panel(group, box=box.ROUNDED, title="Upscayl 进度")


async def run_upscayl_async(input_dir: Path, output_dir: Path, model_name: str, stage: int = 1, dry_run: bool = False, stats: Optional[RunStats] = None) -> int:
    """调用 upscayl 二进制并异步解析其 stdout，识别百分比与成功标记。

    返回子进程退出码。
    """
    check_and_create_dir(output_dir)
    # 声明将在函数中修改的全局变量
    global CURRENT_UPS_PROC, PROCESSED_WORK
    cmd = [str(UPSCAYL_BIN), '-i', str(input_dir), '-o', str(output_dir), '-m', str(MODELS_DIR), '-n', model_name, '-f', OUTPUT_FORMAT, '-c', str(COMPRESSION_LEVEL), '-j', THREADS, '-v']
    if dry_run:
        print('Dry-run command:', ' '.join(cmd))
        return 0
    if not UPSCAYL_BIN.exists() or not os.access(UPSCAYL_BIN, os.X_OK):
        print(f"错误: Upscayl 可执行文件不可用: {UPSCAYL_BIN}")
        return 2

    # 启动子进程并记录用于后续 kill
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    # 记录 psutil 进程以便信号处理使用
    try:
        global CURRENT_UPS_PROC
        CURRENT_UPS_PROC = psutil.Process(proc.pid)
    except Exception:
        CURRENT_UPS_PROC = None
    start_ns = time.perf_counter_ns()
    last_reported = None
    processed_local = 0
    total_images = count_images(input_dir)
    if stats is not None:
        stats.total_images = total_images
    # 读取输出
    assert proc.stdout is not None
    # 不修改任务描述（保持左侧标签为“当前进度”/“整体进度”），只更新进度值
    try:
        pass
    except Exception:
        pass
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        try:
            text = line.decode('utf-8', errors='ignore').rstrip('\n')
        except Exception:
            text = str(line)
        # 尝试解析百分比
        m = PCT_RE.search(text)
        if m:
            last_reported = m.group(1)
            # 更新 rich 当前阶段进度（百分比）
            try:
                if RICH_PROGRESS is not None and RICH_STAGE_TASK is not None:
                    # RICH_STAGE_TASK 的 total 设为 100
                    RICH_PROGRESS.update(RICH_STAGE_TASK, completed=float(last_reported))
                    # 同步更新面板
                    if RICH_LIVE is not None:
                        try:
                            RICH_LIVE.update(build_panel())
                        except Exception:
                            pass
            except Exception:
                pass
        # 成功标志
        if SUCCESS_MARKER in text:
            processed_local += 1
            if stats is not None:
                stats.processed += 1
            # 更新全局计数（线程安全取决于 asyncio 单线程）
            PROCESSED_WORK += 1
            # 简短输出或 rich 更新
            try:
                if RICH_PROGRESS is not None and RICH_SCRIPT_TASK is not None:
                    RICH_PROGRESS.advance(RICH_SCRIPT_TASK, 1)
                    # 重置阶段进度
                    RICH_PROGRESS.update(RICH_STAGE_TASK, completed=0)
                    if RICH_LIVE is not None:
                        try:
                            RICH_LIVE.update(build_panel())
                        except Exception:
                            pass
            except Exception:
                pass
            print(f"[{model_name}] 处理完成单张，已处理 {processed_local}/{total_images} (阶段 {stage})")
        # 可选：打印或用 rich 更新 UI
        # print(text)
    ret = await proc.wait()
    # 清理 psutil 引用
    CURRENT_UPS_PROC = None
    return ret


def ensure_first_stage_done(batch_dir: Path, model: str, dry_run: bool = False) -> bool:
    model_clean = clean_model_name(model)
    first_out = batch_dir / f"upscayl_{OUTPUT_FORMAT}_{model_clean}"
    if count_images(first_out) > 0:
        print(f"第一次放大结果已存在: {first_out}")
        return True
    print(f"第一次放大结果缺失: {first_out}，将执行放大...")
    stats = RunStats()
    rc = asyncio.run(run_upscayl_async(batch_dir, first_out, model, stage=1, dry_run=dry_run, stats=stats))
    return rc == 0


def copy_images(src: Path, dst: Path):
    check_and_create_dir(dst)
    files = [p for p in src.iterdir() if p.is_file() and is_supported_image(p)]
    if not files:
        return
    def _copy(p: Path):
        try:
            shutil.copy2(p, dst / p.name)
            return True, p
        except Exception as e:
            return False, f"{p} -> {dst}: {e}"
    # 并行复制以加速大量文件拷贝
    with ThreadPoolExecutor(max_workers=8) as ex:
        for ok, info in ex.map(_copy, files):
            if not ok:
                WARNINGS.append(f"复制文件失败: {info}")


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='只打印将要执行的命令，不实际调用 upscayl')
    ap.add_argument('--download-dir', type=Path, default=DOWNLOAD_DIR)
    ap.add_argument('--upscayl-bin', type=Path, default=UPSCAYL_BIN)
    ap.add_argument('--models-dir', type=Path, default=MODELS_DIR)
    ap.add_argument('--first-model', default=FIRST_MODEL)
    ap.add_argument('--second-model', default=SECOND_MODEL)
    return ap.parse_args()


def main():
    args = parse_args()
    global DOWNLOAD_DIR, UPSCAYL_BIN, MODELS_DIR, FIRST_MODEL, SECOND_MODEL, CURRENT_DIR_STR, CURRENT_MODEL_STR, TOTAL_WORK
    DOWNLOAD_DIR = args.download_dir
    UPSCAYL_BIN = args.upscayl_bin
    MODELS_DIR = args.models_dir
    FIRST_MODEL = args.first_model
    SECOND_MODEL = args.second_model

    print('配置:')
    print(' DOWNLOAD_DIR=', DOWNLOAD_DIR)
    print(' UPSCAYL_BIN=', UPSCAYL_BIN)
    print(' MODELS_DIR=', MODELS_DIR)
    print(' FIRST_MODEL=', FIRST_MODEL)
    print(' SECOND_MODEL=', SECOND_MODEL)
    print(' OUTPUT_FORMAT=', OUTPUT_FORMAT)
    print('\n发现批次目录...')
    batches = discover_batches(DOWNLOAD_DIR)
    if not batches:
        print(f"错误: 未找到任何 temp*-1080 批次目录（在 {DOWNLOAD_DIR} 下）。")
        sys.exit(1)
    print(f"检测到批次数量: {len(batches)}，按序号处理。")

    # 检查 temp-3k
    if count_images(TEMP_3K_DIR) == 0:
        print(f"错误: 目录 {TEMP_3K_DIR} 中未检测到图片或目录不存在。")
        sys.exit(1)

    if not UPSCAYL_BIN.exists() or not os.access(UPSCAYL_BIN, os.X_OK):
        print(f"错误: Upscayl程序不可执行或不存在: {UPSCAYL_BIN}")
        sys.exit(1)

    # 检查模型文件
    param1 = MODELS_DIR / f"{FIRST_MODEL}.param"
    bin1 = MODELS_DIR / f"{FIRST_MODEL}.bin"
    if not param1.exists() or not bin1.exists():
        print(f"错误: FIRST_MODEL 文件缺失: {param1} 或 {bin1}")
        sys.exit(1)
    param2 = MODELS_DIR / f"{SECOND_MODEL}.param"
    bin2 = MODELS_DIR / f"{SECOND_MODEL}.bin"
    if not param2.exists() or not bin2.exists():
        print(f"错误: SECOND_MODEL 文件缺失: {param2} 或 {bin2}")
        sys.exit(1)

    # 注意：temp-poor 处理将在 rich 启动后执行（以便显示进度）

    # 统计 TOTAL_WORK
    poor_count = count_images(TEMP_POOR_DIR)
    temp3k_count = count_images(TEMP_3K_DIR)
    batch_count_sum = sum(count_images(b) for b in batches)
    TOTAL_WORK = poor_count + 2 * (temp3k_count + batch_count_sum)
    print(f"预计总处理单元: {TOTAL_WORK} (poor: {poor_count}, temp-3k: {temp3k_count}, temp*-1080: {batch_count_sum})")

    second_model_clean = clean_model_name(SECOND_MODEL)
    # 初始化 rich 进度（如可用）并启动 Live 面板
    global RICH_PROGRESS, RICH_SCRIPT_TASK, RICH_STAGE_TASK, RICH_LIVE
    if RICH_AVAILABLE:
        try:
            RICH_PROGRESS = Progress(TextColumn("{task.description}"), BarColumn(bar_width=None), TextColumn("{task.percentage:>3.0f}%"), TimeElapsedColumn(), expand=True)
            # 先添加阶段任务，再添加总体任务（使阶段显示在上方）
            RICH_STAGE_TASK = RICH_PROGRESS.add_task("当前进度", total=100)
            RICH_SCRIPT_TASK = RICH_PROGRESS.add_task("整体进度", total=TOTAL_WORK if TOTAL_WORK > 0 else None)
            RICH_LIVE = Live(build_panel(), refresh_per_second=4)
            RICH_LIVE.start()
        except Exception:
            RICH_PROGRESS = None
    total_main_images = 0
    try:
        for batch_dir in batches:
            print('\n=== 处理批次目录: {} ==='.format(batch_dir))
            # 设置当前信息并 ensure first stage
            CURRENT_DIR_STR = str(batch_dir)
            CURRENT_MODEL_STR = FIRST_MODEL
            # 尝试更新 Live
            try:
                if RICH_LIVE is not None:
                    RICH_LIVE.update(build_panel())
            except Exception:
                pass
            ok = ensure_first_stage_done(batch_dir, FIRST_MODEL, dry_run=args.dry_run)
            if not ok:
                WARNINGS.append(f"当前批次第一次放大失败并跳过: {batch_dir}")
                continue
            first_model_clean = clean_model_name(FIRST_MODEL)
            first_output_dir = batch_dir / f"upscayl_{OUTPUT_FORMAT}_{first_model_clean}"
            print(f"将 {TEMP_3K_DIR} 中的图片复制到 {first_output_dir}")
            copy_images(TEMP_3K_DIR, first_output_dir)
            if not all(is_supported_image(p) for p in first_output_dir.iterdir() if p.is_file()):
                WARNINGS.append(f"合并后的目录中包含非图片或为空: {first_output_dir}")
                continue
            second_output_dir = first_output_dir / f"upscayl_{OUTPUT_FORMAT}_{second_model_clean}"
            # 设置当前信息为合并后的目录与第二模型
            CURRENT_DIR_STR = str(first_output_dir)
            CURRENT_MODEL_STR = SECOND_MODEL
            try:
                if RICH_LIVE is not None:
                    RICH_LIVE.update(build_panel())
            except Exception:
                pass
            print(f"开始第二次放大: {first_output_dir} -> {second_output_dir}")
            rc = asyncio.run(run_upscayl_async(first_output_dir, second_output_dir, SECOND_MODEL, stage=2, dry_run=args.dry_run, stats=None))
            if rc != 0:
                WARNINGS.append(f"批次 {batch_dir} 第二次放大失败，跳过")
                continue
            print(f"复制批次结果到 {FINAL_OUTPUT_DIR}")
            copy_images(second_output_dir, FINAL_OUTPUT_DIR)
            batch_count = count_images(second_output_dir)
            total_main_images += batch_count
            print(f"批次放大后图像数: {batch_count}")
    except KeyboardInterrupt:
        print("\n[!] 中断：收到 Ctrl-C，正在退出...")
        sys.exit(130)

    overall_duration = 0
    print('\n=== 处理完成 ===')
    print(f"总共放大图片数量: {total_main_images}")
    if WARNINGS:
        print('\n=== 警告汇总 ===')
        for w in WARNINGS:
            print('-', w)
    # 不在此处停止 rich，保留直到 temp-poor 也处理完（以便显示进度）

    # 如果 temp-poor 在开始时存在，则在 rich 启动后处理它（以便显示进度）
    if count_images(TEMP_POOR_DIR) > 0:
        print('检测到 temp-poor（开始后处理），开始执行...')
        poor_model_clean = clean_model_name(FIRST_MODEL)
        poor_output = TEMP_POOR_DIR / f"upscayl_{OUTPUT_FORMAT}_{poor_model_clean}"
        # 设置当前信息
        CURRENT_DIR_STR = str(TEMP_POOR_DIR)
        CURRENT_MODEL_STR = FIRST_MODEL
        rc = asyncio.run(run_upscayl_async(TEMP_POOR_DIR, poor_output, FIRST_MODEL, stage=0, dry_run=args.dry_run, stats=None))
        if rc == 0:
            print('temp-poor 处理完成，复制结果到 final')
            copy_images(poor_output, FINAL_OUTPUT_DIR)
        else:
            print('警告: temp-poor 处理失败，跳过')

    # 停止 rich Live 与 Progress（如果在运行中）
    try:
        if RICH_LIVE is not None:
            RICH_LIVE.stop()
    except Exception:
        pass
    try:
        if RICH_PROGRESS is not None:
            RICH_PROGRESS.stop()
    except Exception:
        pass


def _signal_handler(signum, frame):
    print(f"\n[!] 收到信号 {signum}，正在尝试终止子进程...")
    try:
        if CURRENT_UPS_PROC is not None:
            # 递归结束子进程树
            for child in CURRENT_UPS_PROC.children(recursive=True):
                try:
                    child.kill()
                except Exception:
                    pass
            try:
                CURRENT_UPS_PROC.kill()
            except Exception:
                pass
    except Exception:
        pass
    sys.exit(130)


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


if __name__ == '__main__':
    main()

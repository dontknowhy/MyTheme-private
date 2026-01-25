#!/usr/bin/env python3
"""
同步文件夹中图片对的元数据。

此脚本会查找具有相同基础名称但可能不同扩展名的图片对，
例如 'image.jpg' 和 'image_cleanup.jpg'，然后将原始文件的
所有元数据（包括ICC配置文件）同步到其对应的清理/修改后的文件。
"""

import argparse
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
import threading

# --- 可配置项 ---
# 图片文件扩展名列表
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}
# 默认线程数为CPU核心数
DEFAULT_NUM_THREADS = os.cpu_count()
# --- 可配置项结束 ---

console = Console()

def find_image_pairs(directory_path):
    """
    在指定目录中查找图片对。
    
    Args:
        directory_path (str): 要扫描的目录路径。
        
    Returns:
        list: 包含 (original_file, modified_file) 元组的列表。
    """
    files = os.listdir(directory_path)
    file_paths = [Path(f) for f in files if Path(f).suffix.lower() in IMAGE_EXTENSIONS]
    
    # 分离原始文件和修改后的文件
    original_files = set()
    modified_files = set()
    
    for p in file_paths:
        stem = p.stem
        # 检查是否为修改后的文件 (以 _cleanup 结尾)
        if stem.endswith('_cleanup'):
            base_name = stem[:-len('_cleanup')]
            modified_files.add(p)
        else:
            # 尝试匹配模式，如 original -> original-test
            # 这里假设除了_cleanup外的其他变化形式也需要检查是否有原始对应文件
            # 更严格的逻辑是只看_cleanup，所以这里只处理_cleanup的情况
            # 其他如 114.jpg 和 114-test.jpg 需要明确规则，当前实现按描述处理
            # 根据描述，114.jpg -> 114-test.jpg，这意味着如果文件名不是以_cleanup结尾，
            # 它本身可能是原始文件。
            original_files.add(p)

    pairs = []
    for mod_file in modified_files:
        base_stem = mod_file.stem[:-len('_cleanup')] # 移除 '_cleanup'
        # 寻找任何具有相同基础名称的原始文件
        matching_originals = [f for f in original_files if f.stem == base_stem]
        if matching_originals:
            # 如果有多个匹配，选择第一个（可以根据需要调整策略）
            original_file = matching_originals[0]
            pairs.append((original_file, mod_file))
    
    # 处理非_cleanup的匹配，例如 114.jpg -> 114-test.jpg
    # 这意味着 114-test.jpg 是修改版，114.jpg 是原始版
    # 我们需要反向查找，看看哪个文件可能是另一个的修改版
    # 创建一个不含_cleanup后缀的字典来快速查找
    cleanup_to_orig_map = {}
    for mod_file in modified_files:
        base_stem = mod_file.stem[:-len('_cleanup')]
        cleanup_to_orig_map[base_stem] = mod_file
    
    # 遍历原始文件，看是否能找到对应的修改版
    temp_pairs = []
    remaining_originals = set(original_files)
    for orig_file in original_files:
        base_stem = orig_file.stem
        if base_stem in cleanup_to_orig_map:
            # 这种情况是 cleanup 文件找到了原始文件，已经在上面处理过了
            continue
        # 检查是否有其他文件以 base_stem 开头（例如，114.jpg 和 114-test.jpg）
        # 这种情况是原始文件找到了修改版
        for other_file in original_files:
            if other_file != orig_file:
                # 检查 other_file 是否以 orig_file.stem 开头，并且后面跟的是 '-', '_' 或类似字符
                # 例如: orig.stem='114', other.stem='114-test'
                if other_file.stem.startswith(orig_file.stem + '-') or other_file.stem.startswith(orig_file.stem + '_'):
                    # 这意味着 orig_file 是原始文件，other_file 是修改后的文件
                    # 检查这个other_file是否已经被配对过
                    if other_file not in [p[1] for p in pairs]:
                        temp_pairs.append((orig_file, other_file))
                        remaining_originals.discard(orig_file)
                        remaining_originals.discard(other_file)
                        break # 假设一个原始文件只有一个修改版，找到就跳出

    pairs.extend(temp_pairs)

    return pairs


def sync_metadata_pair(args):
    """
    同步一对图片的元数据。
    
    Args:
        args (tuple): 包含 (original_path, modified_path, directory_path) 的元组。
        
    Returns:
        tuple: (success: bool, original_path: str, modified_path: str, duration: float)
    """
    original_file, modified_file, directory_path = args
    start_time = time.time()
    
    try:
        # 构建完整的文件路径
        input_path = os.path.join(directory_path, original_file.name)
        output_path = os.path.join(directory_path, modified_file.name)

        # 执行 exiftool 命令
        cmd = [
            "exiftool", "-quiet", "-TagsFromFile", input_path,
            "-all:all", "-icc_profile", "-ignoreMinorErrors",
            "-overwrite_original", output_path
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        # 执行 touch 命令同步时间戳
        touch_cmd = ["touch", "-r", input_path, output_path]
        subprocess.run(touch_cmd, check=True)

        duration = time.time() - start_time
        return True, original_file.name, modified_file.name, duration
    except subprocess.CalledProcessError as e:
        console.log(f"[red]Error syncing {original_file} -> {modified_file}: {e}")
        duration = time.time() - start_time
        return False, original_file.name, modified_file.name, duration
    except Exception as e:
        console.log(f"[red]Unexpected error syncing {original_file} -> {modified_file}: {e}")
        duration = time.time() - start_time
        return False, original_file.name, modified_file.name, duration


def main():
    parser = argparse.ArgumentParser(description="Synchronize metadata between image pairs.")
    parser.add_argument('-j', '--jobs', type=int, default=DEFAULT_NUM_THREADS,
                        help=f'Number of parallel jobs (default: {DEFAULT_NUM_THREADS})')
    args = parser.parse_args()

    num_threads = args.jobs
    directory_path = os.getcwd()

    console.log(f"[green]Scanning directory:[/green] {directory_path}")
    console.log(f"[green]Using[/green] {num_threads} [green]threads for processing.[/green]")

    # Step 1: 查找图片对
    console.log("[blue]Step 1: Finding image pairs...[/blue]")
    start_scan_time = time.time()
    image_pairs = find_image_pairs(directory_path)
    scan_duration = time.time() - start_scan_time

    console.log(f"[green]Found {len(image_pairs)} image pairs to process.[/green] (Scan took {scan_duration:.2f}s)")

    if not image_pairs:
        console.log("[yellow]No image pairs found. Exiting.[/yellow]")
        return

    total_pairs = len(image_pairs)
    completed_tasks = 0
    failed_tasks = 0
    processed_durations = [] # 存储已完成任务的持续时间，用于ETA计算
    lock = threading.Lock() # 保护共享变量

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.2f}% ({completed}/{total})"),
        console=console,
        transient=False,
    )
    overall_task = progress.add_task("Processing...", total=total_pairs)

    def update_progress(success, orig_name, mod_name, duration):
        nonlocal completed_tasks, failed_tasks
        with lock:
            completed_tasks += 1
            if not success:
                failed_tasks += 1
            processed_durations.append(duration)
            progress.update(overall_task, advance=1, completed=completed_tasks)

    # 状态面板更新函数
    def update_status_panel():
        with lock:
            current_percentage = (completed_tasks / total_pairs) * 100 if total_pairs > 0 else 0
            current_stage = "同步数据" if completed_tasks > 0 else "查找图片"
            
            # 计算ETA
            avg_duration = sum(processed_durations) / len(processed_durations) if processed_durations else 0
            remaining_count = total_pairs - completed_tasks
            eta_seconds = avg_duration * remaining_count
            
            elapsed_total = time.time() - start_scan_time # 从开始扫描算起的总时间
            if eta_seconds > 0:
                 # 避免ETA显示负数或奇怪的格式
                eta_str = f"{eta_seconds//3600:02.0f}:{(eta_seconds%3600)//60:02.0f}:{eta_seconds%60:02.0f}"
            else:
                eta_str = "00:00:00"
            
            elapsed_str = f"{elapsed_total//3600:02.0f}:{(elapsed_total%3600)//60:02.0f}:{elapsed_total%60:02.0f}"

            status_text = (
                f"当前百分比: {current_percentage:.2f}%\n"
                f"当前阶段: {current_stage}\n"
                f"需要处理数量: {total_pairs}\n"
                f"已处理数量: {completed_tasks}\n"
                f"失败数量: {failed_tasks}\n"
                f"预计剩余时间: {eta_str}\n"
                f"已运行时间: {elapsed_str}"
            )
        return Panel(status_text, title="同步状态", border_style="blue")


    console.clear()
    # 使用 Rich.Live 来持续更新底部面板
    with Live(update_status_panel(), refresh_per_second=4, console=console) as live:
        # Step 2: 并行同步元数据
        console.log("[blue]Step 2: Synchronizing metadata...[/blue]")
        start_sync_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            # 准备任务参数
            tasks = [(pair[0], pair[1], directory_path) for pair in image_pairs]
            future_to_pair = {executor.submit(sync_metadata_pair, task): task for task in tasks}

            for future in as_completed(future_to_pair):
                success, orig_name, mod_name, duration = future.result()
                update_progress(success, orig_name, mod_name, duration)
                # 更新Live显示的面板
                live.update(update_status_panel())

    sync_duration = time.time() - start_sync_time
    total_duration = time.time() - start_scan_time

    # Step 3: 总结
    console.log("\n" + "="*40)
    console.log("[bold green]Summary:[/bold green]")
    console.log(f"- Total runtime: {total_duration:.2f} seconds")
    console.log(f"- Total items processed: {total_pairs}")
    console.log(f"- Successfully synced: {completed_tasks - failed_tasks}")
    console.log(f"- Failed: {failed_tasks}")
    console.log(f"- Average time per item: {sync_duration / completed_tasks:.2f} seconds" if completed_tasks > 0 else "- Average time per item: N/A (no items processed)")
    console.log("="*40)


if __name__ == "__main__":
    main()
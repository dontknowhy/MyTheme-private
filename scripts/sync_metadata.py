#!/usr/bin/env python3
"""
`sync_metadata.sh` 的 Python 重写版本。

保持原有逻辑:遍历当前(或指定)目录下的媒体文件,将原图的元数据
(EXIF/IPTC/XMP/ICC 等)与时间戳同步到同名的处理后文件上。

与原脚本的差异(修复项):
 - 不再依赖 GNU parallel,改用 ThreadPoolExecutor 并行;
 - 匹配使用的正则对文件名基底做了转义(原来基底中的正则元字符会被解释);
 - 同一输出被多个输入匹配时去重,只处理一次;
 - 任务以元组传递,文件名含 ':' 不再破坏解析。

依赖: exiftool(仅此一个外部工具)。
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

VERSION = "2.4"
PROG = os.path.basename(sys.argv[0])

MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".webp", ".heic"}

# input -> output 任务
Task = Tuple[str, str]


def show_help() -> str:
    return f"""元数据同步工具 v{VERSION}
在当前目录下同步文件元数据

用法: {PROG} [选项]

选项:
  -h, --help        显示帮助信息
  -j <NUM>          指定并行任务数 (默认: CPU核心数)
  -v, --verbose     显示详细输出

示例:
  {PROG} -j 8          # 使用8个线程处理当前目录
  {PROG} -v            # 显示详细处理信息
"""


@dataclass
class Params:
    work_dir: str
    jobs: int
    verbose: bool


def parse_args(argv: Sequence[str]) -> tuple[Params, int]:
    """解析命令行参数,返回 (参数, 退出码)。退出码为 None 表示继续执行。"""
    work_dir = os.getcwd()
    jobs = os.cpu_count() or 1
    verbose = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print(show_help(), end="")
            return Params(work_dir, jobs, verbose), 0
        elif arg == "-j":
            if i + 1 >= len(argv):
                print("未知选项: -j")
                return Params(work_dir, jobs, verbose), 1
            i += 1
            try:
                jobs = max(1, int(argv[i]))
            except ValueError:
                print(f"无效的任务数: {argv[i]}")
                return Params(work_dir, jobs, verbose), 1
        elif arg in ("-v", "--verbose"):
            verbose = True
        elif arg == "--version":
            print(f"版本: {VERSION}")
            return Params(work_dir, jobs, verbose), 0
        elif arg == "-d":
            if i + 1 >= len(argv):
                print("未知选项: -d")
                return Params(work_dir, jobs, verbose), 1
            i += 1
            work_dir = argv[i]
        else:
            print(f"未知选项: {arg}")
            return Params(work_dir, jobs, verbose), 1
        i += 1

    return Params(work_dir, jobs, verbose), None


def check_deps() -> None:
    """检查外部依赖。原脚本要求 exiftool 与 parallel,重写后仅需 exiftool。"""
    missing: List[str] = []
    if shutil.which("exiftool") is None:
        missing.append("exiftool")

    if missing:
        print("缺少依赖: " + " ".join(missing))
        sys.exit(1)


def find_media_files(work_dir: str) -> List[str]:
    """递归收集媒体文件,结果按(排序后的)完整路径返回。

    对应原脚本 `find "$WORK_DIR" -type f ... -print0 | sort -z`:
    不跟随符号链接,`-type f` 要求普通文件。
    """
    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(work_dir):
        del dirnames  # 需要递归,默认行为即可
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                mode = os.lstat(full).st_mode
            except OSError:
                continue
            if not stat.S_ISREG(mode):
                continue
            if os.path.splitext(name)[1].lower() in MEDIA_EXTS:
                files.append(full)
    files.sort()
    return files


def base_without_ext(name: str) -> str:
    """等价于 bash 的 `${name%.*}`:去掉最后一个点及其后面的部分。

    与 os.path.splitext 不同:`.jpg` 会得到空串而非 `.jpg`。
    """
    idx = name.rfind(".")
    return name[:idx] if idx >= 0 else name


def match_output_files(input_file: str, files: Sequence[str]) -> List[str]:
    """返回所有能与输入文件构成 "原图 -> 处理后文件" 关系的输出文件。

    匹配规则与原脚本一致(修复了正则转义):
      basename(out) 以 "<base>" 开头,其后为可选的 "-..." 或 "_..." 段,
      再跟一个点及扩展名;并跳过输入文件自身。
    """
    input_name = os.path.basename(input_file)
    base = base_without_ext(input_name)
    pattern = "^" + re.escape(base) + r"([-_].+)?\..+$"
    regex = re.compile(pattern, re.DOTALL)

    matches: List[str] = []
    for output_file in files:
        if output_file == input_file:
            continue
        if regex.match(os.path.basename(output_file)):
            matches.append(output_file)
    return matches


def generate_tasks(files: Sequence[str]) -> List[Task]:
    """生成任务列表并去重。

    原脚本会对每个输入重复扫描,且同一输出可被多个输入匹配,导致任务重复;
    这里按输出路径去重,保留首次出现的输入(结果确定)。
    """
    tasks: List[Task] = []
    seen: set[str] = set()
    for input_file in files:
        for output_file in match_output_files(input_file, files):
            if output_file in seen:
                continue
            seen.add(output_file)
            tasks.append((input_file, output_file))
    return tasks


def process_task(task: Task, verbose: bool) -> bool:
    """同步单个任务:存在性检查 -> exiftool 复制元数据 -> 复制时间戳。

    对应原脚本 process_task(exiftool 与 touch -r)。
    """
    input_file, output_file = task

    if not os.path.isfile(input_file) or not os.path.isfile(output_file):
        return False
    if verbose:
        print(f"处理: {input_file} → {output_file}")

    cmd = [
        "exiftool",
        "-quiet",
        "-TagsFromFile",
        input_file,
        "-all:all",
        "-icc_profile",
        "-ignoreMinorErrors",
        "-overwrite_original",
        output_file,
    ]
    subprocess.run(cmd, check=False)

    st = os.stat(input_file)
    os.utime(output_file, ns=(st.st_atime_ns, st.st_mtime_ns))
    return True


def main(argv: Optional[Sequence[str]] = None) -> int:
    check_deps()

    if argv is None:
        argv = sys.argv[1:]

    params, exit_code = parse_args(argv)
    if exit_code is not None:
        return exit_code

    files = find_media_files(params.work_dir)
    tasks = generate_tasks(files)
    task_count = len(tasks)
    jobs = params.jobs
    verbose = params.verbose

    if verbose:
        print(f"找到 {task_count} 个任务，使用 {jobs} 个线程处理")

    if not tasks:
        return 0

    done = 0
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(process_task, task, verbose) for task in tasks]
        for future in futures:
            future.result()
            done += 1
            sys.stderr.write(f"\r进度: {done}/{task_count}")
            sys.stderr.flush()
    if task_count:
        sys.stderr.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""Git pre-commit hook：图片文件夹编号检查 + 缩略图修复。

默认检查仓库中的 ``横``、``竖`` 两个文件夹（可在
``scripts/pre_commit_exceptions.json`` 中修改）：

* 去掉扩展名后必须是纯数字；
* 同一文件夹内编号不能重复，也不能有前导零；
* 默认要求编号从 1 开始连续排列；
* 例外文件写在每个文件夹自己的例外列表里；
* 默认拒绝超过 7 MiB 的暂存文件（按真正进入 commit 的 blob 大小）；
* 支持 linked worktree：共享 hooks 里的软链接会优先使用当前 worktree 的脚本和配置；
* worktree_overrides 可按 worktree 目录名或分支名覆盖 folders 等配置；
* 只对本次已暂存的 JPEG 运行 ``fix_thumbnail.py --verify``；
* 如果缩略图被修改，自动 ``git add`` 重新暂存，使修复进入本次提交。

这个脚本只使用 Python 标准库。缩略图修复本身仍然需要 Pillow 和 exiftool。
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

VERSION = "1.2"
DEFAULT_CONFIG = "scripts/pre_commit_exceptions.json"
DEFAULT_MAX_FILE_SIZE = 7 * 1024 * 1024
JPEG_SUFFIXES = {".jpg", ".jpeg"}
NUMBER_RE = re.compile(r"[0-9]+\Z")
BATCH_SIZE = 200


class HookError(Exception):
    """可以直接展示给用户的错误。"""


@dataclass(frozen=True)
class RepairConfig:
    enabled: bool
    script: Path
    python: str | None
    args: tuple[str, ...]


@dataclass(frozen=True)
class HookConfig:
    folders: tuple[str, ...]
    exceptions: dict[str, tuple[str, ...]]
    require_contiguous: bool
    max_file_size_bytes: int | None
    worktree_override: str | None
    repair: RepairConfig


# ---------------------------------------------------------------------------
# Git 辅助函数
# ---------------------------------------------------------------------------


def _run_git(
    root: Path,
    args: Sequence[str],
    *,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    command = ["git", *[str(arg) for arg in args]]
    try:
        proc = subprocess.run(
            command,
            cwd=str(root),
            check=False,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
    except OSError as exc:
        raise HookError(f"无法运行 git: {exc}") from exc

    if proc.returncode != 0:
        stderr = os.fsdecode(proc.stderr or b"").strip()
        detail = f": {stderr}" if stderr else ""
        raise HookError(f"git {' '.join(command[1:])} 失败{detail}")
    return proc


def _git_z(root: Path, *args: str) -> list[str]:
    proc = _run_git(root, args)
    return [os.fsdecode(item) for item in (proc.stdout or b"").split(b"\0") if item]


def _git_text(root: Path, *args: str) -> str:
    proc = _run_git(root, args)
    return os.fsdecode(proc.stdout or b"").strip()


def _find_root() -> Path:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=os.getcwd(),
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise HookError(f"无法运行 git: {exc}") from exc

    if proc.returncode != 0:
        raise HookError("当前目录不在 Git 仓库中")
    return Path(os.fsdecode(proc.stdout).strip())


def _ensure_worktree_script(root: Path) -> Path:
    """如果当前 worktree 里有自己的脚本，就切换过去。

    共享的 .git/hooks 里可以放一个指向主 worktree 脚本的软链接。
    这样在主 worktree 里运行的是主脚本，在其它 worktree 里则优先运行
    该 worktree 自己的 scripts/pre_commit.py；如果没有，再回退到主脚本。
    """
    script_path = Path(__file__).resolve()
    current_script = (root / "scripts" / "pre_commit.py").resolve()

    if (
        current_script.is_file()
        and current_script != script_path
        and os.environ.get("PRE_COMMIT_REEXEC") != "1"
    ):
        os.environ["PRE_COMMIT_REEXEC"] = "1"
        python = sys.executable or shutil.which("python3") or "python3"
        try:
            os.execv(
                python,
                [python, str(current_script), *sys.argv[1:]],
            )
        except OSError as exc:
            raise HookError(
                f"无法切换到当前 worktree 的脚本 {current_script}: {exc}"
            ) from exc

    return script_path


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------


def _normalize_folder(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise HookError(f"{where}: 文件夹名必须是字符串")
    folder = value.strip().strip("/")
    if not folder:
        raise HookError(f"{where}: 文件夹名不能为空")
    path = PurePosixPath(folder)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise HookError(f"{where}: 非法文件夹名: {value!r}")
    return path.as_posix()


def _resolve_path_with_fallback(
    root: Path,
    fallback_root: Path,
    value: str,
) -> Path:
    """优先当前 worktree，其次运行脚本所在的 worktree。"""
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()

    bases = [root]
    if fallback_root != root:
        bases.append(fallback_root)
    for base in bases:
        candidate = base / path
        if candidate.is_file():
            return candidate.resolve()
    return (root / path).resolve()


def load_config(
    root: Path,
    config_arg: str,
    fallback_root: Path | None = None,
) -> HookConfig:
    fallback_root = fallback_root or root
    config_path = _resolve_path_with_fallback(root, fallback_root, config_arg)

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        hint = ""
        if fallback_root != root:
            fallback_config = Path(config_arg).expanduser()
            if not fallback_config.is_absolute():
                fallback_config = fallback_root / fallback_config
            if fallback_config != config_path:
                hint = f"（也查找过 {fallback_config}）"
        raise HookError(f"找不到配置文件: {config_path}{hint}") from None
    except json.JSONDecodeError as exc:
        raise HookError(f"配置文件不是合法 JSON: {config_path}: {exc}") from None
    except OSError as exc:
        raise HookError(f"无法读取配置文件: {config_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise HookError("配置文件顶层必须是 JSON 对象")

    raw_overrides = payload.get("worktree_overrides", {})
    if raw_overrides is None:
        raw_overrides = {}
    if not isinstance(raw_overrides, dict):
        raise HookError("配置项 worktree_overrides 必须是 JSON 对象")

    for key, value in raw_overrides.items():
        if not isinstance(key, str) or not key:
            raise HookError("worktree_overrides 的键必须是非空字符串")
        if not isinstance(value, dict):
            raise HookError(f"worktree_overrides[{key!r}] 必须是 JSON 对象")

    branch = ""
    try:
        branch = _git_text(root, "branch", "--show-current")
    except HookError:
        pass

    worktree_keys = [root.name]
    if branch and branch not in worktree_keys:
        worktree_keys.append(branch)

    override_name: str | None = None
    override: dict | None = None
    for key in worktree_keys:
        candidate = raw_overrides.get(key)
        if candidate is not None:
            override_name = key
            override = candidate
            break

    if override is not None:
        # 覆盖配置是浅合并；如果只换了 folders，默认清掉旧文件夹的例外。
        merged = {**payload, **override}
        override_folders = override.get("folders")
        if (
            "folders" in override
            and "exceptions" not in override
            and isinstance(override_folders, list)
        ):
            old_exceptions = payload.get("exceptions", {})
            if isinstance(old_exceptions, dict):
                merged["exceptions"] = {
                    folder: old_exceptions[folder]
                    for folder in override_folders
                    if isinstance(folder, str) and folder in old_exceptions
                }
            else:
                merged["exceptions"] = {}
        if (
            isinstance(override.get("repair"), dict)
            and isinstance(payload.get("repair"), dict)
        ):
            merged["repair"] = {**payload["repair"], **override["repair"]}
        payload = merged

    raw_folders = payload.get("folders")
    if not isinstance(raw_folders, list) or not raw_folders:
        raise HookError("配置项 folders 必须是非空数组")

    folders: list[str] = []
    for item in raw_folders:
        folder = _normalize_folder(item, "folders")
        if folder in folders:
            raise HookError(f"folders 中有重复文件夹: {folder}")
        folders.append(folder)

    raw_exceptions = payload.get("exceptions", {})
    if not isinstance(raw_exceptions, dict):
        raise HookError("配置项 exceptions 必须是 JSON 对象")

    exceptions: dict[str, tuple[str, ...]] = {folder: () for folder in folders}
    seen_exception_folders: set[str] = set()
    for raw_folder, raw_patterns in raw_exceptions.items():
        folder = _normalize_folder(raw_folder, "exceptions")
        if folder not in exceptions:
            raise HookError(f"exceptions 中的文件夹不在 folders 里: {raw_folder!r}")
        if folder in seen_exception_folders:
            raise HookError(f"exceptions 中文件夹重复: {folder}")
        seen_exception_folders.add(folder)

        if not isinstance(raw_patterns, list):
            raise HookError(f"exceptions[{folder!r}] 必须是数组")
        patterns: list[str] = []
        for pattern in raw_patterns:
            if not isinstance(pattern, str) or not pattern:
                raise HookError(f"exceptions[{folder!r}] 中有非法的例外文件名")
            patterns.append(pattern)
        exceptions[folder] = tuple(patterns)

    require_contiguous = payload.get("require_contiguous", True)
    if not isinstance(require_contiguous, bool):
        raise HookError("配置项 require_contiguous 必须是 true 或 false")

    raw_max_size = payload.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE)
    if raw_max_size is None:
        max_file_size_bytes = None
    elif (
        isinstance(raw_max_size, bool)
        or not isinstance(raw_max_size, int)
        or raw_max_size <= 0
    ):
        raise HookError("配置项 max_file_size_bytes 必须是正整数或 null")
    else:
        max_file_size_bytes = raw_max_size

    raw_repair_script = payload.get("repair_script", "scripts/fix_thumbnail.py")
    if not isinstance(raw_repair_script, str) or not raw_repair_script:
        raise HookError("配置项 repair_script 必须是非空字符串")
    repair_script = _resolve_path_with_fallback(
        root,
        fallback_root,
        raw_repair_script,
    )

    raw_repair = payload.get("repair", {})
    if not isinstance(raw_repair, dict):
        raise HookError("配置项 repair 必须是 JSON 对象")

    enabled = raw_repair.get("enabled", True)
    if not isinstance(enabled, bool):
        raise HookError("repair.enabled 必须是 true 或 false")

    python = raw_repair.get("python")
    if python is not None and (not isinstance(python, str) or not python):
        raise HookError("repair.python 必须是 null 或非空字符串")
    if python and ("/" in python or os.sep in python):
        python_path = Path(python).expanduser()
        if not python_path.is_absolute():
            python = str(
                _resolve_path_with_fallback(root, fallback_root, python)
            )

    raw_args = raw_repair.get("args", ["--verify"])
    if not isinstance(raw_args, list) or any(not isinstance(arg, str) for arg in raw_args):
        raise HookError("repair.args 必须是字符串数组")
    args = list(raw_args)
    if enabled and "--verify" not in args:
        # 用户要求修复时必须校验主图，不允许配置里漏掉。
        args.insert(0, "--verify")

    return HookConfig(
        folders=tuple(folders),
        exceptions=exceptions,
        require_contiguous=require_contiguous,
        max_file_size_bytes=max_file_size_bytes,
        worktree_override=override_name,
        repair=RepairConfig(
            enabled=enabled,
            script=repair_script,
            python=python,
            args=tuple(args),
        ),
    )


# ---------------------------------------------------------------------------
# 文件名检查
# ---------------------------------------------------------------------------


def _index_names(root: Path, folder: str) -> list[str]:
    """返回暂存区中该文件夹第一层的文件名。"""
    prefix = folder + "/"
    names: list[str] = []
    nested: list[str] = []

    for path in _git_z(root, "ls-files", "-z", "--", folder):
        if path == folder or not path.startswith(prefix):
            continue
        rest = path[len(prefix) :]
        if "/" in rest:
            nested.append(path)
        else:
            names.append(rest)

    if nested:
        preview = "、".join(nested[:5])
        more = " 等" if len(nested) > 5 else ""
        raise HookError(
            f"{folder}: 检测到子目录文件，当前脚本只检查文件夹第一层: {preview}{more}"
        )
    return sorted(names)


def _is_exception(filename: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(filename, pattern) for pattern in patterns)


def _check_folder(
    folder: str,
    names: Sequence[str],
    patterns: Sequence[str],
    require_contiguous: bool,
) -> tuple[list[str], str]:
    errors: list[str] = []
    exceptions = [name for name in names if _is_exception(name, patterns)]
    regular = [name for name in names if not _is_exception(name, patterns)]

    by_number: dict[int, list[str]] = {}
    for filename in regular:
        base, extension = os.path.splitext(filename)
        if not NUMBER_RE.fullmatch(base):
            errors.append(f"{folder}/{filename}: 去掉后缀后不是纯数字（{base!r}）")
            continue

        try:
            number = int(base)
        except ValueError:
            errors.append(f"{folder}/{filename}: 编号过大，无法解析")
            continue
        if number < 1:
            errors.append(f"{folder}/{filename}: 编号必须从 1 开始")
            continue
        if base != str(number):
            errors.append(
                f"{folder}/{filename}: 不要使用前导零，应命名为 {number}{extension}"
            )
        by_number.setdefault(number, []).append(filename)

    for number, group in sorted(by_number.items()):
        if len(group) > 1:
            errors.append(f"{folder}: 编号 {number} 重复: {'、'.join(group)}")

    if require_contiguous and by_number:
        maximum = max(by_number)
        missing_count = maximum - len(by_number)
        if missing_count:
            # 不直接 range(1, maximum+1)：如果误命名为一个很大的数，
            # 那样会卡住 hook。这里只按已存在的编号找前 20 个缺口。
            missing_preview: list[int] = []
            previous = 0
            for number in sorted(by_number):
                gap = number - previous - 1
                if gap > 0:
                    take = min(gap, 20 - len(missing_preview))
                    missing_preview.extend(range(previous + 1, previous + 1 + take))
                previous = number
                if len(missing_preview) >= 20:
                    break
            preview = "、".join(str(number) for number in missing_preview)
            more = (
                f" …（共 {missing_count} 个）"
                if missing_count > len(missing_preview)
                else ""
            )
            errors.append(f"{folder}: 编号不连续，缺少 {preview}{more}")

    if by_number:
        summary = (
            f"{folder}: {len(by_number)} 个编号 "
            f"（{min(by_number)}..{max(by_number)}）"
        )
        if len(by_number) != len(regular):
            summary += f"，{len(regular) - len(by_number)} 个文件有命名问题"
    else:
        summary = f"{folder}: 0 个编号"

    if exceptions:
        summary += f"，例外 {len(exceptions)}"
    return errors, summary


# ---------------------------------------------------------------------------
# 缩略图修复
# ---------------------------------------------------------------------------


def _resolve_python(root: Path, configured: str | None) -> str:
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_absolute() or "/" in configured:
            if not candidate.is_absolute():
                candidate = root / candidate
            if not candidate.is_file():
                raise HookError(f"repair.python 不存在: {candidate}")
            return str(candidate)

        found = shutil.which(configured)
        if not found:
            raise HookError(f"找不到 repair.python: {configured}")
        return found

    env_python = os.environ.get("THUMBFIX_PYTHON")
    if env_python:
        return _resolve_python(root, env_python)

    return sys.executable


def _repair_env(python: str) -> dict[str, str]:
    """让 conda/venv 里的 exiftool 也能被修复脚本找到。"""
    env = os.environ.copy()
    bin_dir = str(Path(python).resolve().parent)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    return env


def _check_repair_env(python: str, env: dict[str, str]) -> None:
    check = subprocess.run(
        [python, "-c", "import PIL"],
        cwd=os.getcwd(),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        detail = (check.stderr or "").strip()
        raise HookError(
            "缩略图修复环境缺少 Pillow。\n"
            f"使用的 Python: {python}\n"
            "可以激活安装了 Pillow 的环境，或设置 THUMBFIX_PYTHON 指向该环境的 Python。"
            + (f"\n{detail}" if detail else "")
        )

    exiftool = shutil.which("exiftool", path=env.get("PATH"))
    if not exiftool:
        raise HookError(
            "找不到 exiftool。请安装 exiftool，或激活包含 exiftool 的环境后再提交。"
        )


def _staged_files(root: Path) -> list[str]:
    return _git_z(
        root,
        "diff",
        "--cached",
        "--name-only",
        "-z",
        "--diff-filter=ACMR",
        "--",
    )


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


def _staged_blob_sizes(root: Path, paths: Sequence[str]) -> dict[str, int]:
    """返回暂存区里这些文件的实际 blob 大小。

    使用暂存区内容而不是工作区文件，这样部分暂存时检查的也是真正会
    进入 commit 的版本。
    """
    if not paths:
        return {}

    wanted = set(paths)
    sha_by_path: dict[str, str] = {}
    for item in _git_z(root, "ls-files", "-s", "-z", "--"):
        try:
            meta, path = item.split("\t", 1)
        except ValueError:
            continue
        fields = meta.split()
        if len(fields) != 3:
            continue
        mode, sha, stage = fields
        if stage != "0" or path not in wanted:
            continue
        # 普通文件和可执行文件才检查大小；符号链接/子模块不参与。
        if mode not in {"100644", "100755"}:
            continue
        sha_by_path[path] = sha

    if not sha_by_path:
        return {}

    unique_shas = sorted(set(sha_by_path.values()))
    try:
        proc = subprocess.run(
            ["git", "cat-file", "--batch-check"],
            cwd=str(root),
            check=False,
            input="\n".join(unique_shas) + "\n",
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        raise HookError(f"无法读取暂存文件大小: {exc}") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or "").strip()
        raise HookError(f"读取暂存文件大小失败: {detail}")

    sizes: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[1] == "blob":
            sizes[fields[0]] = int(fields[2])

    missing = [sha for sha in unique_shas if sha not in sizes]
    if missing:
        raise HookError("读取暂存文件大小失败：有文件无法解析")

    return {path: sizes[sha] for path, sha in sha_by_path.items()}


def _check_staged_sizes(
    root: Path,
    paths: Sequence[str],
    limit: int | None,
) -> list[str]:
    if limit is None:
        return []

    sizes = _staged_blob_sizes(root, paths)
    errors: list[str] = []
    for path in paths:
        size = sizes.get(path)
        if size is not None and size > limit:
            errors.append(f"{path}（{_format_size(size)}）")
    return errors


def _is_direct_child(path: str, folder: str) -> bool:
    return PurePosixPath(path).parent.as_posix() == folder


def _staged_jpegs(root: Path, staged: Iterable[str], folders: Sequence[str]) -> list[str]:
    result: list[str] = []
    for path in staged:
        pure = PurePosixPath(path)
        if pure.suffix.lower() not in JPEG_SUFFIXES:
            continue
        if not any(_is_direct_child(path, folder) for folder in folders):
            continue

        full_path = root / path
        if full_path.is_symlink():
            print(f"[hook] 跳过符号链接: {path}", file=sys.stderr)
            continue
        if not full_path.is_file():
            raise HookError(f"暂存图片在工作区不存在: {path}")
        result.append(path)
    return sorted(result)


def _chunks(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _unstaged_for(root: Path, paths: Sequence[str]) -> list[str]:
    changed: list[str] = []
    for batch in _chunks(paths, BATCH_SIZE):
        changed.extend(
            _git_z(root, "diff", "--name-only", "-z", "--", *batch)
        )
    return sorted(set(changed))


def _repair_staged(root: Path, config: HookConfig, paths: Sequence[str]) -> None:
    if not config.repair.enabled:
        print("[hook] 缩略图修复已禁用，跳过。")
        return
    if not paths:
        print("[hook] 没有暂存的 JPEG，跳过缩略图修复。")
        return
    if not config.repair.script.is_file():
        raise HookError(f"找不到缩略图修复脚本: {config.repair.script}")

    python = _resolve_python(root, config.repair.python)
    env = _repair_env(python)
    _check_repair_env(python, env)

    unstaged = _unstaged_for(root, paths)
    if unstaged:
        print(
            "[hook] 以下暂存图片还有未暂存修改，拒绝自动修复以免覆盖：",
            file=sys.stderr,
        )
        for path in unstaged:
            print(f"  {path}", file=sys.stderr)
        print(
            "[hook] 请先 git add 这些文件，或提交/还原未暂存修改后再提交。",
            file=sys.stderr,
        )
        raise HookError("存在未暂存修改")

    total_changed = 0
    for batch in _chunks(paths, BATCH_SIZE):
        print(f"[hook] 检查 {len(batch)} 张暂存图片的缩略图...")
        command = [
            python,
            str(config.repair.script),
            *config.repair.args,
            *batch,
        ]
        proc = subprocess.run(command, cwd=str(root), env=env, check=False)
        if proc.returncode != 0:
            raise HookError(
                f"缩略图修复脚本失败（退出码 {proc.returncode}），提交已中止"
            )

        changed = _git_z(root, "diff", "--name-only", "-z", "--", *batch)
        if changed:
            _run_git(root, ["add", "--", *changed])
            print("[hook] 已修复并重新暂存：")
            for path in changed:
                print(f"  {path}")
            total_changed += len(changed)

    if total_changed:
        print(f"[hook] 共重新暂存 {total_changed} 张图片的缩略图。")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="检查横/竖文件夹编号和暂存文件大小，并修复本次暂存 JPEG 的缩略图。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  scripts/pre_commit.py --no-repair   # 只检查文件名和大小\n"
            "  scripts/pre_commit.py -v            # 显示例外文件\n"
            "  THUMBFIX_PYTHON=/path/to/python scripts/pre_commit.py\n"
        ),
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"例外列表配置文件（默认 {DEFAULT_CONFIG}）",
    )
    parser.add_argument(
        "--no-repair",
        action="store_true",
        help="只做文件名和大小检查，不运行缩略图修复",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="显示每个文件夹的例外文件",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # 让 hook 自己的输出和 fix_thumbnail.py 子进程的输出保持顺序。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)
        except (AttributeError, ValueError):
            pass

    try:
        root = _find_root()
        script_path = _ensure_worktree_script(root)
        script_root = script_path.parent.parent
        config = load_config(root, args.config, script_root)

        if args.verbose and config.worktree_override:
            print(f"[hook] 使用 worktree 覆盖配置: {config.worktree_override}")

        all_errors: list[str] = []
        for folder in config.folders:
            names = _index_names(root, folder)
            errors, summary = _check_folder(
                folder,
                names,
                config.exceptions.get(folder, ()),
                config.require_contiguous,
            )
            if errors:
                all_errors.extend(errors)
            else:
                print(f"[hook] {summary}")

            if args.verbose:
                for pattern in config.exceptions.get(folder, ()):
                    print(f"[hook] {folder} 例外: {pattern}")

        if all_errors:
            print("[hook] 文件名检查失败：", file=sys.stderr)
            for error in all_errors[:100]:
                print(f"  - {error}", file=sys.stderr)
            if len(all_errors) > 100:
                print(
                    f"  ... 还有 {len(all_errors) - 100} 条错误",
                    file=sys.stderr,
                )
            return 1

        staged = _staged_files(root)
        size_errors = _check_staged_sizes(
            root,
            staged,
            config.max_file_size_bytes,
        )
        if size_errors:
            limit = config.max_file_size_bytes
            limit_text = _format_size(limit) if limit is not None else "?"
            print(
                f"[hook] 文件大小超过限制（{limit_text}）：",
                file=sys.stderr,
            )
            for error in size_errors:
                print(f"  - {error}", file=sys.stderr)
            return 1

        if args.no_repair:
            print("[hook] --no-repair: 已跳过缩略图修复。")
        elif not config.repair.enabled:
            print("[hook] 缩略图修复已在配置中禁用，跳过。")
        else:
            jpegs = _staged_jpegs(root, staged, config.folders)
            _repair_staged(root, config, jpegs)

    except HookError as exc:
        print(f"[hook] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("[hook] 已取消。", file=sys.stderr)
        return 130

    print("[hook] 检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/bin/bash

# 配置默认参数
WORK_DIR=$(pwd)
JOBS=$(nproc)
VERBOSE=0
VERSION="2.3"

show_help() {
    cat <<EOF
元数据同步工具 v${VERSION}
在当前目录下同步文件元数据

用法: $0 [选项]

选项:
  -h, --help        显示帮助信息
  -j <NUM>          指定并行任务数 (默认: CPU核心数)
  -v, --verbose     显示详细输出

示例:
  $0 -j 8          # 使用8个线程处理当前目录
  $0 -v            # 显示详细处理信息
EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)   show_help; exit 0 ;;
        -j)          JOBS="$2"; shift 2 ;;
        -v|--verbose) VERBOSE=1; shift ;;
        --version)   echo "版本: $VERSION"; exit 0 ;;
        -d)       WORK_DIR="$2"; shift 2 ;;
        *)          echo "未知选项: $1"; exit 1 ;;
    esac
done

check_deps() {
    local missing=()
    ! command -v exiftool &> /dev/null && missing+=("exiftool")
    ! command -v parallel &> /dev/null && missing+=("parallel")
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "缺少依赖: ${missing[*]}"
        exit 1
    fi
}

# 文件名匹配核心逻辑
match_output_files() {
    local input_file="$1"
    local input_name
    input_name=$(basename "$input_file")
    local input_base="${input_name%.*}"
    local base_pattern="^${input_base}([-_].+)?\..+$"
    
    find "$WORK_DIR" -type f \( \
        -iname "*.jpg" -o \
        -iname "*.jpeg" -o \
        -iname "*.png" -o \
        -iname "*.tiff" -o \
        -iname "*.webp" -o \
        -iname "*.heic" \
    \) -print0 | 
    while IFS= read -r -d '' output_file; do
        [[ "$output_file" == "$input_file" ]] && continue
        [[ "$(basename "$output_file")" =~ $base_pattern ]] && printf "%s\0" "$output_file"
    done
}

generate_tasks() {
    find "$WORK_DIR" -type f \( \
        -iname "*.jpg" -o \
        -iname "*.jpeg" -o \
        -iname "*.png" -o \
        -iname "*.tiff" -o \
        -iname "*.webp" -o \
        -iname "*.heic" \
    \) -print0 |
    while IFS= read -r -d '' input_file; do
        while IFS= read -r -d '' output_file; do
            [[ -n "$output_file" ]] && echo "${input_file}:${output_file}"
        done < <(match_output_files "$input_file")
    done
}

process_task() {
    local input="$1"
    local output="$2"
    
    [[ ! -f "$input" || ! -f "$output" ]] && return 1
    [[ $VERBOSE -eq 1 ]] && echo "处理: $input → $output"
    
    exiftool -quiet -TagsFromFile "$input" -all:all -icc_profile -ignoreMinorErrors -overwrite_original "$output"
    touch -r "$input" "$output"
}

export -f process_task

# 主流程
check_deps
task_list=$(generate_tasks)

[[ $VERBOSE -eq 1 ]] && echo "找到 $(echo "$task_list" | grep -c '[^[:space:]]') 个任务，使用 $JOBS 个线程处理"

echo "$task_list" | parallel --colsep ':' \
    -j "$JOBS" \
    --eta \
    --progress \
    --tagstring "{2}" \
    'process_task {1} {2}'
#!/bin/bash

# 配置默认参数
WORK_DIR=$(pwd)
JOBS=$(nproc)
VERBOSE=0
VERSION="2.4"

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

# 优化的文件查找和缓存函数
find_media_files() {
    find "$WORK_DIR" -type f \( \
        -iname "*.jpg" -o \
        -iname "*.jpeg" -o \
        -iname "*.png" -o \
        -iname "*.tiff" -o \
        -iname "*.webp" -o \
        -iname "*.heic" \
    \) -print0 | sort -z  # 添加排序以提高后续匹配效率
}

generate_tasks() {
    local temp_file
    temp_file=$(mktemp)
    
    find_media_files | while IFS= read -r -d '' input_file; do
        match_output_files "$input_file" >> "$temp_file"
    done
    
    cat "$temp_file"
    rm -f "$temp_file"
}

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
    \) -print0 | while IFS= read -r -d '' output_file; do
        [[ "$output_file" == "$input_file" ]] && continue
        if [[ "$(basename "$output_file")" =~ $base_pattern ]]; then
            echo "${input_file}:${output_file}"
        fi
    done
}

# 优化的任务处理函数
process_task() {
    local input="$1"
    local output="$2"
    
    # 添加文件检查
    [[ ! -f "$input" || ! -f "$output" ]] && return 1
    [[ $VERBOSE -eq 1 ]] && echo "处理: $input → $output"
    
    exiftool -quiet -TagsFromFile "$input" -all:all -icc_profile -ignoreMinorErrors -overwrite_original "$output"
    touch -r "$input" "$output"
}

# 批处理函数
process_batch() {
    local batch="$1"
    while IFS=: read -r input output; do
        process_task "$input" "$output"
    done <<< "$batch"
}

export -f process_task
export -f process_batch
export VERBOSE

# 优化的主流程
main() {
    check_deps
    
    # 生成任务列表并计算总数
    local task_list
    task_list=$(generate_tasks)
    local task_count
    task_count=$(echo "$task_list" | grep -c '[^[:space:]]')
    
    [[ $VERBOSE -eq 1 ]] && echo "找到 $task_count 个任务，使用 $JOBS 个线程处理"
    
    # 修改并行处理方式
    echo "$task_list" | parallel --will-cite \
        -j "$JOBS" \
        --progress \
        --bar \
        --colsep ':' \
        'process_task {1} {2}'
}

main
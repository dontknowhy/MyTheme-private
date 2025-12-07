#!/bin/bash

# ===============================================
# 用户配置区域 - 请根据实际情况修改这些变量
# ===============================================

# 文件夹配置
DOWNLOAD_DIR="$HOME/下载"                 # 下载文件夹路径
TEMP_1080_DIR="$DOWNLOAD_DIR/temp-1080" # 第一次处理图片目录
TEMP_3K_DIR="$DOWNLOAD_DIR/temp-3k"     # 待合并处理图片目录
TEMP_POOR_DIR="$DOWNLOAD_DIR/temp-poor" # 低质量图片处理目录（可选）
FINAL_OUTPUT_DIR="$DOWNLOAD_DIR/final"  # 最终输出目录

# 程序配置
UPSCAYL_BIN="/opt/Upscayl/resources/bin/upscayl-bin" # upscayl程序路径
MODELS_DIR="$HOME/custom-models/models"              # 模型目录

# 模型配置
FIRST_MODEL="1x_JPEGDestroyerV2_96000G-fp16" # 第一次放大模型
SECOND_MODEL="4xNomos8kSC"                   # 第二次放大模型

# 程序参数配置
OUTPUT_FORMAT="png"   # 输出格式
COMPRESSION_LEVEL=100 # 压缩级别
THREADS="1:2:2"       # 线程配置

# ===============================================
# 函数定义
# ===============================================

# 检查目录是否存在，不存在则创建
check_and_create_dir() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        echo "创建目录: $dir"
        mkdir -p "$dir"
    fi
}

# 检查文件是否为支持的图片格式
is_supported_image() {
    local file="$1"
    case "${file,,}" in
        *.jpg|*.jpeg|*.png|*.webp|*.bmp|*.tif|*.tiff)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# 检查模型文件是否存在
check_model() {
    local model_name="$1"
    local param_file="$MODELS_DIR/${model_name}.param"
    local bin_file="$MODELS_DIR/${model_name}.bin"

    if [ ! -f "$param_file" ]; then
        echo "错误: 模型参数文件不存在: $param_file"
        return 1
    fi

    if [ ! -f "$bin_file" ]; then
        echo "错误: 模型二进制文件不存在: $bin_file"
        return 1
    fi

    echo "模型检查通过: $model_name"
    return 0
}

draw_progress_box() {
    local cur_img_pct=$1
    local cur_img_elapsed=$2
    local stage_pct=$3
    local stage_elapsed=$4
    local stage=$5
    local script_pct=${6:-"0.00"}
    local script_elapsed=${7:-"0秒"}
    local current_dir=${8:-"-"}
    local model_name=${9:-"-"}

    local cols lines
    if command -v tput >/dev/null 2>&1; then
        cols=$(tput cols 2>/dev/null || echo 80)
        lines=$(tput lines 2>/dev/null || echo 24)
    else
        cols=80
        lines=24
    fi
    # 清理可能的空格与前导零，确保十进制整数（避免 082 之类被当作八进制）
    cols=$(echo "$cols" | tr -d '[:space:]')
    lines=$(echo "$lines" | tr -d '[:space:]')
    local box_h=9
    local box_w=$((10#${cols:-80}))
    local start_row=$((10#${lines:-24} - box_h))
    clear # 清理屏幕，防止终端堆得跟史一样。debug时记得注释掉
    local interior_w=$((box_w - 2))
    local bar_margin=2
    local content_w=$((interior_w - bar_margin * 2))
    if [ $content_w -lt 20 ]; then content_w=20; fi
    local cur_pct_display="${cur_img_pct}%"
    local stage_pct_display="${stage_pct}%"
    local script_pct_display="${script_pct}%"
    # 统一检测UTF-8，非UTF-8降级为ASCII
    local use_utf8=0
    if [ "${LANG:-}" != "" ] && echo "$LANG" | grep -qi utf-8; then use_utf8=1; fi
    local img_bar stage_bar script_bar
    img_bar=$(render_bar "${cur_img_pct:-0}" "${content_w:-20}")
    stage_bar=$(render_bar "${stage_pct:-0}" "${content_w:-20}")
    script_bar=$(render_bar "${script_pct:-0}" "${content_w:-20}")
    # 保存光标
    if command -v tput >/dev/null 2>&1; then tput sc; fi
    if command -v tput >/dev/null 2>&1; then tput cup $start_row 0; fi
    for i in $(seq 1 $box_h); do printf '%*s\n' "$box_w" ''; done
    if command -v tput >/dev/null 2>&1; then tput cup $start_row 0; fi
    # 顶部边框
    if [ $use_utf8 -eq 1 ]; then
        printf '╭%*s╮\n' $((box_w - 2)) "" | sed 's/ /─/g'
    else
        printf '+%*s+\n' $((box_w - 2)) "" | sed 's/ /-/g'
    fi
    local line1="当前: ${cur_pct_display}"
    printf '| %-*s|\n' "$interior_w" "$line1"
    local bar_line1; bar_line1="$(printf '%*s' $bar_margin '')${img_bar}"
    printf '| %-*s|\n' "$interior_w" "$bar_line1"
    local line3="阶段: ${stage_pct_display}"
    printf '| %-*s|\n' "$interior_w" "$line3"
    local bar_line2; bar_line2="$(printf '%*s' $bar_margin '')${stage_bar}"
    printf '| %-*s|\n' "$interior_w" "$bar_line2"
    local line5="脚本总体: ${script_pct_display}"
    printf '| %-*s|\n' "$interior_w" "$line5"
    local bar_line3; bar_line3="$(printf '%*s' $bar_margin '')${script_bar}"
    printf '| %-*s|\n' "$interior_w" "$bar_line3"
    local line7="脚本用时: ${script_elapsed}  阶段用时: ${stage_elapsed}  阶段: ${stage}  目录: ${current_dir}  模型: ${model_name}"
    printf '| %-*s|\n' "$interior_w" "$line7"
    if [ $use_utf8 -eq 1 ]; then
        printf '╰%*s╯\n' $((box_w - 2)) "" | sed 's/ /─/g'
    else
        printf '+%*s+\n' $((box_w - 2)) "" | sed 's/ /-/g'
    fi
    if command -v tput >/dev/null 2>&1; then tput rc; fi
}

# 清理模型名称中的特殊字符（用于文件夹命名）
clean_model_name() {
    local model_name="$1"
    # 只保留字母、数字、下划线、点、减号，其他全部替换为下划线
    echo "$model_name" | sed 's#[^a-zA-Z0-9._-]#_#g'
}

# 检查目录中所有文件是否都是受支持的图片格式
check_all_images() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        echo "错误: 目录不存在: $dir"
        return 1
    fi
    # 统计所有文件数
    local total_files
    total_files=$(find "$dir" -maxdepth 1 -type f | wc -l)
    # 统计受支持图片文件数
    local image_files
    image_files=$(find "$dir" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" \) | wc -l)
    if [ "$total_files" -eq 0 ]; then
        echo "错误: 目录 $dir 中没有文件"
        return 1
    fi
    if [ "$total_files" -ne "$image_files" ]; then
        echo "错误: 目录 $dir 中包含非图片文件"
        return 1
    fi
    return 0
}

# 格式化秒数为“XX小时XX分XX秒”
format_duration() {
    local seconds=$1
    local h m s
    h=$((seconds / 3600))
    m=$((seconds % 3600 / 60))
    s=$((seconds % 60))
    local out=""
    if [ $h -gt 0 ]; then out+="${h}小时"; fi
    if [ $m -gt 0 ]; then out+="${m}分"; fi
    out+="${s}秒"
    echo "$out"
}

# 渲染进度条（独立函数，不能嵌套）
render_bar() {
    local pct="${1:-0}"
    local width="${2:-20}"
    local pct_centi
    if [[ $pct == *.* ]]; then
        pct_centi=${pct//./}
    else
        pct_centi=$((pct * 100))
    fi
    # 使用 10# 前缀强制十进制，避免以 0 开头的数字被当作八进制导致错误（例如 "082"）
    local filled_count=$(( (10#${pct_centi:-0} * 10#${width:-20}) / 10000 ))
    local empty_count=$(( 10#${width:-20} - filled_count ))
    local filled=""
    local empty=""
    local use_utf8=0
    if [ "${LANG:-}" != "" ] && echo "$LANG" | grep -qi utf-8; then use_utf8=1; fi
    local bar_filled bar_empty
    if [ $use_utf8 -eq 1 ]; then
        bar_filled="█"
        bar_empty="─"
    else
        bar_filled="#"
        bar_empty="-"
    fi
    if [ "$filled_count" -gt 0 ] 2>/dev/null; then
        printf -v filled '%*s' "$filled_count" ''
        filled=${filled// /$bar_filled}
    fi
    if [ "$empty_count" -gt 0 ] 2>/dev/null; then
        printf -v empty '%*s' "$empty_count" ''
        empty=${empty// /$bar_empty}
    fi
    printf "%s%s" "$filled" "$empty"
}

# 执行放大操作并在终端底部显示进度框
# 调用: run_upscayl input_dir output_dir model_name [stage]
run_upscayl() {
    local input_dir="$1"
    local output_dir="$2"
    local model_name="$3"
    local stage=${4:-1}
    local overall_start=$(date +%s)
    # 记录毫秒级起始时间，用于短暂冷静期比较
    local overall_start_ms
    overall_start_ms=$(date +%s%3N)

    echo "开始放大操作..."
    echo "输入目录: $input_dir"
    echo "输出目录: $output_dir"
    echo "使用模型: $model_name"

    check_and_create_dir "$output_dir"

    # 计算待处理图片总数（该阶段内）
    local total_images
    total_images=$(count_images "$input_dir")
    if [ -z "$total_images" ] || [ "$total_images" -eq 0 ]; then
        echo "警告: 输入目录没有图片: $input_dir"
        total_images=0
    fi

    # 状态变量
    local processed=0
    local cur_pct="0.00"
    local last_reported_centi=-100000
    local per_image_start
    per_image_start=$(date +%s)

    # 启动期忽略 upscayl 启动时的初始噪声输出（秒）
    # 使用毫秒整数比较以避免浮点/科学计数问题
    local warmup_secs=0.2
    local warmup_ms
    warmup_ms=$(awk -v s="$warmup_secs" 'BEGIN{printf "%d", s*1000}')
    local warmup_until_ms=$(( overall_start_ms + warmup_ms ))

    # 使用 coproc 运行 upscayl，主 shell 读取其输出（避免 subshell 导致变量不可见）
    coproc UPSCAYL_PROC { stdbuf -oL "$UPSCAYL_BIN" -i "$input_dir" -o "$output_dir" -m "$MODELS_DIR" -n "$model_name" -f "$OUTPUT_FORMAT" -c "$COMPRESSION_LEVEL" -j "$THREADS" -v 2>&1; }
    UPS_PID=$!

    # 初始显示一次（避免启动期不停重绘）
    # 计算脚本总体进度（基于全局 TOTAL_WORK / PROCESSED_WORK）
    local script_pct_str="0.00"
    local script_elapsed_str
    if [ "$TOTAL_WORK" -gt 0 ]; then
        local script_centi=$(( PROCESSED_WORK * 10000 / TOTAL_WORK ))
        local script_whole=$(( script_centi / 100 ))
        local script_frac=$(( script_centi % 100 ))
        script_pct_str="${script_whole}.$(printf '%02d' "$script_frac")"
    fi
    script_elapsed_str="$(format_duration $(( $(date +%s) - SCRIPT_START )))"
    draw_progress_box "$cur_pct" "$(format_duration 0)" "0.00" "$(format_duration 0)" "$stage" "$script_pct_str" "$script_elapsed_str" "$input_dir" "$model_name"

    # 非阻塞读取输出并解析
    while true; do
        # 尝试读取一行，超时 0.2s
        if [ -n "${UPSCAYL_PROC[0]:-}" ]; then
            # 只在文件描述符存在时读取，避免无效FD错误
            if read -t 0.2 -u "${UPSCAYL_PROC[0]}" line 2>/dev/null; then
                : # 成功读取，下面的逻辑会处理
            else
                # 读取超时或失败，继续到后续进程检查
                line=""
                read_status=1
            fi
        else
            # coproc 未正确建立，避免尝试无效的文件描述符
            line=""
            read_status=1
        fi
        if [ -n "${line}" ]; then
                local now_ms
                now_ms=$(date +%s%3N)
                local in_warmup=0
                if [ "$now_ms" -lt "$warmup_until_ms" ]; then
                    in_warmup=1
                fi
            # 解析百分比（形如 0.00% 或 100.00%），取第一个匹配
            if [[ $line =~ ([0-9]{1,3}\.[0-9]{2})% ]]; then
                local val=${BASH_REMATCH[1]}
                local val_centi=${val//./}
                if [ $in_warmup -eq 1 ]; then
                    # 启动期忽略，但记录以防止后续剧烈跳变
                    last_reported_centi=$val_centi
                else
                    if [ $last_reported_centi -eq -100000 ]; then
                        # 首次有效值，直接接受
                        cur_pct="$val"
                        last_reported_centi=$val_centi
                    else
                            # 强制十进制防止前导0导致八进制解析错误
                            local diff=$(( 10#${val_centi:-0} - 10#${last_reported_centi:-0} ))
                            if [ $diff -lt 0 ]; then diff=$(( -diff )); fi
                        # 50% -> 50.00 -> 5000 centi
                        if [ $diff -le 5000 ]; then
                            cur_pct="$val"
                            last_reported_centi=$val_centi
                        else
                            # 略过异常跳变
                            :
                        fi
                    fi
                fi
            fi

            # 检测成功标志
            if [[ $line == *"🙌 Upscayled Successfully!"* ]]; then
                # 视为一张图处理完成
                processed=$((processed + 1))
                # 更新脚本总体已处理计数
                PROCESSED_WORK=$((PROCESSED_WORK + 1))
                cur_pct="100.00"
                # 更新框显示
                local now
                now=$(date +%s)
                local per_elapsed=$(( now - per_image_start ))
                local overall_elapsed=$(( now - overall_start ))
                local overall_centi=0
                if [ $total_images -gt 0 ]; then
                    overall_centi=$(( processed * 10000 / total_images ))
                fi
                local overall_whole=$(( overall_centi / 100 ))
                local overall_frac=$(( overall_centi % 100 ))
                local overall_pct_str
                overall_pct_str="${overall_whole}.$(printf '%02d' "$overall_frac")"
                # 计算脚本总体百分比
                local script_pct_str2="0.00"
                if [ "$TOTAL_WORK" -gt 0 ]; then
                    local script_centi2=$(( PROCESSED_WORK * 10000 / TOTAL_WORK ))
                    local script_whole2=$(( script_centi2 / 100 ))
                    local script_frac2=$(( script_centi2 % 100 ))
                    script_pct_str2="${script_whole2}.$(printf '%02d' "$script_frac2")"
                fi
                local script_elapsed2="$(format_duration $(( now - SCRIPT_START )))"
                draw_progress_box "$cur_pct" "$(format_duration $per_elapsed)" "$overall_pct_str" "$(format_duration $overall_elapsed)" "$stage" "$script_pct_str2" "$script_elapsed2" "$input_dir" "$model_name"
                # 短暂显示 100%，然后重置
                sleep 0.25
                cur_pct="0.00"
                per_image_start=$(date +%s)
            fi

            local now2
            now2=$(date +%s)
            local per_elapsed2=$(( now2 - per_image_start ))
            local overall_elapsed2=$(( now2 - overall_start ))
            local overall_centi2=0
            if [ $total_images -gt 0 ]; then
                overall_centi2=$(( processed * 10000 / total_images ))
            fi
            local overall_whole2=$(( overall_centi2 / 100 ))
            local overall_frac2=$(( overall_centi2 % 100 ))
            local overall_pct_str2
            overall_pct_str2="${overall_whole2}.$(printf '%02d' "$overall_frac2")"
            # 如果仍在启动期，跳过频繁绘制
            if [ $in_warmup -eq 0 ]; then
                # 计算脚本总体百分比
                local script_pct_str3="0.00"
                if [ "$TOTAL_WORK" -gt 0 ]; then
                    local script_centi3=$(( PROCESSED_WORK * 10000 / TOTAL_WORK ))
                    local script_whole3=$(( script_centi3 / 100 ))
                    local script_frac3=$(( script_centi3 % 100 ))
                    script_pct_str3="${script_whole3}.$(printf '%02d' "$script_frac3")"
                fi
                local script_elapsed3="$(format_duration $(( now2 - SCRIPT_START )))"
                draw_progress_box "$cur_pct" "$(format_duration $per_elapsed2)" "$overall_pct_str2" "$(format_duration $overall_elapsed2)" "$stage" "$script_pct_str3" "$script_elapsed3" "$input_dir" "$model_name"
            fi
        else
            # 没有新行可读或读取失败，检查进程是否仍在运行
            if ! kill -0 "$UPS_PID" 2>/dev/null; then
                break
            fi
            # 等待短暂间隔再继续循环
            sleep 0.1
        fi
    done

    # 等待进程结束，收集退出码
    wait "$UPS_PID"
    local exit_code=$?
    # coproc清理：关闭文件描述符，杀死子进程，避免内存泄漏
    if [ -n "${UPSCAYL_PROC[0]:-}" ]; then
        exec {UPSCAYL_PROC[0]}>&- 2>/dev/null
    fi
    if [ -n "${UPSCAYL_PROC[1]:-}" ]; then
        exec {UPSCAYL_PROC[1]}>&- 2>/dev/null
    fi
    if kill -0 "$UPS_PID" 2>/dev/null; then
        kill "$UPS_PID" 2>/dev/null
    fi
    local final_now=$(date +%s)
    local final_per_elapsed=$((final_now - per_image_start))
    local final_overall_elapsed=$((final_now - overall_start))
    # final overall percent string with two decimals
    local final_overall_centi=0
    if [ $total_images -gt 0 ]; then
        final_overall_centi=$(( processed * 10000 / total_images ))
    fi
    local final_overall_whole=$((final_overall_centi / 100))
    local final_overall_frac=$((final_overall_centi % 100))
    local final_overall_pct_str
    final_overall_pct_str="${final_overall_whole}.$(printf '%02d' "$final_overall_frac")"
    draw_progress_box "0.00" "$(format_duration $final_per_elapsed)" "$final_overall_pct_str" "$(format_duration $final_overall_elapsed)" "$stage"
    local final_overall_pct_str="${final_overall_whole}.$(printf '%02d' $final_overall_frac)"
    draw_progress_box "0.00" "$(format_duration $final_per_elapsed)" "$final_overall_pct_str" "$(format_duration $final_overall_elapsed)" "$stage"

    if [ $exit_code -eq 0 ]; then
        echo "放大操作完成，用时: $(format_duration $(($(date +%s) - overall_start)))"
        return 0
    else
        echo "错误: 放大操作失败，退出码: $exit_code"
        return 1
    fi
}

# 统计目录中的图片数量（安全处理空格/特殊字符/大文件量）
count_images() {
    local dir="$1"
    if command -v find >/dev/null 2>&1; then
        find "$dir" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" -o -iname "*.bmp" -o -iname "*.tif" -o -iname "*.tiff" \) | wc -l
    else
        local count=0
        for file in "$dir"/*; do
            if [ -f "$file" ] && is_supported_image "$file"; then
                count=$((count + 1))
            fi
        done
        echo $count
    fi
}

check_dir_has_images() {
  local dir="$1"

  # 参数校验
  if [ -z "$dir" ]; then
    return 1
  fi

  # 目录必须存在且为目录
  if [ ! -d "$dir" ]; then
    return 1
  fi

  # 首选使用 find（可处理奇怪的文件名/空格）
  if command -v find >/dev/null 2>&1; then
    if find "$dir" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" -o -iname "*.bmp" -o -iname "*.tif" -o -iname "*.tiff" \) -print -quit | grep -q .; then
      return 0
    else
      return 1
    fi
  fi

  # 回退：shell glob（兼容没有 find 的极端环境）
  # 尝试开启 nullglob（在 bash 中可用），否则以测试第一个参数方式判断
  local has_glob=0
  # 开启 nullglob 若可用（bash 特性），避免未匹配时返回字面模式
  if (shopt -s nullglob) >/dev/null 2>&1; then
    has_glob=1
    shopt -s nullglob
  fi

  local patterns=( "$dir"/*.jpg "$dir"/*.jpeg "$dir"/*.png "$dir"/*.webp "$dir"/*.bmp "$dir"/*.tif "$dir"/*.tiff )
  if [ "${#patterns[@]}" -gt 0 ] && [ -e "${patterns[0]}" ]; then
    # 如果开启了 nullglob，匹配到文件则返回 0
    if [ "$has_glob" -eq 1 ]; then
      # 关闭 nullglob 以恢复原状
      shopt -u nullglob
      return 0
    else
      # 在不支持 nullglob 的 shell 中，检查第一个匹配是否是真实文件
      if [ -f "${patterns[0]}" ]; then
        return 0
      fi
    fi
  fi

  # 关闭 nullglob（若之前开启）
  if [ "$has_glob" -eq 1 ]; then
    shopt -u nullglob
  fi

  return 1
}

# 发现并按序号排序所有 temp*-1080 批次目录，返回由批次号排序的数组（全局变量 BATCH_DIRS）
discover_batches() {
    declare -A map
    local dir base num
    # 用find防止分词和特殊字符问题
    while IFS= read -r -d '' dir; do
        base=$(basename "$dir")
        if [[ $base =~ ^temp-1080$ ]]; then
            num=1
        elif [[ $base =~ ^temp([0-9]+)-1080$ ]]; then
            num=${BASH_REMATCH[1]}
        else
            continue
        fi
        map[$num]="$dir"
    done < <(find "$DOWNLOAD_DIR" -maxdepth 1 -type d -name 'temp*-1080' -print0)
    BATCH_DIRS=()
    if [ ${#map[@]} -eq 0 ]; then
        return 0
    fi
    local nums
    nums=$(printf "%s\n" "${!map[@]}" | sort -n)
    for n in $nums; do
        BATCH_DIRS+=("${map[$n]}")
    done
}

# 全局警告收集
WARNINGS=()

add_warning() {
    WARNINGS+=("$1")
}

# 确保指定批次的第一次放大结果存在且包含图片；否则执行放大
ensure_first_stage_done() {
    local batch_dir="$1"
    local model_clean
    model_clean=$(clean_model_name "$FIRST_MODEL")
    local first_out="$batch_dir/upscayl_${OUTPUT_FORMAT}_${model_clean}"

    if check_dir_has_images "$first_out"; then
        echo "第一次放大结果已存在: $first_out"
        return 0
    fi

    echo "第一次放大结果缺失或为空: $first_out ，将执行放大处理..."
    if run_upscayl "$batch_dir" "$first_out" "$FIRST_MODEL" 1; then
        echo "已生成第一次放大结果: $first_out"
        return 0
    else
        echo "错误: 无法为批次目录生成第一次放大结果: $batch_dir"
        return 1
    fi
}

# ===============================================
# 主程序开始
# ===============================================

main() {
    local overall_start
    overall_start=$(date +%s)
    # 脚本级开始时间（用于脚本总体进度）
    SCRIPT_START=$overall_start
    # 脚本总体工作量与已完成计数
    TOTAL_WORK=0
    PROCESSED_WORK=0
    local poor_duration=0
    local poor_image_count=0

    echo "=== Upscayl 批量图片处理脚本 ==="
    echo "开始时间: $(date)"

    # 准备工作阶段
    echo -e "\n=== 准备工作 ==="

    # 检查并创建目录
    check_and_create_dir "$TEMP_1080_DIR"
    check_and_create_dir "$TEMP_3K_DIR"
    check_and_create_dir "$FINAL_OUTPUT_DIR"

    # 发现并检查批次目录
    discover_batches
    if [ ${#BATCH_DIRS[@]} -eq 0 ]; then
        echo "错误: 未找到任何 temp*-1080 批次目录（在 $DOWNLOAD_DIR 下）。"
        exit 1
    fi
    echo "检测到批次数量: ${#BATCH_DIRS[@]}，将按序号依次处理。"

    # 检查 temp-3k 是否包含图片
    if ! check_dir_has_images "$TEMP_3K_DIR"; then
        echo "错误: 目录 $TEMP_3K_DIR 中未检测到图片或目录不存在。"
        exit 1
    fi

    # 检查程序可执行性
    if [ ! -x "$UPSCAYL_BIN" ]; then
        echo "错误: Upscayl程序不可执行或不存在: $UPSCAYL_BIN"
        exit 1
    fi
    echo "程序检查通过: $UPSCAYL_BIN"

    # 检查模型文件
    echo "检查模型文件..."
    if ! check_model "$FIRST_MODEL"; then
        exit 1
    fi

    if ! check_model "$SECOND_MODEL"; then
        exit 1
    fi

    # 检查并处理temp-poor目录（如果存在）
    if check_dir_has_images "$TEMP_POOR_DIR"; then
        echo -e "\n=== 检测到temp-poor目录，开始处理低质量图片 ==="
        local poor_start
        poor_start=$(date +%s)
        local poor_model_clean
        poor_model_clean=$(clean_model_name "$FIRST_MODEL")
        local poor_output_dir="$TEMP_POOR_DIR/upscayl_${OUTPUT_FORMAT}_${poor_model_clean}"

        if run_upscayl "$TEMP_POOR_DIR" "$poor_output_dir" "$FIRST_MODEL" 0; then
            local poor_end
            poor_end=$(date +%s)
            poor_duration=$((poor_end - poor_start))
            poor_image_count=$(count_images "$poor_output_dir")

            # 将处理结果复制到final目录
            echo "复制temp-poor处理结果到 $FINAL_OUTPUT_DIR"
            # 批量复制，防止文件名分词和命令行长度限制
            if command -v find >/dev/null 2>&1; then
                find "$poor_output_dir" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" -o -iname "*.bmp" -o -iname "*.tif" -o -iname "*.tiff" \) -print0 | xargs -0 -I{} cp "{}" "$FINAL_OUTPUT_DIR/"
            else
                cp "$poor_output_dir"/* "$FINAL_OUTPUT_DIR/" 2>/dev/null
            fi
            echo "已处理 $poor_image_count 张低质量图片"
        else
            echo "警告: temp-poor目录处理失败，跳过此目录"
        fi
    else
        echo "未检测到temp-poor目录或目录中无图片，跳过处理"
    fi


    # ====== 修正：预先统计 upscayl-bin 实际需要处理的图片总次数 ======
    # poor_count = temp-poor目录图片数
    local poor_count=0
    if check_dir_has_images "$TEMP_POOR_DIR"; then
        poor_count=$(count_images "$TEMP_POOR_DIR")
    fi

    # temp3k_count = temp-3k目录图片数
    local temp3k_count=0
    if check_dir_has_images "$TEMP_3K_DIR"; then
        temp3k_count=$(count_images "$TEMP_3K_DIR")
    fi

    # batch_count_sum = 所有 temp*-1080 目录图片数之和
    local batch_count_sum=0
    for batch_dir in "${BATCH_DIRS[@]}"; do
        if check_dir_has_images "$batch_dir"; then
            batch_count_sum=$((batch_count_sum + $(count_images "$batch_dir")))
        fi
    done

    TOTAL_WORK=$(( poor_count + 2 * (temp3k_count + batch_count_sum) ))
    echo "预计总处理单元（图片次数）: $TOTAL_WORK (poor: $poor_count, temp-3k: $temp3k_count, temp*-1080: $batch_count_sum)"

    # 为第二次放大准备模型名
    local second_model_clean
    second_model_clean=$(clean_model_name "$SECOND_MODEL")

    # 逐批次处理
    local total_main_images=0
    for batch_dir in "${BATCH_DIRS[@]}"; do
        echo -e "\n=== 处理批次目录: $batch_dir ==="
        local base batch_num prev_num prev_dir first_model_clean first_output_dir second_output_dir batch_count

        # 解析批次号以便检查前一批次
        base=$(basename "$batch_dir")
        if [[ $base =~ ^temp-1080$ ]]; then
            batch_num=1
        elif [[ $base =~ ^temp([0-9]+)-1080$ ]]; then
            batch_num=${BASH_REMATCH[1]}
        else
            echo "警告: 无法解析批次号，跳过: $batch_dir"
            add_warning "无法解析批次号，跳过: $batch_dir"
            continue
        fi

        # 检查并补跑上一批次（如果存在）
        if [ "$batch_num" -gt 1 ]; then
            prev_num=$((batch_num - 1))
            if [ $prev_num -eq 1 ]; then
                prev_dir="$DOWNLOAD_DIR/temp-1080"
            else
                prev_dir="$DOWNLOAD_DIR/temp${prev_num}-1080"
            fi
            if [ -d "$prev_dir" ]; then
                echo "检测到上一批次目录: $prev_dir，确保其第一次放大已完成。"
                if ! ensure_first_stage_done "$prev_dir"; then
                    msg="无法确保上一批次($prev_dir)的第一次放大结果，已记录警告并继续。"
                    echo "警告: $msg"
                    add_warning "$msg"
                    # 不退出，继续处理当前批次
                fi
            else
                echo "上一批次目录不存在: $prev_dir，跳过补跑。"
                add_warning "上一批次目录不存在: $prev_dir"
            fi
        fi

        # 确保当前批次第一次放大结果存在（否则执行）
        if ! ensure_first_stage_done "$batch_dir"; then
            msg="当前批次第一次放大失败并跳过: $batch_dir"
            echo "警告: $msg"
            add_warning "$msg"
            continue
        fi

        # 复制 temp-3k 到当前批次的第一次输出目录
        first_model_clean=$(clean_model_name "$FIRST_MODEL")
        first_output_dir="$batch_dir/upscayl_${OUTPUT_FORMAT}_${first_model_clean}"
        echo "将 $TEMP_3K_DIR 中的图片复制到 $first_output_dir"
        # 批量复制，防止文件名分词和命令行长度限制
        if command -v find >/dev/null 2>&1; then
            find "$TEMP_3K_DIR" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" -o -iname "*.bmp" -o -iname "*.tif" -o -iname "*.tiff" \) -print0 | xargs -0 -I{} cp "{}" "$first_output_dir/"
        else
            cp "$TEMP_3K_DIR"/* "$first_output_dir/" 2>/dev/null || true
        fi

        # 检查合并后的目录是否全是图片
        echo "检查合并后的目录: $first_output_dir"
        if ! check_all_images "$first_output_dir"; then
            msg="合并后的目录中包含非图片或为空，跳过批次: $first_output_dir"
            echo "警告: $msg"
            add_warning "$msg"
            continue
        fi

        # 第二次放大
        second_output_dir="$first_output_dir/upscayl_${OUTPUT_FORMAT}_${second_model_clean}"
        echo "开始第二次放大（批次 $batch_num）: $first_output_dir -> $second_output_dir"
        if ! run_upscayl "$first_output_dir" "$second_output_dir" "$SECOND_MODEL" 2; then
            msg="批次 $batch_num 第二次放大失败，跳过该批次"
            echo "警告: $msg"
            add_warning "$msg"
            continue
        fi

        # 复制第二次放大结果到最终目录
        echo "复制批次 $batch_num 的最终结果到 $FINAL_OUTPUT_DIR"
        # 批量复制，防止文件名分词和命令行长度限制
        if command -v find >/dev/null 2>&1; then
            find "$second_output_dir" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" -o -iname "*.bmp" -o -iname "*.tif" -o -iname "*.tiff" \) -print0 | xargs -0 -I{} cp "{}" "$FINAL_OUTPUT_DIR/"
        else
            cp "$second_output_dir"/* "$FINAL_OUTPUT_DIR/" 2>/dev/null || true
        fi

        # 累计统计
        batch_count=$(count_images "$second_output_dir")
        total_main_images=$((total_main_images + batch_count))
        echo "批次 $batch_num 放大后图像数: $batch_count"
    done

    # 总计与结束信息
    local overall_end
    overall_end=$(date +%s)
    local overall_duration=$((overall_end - overall_start))
    local total_images=$((total_main_images + poor_image_count))

    echo -e "\n=== 处理完成 ==="
    echo "完成时间: $(date)"
    echo "  - 总用时: ${overall_duration}秒"
    if [ $poor_image_count -gt 0 ]; then
        echo "  - temp-poor处理: ${poor_duration}秒"
    fi
    echo "总共放大图片数量: $total_images"
    echo "  - 主流程(所有批次): $total_main_images 张"
    if [ $poor_image_count -gt 0 ]; then
        echo "  - temp-poor: $poor_image_count 张"
    fi
    echo "最终输出目录: $FINAL_OUTPUT_DIR"
    # 打印运行期间收集到的警告（如果有）
    if [ ${#WARNINGS[@]} -gt 0 ]; then
        echo -e "\n=== 警告汇总 (${#WARNINGS[@]}) ==="
        for w in "${WARNINGS[@]}"; do
            echo "- $w"
        done
    fi
}

# 信号处理：中断时清理子进程和临时文件
cleanup() {
    echo "\n[!] 捕获到中断信号，正在清理..."
    # 杀死所有upscayl子进程
    pkill -f "$UPSCAYL_BIN" 2>/dev/null || true
    # 可扩展：清理临时文件等
    exit 130
}
trap cleanup INT TERM

# 执行主程序
main "$@"

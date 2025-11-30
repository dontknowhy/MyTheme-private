#!/bin/bash

# ===============================================
# 用户配置区域 - 请根据实际情况修改这些变量
# ===============================================

# 文件夹配置
DOWNLOAD_DIR="$HOME/下载"  # 下载文件夹路径
TEMP_1080_DIR="$DOWNLOAD_DIR/temp-1080"  # 第一次处理图片目录
TEMP_3K_DIR="$DOWNLOAD_DIR/temp-3k"      # 待合并处理图片目录
TEMP_POOR_DIR="$DOWNLOAD_DIR/temp-poor"  # 低质量图片处理目录（可选）
FINAL_OUTPUT_DIR="$DOWNLOAD_DIR/final"   # 最终输出目录

# 程序配置
UPSCAYL_BIN="/opt/Upscayl/resources/bin/upscayl-bin"  # upscayl程序路径
MODELS_DIR="$HOME/custom-models/models"  # 模型目录

# 模型配置
FIRST_MODEL="1x_JPEGDestroyerV2_96000G-fp16"  # 第一次放大模型
SECOND_MODEL="4xNomos8kSC"                    # 第二次放大模型

# 程序参数配置
OUTPUT_FORMAT="png"    # 输出格式
COMPRESSION_LEVEL=100  # 压缩级别
THREADS="1:2:2"        # 线程配置

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
        *.jpg|*.jpeg|*.png|*.webp)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# 检查目录中是否都是图片文件
check_all_images() {
    local dir="$1"
    local total_files=0
    local image_files=0
    
    if [ ! -d "$dir" ]; then
        echo "错误: 目录不存在: $dir"
        return 1
    fi
    
    # 统计总文件数和图片文件数
    for file in "$dir"/*; do
        if [ -f "$file" ]; then
            total_files=$((total_files + 1))
            if is_supported_image "$file"; then
                image_files=$((image_files + 1))
            fi
        fi
    done
    
    echo "目录 $dir 中: 总文件数=$total_files, 图片文件数=$image_files"
    
    if [ $total_files -eq 0 ]; then
        echo "错误: 目录 $dir 中没有文件"
        return 1
    fi
    
    if [ $total_files -ne $image_files ]; then
        echo "错误: 目录 $dir 中包含非图片文件"
        return 1
    fi
    
    return 0
}

# 检查目录是否存在且包含图片（不强制要求全部是图片）
check_dir_has_images() {
    local dir="$1"
    local image_files=0
    
    if [ ! -d "$dir" ]; then
        return 1
    fi
    
    # 统计图片文件数
    for file in "$dir"/*; do
        if [ -f "$file" ] && is_supported_image "$file"; then
            image_files=$((image_files + 1))
        fi
    done
    
    if [ $image_files -eq 0 ]; then
        return 1
    fi
    
    echo "目录 $dir 中包含 $image_files 个图片文件"
    return 0
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

# 清理模型名称中的特殊字符（用于文件夹命名）
clean_model_name() {
    local model_name="$1"
    # 替换特殊字符为下划线
    echo "$model_name" | sed 's/[^a-zA-Z0-9._-]/_/g'
}

# 执行放大操作
run_upscayl() {
    local input_dir="$1"
    local output_dir="$2"
    local model_name="$3"
    local start_time
    start_time=$(date +%s)
    
    echo "开始放大操作..."
    echo "输入目录: $input_dir"
    echo "输出目录: $output_dir"
    echo "使用模型: $model_name"
    
    # 创建输出目录
    check_and_create_dir "$output_dir"
    
    # 执行放大命令
    "$UPSCAYL_BIN" -i "$input_dir" -o "$output_dir" -m "$MODELS_DIR" -n "$model_name" -f "$OUTPUT_FORMAT" -c "$COMPRESSION_LEVEL" -j "$THREADS" -v
    
    local exit_code=$?
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [ $exit_code -eq 0 ]; then
        echo "放大操作完成，用时: ${duration}秒"
        return 0
    else
        echo "错误: 放大操作失败，退出码: $exit_code"
        return 1
    fi
}

# 统计目录中的图片数量
count_images() {
    local dir="$1"
    local count=0
    
    for file in "$dir"/*; do
        if [ -f "$file" ] && is_supported_image "$file"; then
            count=$((count + 1))
        fi
    done
    
    echo $count
}

# ===============================================
# 主程序开始
# ===============================================

main() {
    local overall_start=$(date +%s)
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
    
    # 检查图片目录内容
    echo "检查图片目录..."
    if ! check_all_images "$TEMP_1080_DIR"; then
        exit 1
    fi
    
    if ! check_all_images "$TEMP_3K_DIR"; then
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
        local poor_start=$(date +%s)
        local poor_model_clean=$(clean_model_name "$FIRST_MODEL")
        local poor_output_dir="$TEMP_POOR_DIR/upscayl_${OUTPUT_FORMAT}_${poor_model_clean}"
        
        if run_upscayl "$TEMP_POOR_DIR" "$poor_output_dir" "$FIRST_MODEL"; then
            local poor_end=$(date +%s)
            poor_duration=$((poor_end - poor_start))
            poor_image_count=$(count_images "$poor_output_dir")
            
            # 将处理结果复制到final目录
            echo "复制temp-poor处理结果到 $FINAL_OUTPUT_DIR"
            cp "$poor_output_dir"/* "$FINAL_OUTPUT_DIR/" 2>/dev/null
            echo "已处理 $poor_image_count 张低质量图片"
        else
            echo "警告: temp-poor目录处理失败，跳过此目录"
        fi
    else
        echo "未检测到temp-poor目录或目录中无图片，跳过处理"
    fi
    
    # 第一次放大阶段
    echo -e "\n=== 第一次放大处理 ==="
    local first_model_clean=$(clean_model_name "$FIRST_MODEL")
    local first_output_dir="$TEMP_1080_DIR/upscayl_${OUTPUT_FORMAT}_${first_model_clean}"
    local first_start=$(date +%s)
    
    if ! run_upscayl "$TEMP_1080_DIR" "$first_output_dir" "$FIRST_MODEL"; then
        exit 1
    fi
    
    local first_end=$(date +%s)
    local first_duration=$((first_end - first_start))
    
    # 复制temp-3k图片到第一次输出目录
    echo -e "\n=== 复制temp-3k图片 ==="
    echo "将 $TEMP_3K_DIR 中的图片复制到 $first_output_dir"
    cp "$TEMP_3K_DIR"/* "$first_output_dir/" 2>/dev/null
    
    # 检查复制后的目录
    echo "检查合并后的目录..."
    if ! check_all_images "$first_output_dir"; then
        exit 1
    fi
    
    # 第二次放大阶段
    echo -e "\n=== 第二次放大处理 ==="
    local second_model_clean=$(clean_model_name "$SECOND_MODEL")
    local second_output_dir="$first_output_dir/upscayl_${OUTPUT_FORMAT}_${second_model_clean}"
    local second_start=$(date +%s)
    
    if ! run_upscayl "$first_output_dir" "$second_output_dir" "$SECOND_MODEL"; then
        exit 1
    fi
    
    local second_end=$(date +%s)
    local second_duration=$((second_end - second_start))
    
    # 最终工作阶段
    echo -e "\n=== 最终处理 ==="
    
    # 复制第二次放大结果到final目录
    echo "复制最终结果到 $FINAL_OUTPUT_DIR"
    cp "$second_output_dir"/* "$FINAL_OUTPUT_DIR/" 2>/dev/null
    
    # 统计信息
    local overall_end=$(date +%s)
    local overall_duration=$((overall_end - overall_start))
    local main_image_count=$(count_images "$second_output_dir")
    local total_images=$((main_image_count + poor_image_count))
    
    echo -e "\n=== 处理完成 ==="
    echo "完成时间: $(date)"
    echo "各阶段用时:"
    echo "  - 第一次放大: ${first_duration}秒"
    echo "  - 第二次放大: ${second_duration}秒"
    if [ $poor_image_count -gt 0 ]; then
        echo "  - temp-poor处理: ${poor_duration}秒"
    fi
    echo "  - 总用时: ${overall_duration}秒"
    echo "总共放大图片数量: $total_images"
    if [ $poor_image_count -gt 0 ]; then
        echo "  - 主流程: $main_image_count 张"
        echo "  - temp-poor: $poor_image_count 张"
    fi
    echo "最终输出目录: $FINAL_OUTPUT_DIR"
}

# 执行主程序
main "$@"
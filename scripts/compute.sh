#!/bin/env bash
trap handle_sigill SIGILL
###config
work_dir="$(git rev-parse --show-toplevel)"/ # 获取当前脚本所在目录,用于获取upscayl-bin和模型
upscaler="$work_dir/scripts/binary/upscayl-bin"
jpegoptim="$work_dir/scripts/binary/jpegoptim"
jpegoptim_args="--strip-none -f -w 20 --all-progressive -m 95"
model_path="$work_dir/scripts/models"
pic_path="$work_dir/scripts/input"
model_name="4xNomos8kSC"
tmp_dir="$work_dir/scripts/tmp"
default_width="4000" # 控制upscaler输出图片的宽度,一般来说1080p的图片会放大到4320,但是出于某些原因,像素会偏移,所以降采样到4000
# 这里说的宽度指的是最短边而不是物理意义上的宽度
defalut_format="png" # 控制upscaler输出图片的格式
thumbnail_short_resolution="400" # 怎么写的变量名.jpg
folder_portrait="../竖"
folder_landscape="../横"
###config end

check_resolution() {
    # 获取图片的分辨率
    dimensions=$(identify -format "%wx%h" "$1")
    width=$(echo "$dimensions" | cut -d'x' -f1)
    height=$(echo "$dimensions" | cut -d'x' -f2)

    # 比较宽度和高度，确定最短分辨率
    if [ "$width" -lt "$height" ]; then
        shortest_resolution=$width
    else
        shortest_resolution=$height
    fi
    echo "$shortest_resolution"
}

upscale_image() {
    #Usage: upscayl-bin -i infile -o outfile [options]...
    #-h                   show this help
    #-i input-path        input image path (jpg/png/webp) or directory
    #-o output-path       output image path (jpg/png/webp) or directory
    #-z model-scale       scale according to the model (can be 2, 3, 4. default=4)
    #-s output-scale      custom output scale (can be 2, 3, 4. default=4)
    #-r resize            resize output to dimension (default=WxH:default), use '-r help' for more details
    #-w width             resize output to a width (default=W:default), use '-r help' for more details
    #-c compress          compression of the output image, default 0 and varies to 100
    #-t tile-size         tile size (>=32/0=auto, default=0) can be 0,0,0 for multi-gpu
    #-m model-path        folder path to the pre-trained models. default=models
    #-n model-name        model name (default=realesrgan-x4plus, can be realesr-animevideov3 | realesrgan-x4plus-anime | realesrnet-x4plus or any other model)
    #-g gpu-id            gpu device to use (default=auto) can be 0,1,2 for multi-gpu
    #-j load:proc:save    thread count for load/proc/save (default=1:2:2) can be 1:2,2,2:2 for multi-gpu
    #-x                   enable tta mode
    #-f format            output image format (jpg/png/webp, default=ext/png)
    #-v                   verbose output

    #'-r widthxheight:filter' argument usage:
    #For example '-r 1920x1080' or '-r 1920x1080:default' will force all output images to be
    #resized to 1920x1080 with the default filter if they aren't already.
    #Similarly, '-w 1920' will force all output images to be resized to a width of 1920.
    #Avaliable filters:
    #default       - Automatically decide
    #box           - A trapezoid w/1-pixel wide ramps, same result as box for integer scale ratios
    #triangle      - On upsampling, produces same results as bilinear texture filtering
    #cubicbspline  - The cubic b-spline (aka Mitchell-Netrevalli with B=1,C=0), gaussian-esque
    #catmullrom    - An interpolating cubic spline
    #mitchell      - Mitchell-Netrevalli filter with B=1/3, C=1/3
    #pointsample   - Simple point sampling

    #计算分辨率,因为emm,最短边4000像素嘛
    dimensions=$(identify -format "%wx%h" "$1")
    width=$(echo "$dimensions" | cut -d'x' -f1)
    height=$(echo "$dimensions" | cut -d'x' -f2)
    out_resolution=$(calc_resolution "$width" "$height" "$default_width")
    echo "$out_resolution"
    $upscaler -v \
    -i "$pic_path" \
    -o "$tmp_dir" \
    -m "$model_path" \
    -n "$model_name" \
    -r "$out_resolution:default" \
    -f "$defalut_format"
    return 0
}

check_and_up() {
for pics in "$pic_path"/*; do
    if [ "$(check_resolution "$pics")" -gt 4000 ]; then
        echo "$pics 分辨率大于4000,不需要放大"
        cp "$pics" "$tmp_dir"/
    else
        upscale_image "$pics"
    fi
    done
}

check_if_vertical() {
    # 判断图片是否为竖屏的功能
    # 获取图片的分辨率
    dimensions=$(identify -format "%wx%h" "$1")
    width=$(echo "$dimensions" | cut -d'x' -f1)
    height=$(echo "$dimensions" | cut -d'x' -f2)

    # 通过比较纵向分辨率和横向分辨率确定是否为竖屏的图片
    # width:横向分辨率 height:纵向分辨率
    if [[ "$width" -lt "$height" ]]; then
        is_vertical="1"
    else
        is_vertical="0"
    fi
    return $is_vertical
}

calc_resolution() { #保留手动输入宽高分辨率保证通用性,至于分辨率的话每次调用前手动获取
    width=$1
    height=$2
    shortest_side=$3

    # 根据最短边计算新的分辨率
    if [[ "$width" -lt "$height" ]]; then
        new_width=$shortest_side
        new_height=$((height * new_width / width))
    else
        new_height=$shortest_side
        new_width=$((width * new_height / height))
    fi

    # 输出最终分辨率
    echo "${new_width}x${new_height}"
}

deps_check() {
    if ! command -v bc &> /dev/null
    then
        echo "哥们使用bc,不如咱装一个?"
        exit 1
    fi

    if ! command -v identify &> /dev/null
    then
        echo "哥们使用Image Magick,不如咱装一个?"
        exit 1
    fi

    if ! command -v "wc" &> /dev/null
    then
        echo "哥们使用coreutils,不如咱装一个?"
        exit 1
    fi
}

convert_to_jpg() {
    # magick的convert指令被标记为过时,但是哥们提供了更简单的法子,甚至输入的字母更少(?
    # https://imagemagick.org/script/convert.php
    for pics in "$tmp_dir"/*; do #实测不会检测目录下的dotfile
        dimensions=$(identify -format "%wx%h" "$pics") #获取图片分辨率,后面使用calc_resolution计算略缩图(thumbnail)的分辨率
        width=$(echo "$dimensions" | cut -d'x' -f1)
        height=$(echo "$dimensions" | cut -d'x' -f2)
        thumbnail_resolution=$(calc_resolution "$width" "$height" "$thumbnail_short_resolution")

        magick "$pics" "${pics%.*}.jpg" \
        -interlane Plane \
        -define jpeg:dct-method=int \
        -sampling-factor 4:4:4 \
        -thumbnail "$thumbnail_resolution" \
        -define jpeg:optimize-coding=true \
        -define jpeg:smooth=0 \
         #设置为100%是为了下一步的jpegoptim

        $jpegoptim "$jpegoptim_args" "${pics%.*}.jpg" #这里又处理了一遍文件名,未知会不会出问题
    done
}

handle_sigill() {
    while IFS= read -r line; do
    if [[ $line == "model name"* ]]; then
        # 提取冒号后的部分，并去除前后的空格
        cpu_model="${line#*: }"
        cpu_model="${cpu_model#"${cpu_model%%[![:space:]]*}"}"
        cpu_model="${cpu_model%"${cpu_model##*[![:space:]]}"}"
        break
    fi

    done < /proc/cpuinfo
    echo "捕捉到非法指令错误,是不是你的CPU不是Intel i5 12500H?"
    echo "仓库自带的二进制文件都使用Intel i5 12500H加上-march=native编译"
    echo "如果你看见这条信息请自行编译"
    echo "你的CPU型号为: ${cpu_model}"
    exit 4 #illegal instruction的错误码
}

add_into_folder() {
    for pics in "$tmp_dir"/*; do
        result="$(check_if_vertical "$pics")" #方便下一步不需要反复检测浪费时间
        if [[ $result = 1 ]]; then
            #图片为竖屏
            mv "$pics" "$folder_portrait"/
        elif [[ $result = 0 ]]; then
            mv "$pics" "$folder_landscape"/
        else
            echo "貌似要似了,错误原因:"
            echo "不认识${pics}"
        fi
    done

}

rename() {
    dir="$1"

    # 获取目录下最后一个被git追踪的jpg文件的编号
    last_tracked=$(git ls-files "$dir"/*.jpg | sort | sort -n | tail -n 1 |grep -o '[0-9]\+' | tail -n 1)
    if [ -z "$last_tracked" ]; then
        last_tracked=0
    fi

    # 找到未被跟踪的jpg文件
    untracked_files=$(git ls-files --others --exclude-standard "$dir"/*.jpg)

    # 初始化新的文件编号
    new_number=$((last_tracked + 1))

    for file in $untracked_files; do
        # 生成新的文件名
        new_filename=$(printf "%03d.jpg" "$new_number")
        # 重命名文件
        mv "$file" "$dir/$new_filename"
        # 增加文件编号
        new_number=$((new_number + 1))
    done

}

main() {
    check_and_up
    convert_to_jpg
    add_into_folder
    rename "$folder_portrait"
    rename "$folder_landscape"
}

##正式开始(
echo "亻尔 女子"
#检查依赖
deps_check
#有图片吗,没有那我们不是朋友
if [ ! "$(ls "$pic_path")" ]; then # 这里理论来说并不会显示.nomedia文件
    echo "没有图片,我不干了"
    exit 1
else
    echo "检测到图片,我要开始吃你电费了"
    main
    echo "农村人自己去commit"
fi
#!/usr/bin/python3
import random
import os
import json
import platform
# 网上拷贝的按任意键退出的模块
import sys
import tty
import termios

#学校教了点蟒蛇
#config start>>>
cfg_folder = os.path.dirname(os.path.realpath(__file__)) #扫描当前目录
cfg_extension = ".jpg" #预览图为png文件,应该不会变化
cfg_json_path = os.path.dirname(os.path.realpath(__file__)) + "/theme.json"
###
cfg_key_daytime = "dayImageList"
cfg_key_nightime = "nightImageList"
cfg_key_displayName = "displayName"
cfg_key_imageFilename = "imageFilename"
cfg_key_imageCredits = "imageCredits"
cfg_key_dayHighlight = "dayHighlight"
cfg_key_nightHighlight = "nightHighlight"
###
cfg_displayName = "Roll out the pics"
cfg_imageFilename = "*.jpg"
cfg_imageCredits = "dontknowhy"
cfg_dayHighlight = "13"
cfg_nightHighlight = "23"
###
cfg_hack_remove_char = '"'
###
cfg_shuffle_time = "10000" # 不知道为啥要这么多次,可能吃满你的单核很酷
#<<< config Stop

def count_files(folder, extension): #计算目录下文件
    filecount = 0 #声明文件数量先为0
    for root, dirs, files in os.walk(folder):
        for files in files:
            if files.endswith(extension):
                filecount += 1
    return filecount

def mod_json(file_path, key, new_value): #json
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file) #load json
    data[key] = new_value

    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def hack(file_path):
    ###非常坏hack工作,你还要在写好json之后再操作
    ###因为WinDynamicDesktop对于dayImageList和nightImageList指定需要下面的格式,其他的会报错
    ###"dayImageList" : [1,2,3,4,69]
    ###注意到了吗,数字部分用中括号括起来的而不是双引号
    ###而正常python对于json的写入长这样:
    ###"dayImageList" : "[1,2,3,4,69]"
    ###这里的中括号在shuffle_list就预先加好了
    ###做点hack工作来去掉双引号
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # 处理每一行
    processed_lines = []
    for line in lines:
        if cfg_key_daytime in line:
            # 去除指定的字符
            line = line.replace(cfg_hack_remove_char, '')
            start_index = line.find(cfg_key_daytime)
            end_index = start_index + len(cfg_key_daytime)

            # 在目标字符串前后加上双引号
            line = line[:start_index] + cfg_hack_remove_char + line[start_index:end_index] + cfg_hack_remove_char + line[end_index:]
            processed_lines.append(line)

        elif cfg_key_nightime in line:
            line = line.replace(cfg_hack_remove_char, '')
            start_index = line.find(cfg_key_nightime)
            end_index = start_index + len(cfg_key_nightime)

            # 在目标字符串前后加上双引号
            line = line[:start_index] + cfg_hack_remove_char + line[start_index:end_index] + cfg_hack_remove_char + line[end_index:]
            processed_lines.append(line)
        else:
            processed_lines.append(line)

    # 将处理后的行写回文件
    with open(file_path, 'w', encoding='utf-8') as file:
        file.writelines(processed_lines)
    # WARN:在此之后就不能再格式化了

def shuffle_list(count):
    count = count + 1 #因为这玩意不会包括最后一个数字
    i = 1 #第一张图一定为1号
    list_s = [i for i in range(i,count)]
    for i in range(int(cfg_shuffle_time)): # 强制转int防止出事
        random.shuffle(list_s)
    #整几次让她更随机点(?
    #list_s = [str(i) for i in list_s]
    list_s = str(list_s)
    #list_s = [(','.join(list_s))]
    #list_final = list_s.replace('"', '')
    return list_s

def press_2_exit(msg):
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        print(msg, end='', flush=True)
        sys.stdin.read(1)  # 读取一个字符
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# Main funtion
# 检测是否为Windows,因为我不在Windows维护仓库,嘻嘻
current_os = platform.system()
if current_os == "Windows":
    print("检测到Windows操作系统，程序将退出。")
    exit(1)  # 退出程序并返回状态码1，表示错误

count = count_files(cfg_folder, cfg_extension)
print("This folder has", count, "files with extension:", cfg_extension)

print("Generating DayTime and NightTime list...")
DayTime_list = shuffle_list(count)
NightTime_list = shuffle_list(count)

print("Writing things above to", cfg_json_path)
mod_json(cfg_json_path, cfg_key_daytime, DayTime_list)
mod_json(cfg_json_path, cfg_key_nightime, NightTime_list)

mod_json(cfg_json_path, cfg_key_displayName, cfg_displayName)
mod_json(cfg_json_path, cfg_key_imageFilename, cfg_imageFilename)
mod_json(cfg_json_path, cfg_key_imageCredits, cfg_imageCredits)
mod_json(cfg_json_path, cfg_key_dayHighlight, cfg_dayHighlight)
mod_json(cfg_json_path, cfg_key_nightHighlight, cfg_nightHighlight)
hack(cfg_json_path)

print("done")
#按任意键退出,防止运行后看不见干啥了
press_2_exit("请按除了电源键,重启按键,Ctrl键,Alt键,CapsLock键,Shift键以外的任意键退出")
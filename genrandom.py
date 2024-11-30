import random
import os
import json
import re
#学校教了点蟒蛇
#config start>>>
cfg_folder = "./" #扫描当前目录
cfg_extension = ".jpg" #预览图为png文件,应该不会变化
cfg_json_path = "./theme.json"
cfg_key_daytime = "dayImageList"
cfg_key_nightime = "nightImageList"
cfg_hack_remove_char = '"'
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

    keys = key.split('.') #modify json
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = new_value

    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

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
            line = line[:start_index] + '"' + line[start_index:end_index] + '"' + line[end_index:]
            print(line)
            processed_lines.append(line)
        elif cfg_key_nightime in line:
            new_line = line.replace(cfg_hack_remove_char, '')
            processed_lines.append(new_line)
        else:
            processed_lines.append(line)

    lines = processed_lines
    for i in range(len(lines)):
        if cfg_key_daytime in lines[i]:
            # 找到目标字符串的位置
            start_index = lines[i].find(cfg_key_daytime)
            end_index = start_index + len(cfg_key_daytime)

            # 在目标字符串前后加上双引号
            lines[i] = lines[i][:start_index] + '"' + lines[i][start_index:end_index] + '"' + lines[i][end_index:]
        elif cfg_key_nightime in lines[i]:
            # 找到目标字符串的位置
            start_index = lines[i].find(cfg_key_nightime)
            end_index = start_index + len(cfg_key_nightime)

            # 在目标字符串前后加上双引号
            lines[i] = lines[i][:start_index] + '"' + lines[i][start_index:end_index] + '"' + lines[i][end_index:]
    processed_lines = lines

    # 将处理后的行写回文件
    with open(file_path, 'w', encoding='utf-8') as file:
        file.writelines(processed_lines)
    # WARN:在此之后就不能再格式化了

def shuffle_list(count):
    count = count + 1 #因为这玩意不会包括最后一个数字
    i = 0
    list_s = [i for i in range(i,count)]
    random.shuffle(list_s)
    #list_s = [str(i) for i in list_s]
    list_s = str(list_s)
    #list_s = [(','.join(list_s))]
    #list_final = list_s.replace('"', '')
    return list_s

count = count_files(cfg_folder, cfg_extension)
print("This folder has", count, "files with extension:", cfg_extension)

print("Generating DayTime list...")
DayTime_list = shuffle_list(count)
NightTime_list = shuffle_list(count)

print("Writing things above to", cfg_json_path)
mod_json(cfg_json_path, cfg_key_daytime, DayTime_list)
mod_json(cfg_json_path, cfg_key_nightime, NightTime_list)

print("done")

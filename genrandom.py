#!/bin/bash
#由バーカチルノ写成(看不懂日文,某个社交平台他是这么写的就是了
#更改525为任意数字就可以输出类似于下面的效果
#1,4,5,2,3
#主要用来写theme.json的随机切换
python3 -c "import random;l=[i for i in range(1,525)];random.shuffle(l);l=[str(i) for i in l];print(','.join(l))"

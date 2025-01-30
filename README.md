 # 防止失忆用文档

如何克隆和维护这个~~智障~~仓库：

> [!WARNING]
>
> 对于这种奇奇怪怪的Git用途来说一块还算比较健康的硬盘是刚需. Git一般没有特别的需求,但是读写在50MB/s且能稳定住的速度为佳. 如果不同这个指标的话你可以问问你自己一个问题: 我的设备开机很慢吗. 如果你的回答是`是`的话,那你依然可以正常游玩,但是在执行写盘操作会很痛苦,因为Git会浏览大量的文件来决定自己要快进哪些地方.

## 这个仓库功能着

1. 惊人的半角全角区别.

2. 不太准确但是It Just Works的信息.

3. 很容易被DMCA的图片.

4. 大哥我错了真的不想拿来大规模传播的.

5. 可能缺失的句号

6. 并没有的[官方正版下载链接](https://www.bilibili.com).

7. 并不想使用Noto Sans CJK的Typora写成的文档.

8. 乱写的commit message.

9. 压根不合适的源码管理器.

10. 转人工.

    

## 分支小注记

| 名称                         | 用处                                                         |         你在何时改选          |
| ---------------------------- | ------------------------------------------------------------ | :---------------------------: |
| main                         | 主要的分支,用来存放其他分支包含的所有基础的图片文件          |      想一下获取到所有图       |
| WinDynamicDesktop (准备废弃) | 用以提供WinDynamic支持,现已经过载且不一定会自动更换          |    PHP变成第一流行的语言时    |
| selected                     | 从WinDynamicDesktop剥离出来的纯图片,可以克隆到文件夹并由支持文件夹内循环/乱序播放壁纸的壁纸软件(Windows的幻灯片,或者带slideshow功能的DE) | 不想用WinDynamicDesktop的时候 |



## SSH

> 你最开始需要做的是自己注册个GitHub账户,如果遇到什么访问不了的问题自行解决，都来这看了不有个号怎么行呢。

检查自己有ssh密钥没。一般来说都可以在[这里](https://docs.github.com/zh/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)查看文档来自行添加一个（ssh密钥是通用的，但通常推荐每个获得Github访问权限的设备都有单独的密钥，万一真的出事了可以方便注销密钥）

> [!CAUTION]
>
> 由于涉及到直接与长城之外的GitHub服务器连接,所以出国流量大的时候最好不要尝试去连接.
>
> 具体时间看各大高校的镜像站同步内容的时间,大部分都在每日的晚上.

> [!WARNING]
>
> GitHub对于ssh密钥的访问貌似很宽松，不要泄漏你的密钥，否则删库从梦想走进现实。

1. 创建一个密钥：

   ````bash
   ssh-keygen -t rsa
   ````

   之后会询问你存储的位置

   ```
   Enter file in which to save the key (/home/dontknowhy/.ssh/id_rsa):
   ```

   这时候最好直接回车，因为这块小破地方ssh尝试连接时会寻找这里的密钥 (家目录的`.ssh`文件夹) 进行验证（记得拷贝括号的内容，后面有用）

   之后按照提示输入一个密码(最好是强密码)，你就有个密钥了

   ```
   Generating public/private rsa key pair.
   Enter file in which to save the key (/home/dontknowhy/.ssh/id_rsa): 
   Enter passphrase (empty for no passphrase): 
   Enter same passphrase again: 
   Your identification has been saved in id_rsa
   Your public key has been saved in id_rsa.pub
   The key fingerprint is:
   SHA256:4GhApi6ovNnEztkLj5f4JA7wFVLmU2lI9c8I5vNnTiM dontknowhy@sb-debian
   The key's randomart image is:
   +---[RSA 3072]----+
   |  o.+oo.         |
   | + +..o.         |
   |. o +.+ .        |
   |o  o B o +       |
   |+.  + + S o      |
   |=..o   o         |
   |.o.=... E =      |
   |  X.Oo   * .     |
   | o Bo=.   .      |
   +----[SHA256]-----+
   ```

2. 拷贝公钥

   把上面说复制的内容准备好

   ````
   $ cat *你刚才复制的内容，后面加上.pub*
   ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCLuwIjqqm7Qy1PaxzvLEVjRVFtPIWj1KaHUIGqDM853KATRsbdvQG5nibKfjrj/g9VsVG4Mq/lQ26JCxLi5ZVI7YAUHq9hMLwnyFx99pVlXzt4GagifmVWX86kbPzFXi8BfvaYFYZR1Wlb3+BC0wOWIK0ZbMvCl1m+Q8IND8jOJYOp2GmvcXqB2DZIIF0OhQWyzMcfy7jR1db4yl5i0fHc8EKHZO20xaZXAvHlCt0008TmF6+xTlkyLylEZzObq1Fo7jNJkgYd1+fEVi1Qs93gyfj3QQQzyToSg8Fl2qj6bfalv0WmUwdrqBfADHWE/6tPcnTmc4cQmHH1pszVBKmP23pXJOxfmx0JhBZEaNep6tG6gioVQPrW2/FO86jb47MoJfq7z9T5okylHM3F+EcEqOEEYL2dWi+vV15eOcoS3/R+lZw+hHGYPlXCBRft+DKqveVIECBD5+kaBi+DwdlICGjJhhU2xskF7ThPdW3wObJqD6Xe/D6qWbPf0waVZss= dontknowhy@sb-debian
   ````

   把上面输出的内容给复制好。

3. 喂给[~~GutHib~~](https://guthib.com)你新鲜的公钥

   进入GitHub官网，点右上角你的~~随机生成~~的头像，点`Settings`，再点`SSH and GPG keys`，接着是`New SSH key` ，在`Title`输入备注(例如用于哪个设备的)，在`Key`栏目输入你刚才复制的内容，最后点`Add SSH key`完成添加。

4. 看看~~GayHub~~认识不认识你的密钥

   在终端输入`ssh git@github.com`，如果你的密钥设置了密码此时会询问密码，完成后你应该看得见：

   ```
   Hi dontknowhy! You've successfully authenticated, but GitHub does not provide shell access.
   Connection to github.com closed.
   ```

   如果~~GitCode~~对你问好那你就可以用这个密钥愉快进行操作了。

5. 透过ssh克隆这个仓库

   `git clone --depth=1 -j 16 git@github.com:dontknowhy/MyTheme-private.git`

   注释: 1.  `--depth=1`只仅克隆一层仓库,人话就是哥们不用下载我黑历史,另外也有助于你节省磁盘空间

   2. `-j 16`可以加速下载，如果失败请改成`-j 8`。在广东特供中国移动可以跑到5M/s，但其他网络一般都有效，且流量全程被你的密钥加密。

## `gh`工具？

很遗憾的是`gh`工具即使你登陆的时候用ssh密钥了，克隆仓库还是会使用一等一慢的https。但是好消息是她上传releases的速度很快。

## 快速克隆

 <a href='https://gitclone.com'><img src='https://gitclone.com/img/title.ico' style='width:300px;'/></a>

↑你可以尝试用GitClone网站来克隆

`git clone --depth=1 -j 16 https://gitlone.com/github.com/dontknowhy/MyTheme-private.git`

> [!NOTE]
>
> （当然我没有成功过，放这玩的）

你也可以试试[KGitHub](https://help.kkgithub.com/donate/)(点进去是赞助人家的链接，爆点米给人家罢)

> **KGitHub目前的限制：**
>
> 1.不能注册
>
> 2.不能上传文件，可以登录，可以在线编辑
>
> 3.来自raw.githubusercontent.com的下载可使用raw.kkgithub.com替代
>
> 4.仓库拦截采用黑名单关键字拦截，若产生误判可联系站长邮箱（kgithub@uoo.im）处理

`git clone --depth=1 -j 16 https://kkgithub.com/dontknowhy/MyTheme-private.git`

或者去寻找一些proxy方案,例如[GitHub Proxy](https://ghp.ci/donate)

`git clone --depth=1 -j 16 https://ghp.ci/https://github.com/dontknowhy/MyTheme-private.git`

## `github.com`永不为奴！

感觉不如[____](https://ys-api.mihoyo.com/event/download_porter/link/ys_cn/official/android_default).

如果GFW漏风都是万幸。

如果你为自己创造了良好的网络环境(大嘘)的话可以用.

<!--讨厌全角和半角符号区别-->

## 貌似是常见的问题

1. ​	在一些罕见的地方可能遇到git很难克服的问题,例如实在没有办法撑住时不时断开连接的网络.这时候可以去[releases](https://github.com/dontknowhy/MyTheme-private/releases/tag/v2.1)(链接为原版GitHub,自己替换为镜像站)下载大约6.5GB的[7zip](https://7-zip.org)分片压缩包,解压出来后会出现一个叫`main.bundle`的东西,这个叫`git bundle`,可以直接使用`git clone main.bundle theme`来像在线链接一样克隆(不接受`--depth`参数,`-j`参数也是).

   ​	克隆下来后默认的上游为`main.bundle`的绝对路径,需要手动设置上游:`git remote set-url origin git@github.com:dontknowhy/MyTheme-private.git`(ssh坏了的话自行寻找镜像站替换).

   > [!NOTE]
   >
   > `git bundle`克隆出来的仓库可能有12G以上的大小,请应用下面的配置并gc一下.

   > [!NOTE]
   >
   > 你现在下载的bundle肯定已经落后与本仓库了,请看看[下面](https://github.com/dontknowhy/MyTheme-private#如何接收更新)的介绍来更新.

2. `.git`文件夹过大是因为git压根不适合处理图片文件,我保存的全是已经经过jpeg压缩的图片,git那赢弱的zlib压缩就算了.

3. 有时候网络环境比较自由的空气但是还是断了.这时候可能需要整点git配置文件:

   ```bash
   # 这里边还是有些多余的我闲着没事干加上去的配置
   git config --global checkout.workers 20
   git config --global core.compression 9
   git config --global pack.comppression 9
   git config --global pack.threads 20
   git config --global index.threads 20
   git config --global repack.cruftThreads 20
   git config --global http.minSessions 5
   git config --global http.maxRequests 5
   git config --global http.postBuffer 5M
   git config --global http.lowSpeedLimit 0
   git config --global http.lowSpeedTime 999999
   git config --global core.fscache true
   git config --global core.preloadindex true
   git config --global gc.auto 256
   git config --global core.multiPackIndex true
   git config --global pack.useSparse true
   ```

> [!WARNING]
>
> 这些commit有助于减小`.git`文件夹的大小,所以务必应用完后运行:
>
> ```bash
> git gc --prune=now
> ```
>
> 这样你就会惊喜的发现`.git`文件夹比图片还大,没办法,git天生不适合存储大量图片.



## 如何接收更新

一般来说你使用上述方法都可以设置好上游,但是你克隆好后可能还是需要检查一下:`git remote -v`,一般会输出以下东西:

```bash
origin  git@github.com:dontknowhy/MyTheme-private.git (fetch)
origin  git@github.com:dontknowhy/MyTheme-private.git (push)
```

如果origin行是一串网址或者以`git@github.com`开头的地址那你一般可以用

```bash
git fetch -j8 && git pull
```

或者更加简单的

```bash
git pull -j8
```

最后你应该都可以得到类似于以下的输出:

```bash
updating 4990df4..521802e
updating files: 100% (85/85), done.
fast-forward
"\346\250\252/723.jpg"  | bin 3098000 -> 3032067 bytes
##有可能很长
85 files changed, 0 insertions(+), 0 deletions(-)
```

如果发现最后带有`xxx files changed, 0 insertions(+), 0 deletions(-)`的字样,那你就更新好了.

## 如何自动更新

> [!TIP]
>
> 准确的来说`scalar`帮你省下了接收更新的时间,不会自动更新你的工作目录到最新的commit id.
>
> 所以此工具对于这个仓库来说仅用于接收更新,图片的检出还需要手动操作.

你可以依赖一些例如`crontab`的玩意来创建自动任务来更新,但是很明显这玩意不认识的一定不会写,认识了也会写.所以我们可以用[巨硬](https://zhidao.baidu.com/question/1650077279199221540.html)制作的[Scalar](https://github.com/microsoft/git)工具来帮我们创建看不懂的自动任务.

> [!NOTE]
>
> `Scalar`貌似在git的2.38版进入主线,所以确保你的git版本为最新版来防止找不到此工具.
>
> `Scalar`貌似在Windows 7上无法创建自动任务.(这么老了不如早日放弃)

#### */Linux

如果你的`git`版本符合要求,那么你可以尝试运行`scalar`来验证你的发行版有没有加入此工具,如果有输出的内容那就是有.

如果有输出的话可以运行:

```bash
scalar reconfigure
```

来注册`scalar`的自动任务.

> [!NOTE]
>
> 貌似`scalar`的注册并不会告诉你什么,所以你需要靠返回的状态值是否为0来判断注册成功,或者可以去看`.gitconfig`文件,具体这样操作:
>
> ```bash
> cat ~/.gitconfig|grep scalar
> ```
>
> 如果输出了带scalar字眼的内容那就是注册好了.

注册好后需要再注册你克隆的仓库:

```bash
scalar register #麻烦确保自己在仓库目录内
```

可以通过以下指令来验证:

```bash
scalar list
```

如果输出东西了就是可以.

最后可以尝试手动运行维护仓库进程:

```bash
scalar run all #后期发现你上边啥也不做这个步骤也会帮你完成
```

会产生类似于下面的输出:

```bash
/home/dontknowhy/图片/MyTheme-private
枚举对象中: 61, 完成.
对象计数中: 100% (61/61), 完成.
使用 16 个线程进行压缩压缩对象中: 100% (61/61), 完成.
47d6e6467f35194610c51c91aa638d267d6d5201
写入对象中: 100% (61/61), 完成.
总共 61（差异 0），复用 0（差异 0），包复用 0（来自  0 个包）枚举对象中: 160, 完成.
```

最后`Scalar`会以每小时,每天,每周的频率维护仓库.

#### Windows

类似,但确保Windows版本在10或以上.

其余的使用

```bash
scalar run all
```

就会自动配置好

## 自动更换壁纸

> [!WARNING]
>
> 只有Windows才有[WinDynamicDesktop](https://github.com/t1m0thyj/WinDynamicDesktop/),其余平台[自己找](https://github.com/zzag/plasma5-wallpapers-dynamic)

> [!IMPORTANT]
>
> Windows内置的幻灯片足够了,但是如果你想类似于保活一样的换壁纸还是这个好玩.
>
> WinDynamicDesktop准备废弃

1. 从[人家仓库的releases](https://github.com/t1m0thyj/WinDynamicDesktop/releases/latest)下载自己架构的安装包(不推荐下载带Portable标签的包)(你的电脑架构自行查询).
2. 安装(麻烦默认配置不要动,顶多给我改桌面图标)
3. 下载**这个仓库的**releases中的ddw文件或选择使用仓库中的WinDynamicDesktop分支(里边我随便挑了点用,WinDynamicDesktop很好改主题的,全是json)
4. 双击打开ddw,如果是git分支的话自行研究克隆到Appdata\Local\WinDynamicDesktop\themes内
5. 完事了
6. 你会发现几乎1分钟换一张



## 维护小贴士

1. 准备编译jpegoptim时记得链接mozjpeg,如果事后强行加载会无法启动
2. 使用jpegoptim的`-m`参数去压缩图片而不是图片编辑(在我这是GIMP)内置的压缩,很显然的是jpegoptim的压缩效果会因为调用了mozjpeg而小一点或很多(具体的:`--strip-none -f -w 20 --all-progressive -m 85`,`-w`部分可以指定别的,我喜欢是20)
3. 不清楚有没有效果,我使用的[upscayl-bin](https://github.com/upscayl/upscayl-ncnn)主体是自己替换掉更新的libwebp和ncnn还有`stb_image.h`等依赖的,因为上一次更新依赖是2年前,在这之后的ncnn版本都可以直接灌进去编译,所以为何不嘛
4. 如果自己编译的组件,建议使用`-march=native`之类的优化flag给编译器,对于我的Clang 19来说是:`-Ofast -pipe -march=native -Wno-unused-command-line-argument -mllvm -polly -mllvm -polly-vectorizer=stripmine -flto=thin -mllvm -polly-parallel -mllvm -polly-omp-backend=LLVM -fuse-ld=/usr/bin/ld.lld-19 -mllvm -polly-run-inliner -mllvm -polly-run-dce -fno-semantic-interposition -fvisibility=hidden -mllvm -polly-invariant-load-hoisting -fopenmp=libomp`,什么是更多的,可以给NCNN传递额外的编译选项来稍微给小亮整个活:`-DNCNN_ENABLE_LTO=ON -DNCNN_SIMPLEVK=OFF`
5. 如果很在乎的话,我用的升采样模型是`4xNomos8kSC`
6. 编译flag都是自己随便瞎写的憋骂了,WinDynamicDesktop分支的Python脚本很烂是真的



## 写在最后

这个项目纯粹是我像找个地方存壁纸用的,各位都应该发现了我把摄影师的水印都去掉了.

虽然去水印这事显得我跟海盗一样,但是各位也应该可以猜的到一个水印唐突放桌面上也确实很奇怪.

也很抱歉我没有问过任何一个人,也没有任何人会同意我做这件事,但最起码我自己开心了,有了一个自己时不时维护的东西随时随地都可以取到自己心爱的东西来看. 很明显的是这个小小的仓库被大部分人发现的时候我可能会遭遇很多比较严重的版权问题,但我除了维护这个仓库之外,我也没什么自己真正想做的了. 只能希望各位到时候手下留情,让我自己对着这些"玩偶服"傻笑罢.

不知道长大后回来看自己小时候坚持做的这个无人问津的仓库会是什么心情呢. 这么个为爱维护但是没人理解的小玩意.

也希望看到这里的各位福瑞控们身体健康,万事如意. 就让我自己一个人在这傻笑罢.



## 感谢...

太美丽啦的系统:[⭐Debian GNU/Linux⭐](https://www.debian.org/), 

难学但是貌似挺好用的:[Git SCM](https://git-scm.com/)

虽然可以买但是我没钱买的:[Typora](https://typora.io)

到处可以同步的[Microsoft Edge](https://www.microsoft.com/zh-cn/edge)

比[GNOME](https://wiki.installgentoo.com/wiki/File_Picker_meme)好用且支持非整数缩放的[KDE等离子体桌面](https://kde.org/zh-cn/plasma-desktop/)

给我用来简单编辑图片的[GIMP](https://www.gimp.org/)

简单易用的本地AI图像放大[Upscayl](https://upscayl.org/)

训练出效果超级好的AI放大模型的[Phhofm大佬](https://github.com/Phhofm/models/)

写出Upscayl所使用的AI放大算法软件基底的[xinntao大佬(不知道中文捏)](https://github.com/xinntao/Real-ESRGAN)

用来优化jpeg的[jpegoptim](https://github.com/tjko/jpegoptim)工具

许久未更新的[mozjpeg](https://github.com/mozilla/mozjpeg)

我压根不知道高级功能但是已经离不开的~~臭名昭著的电脑勒索病毒~~[Vim](https://github.com/vim/vim)

在[BiliBili](https://www.bilibili.com)生活的各位兽兽还有摄影师们,抱歉随意拿走你们的幸苦成果了:(

<!--又不是最终结算写这么多干啥-->

 ### 防止失忆用文档

如何克隆这个~~智障~~仓库：

## SSH

> 你最开始需要做的是自己注册个GitHub账户,如果遇到什么访问不了的问题自行解决，都来这看了不有个号怎么行呢。

检查自己有ssh密钥没。一般来说都可以在[这里](https://docs.github.com/zh/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)查看文档来自行添加一个（ssh密钥是通用的，但通常推荐每个获得Github访问权限的设备都有单独的密钥，万一真的出事了可以方便注销密钥）

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

   这时候最好直接回车，因为这块小破地方ssh尝试连接时会寻找这里的密钥进行验证（记得拷贝括号的内容，后面有用）

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

5. 透过ssh技术克隆这个仓库

   `git clone --depth=1 -j 16 git@github.com:dontknowhy/MyTheme-private.git`

   注释: 1.  `--depth=1`只仅克隆一层仓库，人话就是哥们不用下载我黑历史。

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

或者去寻找一些proxy方案,例如[GitHub Proxy](https://mirror.ghproxy.com/donate)

`git clone --depth=1 -j 16 https://mirror.ghproxy.com/https://github.com/dontknowhy/MyTheme-private.git`

## `github.com`永不为奴！

感觉不如______.

如果GFW漏风都是万幸。

如果你为自己创造了良好的网络环境(大嘘)的话可以用.

<!--讨厌全角和半角符号区别-->

## 貌似是常见的问题

1. ​	在一些罕见的地方可能遇到git很难克服的问题,例如实在没有办法撑住时不时断开连接的网络.这时候可以去[releases](https://github.com/dontknowhy/MyTheme-private/releases/tag/v2.1)(链接为原版GitHub,自己替换为镜像站)下载大约6.5GB的[7zip](https://7-zip.org)分片压缩包,解压出来后会出现一个叫`main.bundle`的东西,这个叫`git bundle`,可以直接使用`git clone main.bundle theme`来像在线链接一样克隆(不接受`--depth`参数,`-j`参数也是).

   ​	克隆下来后默认的上游为`main.bundle`的绝对路径,需要手动设置上游:`git remote set-url origin git@github.com:dontknowhy/MyTheme-private.git`(ssh坏了的话自行寻找镜像站替换).

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

我压根不知道高级功能但是已经离不开的~~臭名昭著的电脑勒索病毒~~[Vim](https://github.com/vim/vim)

在[BiliBili](https://www.bilibili.com)生活的各位兽兽还有摄影师们,抱歉随意拿走你们的幸苦成果了:(

<!--又不是最终结算写这么多干啥-->

<!-- .github/copilot-instructions.md - 为 AI 编码代理提供的针对性指南 -->

# 项目快速引导（给 AI 编码代理）

目标：帮助 AI 代码助手快速理解本仓库的 "为什么" 与 "怎么做"，可直接给出安全、可运行的改动建议。

**大体架构与目的**:
- **用途**: 这是一个以 AI 放大/处理图片为主的私人仓库，用来管理壁纸图集并对图片做两次放大/降噪等处理（见 `README.md`）。
- **处理流程**: 从 `scripts/input`（或 `下载` 等自定义目录）读取原图 → 第一次放大/降噪（JPEGDestroyer 等）→ 合并 3K 源图 → 第二次放大（`4xNomos8kSC` 等）→ 转换/优化 → 分类到 `横/` 与 `竖/`。
- **关键实现**: 核心由一组 Bash 脚本驱动（见 `scripts/upscayl.sh`, `scripts/sync_metadata.sh`）。

**关键路径（一定要提及）**:
- `scripts/upscayl.sh` - 用户可配置的批量处理脚本，定义了默认目录、模型名、upscayl 可执行文件位置等。
- `scripts/sync_metadata.sh` - 使用 `exiftool` 和 `parallel` 批量将原图元数据同步到处理后文件。
- `横/`、`竖/` - 最终按方向分类的图片目录（目录名包含中文，注意路径编码）。

**项目特有约定与模式（不要照搬通用做法，按此执行）**:
- 脚本均假定 `zsh`/`bash` 环境（仓库作者在 Linux 上使用 `zsh`）。生成或修改路径时要保留中文目录名的正确编码（例如 `/home/.../图片/...`）。
- 图片处理采用“先降噪/预处理 → 放大 → 修整/优化”的两阶段上采样流程：第一次使用 `FIRST_MODEL`（如 `1x_JPEGDestroyerV2_96000G-fp16`），第二次使用 `SECOND_MODEL`（如 `4xNomos8kSC`）。

**常用命令与示例（直接可用）**:
- 使用用户配置的 upscayl 脚本（示例，脚本内部有配置区）：
  - `bash scripts/upscayl.sh`
- 将元数据从原始图片同步到放大后的图片：
  - `bash scripts/sync_metadata.sh -j 8`  # 使用 8 个并行任务
- 快速将仓库内 PNG 转为 JPG（仅在小文件夹测试时）(目前已废弃)：
  - `bash scripts/png2jpg.sh`

在给出修改建议时，如果要改动脚本默认路径或模型名，请同时给出两条提示：1. 如何在脚本顶部配置变量；2. 推荐的验证命令（如 `file`、`identify`、`which upscayl-bin`、运行一次小样本）。

**外部依赖与检查点**:
- 必备工具（脚本会检查并依赖）：`ImageMagick`（`identify`/`magick`）、`bc`、`exiftool`、`parallel`（仓库内或系统路径）。
- 在变更二进制或模型前，建议先运行：
  - `command -v exiftool`  # 确认依赖
  - `file scripts/binary/upscayl-bin`  # 检查架构

**给 AI 的安全边界（必须遵守）**:
- 不要把大文件（模型、二进制、图片）添加到 git 历史中；若需要改动二进制或模型，优先建议用户在本地重编译或把新文件放在 `scripts/binary/` 并在 README 中记录来源与签名。
- 不要自动删除原始图片或替换 `横/`、`竖/` 中已被 git 跟踪的文件；所有批量操作应先在 `tmp` 或用户配置的 `下载` 目录里做小规模试验。

**快速定位修改点（常见改动）**:
- 更换模型：修改 `scripts/upscayl.sh` 顶部的 `FIRST_MODEL` / `SECOND_MODEL` 变量和 `MODELS_DIR` 路径。
- 更改 upscayl 可执行路径：修改 `UPSCAYL_BIN` 或 `upscaler` 变量。

如果你发现本文件遗漏了与运行或部署直接相关的细节（例如用户本地的 `DOWNLOAD_DIR` 路径习惯、CI 流程或 README 中未提及但脚本依赖的环境变量），请指出并请求我提供样例运行输出或额外文件以补充。谢谢！

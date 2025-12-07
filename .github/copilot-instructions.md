<!-- .github/copilot-instructions.md - 为 AI 编码代理提供的针对性指南 -->

# 项目快速引导（给 AI 编码代理）

目标：帮助 AI 代码助手快速理解本仓库的 "为什么" 与 "怎么做"，可直接给出安全、可运行的改动建议。

**大体架构与目的**:
- **用途**: 这是一个以 AI 放大/处理图片为主的私人仓库，用来管理壁纸图集并对图片做两次放大/降噪等处理（见 `README.md`）。
- **处理流程**: 从 `scripts/input`（或 `下载` 等自定义目录）读取原图 → 第一次放大/降噪（JPEGDestroyer 等）→ 合并 3K 源图 → 第二次放大（`4xNomos8kSC` 等）→ 转换/优化 → 分类到 `横/` 与 `竖/`。
- **关键实现**: 核心由一组 Bash 脚本驱动（见 `scripts/upscayl.sh`, `scripts/sync_metadata.sh`）。
- **编码风格**： 1. 事事要检查；2. 尽可能确保代码的简洁和鲁棒性；3. 注释要清晰，尤其是复杂逻辑处。

```instructions
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

## 额外说明：`scripts/upscayl.sh` 详解与维护要点

**脚本功能概述**:
- **用途**: 批量使用 `upscayl` 可执行文件对图片做两阶段上采样/降噪处理（低质量预处理 -> 第一次放大 -> 合并 3K 源图 -> 第二次放大 -> 输出）。
- **输入/输出目录**: 脚本通过顶部变量控制目录路径，默认使用 `下载` 目录下的若干子目录（例如 `temp-1080`, `temp-3k`, `temp-poor`, `final`）。
- **模型与二进制**: 通过 `UPSCAYL_BIN` 指定 upscayl 程序路径，通过 `MODELS_DIR`、`FIRST_MODEL`、`SECOND_MODEL` 指定模型。

**实现结构（模块化视角）**:
- **配置区**: 顶部变量易于修改（路径、程序、模型、输出格式、线程等）。
- **工具函数**: `check_and_create_dir`, `is_supported_image`, `check_all_images`, `check_dir_has_images`, `check_model`, `clean_model_name`, `run_upscayl`, `count_images` ——将常用操作封装，便于复用和单元调试。
- **主流程** (`main`) :
  - 准备/校验阶段：创建目录、检查目录是否存在且为期望的图片集合、检查可执行文件和模型文件。
  - 可选的 `temp-poor` 处理：若存在，则先用 `FIRST_MODEL` 处理并把结果复制到 `final`。
  - 第一次放大：在 `TEMP_1080_DIR` 上使用 `FIRST_MODEL`，输出到 `TEMP_1080_DIR/upscayl_...`。
  - 合并 `temp-3k`：把 `TEMP_3K_DIR` 中图片复制（合并）到第一次放大输出目录，随后再次校验目录是否全部为图片。
  - 第二次放大：对合并后的目录使用 `SECOND_MODEL`，输出到第二次输出目录。
  - 最终复制到 `FINAL_OUTPUT_DIR` 并输出统计信息。

**后期编辑时需要注意的事项**:
- **路径中的中文/编码**: 仓库的路径包含中文（例如 `图片`, `下载`），在脚本和 CI 环境中必须保持 UTF-8 环境；如果在其他机器上运行，请确认 `LANG`/`LC_ALL` 为 `UTF-8`，否则可能出现路径解析错误。
- **不要覆盖原始/已跟踪文件**: 脚本会把处理结果复制到 `FINAL_OUTPUT_DIR`，但请勿自动删除或覆盖仓库中 `横/`、`竖/` 等已被 git 跟踪的文件。所有大规模操作应先在 `下载` 下的临时目录做小样本测试。
- **模型文件命名与格式**: `check_model` 假定模型为两部分文件：`${model}.param` 和 `${model}.bin`。更换模型时请保证这两种文件存在，或同时更新 `check_model` 的校验逻辑。
- **UPSCAYL 可执行性**: `UPSCAYL_BIN` 必须是可执行文件。脚本用 `-x` 检查；如果 upscayl 为脚本或在 PATH 中，建议把路径改为 `$(which upscayl-bin)` 或在脚本顶部说明如何修改。
- **线程/并发参数**: `THREADS` 变量格式为脚本作者自定义（如 `1:2:2`），确保 `upscayl` 支持该参数格式；若修改并发策略，请同时调整 `run_upscayl` 中传参逻辑或在备注中说明含义。
- **错误处理与退出策略**: 当前脚本在关键步骤（如模型检测或放大失败）会 `exit 1`，这在交互式使用时很方便，但在 CI 或批处理时可能希望改为记录错误并继续处理后续目录——如需改为“容错”模式，请把 `exit` 改为记录警告并跳过。
- **文件类型识别**: `is_supported_image` 使用文件名后缀判断，不使用 `file` 或 `identify` 进行内容检测。在可能存在错误扩展名的环境下，建议补充基于 `file`/`identify` 的验证步骤。
- **拷贝行为**: `cp "src"/* "dst"/ 2>/dev/null` 在源目录为空或包含子目录时会失败或产生警告。若要更健壮的复制（包括子目录或特殊字符），请使用 `rsync -a --ignore-errors` 或 `find ... -exec cp`。

**推荐的验证与调试命令**:
- **检查依赖**: `command -v exiftool || command -v magick || command -v identify`，确认 `upscayl` 二进制：
```
which upscayl-bin
file /opt/Upscayl/resources/bin/upscayl-bin
```
- **检查模型文件**: 列出模型目录：
```
ls -l "$HOME/custom-models/models" | grep "${FIRST_MODEL}\|${SECOND_MODEL}"
```
- **小样本测试运行**: 在 `TEMP_1080_DIR` 放 1-3 张图片，运行：
```
bash scripts/upscayl.sh
```
或直接调用 `run_upscayl`（如果打算单独测试）：
```
"$UPSCAYL_BIN" -i "${TEMP_1080_DIR}" -o "${TEMP_1080_DIR}/test_out" -m "$MODELS_DIR" -n "$FIRST_MODEL" -f "$OUTPUT_FORMAT" -c "$COMPRESSION_LEVEL" -j "$THREADS" -v
```

**常见更改与定位说明**:
- **更换模型**: 编辑脚本顶部 `FIRST_MODEL` / `SECOND_MODEL`，并验证对应的 `${model}.param` 与 `${model}.bin` 存在于 `MODELS_DIR`。
- **更改可执行文件位置**: 修改 `UPSCAYL_BIN` 为新的绝对路径或 `$(which upscayl-bin)`。
- **调整输出格式**: `OUTPUT_FORMAT` 可设为 `png|jpg|webp`，注意对应 `COMPRESSION_LEVEL` 在不同格式下含义不同。
- **从严格检查改为宽容模式**: 把 `check_all_images` 的严格判断改为 `check_dir_has_images` 或在 `main` 中引入 `--force` 参数以跳过非图片文件检验。

```

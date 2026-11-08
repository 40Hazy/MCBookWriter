# MCBookWriter

Minecraft 批量写书工具链，由两个独立组件组成：

- **BookForge（Python）**：读取 txt/EPUB/FB2/DOCX 等书稿，完成编码识别、正文清洗、章节识别、分段，生成可校验的 `job.json`。
- **AutoBook（Fabric 客户端模组）**：读取 `job.json`，按 Minecraft 书本实际排版分页、自动续本，循环写入并签名，支持进度保存与断点续写。

当前版本：**AutoBook 0.11.0**、**BookForge 0.6.0**。支持 Minecraft **1.21.5–1.21.11** 与 **26.1、26.1.1、26.1.2、26.2**，每个版本使用对应的 AutoBook jar。单本写入已在 1.21.8 服务器实测通过；0.3.0 改进跨章节打包与慢速重试，0.4.0 增加标点断书与页数配置，0.5.0 增加内容校验、失败自恢复与配置命令，0.6.0 增加多任务队列，0.7.0 增加游戏内配置界面并支持 Minecraft 1.21.5–1.21.8，0.8.0 增加 Minecraft 26.1.x（26.1.2）支持，0.8.1 修复 `/autobook ui` 不显示界面，0.8.2 修复配置界面文字不可见，0.8.3 将数据目录改为游戏目录下的 `autobook/` 并在加载模组时自动创建，0.9.0 增加整书 SHA-256 摘要校验与已验证本数统计，0.11.0 合并单本与队列为统一运行流水线（add/start/pause/resume/cancel/stop/remove/retry），0.11.0 增加 `/autobook help` 与游戏内说明页；BookForge 0.3.1 增加电子书导入、LLM 抽样核验与补丁 diff，0.4.0 增加桌面 GUI（导入与生成 job），0.4.1 增加成本预估、profile 查看并修正古籍通假字误报，0.5.0 完成 LLM 报告/补丁审阅、配置编辑与 PyInstaller 打包，0.6.0 增加 API key 的 GUI/CLI 管理与 profile key_file。

## 核心能力

- 按游戏内像素宽度分页：每行 114 px、每页 14 行、每页最多 1023 字符。
- 跨章节打包：页会连续装满每本（默认最多 100 页），不再把短章节单独装订，显著减少空书消耗。
- 标点断书：优先让每本的最后一句在句末标点（。！？…等）处结束，避免书与书之间截断句子。
- 每本页数、断句开关、写入节奏都可在 `config.json` 中调整，也可用 `/autobook config` 或 `/autobook ui` 界面修改。
- 内容校验：签名后回读成书页数与文本，检测截断/乱码；不一致时暂停并记录。
- 失败自恢复：多次未确认时自动长等待并模拟“打开/关闭书本页面”，再重试，减少人工 resume。
- LLM 核验/补丁（BookForge）：可选用 OpenAI 兼容接口核验正文；报告模式只出问题，补丁模式输出 `find/replace`，经本地硬校验后生成 reviewed job。
- API key 管理：GUI 与 `bookforge key set/status/clear/test` 均可配置；只显示掩码与来源，支持每本书 profile 的 `key_file`。
- 长内容自动续本，书名按 `基名-01`、`基名-02` 递增。
- 循环写入整个任务的所有书，不再只写第一本。
- 进度写入 `autobook/state/<planHash>.json`，支持 `/autobook resume` 断点续写。
- 统一运行流水线：单本只是“一个任务的运行”，多任务用 `add` 逐个加入；状态保存到 `autobook/run.json`，重启后可继续。
- 成书标题与页数重复检测：已签名的书不会重复印刷。
- 空书耗尽时自动暂停，拾取到新空书后自动继续。
- 可选：写完立即丢出成书，便于红石/漏斗自动收集。

## 快速开始

### 1. 预处理书稿

```powershell
cd bookforge
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

bookforge prepare "D:\path\your-book.txt" --title 三体1 --out work\三体1 --verify

# 也可以直接导入电子书；--title 省略时使用电子书元数据或文件名
bookforge prepare "D:\path\your-book.epub" --out work\your-book --verify
```

支持的输入：

- 原生解析：`.txt`、`.epub`、`.fb2`、`.docx`
- Kindle 格式：`.azw3`、`.mobi`、`.azw`、`.kf8`、`.prc`
  - 优先使用 Calibre；未安装 Calibre 时自动使用 Python `mobi` 库（已包含在依赖中）。
  - 也可用 `--calibre` 指定 `ebook-convert` 路径。
- 只支持无 DRM 的文件，本项目不处理 DRM 移除。

生成：

- `work/三体1/job.json`：模组输入。
- `work/三体1/report.json`：清洗与分段报告。
- `work/三体1/00_imported.txt`、`import.json`：电子书导入的正文与元数据/原始哈希（仅电子书输入）。
- `work/三体1/01_normalized.txt`、`02_cleaned.txt`：中间文本。

### 1.1 可选：LLM 核验与补丁

1. 将 API key 写入 `bookforge/keys/llm_api_key.txt`（该文件默认空，已被 git 忽略）。
2. `bookforge/keys/llm_config.json` 已预置 DeepSeek 连接；`profiles` 按书名配置，可分别设置 `model`、`max_chars`、`max_tokens`、`glossary`、`style`、`min_confidence`、`max_delta`。
3. `keys/glossary.txt` 是全局术语表，`keys/glossary-三体1.txt` 是三体1 专用术语表。
4. 运行：

```powershell
# 只出问题报告
bookforge review work\三体1\job.json --mode report

# 首/中/尾抽样校准
bookforge review work\三体1\job.json --mode report --sample 3

# 小规模试跑补丁
bookforge review work\三体1\job.json --mode patch --limit 2

# 全量生成补丁
bookforge review work\三体1\job.json --mode patch

# 本地校验并应用补丁，生成 reviewed job
bookforge apply-patch work\三体1\job.json --patch work\三体1\llm_patch.json --out work\三体1\reviewed
```

`review` 默认按 job 的 `titleBase` 自动选择 profile；也可用 `--profile <名字>` 显式指定。`--sample N` 会从全书均匀抽取 N 块，适合先做质量校准；`--limit N` 只跑前 N 块。`apply-patch` 额外输出 `diff.patch`，逐条查看已应用修改。网络连接异常会自动重试 3 次。

`deepseek-flash` 默认关闭推理模式（`thinking=false`），`max_tokens=8192`、`max_chars=4000`；实测每块约 2655 输入 + 389 输出 tokens，`reasoning=0`。若要启用推理，需把 `max_tokens` 加大到约 16384。

### 1.2 桌面 GUI

```powershell
cd bookforge
pip install -e ".[gui]"
bookforge-gui
```

GUI 提供 5 个标签页：生成 job、LLM 核验（report/patch、进度/取消）、补丁审阅（勾选/应用/diff/rejected）、配置（profile/API key/测试连接/安装到游戏目录）、帮助（离线内置 HTML、版本与路径信息、打开配置/日志/游戏目录按钮）。也可打包为 exe：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-gui.ps1 -InstallDeps
# dist\gui\BookForge\BookForge.exe
```

### 2. 安装模组

1. 安装 Fabric Loader 0.16.14+、Fabric API 0.136.1+1.21.8、Java 21。
2. 将 `dist/autobook-0.11.0.jar`（Minecraft 1.21.8）放入客户端 `mods/`。
   - 其他版本：运行 `scripts/build-multi.ps1` 生成 `autobook-0.11.0-mc<版本>.jar`，安装与游戏版本匹配的那个。
   - 当前支持 1.21.5、1.21.6、1.21.7、1.21.8、1.21.11，以及 26.1、26.1.1、26.1.2、26.2。
   - 1.21.11：Java 21、Fabric Loader 0.20.1、Fabric API 0.141.6+1.21.11。
   - 26.1 / 26.1.1 / 26.1.2：Java 25、Fabric Loader 0.20.1、Fabric API 0.155.3+26.1.2。
   - 26.2：Java 25、Fabric Loader 0.20.1、Fabric API 0.161.0+26.2。
3. 将 `job.json` 复制到 `.minecraft/autobook/jobs/三体1.json`。
4. 启动游戏，进入允许正常写书/签名的服务器。

### 3. 游戏内操作

```text
/autobook help            查看帮助；help <主题> 查看单项
/autobook plan 三体1      只预演，不改变运行状态
/autobook add 三体1       加入当前运行（可多次添加不同任务）
/autobook start           开始当前运行
/autobook start 三体1     新建单任务运行并开始（等价于 add + start）
/autobook list            查看运行与全部任务状态
/autobook status          查看当前任务、页数与校验统计
/autobook pause           可恢复暂停
/autobook resume          从暂停继续（旧的 resume <任务名> 仍可用）
/autobook cancel          取消当前任务，运行继续下一个
/autobook stop            终止整条运行（CANCELLED，进度保留）
/autobook remove 三体1    移除未开始或已结束的任务记录
/autobook retry 三体1     把失败/已取消的任务重新入队
/autobook ui              打开游戏内配置界面
```

开始前准备足够的**空的书与笔**（一本成书消耗一本空书）。运行期间保持书本编辑界面关闭。

首次使用建议先跑 `dist/jobs/autobook-test.json` 验证服务器是否接受模组的写入包。

## 构建与安装

```powershell
# 构建并暂存到 dist（会先跑 pytest 与 Gradle 测试）
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1

# 构建 GUI 可执行文件（可选）
powershell -ExecutionPolicy Bypass -File .\scripts\build-gui.ps1 -InstallDeps

# 为多个 Minecraft 版本分别构建（发布前默认只构建 1.21.8）
powershell -ExecutionPolicy Bypass -File .\scripts\build-multi.ps1 -SkipTests

# 构建并安装到指定游戏目录（会移除旧的 autobook jar、校验 jar 版本与 Fabric API）
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -GameDir "F:\Minecraft\.minecraft\versions\1.21.8-Fabric 0.17.3"

# 一键发布构建（版本校验 + 全部测试 + 9 版本 jar + GUI + 验收 + 组包到 dist\release）
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1
```

`build.ps1 -GameDir` 安装的是当前 `gradle.properties` 对应版本（默认 1.21.8）。26.x 请手动复制 `dist/autobook-0.11.0-mc26.x.jar` 到该客户端 `mods/`。

安装脚本会创建 `autobook/jobs`、`state` 目录，并提示任务数量。

发布：`scripts/release.ps1` 生成 `dist/release/MCBookWriter-<版本>/`（全部 jar、GUI zip、文档、示例 job、`checksums-sha256.txt`），GitHub Release / Modrinth 流程与验收清单见 [发布流程](docs/release.md)。

## 目录结构

```text
MCBookWriter/
├─ bookforge/        Python 预处理与 LLM 核验（含 pytest 测试）
│  └─ keys/          llm_api_key.txt（空）、llm_config.json、glossary*.txt
├─ autobook/         Fabric 客户端模组（含 JUnit 测试）
├─ autobook-26/      Minecraft 26.x 独立构建工程（unobfuscated Loom）
├─ scripts/          build.ps1 / build-multi.ps1 / build-gui.ps1 / release.ps1
├─ dist/             已构建 jar 与示例 job
│  └─ jobs/          autobook-test.json、三体1.json
└─ docs/             架构、使用、任务格式、红石与计划文档
```

## 文档

- [架构说明](docs/architecture.md)
- [使用手册](docs/usage.md)
- [任务格式](docs/job-schema.md)
- [红石补给方案](docs/redstone.md)
- [项目计划与路线图](docs/plan.md)
- [发布流程](docs/release.md)
- [更新日志](CHANGELOG.md)

## 已知限制

- 只保证写入流程与页面文本一致；不做服务端存储层面的逐字节校验。
- 支持 Minecraft 1.21.5–1.21.11 与 26.1、26.1.1、26.1.2、26.2；每个版本使用 `build-multi.ps1` 生成的对应 jar。1.21.4 及更早版本暂不支持。
- 构建 26.x 需要 JDK 25、Gradle 9.8.2、Loom 1.19.4；1.21.x jar 仍以 Java 21 为目标。
- 默认会跳过背包中标题与页数都相同的已签名书；需要重印时先移除旧书或设置 `skipExistingBooks=false`。
- 内容校验失败会暂停并保留问题书，需人工移除后 resume。
- 电子书导入支持 EPUB/FB2/DOCX 原生解析；AZW3/MOBI/AZW/KF8 需要 Calibre，且只支持无 DRM 文件。
- LLM 补丁只应用 `high` 置信度且通过本地硬校验的修改；被拒绝项需人工处理。
- 推理模式默认关闭（`thinking=false`）；若开启，reasoning tokens 会占用输出预算，需要加大 `max_tokens`。
- 使用 reviewed job 会改变 `planHash`，需要在游戏内重新 `/autobook start`。
- 队列中修改 job 内容或 `options` 也会改变 `planHash`，该任务会从头开始；默认会跳过已签名书。
- 依赖服务器正常处理原版书本编辑包；部分服务器可能有额外限制。
- 客户端模组，仅需客户端安装，不需要服务端装模组。
- `config.json` 在每次 `start`/`resume` 时重新读取，无需重启游戏。

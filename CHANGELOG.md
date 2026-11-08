# 更新日志

## 版本适配：1.21.11 与 26.1 / 26.1.1 / 26.2 — 2026-11-08

不改变功能版本号（AutoBook 0.11.0 / BookForge 0.6.0），新增四个 Minecraft 目标版本。

新增：

- 构建目标：`1.21.11`（Java 21、Fabric API `0.141.6+1.21.11`、Loader `0.20.1`）、`26.1` / `26.1.1`（Java 25、Fabric API `0.155.3+26.1.2`、Loader `0.20.1`）、`26.2`（Java 25、Fabric API `0.161.0+26.2`、Loader `0.20.1`）。
- `compat/ScreenCompat`（`java-21` / `java-26`）：统一当前界面读取与切换。1.21 直接访问 `Minecraft.screen`；26.x 通过反射同时兼容 `Minecraft.screen/setScreen`（26.1.x）与 `Gui.screen()/setScreen()`（26.2）。
- `scripts/build-multi.ps1`：`autobook-26` 工程按目标版本自动改写 `mod_version`、`minecraft_version`、`fabric_version`、`loader_version`、`java_release`，并在 `finally` 中恢复两个工程的 `gradle.properties`。

修复：

- `ClientCompat.playerName` 改用 `Player.getName().getString()`：1.21.11 的 authlib 中 `GameProfile` 已为 record，`getName()` 不存在。
- 删除未被引用的 `autobook/build-26.gradle`。
- `.gitignore` 补充 `autobook-26/` 的 `build/`、`run/`、`.gradle/` 与日志目录。

验证：

- 四个新 jar 均构建成功：`dist/autobook-0.11.0-mc1.21.11.jar`、`-mc26.1.jar`、`-mc26.1.1.jar`、`-mc26.2.jar`。
- 26.2 的界面 API 迁移（`Minecraft.screen` → `Gui.screen()`）已编译通过。
- 待真实客户端验证四个版本的写书、内容校验与 `/autobook ui`。

## P5.5 发布准备 — 2026-11-07

发布基础设施，不含功能版本变更（AutoBook 0.11.0 / BookForge 0.6.0 保持不变）。

新增：

- `scripts/release.ps1`：一键发布构建。
  - 版本一致性校验：两个工程的 `gradle.properties`、`__init__.py`、`pyproject.toml`、README、CHANGELOG 不一致即中止。
  - 测试：pytest、JUnit（1.21.8 与 26.1.2）。
  - 构建：5 个 Minecraft 版本 jar + PyInstaller GUI。
  - 验收：每个 jar 的 `fabric.mod.json` 版本与 Minecraft 依赖精确匹配文件名，且包含帮助类 `HelpText`；GUI 打包不含非空 API key；按默认 key 与 `llm_config.json` 中所有 `key_file` 全文扫描发布包，确保无明文 key。
  - 组包：`dist/release/MCBookWriter-<版本>/`（jar、GUI zip、README/CHANGELOG/INSTALL/RELEASE_NOTES、docs、examples），并生成 `checksums-sha256.txt` 与整包 zip。
  - 安装验收：发布包内示例 job 通过 `bookforge validate`，并检查样例不少于 4 段。
- `docs/release.md`：GitHub Release / Modrinth 发布流程、分阶段验收清单与已知风险表。
- `docs/examples/sample_job.json` + `sample_source.txt`：可复现的 4 章示例 job（`pageLimit=5`，约 1800 字，预期 3 本），覆盖跨章节续本、对话引号、省略号与破折号断句、英文数字混排。
- `docs/usage.md` 修正构建产物版本号（0.9.0 → 0.11.0），补充 release.ps1 说明。

修复：

- CHANGELOG 中两个重复的 `BookForge 0.6.0` 段落合并为一段（P7.2 / P7.3 子标题），避免 `RELEASE_NOTES.md` 重复。
- `INSTALL.txt` 的版本列表按实际构建的 `-Versions` 生成，不再写死 5 个版本。

## 0.11.0 — 2026-11-07

P7.1：AutoBook 游戏内帮助。

新增：

- `/autobook help`：首次使用流程、完整命令表、运行/任务状态简表。
- `/autobook help <主题>`：`start`、`run`、`job`、`cancel`、`config`、`verify`、`recover`；支持中文别名（运行、取消、校验等）。
- 配置界面底部“说明”按钮打开 `AutoBookHelpScreen`：按屏幕宽度换行、上一页/下一页/返回；1.21 与 26.1 各一套渲染实现。
- 帮助文本集中到 `HelpText`，命令与 UI 共用，并显示模组版本号。
- 命令失败时追加提示 `/autobook help`。

验证：

- JUnit 55 项通过（新增 HelpText 3 项；1.21.8 与 26.1.2 各一次）。
- 待真实客户端验证说明页分页、返回与 GUI 缩放。

## BookForge 0.6.0 — 2026-11-07

### P7.2：API key 管理

新增：

- `keymanagement.py`：统一解析 key 来源与路径，优先级为 CLI > `BOOKFORGE_LLM_KEY_FILE` > profile `key_file` > 全局 `key_file` > 默认 `keys/llm_api_key.txt`。
- CLI：
  - `bookforge key status`：只显示 configured/missing、来源、路径与掩码，不输出明文。
  - `bookforge key set`：默认交互输入（不回显）；`--file` 从已有文件读取，避免命令行历史泄露。
  - `bookforge key clear`、`bookforge key test`。
- GUI“配置”页新增 API key 区：密码框输入、保存、清除、测试连接；显示掩码与来源；profile 新增 `key_file` 字段。
- 保存使用 `.tmp` + `os.replace` 原子写入；POSIX 下尝试设置为 600 权限。
- 清除后 profile/全局的空 `key_file` 会从配置中移除，回退到默认路径。

安全：

- 任何界面、日志、报告与 CLI 输出都不包含明文 key。
- PyInstaller 打包仍只带空模板，不打包真实 key。

验证：

- pytest 77 项通过（新增 keymanagement 7 项、profile key_file 1 项）。
- 打包 exe 已随 P7.3 重新构建并验证可启动。

### P7.3：帮助中心

新增：

- GUI 新增第 5 个“帮助”标签页（`gui/help_content.py`）：
  - 离线内置 HTML：快速开始、支持格式、LLM 核验流程、补丁安全规则、密钥配置、安装到游戏、常见错误、游戏联动规划说明。
  - “版本与路径信息”区动态显示版本号、Python、配置/密钥/术语表实际路径、key 状态（掩码）与当前游戏目录；切换到该页自动刷新。
  - “打开配置目录”“打开日志目录”（游戏 logs，缺失时回退到游戏目录）“打开游戏目录”三个按钮，未设置游戏目录时提示并跳转到“配置”页。
  - 内容完全内置在代码中，不读外部文件、不加载网络资源；PyInstaller 打包版可离线查看。
- 各页关键控件补充 tooltip（输入格式、生成参数、核验模式/抽样、补丁应用、profile 字段、安装路径等）。

验证：

- pytest 82 项通过（新增 test_gui_help 5 项：必备章节、离线无外部资源、版本/路径、HTML 转义、空游戏目录）。
- `scripts/build-gui.ps1` 重新打包，BookForge.exe 启动正常。

## 0.10.0 — 2026-11-07

统一单本与队列为一条运行流水线。

破坏性变更：

- `/autobook stop` 的语义改为**终止整条运行**（Run → CANCELLED），不再用于“停止后 resume”。需要可恢复暂停请使用 `/autobook pause`。
- `/autobook resume` 只接受 PAUSED 状态；旧的 `resume <任务名>` 仍可执行，但任务名必须与当前暂停任务一致。
- 队列状态文件从 `queue.json` 迁移为 `run.json`；首次加载自动迁移并保留 `queue.json.bak`。

新增：

- 运行级状态：`CREATED → PLANNING → QUEUING → RUNNING ⇄ PAUSED → COMPLETED`，另有 `FAILED`、`CANCELLED`。
- 任务级状态：`PENDING → QUEUED → RUNNING ⇄ PAUSED → COMPLETED`，另有 `FAILED`、`CANCELLED`。
- 命令：`add`、`start [job]`、`list`、`status`、`pause`、`resume`、`cancel [job]`、`stop`、`remove`、`retry`；`plan` 保持只读预演。
- 单本等价于“只有一个任务的运行”：`start <job>` = `add <job>` + `start`。
- `cancel` 取消当前任务后运行继续下一个；`remove` 只允许移除 PENDING/QUEUED；`retry` 把 FAILED/CANCELLED 重新入队，FAILED/CANCELLED 运行回到 QUEUING。
- 重启后 RUNNING 恢复为 PAUSED，不自动开写。
- 旧 `queue add/list/start` 保留为别名并提示弃用；`queue clear` 等价于 stop + 清空任务。

实现：

- 新增 `run` 包：`RunJob`、`RunState`、`RunStore`、`RunRunner`；删除旧 `queue` 包。
- `RunStore` 读取 `run.json` v2，缺失时迁移旧 `queue.json`（pending→QUEUED、running→PAUSED）。
- `BookWriter.Progress` 增加 `verifiedBooks`；`run.json` 记录每任务的 `totalPages/verifiedBooks/planHash`。

验证：

- JUnit 52 项通过（1.21.8 与 26.1.2 各一次）。
- 待真实客户端验证完整状态流转、cancel/stop/remove 与旧队列迁移。

## 0.9.0 — 2026-11-07

P5.4：整书内容摘要校验。

- `ContentVerifier` 新增 `digest(pages)`：对规范化后的整书页面计算 SHA-256。
- 校验结果附带 `expectedDigest` / `actualDigest`；成功日志记录整书摘要，失败日志同时输出两边摘要，便于排查页数缺失、截断与替换。
- `RunState` 新增 `verifiedBooks`，每次校验成功计数并随进度保存；resume 时恢复，`/autobook status` 行为不变。
- `BookWriter` 校验成功时更新已验证本数；`forceRewrite` 与暂停逻辑不变。

验证：

- JUnit 47 项通过（新增整书摘要 3 项、进度计数 1 项；1.21.8 与 26.1.2 各一次）。
- 待真实客户端确认摘要日志与恢复计数。

## 0.8.3 — 2026-11-07

AutoBook 数据目录改为游戏目录下的 `autobook/`，并在加载模组时自动创建。

- 数据目录从 `config/autobook/` 改为 `.minecraft/autobook/`，与 `mods/` 同级，便于用户直接找到并放入 job。
- 客户端初始化时自动创建 `autobook/jobs/`、`autobook/state/`，并生成默认 `config.json`；无需等到第一次执行命令。
- 首次启动会自动迁移旧 `config/autobook/` 的内容：
  - 只复制新目录中尚不存在的文件/目录，不覆盖已有文件；
  - 迁移后保留旧目录，不做删除。
- 新增 `AutoBookPaths` 统一管理 `config.json`、`jobs/`、`state/`、`queue.json` 路径。
- `scripts/build.ps1 -GameDir` 与 BookForge GUI 的“安装 job”同步改为 `<游戏目录>/autobook/jobs/`。

验证：

- JUnit 43 项通过（1.21.8 与 26.1.2）。
- BookForge pytest 通过。
- 尚未在真实客户端确认自动创建与旧目录迁移，仅完成编译与单元测试。

## 0.8.2 — 2026-11-07

修复配置界面文字不可见。

- 原因：`drawString/drawCenteredString` 的颜色值缺少 Alpha 通道（`0xFFFFFF`、`0xA0A0A0`、`0xFF5555` 的 Alpha 为 0，完全透明）。
- 修复：标题改为 `0xFFFFFFFF`，整数标签改为 `0xFFA0A0A0`，错误提示改为 `0xFFFF5555`；1.21 与 26.1 两套界面同步修改。
- 现在右侧整数项会显示“每本页数 (0=job)”“恢复等待 tick”等标签，标题与校验错误也可见。

## 0.8.1 — 2026-11-07

修复 `/autobook ui` 没有界面的问题。

- 原因：从聊天命令直接调用 `Minecraft.setScreen`，聊天界面随后关闭时会把新界面覆盖掉。
- 改为 `UiScreens` 延迟到下一个客户端 tick、且当前没有其他界面时再打开配置界面。
- 新增命令树单元测试，确认 `/autobook ui`、`config`、`queue add/list/start/clear` 均正确注册。
- JUnit 43 项通过（1.21.8 与 26.1.2）。

## 0.8.0 — 2026-11-07

Minecraft 26.1.x 支持。

背景：

- 26.1 是首个不再混淆的 Minecraft 版本，Mojang 不再发布 mappings。
- Fabric 改用 `net.fabricmc.fabric-loom`（unobfuscated）插件，Fabric API 名称同步调整。

新增：

- **独立 26.x 工程**：`autobook-26/`，使用 Loom 1.19.4（unobfuscated）、Gradle 9.8.2、JDK 25。
- **版本兼容层**：
  - `ClientCommandsCompat`：1.21 的 `ClientCommandManager` / 26.1 的 `ClientCommands`。
  - `ClientCompat`：动作栏消息、玩家名、背包点击（`ClickType` → `ContainerInput`）。
  - `AutoBookConfigScreen`：1.21 的 `GuiGraphics/render` / 26.1 的 `GuiGraphicsExtractor/extractRenderState`。
- **构建工具升级**：Gradle 9.8.2、Loom 1.19.4、JDK 25；1.21.x jar 仍以 Java 21 编译。
- **多版本构建**：`build-multi.ps1` 增加 26.1.2，自动使用 `autobook-26/` 工程；输出 `dist/autobook-0.8.0-mc<版本>.jar`。

版本依赖：

| Minecraft | Loader | Fabric API | Java |
| --- | --- | --- | --- |
| 26.1.2 | 0.20.1 | 0.155.3+26.1.2 | 25 |
| 1.21.5–1.21.8 | 0.16.14+ | 见文档 | 21 |

验证：

- JUnit 42 项通过（1.21.8 与 26.1.2 各一次）。
- 26.1.2 jar 元数据：`minecraft=26.1.2`、`fabricloader>=0.20.1`、`java>=25`。
- 尚未在真实 26.1.2 客户端验证写书/校验/队列，仅完成编译级适配。

## 0.7.0 — 2026-11-07

P5.3：游戏内配置界面；同时扩展 Minecraft 版本适配。

新增：

- **配置界面**：`/autobook ui` 打开 `AutoBookConfigScreen`。
  - 左侧按钮切换全部开关项：`keepWrittenBooks`、`skipExistingBooks`、`breakAtSentence`、`verifyContent`、`autoRecover`、`queueStopOnFailure`。
  - 右侧输入框修改全部整数项：`pageLimit`、`recoveryWaitTicks`、`settleTicks`、`inventoryWaitTicks`、`confirmWaitTicks`、`retryDelayTicks`、`maxInventoryRetries`。
  - 保存复用 `AutoBookConfig.set` 的范围/布尔校验并写回 `config.json`；非法值在界面底部提示且不保存。
- **版本适配**：
  - 删除未使用的 `BookEditScreenAccessor` mixin（1.21.5 及更早版本没有 `saveChanges`）。
  - `fabric.mod.json` 的 `minecraft` 依赖改为构建时注入，每个 jar 与目标版本精确匹配。
  - 新增 `scripts/build-multi.ps1`，一次生成 1.21.5/1.21.6/1.21.7/1.21.8 的独立 jar。
  - 编译验证通过 1.21.5、1.21.6、1.21.7、1.21.8；1.21.4 及更早版本因缺少 `Inventory.getSelectedSlot/getSelectedItem/setSelectedSlot` 暂不支持。
- 新增 `AutoBookConfigTest`（4 项）。

验证：

- JUnit 42 项通过。
- 多版本构建产出 `dist/autobook-0.7.0-mc<版本>.jar`。
- 配置界面与多版本 jar 仍需在各目标客户端实测。

## 0.6.0 — 2026-10-31

P5.2：AutoBook 多任务队列。

新增：

- **队列命令**：`/autobook queue add <任务名>`、`queue list`、`queue start`、`queue clear`。
- **队列持久化**：状态写入 `config/autobook/queue.json`，记录 `active`、`currentIndex` 与每个任务的 `status/nextIndex/completedBooks/totalBooks/error`。
- **自动推进**：一个任务完成后自动开始下一个；已签名/已完成的 job 通过 `planHash` 进度跳过，不重复印刷。
- **失败处理**：默认记录失败原因并继续下一个任务；`/autobook config queueStopOnFailure true` 改为暂停队列。
- **手动命令联动**：`start` 退出队列；`stop` 停用队列并保存；`pause` 只暂停当前任务，`resume` 后继续推进。
- **共享 JobRunner**：`plan/start/queue` 统一使用 `job/JobRunner` 的加载、参数覆盖与分页逻辑。
- 新增 `queueStopOnFailure` 配置；重启游戏后队列不会自动开跑，需手动 `queue start`。

验证：

- JUnit 38 项通过（新增 QueueState 6 项、QueueStore 3 项）。

## 0.5.0 — 2026-10-28

P4：内容校验、失败自恢复、配置与发布。

新增：

- **内容校验**：新增 `ContentVerifier`。签名后读取成书页，与计划逐页比较，忽略 `§` 格式码、CR、行尾与页面首尾空白。
  - 通过：日志记录 `verified '<书名>' (N pages)`。
  - 失败：`VERIFY` 暂停，不推进进度，日志记录页数、首个不一致页与片段；resume 时强制重写。
  - 配置：`verifyContent`，或 job `options.verifyContent`。
- **失败自恢复**：连续 3 次未确认后，等待 `recoveryWaitTicks`（默认 200 tick），自动打开并关闭书本页面，再重新写入；每本书一轮。仍失败才 `CONFIRM` 暂停。
- 重试等待改为按尝试次数递增（`retryDelayTicks × attempts`，上限 600 tick）。
- **游戏内配置命令**：`/autobook config` 查看，`/autobook config <key> <value>` 修改并保存。
- **每任务覆盖**：`job.json` 的 `options` 支持 `pageLimit`、`breakAtSentence`、`verifyContent`，优先级高于全局配置。
- **一键构建/安装**：`scripts/build.ps1` 跑 Python/Java 测试并构建；带 `-GameDir` 时安装、校验 jar 版本、清理旧 autobook jar、检查 Fabric API 与创建配置目录。
- `/autobook plan` 增加内容校验与自动恢复状态输出。

注意：

- 修改 `pageLimit` 或 `breakAtSentence` 会改变 `planHash`，旧进度不能续写；`verifyContent`、`autoRecover` 与节奏参数不影响续写。
- 内容校验失败时问题书会保留，需要人工移除后再 resume。

## BookForge 0.5.0 — 2026-11-07

P6 G2–G5：桌面 GUI 完整闭环。

新增：

- **LLM 核验页**：report/patch 模式、抽样、逐块进度、取消、问题/补丁表格、token 统计；`review_job` 新增 `progress` 与 `cancel` 回调。
- **补丁审阅页**：加载 `llm_patch.json`，默认勾选 high 置信度，可逐条勾选；应用后生成 reviewed job、`03_reviewed.txt`、`diff.patch`、`patch_apply.json`；显示 diff 与被拒绝原因。
- **配置页**：编辑全局或每本书 profile，保存写回 `keys/llm_config.json`；显示 key 状态、测试连接；把 job 安装到游戏 `config/autobook/jobs/`；QSettings 记住最近路径。
- **打包**：新增 `BookForge.spec` 与 `scripts/build-gui.ps1`（可选依赖 `[package]`），已构建 `dist/gui/BookForge/BookForge.exe`。
- **PyInstaller 路径适配**：`job.schema.json` 增加打包内查找路径；keys 只带配置与术语表模板，不打包真实 API key。
- 新增 `tests/test_gui_settings.py`、`tests/test_gui_models.py`。

验证：

- pytest 69 项通过。
- offscreen GUI 4 个标签页可创建。
- 端到端补丁 apply：1 条 high 补丁 → reviewed job、5 行 diff、patch_apply.json。
- 打包版 `BookForge.exe` 可启动。

## BookForge 0.4.1 — 2026-10-31

P5.1：成本预估、profile 查看与古籍误报修正。

新增：

- **`review --estimate`**：只统计块数、字符数、预估 tokens 与费用，不调用 API；可与 `--sample`、`--limit`、`--mode` 组合。
- **费用估算**：`llm_config.json` 新增 `pricing`（`inputPerMillion`、`outputPerMillion`、`offpeakFactor`、`currency`），按低谷/高峰给出费用区间；未配置价格时只显示 tokens。
- **`bookforge profile list` / `profile show <名字>`**：查看全局与每本书 profile 的模型、块大小、thinking、置信度、术语表条数与 key 状态，不输出 key 内容。
- **古籍误报修正**：report 与 patch prompt 明确不把通假字、古今字、古今异义、古汉语语法与文学修辞当错误；西游记 profile 的 `style` 同步强调。
- `review` 的块规划统一到 `plan_review`，report 与 estimate 使用同一套抽样/截断规则。

验证：

- pytest 62 项通过。
- 三体1 `--estimate`：66 块、191,986 字符、约 154,791 tokens，费用约 CNY 0.17–0.33（低谷–高峰）。
- `profile list` / `profile show 西游记` 输出正确；术语表 15 条，key 状态仅显示 configured/missing。

## BookForge 0.4.0 — 2026-10-31

P6 G1：桌面 GUI 与共享工作流。

新增：

- **共享工作流**：新增 `bookforge/workflow.py` 的 `prepare_input` / `PrepareOutcome`，CLI 与 GUI 共用电子书导入、`00_imported.txt`、`import.json`、`prepare_document` 逻辑；`bookforge prepare` 改为调用它。
- **桌面 GUI（G1）**：新增 `bookforge/gui/`：
  - `app.py`：`QApplication` 与 `main()`。
  - `main_window.py`：输入/输出/书名、每本页数、单段字符、摘要、进度与日志。
  - `workers.py`：`PrepareWorker(QThread)`，后台执行导入，UI 不冻结。
  - 入口 `bookforge-gui`，可选依赖 `pip install -e ".[gui]"`（PySide6-Essentials）。
- 书名超过 24 字符（job schema 上限）时提前给出中文错误，不再落到 schema 的英文报错。
- 新增 `tests/test_workflow.py`（txt、EPUB、超长书名）。

验证：

- pytest 57 项通过。
- CLI `prepare` 西游记 EPUB：101 章、112 段、最大预估 84 页、1 条目录页警告。
- offscreen GUI 端到端：同一 EPUB 生成 job/report/import，摘要与日志显示正常。

## BookForge 0.3.1 — 2026-10-31

LLM 抽样校准与补丁审阅。

新增：

- `bookforge review --sample N`：从全书首/中/尾等距抽取 N 块；与 `--limit` 互斥。
- `apply-patch` 额外输出 `diff.patch`（统一 diff），逐条查看已应用修改。
- 网络连接异常（含 `RemoteDisconnected`）自动重试 3 次；报告问题上限从 500 提高到 5000，避免整书截断。
- 报告 prompt 收紧：只报可确定的 OCR/缺字/乱码/重复/明显缺失标点，不报风格、断句偏好、异体字统一等建议。
- 西游记 profile 增加“保留异体字/古字、脚注编号、校注内容”的要求。
- pytest 54 项通过。

三体1 全量实测：

- 报告 66/66 块、697 条问题（655 high）、0 错误/拦截，165,564 tokens。
- 补丁 629 条；应用 600、拒绝 29（16 medium、11 find 不唯一、2 low），36 段修改，diff 2,371 行。
- 抽样 3 块高置信度约 94% 可信；`文革`、`坐到/做到` 等语义改动仍需人工审阅。

待办：人工审阅 `work/三体1/full-reviewed/diff.patch`，再进游戏印刷 2–3 本验证。

## BookForge 0.3.0 — 2026-10-31

电子书导入。

新增：

- `bookforge/ebook.py`：
  - `.epub`：解析 container.xml/OPF/spine，按阅读顺序提取 XHTML 正文，跳过 nav 与疑似目录页。
  - `.fb2`：解析 XML 正文与元数据。
  - `.docx`：解析 `word/document.xml` 与 `docProps/core.xml`。
  - `.azw3/.mobi/.azw/.kf8/.prc`：优先调用 Calibre `ebook-convert --no-images` 转 EPUB；无 Calibre 时自动使用 Python `mobi` 库。
- 目录页识别：首行“目录/Contents”、文件名或高链接密度 + 短回目行；跳过并在 `import.json` 记录警告。
- `bookforge prepare` 直接接受电子书；`--title` 改为可选，省略时使用元数据或文件名。
- 新增 `--calibre` 参数，可指定 `ebook-convert` 路径。
- 电子书输入输出 `00_imported.txt` 与 `import.json`（原始格式、原始 SHA-256、标题、作者、字符数、警告）。
- 拒绝加密 EPUB；Calibre 失败时提示可能受 DRM 保护，不处理 DRM 移除。
- pytest 51 项通过（新增 EPUB/FB2/DOCX/Calibre 缺失用例）。

注意：

- 本机未安装 Calibre，当前 MOBI/AZW3 走 Python `mobi` 回退；Calibre 优先路径待有环境时再验证。
- EPUB 端到端实测通过：自动使用元数据标题，生成 2 章节 job，`import.json` 记录原始哈希。
- 真实《西游记》校注本三格式实测：EPUB/MOBI/AZW3 的 `00_imported.txt` 与 job 文本 SHA-256 完全一致；均为 850,810 字符、101 章、112 段、0 内容警告。MOBI/AZW3 目录页被正确跳过。

## BookForge 0.2.0 — 2026-10-28

P4.1：LLM 核验。

新增：

- `bookforge review <job.json>`：用 OpenAI 兼容接口逐块核验正文，输出 `llm_report.json`。
- `bookforge review --mode patch`：输出 `find/replace` 补丁到 `llm_patch.json`。
- `bookforge apply-patch`：本地校验并应用补丁，生成 `reviewed/job.json`、`03_reviewed.txt`、`patch_apply.json`。
- `bookforge/llm.py`：接口调用、按换行优先分块、JSON 解析、报告/补丁汇总；不新增 Python 依赖。
- `bookforge/patch.py`：`find` 唯一性、`chunkHash`、置信度、长度上限、换行结构、补丁重叠校验。
- 审核拦截 `blocked[]`：记录后继续其他块；`--strict` 将拦截计为失败。
- 问题类型：`typo`、`missing`、`extra`、`garbled`、`duplicate`、`broken`、`punctuation`、`ad`、`other`。
- `bookforge/keys/llm_api_key.txt`（默认空，已 git 忽略）、`llm_config.json`（base_url/model/timeout/max_chars）、`glossary.txt`（术语表）。
- 每本书独立 `profiles`：按 job 的 `titleBase` 自动选择，可覆盖 `base_url/model/key_file/timeout/max_chars/max_tokens/temperature/thinking/glossary/style/min_confidence/max_delta`。
- `thinking` 可关闭推理模式：`false` 时请求体发送 `{"thinking":{"type":"disabled"}}`，默认配置已关闭。
- 报告累计 `usage`：prompt/completion/reasoning/total tokens，便于按 DeepSeek 价格估算成本。
- 报告写入 `settings` 与 `policy`；`apply-patch` 默认使用报告中的置信度与长度阈值，`--min-confidence` 可覆盖。
- CLI 支持 `--mode`、`--profile`、`--temperature`、`--max-tokens`、`--thinking/--no-thinking`、`--glossary`、`--limit`、`--max-chars`、`--key-file`、`--base-url`、`--model`、`--strict`。
- 报告不含 API key；key 为空时跳过请求并生成跳过报告。

注意：

- 补丁不会自动应用，只应用 `high` 置信度且通过本地校验的修改；`ad` 类型不自动应用。
- reviewed job 会改变 `planHash`，需要在游戏内重新 `/autobook start`。
- `deepseek-flash` 默认 `thinking=false`：三体1 首块 4000 字约 2655 输入 + 389 输出 tokens，`reasoning=0`；patch 模式约 2830 + 291 tokens。
- 若开启推理，reasoning tokens 占用输出预算，需要 `max_tokens` 约 16384。
- 真实 API 已用 DeepSeek 实测：非推理模式 report 识别 8 处问题，patch 8 条（7 条通过、1 条 medium 被拒）。

## 0.4.0 — 2026-10-25

阅读观感与配置能力改进。

新增：

- **标点断书**：新增 `SentenceBreaks`。一本超过 `pageLimit` 时，向前回退寻找以 `。！？…` 等句末标点（可带右引号/右括号）结束的页作为书末页，避免在句子中间换书。
- 回退窗口限制在约 20 页，且一本书至少保留约 60% 页数；找不到合适断点时按上限切分。
- **每本页数配置**：`pageLimit`，`0` 表示使用 job.json，1–100 可覆盖。
- **断句开关**：`breakAtSentence`，默认 `true`。
- 写入节奏字段继续可配置：`settleTicks`、`inventoryWaitTicks`、`confirmWaitTicks`、`retryDelayTicks`、`maxInventoryRetries`。
- `/autobook plan` 输出当前页数上限与断句开关。

注意：

- 标点断书只调整书与书的边界，不改变页内排版和总页数。
- 修改 `pageLimit`、`breakAtSentence` 或书稿内容都会改变 `planHash`，旧进度需要重新 `start`。

## 0.3.0 — 2026-10-25

资源优化与稳定性改进。

新增/变更：

- **跨章节打包**：`BookPlanner` 不再按 segment 单独装订，而是把所有页面连续装满 `pageLimit`。三体1 从 36 本降至约 12 本，显著减少空书消耗。
- **慢速可配置时序**：`settleTicks`（15）、`inventoryWaitTicks`（80）、`confirmWaitTicks`（100）、`retryDelayTicks`（120）、`maxInventoryRetries`（3）。
- **库存重试**：空书未在超时内进入主手时，回到 `FIND_BOOK` 重新整理，默认 3 次；仍失败则暂停并给出提示，而不是直接报错。
- **重复印书检测**：按“书名 + 页数”扫描背包，每本开始前跳过已签名书；写入确认也接受背包内的同书名/同页数成书。
- **界面兜底**：写入后意外弹出的书本编辑界面会被自动关闭；确认等待期间不再被非书本界面卡住。
- **重试复查**：失败重试前回到 `FIND_BOOK`，避免服务器已签名但客户端未及时更新时重复印刷。
- `skipExistingBooks` 配置项，默认 `true`；需要重印时设为 `false` 或先移除旧书。

注意：

- 打包方式变化会改变 `planHash`，0.2.x 的旧进度无法续写，需要 `/autobook start` 重新开始。
- 旧版按章节印出的短书与新书边界不同，建议先移除后再开始。

## 0.2.1 — 2026-10-25

修复：

- **切换到下一本空书失败**：切换快捷栏槽时只发送 `ServerboundSetCarriedItemPacket`，未更新客户端 `Inventory.selected`，导致 40 tick 后判定“空书未就位”。现在先本地 `setSelectedSlot` 再发包，与 vanilla 行为一致。
- **config.json 修改不生效**：配置此前在首次读取后缓存；现在每次 `/autobook start`、`/autobook resume` 都重新读取，无需重启游戏。
- 模组初始化时即生成默认 `config/autobook/config.json`。

## 0.2.0 — 2026-10-25

P3：批量写入与可恢复运行。

新增：

- 多本循环：`BookWriter` 遍历整个计划，逐本写入，不再只写第一本。
- 进度持久化：`config/autobook/state/<planHash>.json`，记录下一本索引与统计。
- `PlanDigest` 计划指纹：任务名、标题、页数、全部页面内容参与哈希。
- 命令：`/autobook resume <job>`、`/autobook pause`。
- `/autobook stop` 现在会保存进度。
- 暂停类型：
  - `SUPPLY`：空书耗尽自动暂停，拾取后自动继续。
  - `MANUAL`：命令暂停，当前书写完后停下。
  - `CONFIRM`：连续 3 次未确认后暂停，支持人工打开/关闭书本页面后恢复。
- 动作栏显示 `[当前/总数]` 进度。
- 主背包取书时优先使用空的快捷栏槽，减少成书搬动。
- `config/autobook/config.json` 与 `keepWrittenBooks` 选项。

变更：

- `/autobook start` 改为从头开始，`resume` 专门用于继续。
- 计划输出增加“空书需求”。

测试：

- Java 测试增至 15 项，新增 StateStore、PlanDigest、跨段连续编号。
- 构建产物 `dist/autobook-0.2.0.jar`。

文档：

- 新增 README、架构、使用、任务格式、红石、计划文档。

## 0.1.4 — 2026-10-25

- 确定可用的服务端写入时序：`useItem` → 等待 5 tick → 关闭编辑界面（不调用 `saveChanges`）→ 客户端预测成书内容 → 立即发送 `ServerboundEditBookPacket` → 等待 40 tick 确认。
- 服务器退回空书时最多重试 3 次。
- 中文任务名使用 greedy string 参数。
- 实机验证：`AutoBookTest-01`、`三体1-01`（43 页）成功签名。

## 0.1.0 – 0.1.3

- 迭代完成命令注册、job 加载、像素分页、续本规划、库存移动、编辑界面处理与写入尝试。
- 逐步修正服务端编辑会话的等待时机与确认判断。

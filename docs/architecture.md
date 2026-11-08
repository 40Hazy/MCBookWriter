# 架构说明

## 总览

```text
原始 txt / EPUB / FB2 / DOCX / AZW3 / MOBI
  │
  ├─（电子书）ebook.py：EPUB/FB2/DOCX 原生解析；AZW3/MOBI 经 Calibre 转 EPUB
  │        → 00_imported.txt + import.json
  ▼ BookForge（Python，离线）
编码识别 → 文本规范化 → 广告/页眉清洗 → 章节识别 → 分段
  │
  ├─ 01_normalized.txt
  ├─ 02_cleaned.txt
  ├─ report.json        统计与警告
  └─ job.json           AutoBook 输入（schema v1）
        │
        ├─（可选）bookforge review --mode report|patch
        │        → llm_report.json / llm_patch.json
        │        → bookforge apply-patch → reviewed/job.json
        ▼ AutoBook（Fabric 客户端模组，游戏内）
任务加载 → 像素级分页 → 跨章节打包 → 库存寻书 → 打开/关闭编辑界面 → 发送编辑包 → 确认/校验/重试
        │
        ├─ 动作栏进度
        ├─ autobook/state/<planHash>.json
        └─ 服务端：已签名的成书
```

两个组件通过 `job.json` 解耦，格式见 [job-schema.md](job-schema.md)。

## BookForge

| 模块 | 职责 |
| --- | --- |
| `normalize.py` | BOM/UTF-16 检测、编码猜测、换行统一、控制字符清理、NFC 规范化 |
| `ebook.py` | 电子书导入：EPUB/FB2/DOCX 原生解析，AZW3/MOBI/AZW/KF8 经 Calibre 转 EPUB；拒绝 DRM |
| `rules.py` | 删除广告行、网址行、页码行；保留正文与台词中的引号内容 |
| `chapters.py` | 识别 `1. 标题`、`第X章` 等标题；无标题时归为“正文”，卷首归为“前言” |
| `segment.py` | 章节超过 12000 字符时按行切分；估算页数（12 字/行、14 行/页） |
| `manifest.py` | 生成 job 并做 JSON Schema 校验 |
| `validate.py` | 生成清洗报告与警告（内容损失、删除比例、超页上限等） |
| `pipeline.py` / `cli.py` | 串联流程，提供 `prepare`、`validate`、`review`、`apply-patch`、`profile`、`key` 命令 |
| `workflow.py` | CLI/GUI 共用的 `prepare_input`：电子书导入、`00_imported.txt`、`import.json`、生成 job |
| `llm.py` | OpenAI 兼容接口、分块与 `plan_review`、报告/补丁解析、`review_job`、`--estimate` 与 profile 查看 |
| `keymanagement.py` | key 路径解析（env/profile/全局/默认）、掩码状态、原子保存与清除、最小连接测试 |
| `patch.py` | 补丁本地硬校验、重叠检测、按偏移应用、统一 diff 生成 |
| `gui/` | PySide6 桌面界面：生成、LLM 核验、补丁审阅、配置、帮助五个标签页；含 workers/models/settings/help_content |

设计原则：非空白字符尽量保持不丢；只删除明确的广告/导航行；对疑似误删给出警告而不是静默处理。

### 桌面 GUI（BookForge 0.7.0）

```text
生成        prepare_input → job/report/import
LLM 核验    ReviewWorker → review_job(progress/cancel) → llm_report/llm_patch
补丁审阅    ApplyWorker → apply_patches(selected) → reviewed/job + diff + patch_apply
配置        profile 编辑 / 测试连接 / 安装 job / 最近路径
帮助        内置离线 HTML（help_content）+ 动态版本/路径信息 + 打开目录按钮
```

- `gui/models.py`：`IssueTableModel` 以 report/patch 两种列结构展示问题；patch 模式默认勾选 high。
- `gui/workers.py`：`PrepareWorker`、`ReviewWorker`、`ApplyWorker`、`ConnectionWorker` 均为 `QThread`，主线程不执行网络/大文件。
- `gui/settings.py`：读写 `llm_config.json`、profile 合并、key 状态、术语表计数、测试连接、安装 job。
- `gui/help_content.py`：帮助页 HTML 全部内置在代码常量中，不读外部文件、不加载网络资源；`build_path_info` 动态生成版本与路径表格，打包版可离线查看。
- 补丁应用仍走 `patch.apply_patches` 的本地硬校验；GUI 只负责筛选勾选项与展示 diff/rejected。
- PyInstaller：`BookForge.spec` 打包 schema、配置与术语表模板；`manifest.py` 支持 `_MEIPASS/docs` 查找；不打包真实 key。

### 电子书导入

- `.epub`：读取 `META-INF/container.xml` → OPF → manifest/spine，按阅读顺序提取 XHTML 正文；跳过 `properties=nav` 的条目、`<nav>` 内容以及疑似目录页（目录/Contents、高链接密度）。
- `.fb2`：XML 解析 `book-title`、`author`、`section/p`。
- `.docx`：ZIP 内 `word/document.xml` 按段落提取 `w:t`；元数据读取 `docProps/core.xml`。
- `.azw3/.mobi/.azw/.kf8/.prc`：优先调用 Calibre `ebook-convert --no-images` 转 EPUB；无 Calibre 时用 Python `mobi` 库提取（KF8 输出 EPUB，MOBI7 输出 HTML），再走现有解析。
- 仅处理无 DRM 文件：EPUB 加密条目直接拒绝；Calibre/mobi 失败时提示可能受 DRM 保护。
- 输出 `00_imported.txt` 与 `import.json`（原始格式、原始 SHA-256、标题/作者、字符数、警告），再进入原有 `prepare` 流水线。

### LLM 核验与补丁（可选）

- `bookforge review <job.json> --mode report|patch` 读取任务文本，按配置的 `max_chars`（全局默认 4000，三体1 profile 为 4000，尽量在换行处）切块。
- 每个块调用一次 OpenAI 兼容的 `/chat/completions`：
  - report 模式要求返回 `excerpt/message/suggestion`；
  - patch 模式要求返回 `find/replace/reason/confidence`。
- `llm.py` 负责：
  - 读取 `keys/llm_api_key.txt`、`keys/llm_config.json` 与术语表；
  - 按 job 的 `titleBase` 自动选择 `profiles` 中的每本书配置（也可用 `--profile` 显式指定）；
  - 调用接口（`urllib`，不引入额外依赖），支持每本书不同的 `base_url/model/timeout/max_chars/max_tokens/temperature/thinking/key_file/glossary/style/min_confidence/max_delta`；
  - 解析代码围栏中的 JSON，规范问题类型与置信度；
  - 为每个 issue 记录 `segment/chunk/chunkStart/chunkEnd/chunkHash`；
  - 汇总 `summary`、`issues`、`errors`、`blocked`、`usage`，并写入 `settings` 与 `policy`。
- 配置优先级：命令行 > 环境变量 > profile > 全局 > 内置默认。profile 不存在时回退全局；显式 `--profile` 不存在则报错。
- `--sample N` 会按首/中/尾等距抽取 N 个块；`--limit N` 只取前 N 块，二者互斥。
- 块规划统一由 `plan_review` 实现；`review --estimate` 复用同一套抽样/截断规则，只统计块数、字符数、预估 tokens 与费用，不调用 API。
- 报告与补丁 prompt 采用保守规则：不把通假字、古今字、古今异义、古汉语语法、文学修辞当错误；古籍/校注本的用字差异只保留、不修改。
- `bookforge profile list|show` 读取 `llm_config.json`，展示全局与每本书的模型、块大小、thinking、置信度、术语表条数与 key 状态，不输出 key 内容。
- `pricing` 配置用于 `--estimate` 的费用区间（输入/输出每百万 tokens、低谷系数、币种）；未配置时只显示 tokens。
- `apply-patch` 额外生成 `diff.patch`（统一 diff），便于逐条审阅 600+ 条补丁。
- 网络连接异常（含 `RemoteDisconnected`）重试 3 次；报告问题上限提高到 5000，避免整书截断。
- 审核拦截（`content_filter`）的块进入 `blocked[]` 并继续处理其他块；报告不含 API key。
- `apply-patch` 使用 `patch.py` 做本地硬校验，并默认采用补丁报告 `policy` 中的 `minConfidence` 与 `maxDelta`：
  - `find` 在目标块中唯一、`chunkHash` 匹配；
  - 置信度阈值、按类型的长度变化上限、换行结构、补丁重叠；
  - 只应用通过校验的补丁，输出 `reviewed/job.json`、`03_reviewed.txt`、`diff.patch`、`patch_apply.json`。
- 补丁不自动应用；`ad` 类型一律拒绝。reviewed job 改变 `planHash`，需在游戏内重新 `start`。
- 推理模式由 `thinking` 控制：`false` 时请求体发送 `{"thinking":{"type":"disabled"}}`；`true` 时发送 enabled。默认配置关闭推理，reasoning tokens 为 0；若开启，reasoning tokens 计入输出预算，需要加大 `max_tokens`。
- 每次接口响应都会累计 `usage`（prompt/completion/reasoning/total tokens），写入报告，便于按 DeepSeek 价格估算成本。
- 与 AutoBook 的内容校验互补：LLM 核验书稿文本，AutoBook 校验签名后的成书页。

## AutoBook

### 类结构

| 类 | 职责 |
| --- | --- |
| `AutoBookClient` | 模组入口，注册命令与客户端 tick 回调 |
| `AutoBookCommand` | `/autobook help/plan/add/start/resume/pause/status/list/cancel/stop/remove/retry/config/ui`（保留旧 `queue` 别名） |
| `JobLoader` | 从 `autobook/jobs/` 读取并校验 job |
| `JobRunner` | 统一加载 job、解析 `options` 覆盖、分页并启动 BookWriter，供命令与运行共用 |
| `BookPlanner` | 将各段页面连续装满每本（不超过 `pageLimit`），可选在句末标点处断书，标题全局连续编号 |
| `SentenceBreaks` | 判断页面是否以句末标点结束、下一段是否以右引号等收尾字符开头 |
| `PageLayout` | 像素宽度分页：114 px、14 行、1023 字符、`§` 不占宽度 |
| `MinecraftWidthProvider` | 使用游戏字体计算每个码点宽度 |
| `InventoryHelper` | 查找空书、检测已签名的同书名/同页数成书、按书名读取成书内容 |
| `ContentVerifier` | 逐页比对计划文本与成书文本，忽略 `§` 格式码与行尾空白；同时输出整书 SHA-256 摘要 |
| `BookWriter` | 写入状态机、多本循环、暂停/恢复/自动恢复、内容校验、进度保存 |
| `JobOptions` | job.json 的每任务覆盖参数（页数、断书、校验） |
| `StateStore` / `RunState`（progress） | 单任务进度文件的读写与数据模型 |
| `PlanDigest` | 对任务名与全部页面内容做 SHA-256，生成计划指纹 |
| `RunRunner` | 唯一运行流水线：单本与多任务统一，负责状态推进、暂停/取消/终止/重试 |
| `RunStore` / `RunState` / `RunJob` | `autobook/run.json` 的读写、运行与任务状态模型；自动迁移旧 `queue.json` |
| `AutoBookConfigScreen` | 游戏内配置界面：开关按钮 + 整数输入框，保存复用 `AutoBookConfig.set`（1.21/26.1 各一份渲染实现） |
| `HelpText` | 帮助内容：概览与 start/run/job/cancel/config/verify/recover 主题，命令与 UI 共用 |
| `AutoBookHelpScreen` | 分页说明页：按宽度换行、上一页/下一页/返回（1.21/26.1 各一份渲染实现） |
| `compat/ClientCompat` / `ClientCommandsCompat` | 1.21 与 26.1 的客户端 API 差异封装 |
| `AutoBookConfig` | 读取/保存 `autobook/config.json`，支持 `/autobook config` |

### 写入状态机

```text
SETTLE（默认 15 tick，可配置）
  → FIND_BOOK
      ├─ 当前书已存在（标题+页数一致） → 跳过，直接推进进度
      ├─ 无空书 → PAUSED(SUPPLY)，每 20 tick 检查，拾取后回到 FIND_BOOK
      └─ 有空书 → WAIT_FOR_INVENTORY（默认 80 tick，可配置）
            ├─ 就位 → USE_BOOK
            └─ 超时 → 回到 FIND_BOOK 重试（默认最多 3 次），仍失败则 PAUSED(MANUAL)
  → USE_BOOK（useItem 打开书本）
  → CLOSE_BOOK_SCREEN（等 5 tick；界面出现即关闭且不保存，最多再等 10 tick）
  → WRITE（客户端预测成书内容，立即发送 ServerboundEditBookPacket）
  → WAIT_FOR_CONFIRM（默认 100 tick，可配置）
      ├─ 主手变成本书，或背包出现同书名/同页数成书
      │     → VERIFY（可关闭）
      │         ├─ 通过 → 完成当前书，保存进度，继续下一本
      │         └─ 失败 → PAUSED(VERIFY)，不推进进度，resume 时强制重写
      ├─ 仍是空书且次数 < 3 → RETRY_WAIT（等待按尝试次数递增，可配置）→ FIND_BOOK
      ├─ 次数 = 3 且 autoRecover 且未用过恢复
      │     → RECOVERY_WAIT（默认 200 tick）
      │     → USE_BOOK（只打开并关闭，不写入）
      │     → RECOVERY_WAIT（30 tick）
      │     → USE_BOOK（重新写入）
      └─ 否则 → PAUSED(CONFIRM)，等待人工处理后 resume
  → 全部完成 → DONE
```

关键时序：

1. `useItem` 会创建服务端的书本编辑会话，该会话很快过期（约 2 秒）。
2. 打开界面后等待 5 tick 再关闭，并**不调用** `saveChanges`。
3. 关闭后立即在客户端写入 `WRITTEN_BOOK_CONTENT` 并发送编辑包，使确认窗口落在会话有效期内。
4. 确认等待期间若书本编辑界面又出现，会立即关闭，避免卡在“等待关闭界面”。
5. 确认窗口比旧版本更长；若服务器已签名但客户端状态更新较慢，会通过标题+页数扫描识别为已完成，避免重复印刷。
6. 确认成功后读取成书页并做内容校验，日志记录整书 SHA-256 摘要；通过时累计 `verifiedBooks` 并随进度保存。不一致时不推进进度，等待人工移除问题书后恢复。
7. 连续失败时会先做一轮自动恢复（长等待 + 打开/关闭书本页），仍失败才暂停。

### 统一运行流水线

单本只是“一个任务的运行”。`RunRunner` 在客户端 tick 中跟随 `BookWriter` 推进：

```text
运行级：CREATED → PLANNING → QUEUING → RUNNING ⇄ PAUSED → COMPLETED
                                      ↓          ↓
                                   FAILED     CANCELLED
任务级：PENDING → QUEUED → RUNNING ⇄ PAUSED → COMPLETED
                              ↓
                        FAILED / CANCELLED
```

- `add` 创建/追加任务：PENDING → 加载与分页 → QUEUED；失败直接 FAILED。
- `start`（QUEUING → RUNNING，armed=true）：下一 tick BookWriter IDLE → 重新分页并计算 `planHash` → 按进度恢复或从头开始。
- 运行中每完成一本同步 `run.json` 的 `nextIndex/completedBooks/verifiedBooks`。
- DONE：任务 COMPLETED，停止 BookWriter，推进下一个 QUEUED 任务；没有则运行 COMPLETED。
- ERROR：任务 FAILED；`queueStopOnFailure=false` 继续下一个，否则运行 FAILED。
- PAUSED（SUPPLY/CONFIRM/VERIFY/MANUAL）：运行与当前任务同步为 PAUSED，等待 `/autobook resume`。
- `cancel` 只取消任务并继续下一个；`stop` 终止整条运行；`remove` 只拒绝 RUNNING/PAUSED，其余状态可移除以清理列表；`retry` 重新入队。
- `run.json` v2 的 `currentIndex` 指向当前或下一个未终止任务；旧 `queue.json` 首次加载时自动迁移并保留 `.bak`。
- 每个任务的实际逐本进度仍由 `state/<planHash>.json` 保存；运行恢复时重新分页并计算 `planHash`，据此决定恢复还是从头开始。
- 重启后 RUNNING 一律恢复为 PAUSED，不自动开写；运行文件损坏时记录警告并按空运行处理。

### 游戏内配置界面

`/autobook ui` 打开 `AutoBookConfigScreen`：

- 左侧用 `Button` 切换 6 个布尔项，按钮文本直接显示“名称: 开/关”。
- 右侧用 `EditBox` 编辑 7 个整数项，标签在 `render` 中绘制。
- “保存并关闭”逐项调用 `AutoBookConfig.set(key, value)`，沿用命令行的布尔/范围校验；任一项非法时不写入，错误显示在底部。
- 保存成功后关闭界面，写入 `config.json`；运行中任务不受影响，下次 `plan/start` 生效。
- 底部新增“说明”按钮，打开 `AutoBookHelpScreen`；帮助页按 screen 宽度换行并分页，返回时回到配置界面。
- 不引入 Cloth Config 等额外依赖，避免增加版本适配面。

### 版本适配

- 目标版本：1.21.5、1.21.6、1.21.7、1.21.8、26.1.2；每个版本使用独立 jar，`fabric.mod.json` 的 `minecraft`、`fabricloader`、`java` 依赖在构建时注入。
- 1.21.x 使用 `fabric-loom`（remap）插件，`src/main/java-21` 提供 version-specific compat；26.x 使用 `net.fabricmc.fabric-loom`（unobfuscated）插件与独立工程 `autobook-26/`，`src/main/java-26` 提供 compat。
- 两边同一 FQN 的 compat 类：
  - `ClientCommandsCompat`：1.21 的 `ClientCommandManager` / 26.1 的 `ClientCommands`。
  - `ClientCompat`：动作栏消息、玩家名、背包点击（`ClickType` vs `ContainerInput`）。
  - `AutoBookConfigScreen`：1.21 的 `GuiGraphics/render` 与 26.1 的 `GuiGraphicsExtractor/extractRenderState`。
- 公共 API 在 1.21.5+ 才存在：`Inventory.getSelectedSlot/getSelectedItem/setSelectedSlot`；1.21.4 及更早版本不兼容。
- 原先的 `BookEditScreenAccessor` mixin 未被使用，且在 1.21.5 找不到 `saveChanges`，已删除；关闭书本界面直接使用 `client.setScreen(null)`。
- 构建工具：Gradle 9.8.2、Loom 1.19.4、JDK 25（26.1.2 必需；1.21.x 仍以 Java 21 为目标）。
- `scripts/build-multi.ps1` 对 1.21.x 临时改写 `gradle.properties` 的 `minecraft_version/fabric_version/loader_version/java_release`；对 26.1.2 运行 `autobook-26/` 工程；输出 `dist/autobook-<mod>-mc<mc>.jar`，结束后恢复原文件。
- 版本依赖表：

| Minecraft | Fabric Loader | Fabric API | Java |
| --- | --- | --- | --- |
| 1.21.5 | 0.16.14+ | 0.128.2+1.21.5 | 21 |
| 1.21.6 | 0.16.14+ | 0.128.2+1.21.6 | 21 |
| 1.21.7 | 0.16.14+ | 0.129.0+1.21.7 | 21 |
| 1.21.8 | 0.16.14+ | 0.136.1+1.21.8 | 21 |
| 26.1.2 | 0.20.1 | 0.155.3+26.1.2 | 25 |

### 跨章节打包

旧逻辑按 segment 分组，短章节会单独装订成一本（可能只有十几页）。现在 `BookPlanner` 把所有 segment 的页面按顺序放入同一个缓冲区，装满 `pageLimit` 再生成一本：

```text
segment 1 pages 1..3 ┐
segment 2 pages 1..3 ┴→ book 1 (pageLimit=6)
```

- 书名仍全局连续递增。
- 每本的第一页所在 segment 会记录到 `PlannedBook` 用于日志。
- 结果：三体1 从 36 本降到约 12 本（按 100 页/本），显著减少空书消耗。

### 标点断书

`breakAtSentence=true`（默认）时，`BookPlanner` 在缓冲区超过 `pageLimit` 后不会立即按上限切分，而是向前回退寻找最近的干净断点：

```text
第 98 页：句子完整。      ← 候选
第 99 页：句子未结束       ← 跳过
第 100 页：句子未结束      ← 跳过
下一本从第 99 页开始
```

判定规则：

- 页面的最后一个非空白字符是 `。！？!?…．.` 之一，或其后只跟右引号/右括号（`”’」』】）》` 等）。
- 下一页不能以这些收尾字符开头，避免把上一句的尾巴带到新书开头。
- 回退窗口约为 `min(20, max(5, pageLimit/5))` 页，且一本书至少保留约 60% 的页数；窗口内找不到断点时才按上限切分。
- 该逻辑只调整书与书的边界，不改变页内排版和总页数，剩余页自动进入下一本。

### 节奏控制与配置

`autobook/config.json`（每次 `start`/`resume` 重新读取）：

| 字段 | 默认 | 作用 |
| --- | --- | --- |
| `keepWrittenBooks` | `true` | 是否保留成书；`false` 时写完即丢 |
| `skipExistingBooks` | `true` | 是否跳过背包中同书名/同页数的成书 |
| `pageLimit` | `0` | 每本页数上限；`0` 表示使用 job.json，否则 1–100 覆盖 |
| `breakAtSentence` | `true` | 是否优先在句末标点处断书 |
| `verifyContent` | `true` | 签名后是否逐页校验成书文本 |
| `autoRecover` | `true` | 多次未确认时是否自动执行一轮恢复 |
| `recoveryWaitTicks` | `200` | 自动恢复前的等待 tick |
| `settleTicks` | `15` | 每本开始前的缓冲 tick |
| `inventoryWaitTicks` | `80` | 等待空书进入主手的 tick |
| `confirmWaitTicks` | `100` | 等待服务器确认成书的 tick |
| `retryDelayTicks` | `120` | 写失败后到下一次尝试的 tick |
| `maxInventoryRetries` | `3` | 库存切换重试次数 |

服务器较慢时可适当加大这些 tick 值。`useItem` 到发送编辑包的 5 tick 窗口保持不变，因为它受服务端会话有效期限制。

### 多本循环与库存

- `BookWriter` 持有完整的 `List<PlannedBook>`，通过 `index` 指向当前书。
- 每完成一本：`index++`、写入状态文件，再进入下一本的 `SETTLE`。
- 空书在快捷栏：本地 `setSelectedSlot` + 发送 `ServerboundSetCarriedItemPacket`，避免客户端选中槽与服务端不同步。
- 空书在主背包：优先 SWAP 到一个空的快捷栏槽；没有空槽时退回当前选中槽。
- 库存切换超时会回到 `FIND_BOOK` 重新整理，默认最多 3 次，仍失败则暂停而不是报错退出。
- 已签名的书默认保留在背包；设置 `keepWrittenBooks=false` 后，每本完成后用 `ClickType.THROW` 整栈丢出。
- 已签名书默认会被跳过：按“书名 + 页数”匹配，避免崩溃/重启/重试后重复印刷。

### 每任务覆盖

`job.json` 的可选 `options` 字段可覆盖：

```json
{
  "options": {
    "pageLimit": 80,
    "breakAtSentence": false,
    "verifyContent": true
  }
}
```

优先级：`job.options` > `config.json` > 内置默认。`pageLimit` 为 0 时继续回退到 job 顶层 `pageLimit`。

### 内容校验

- 确认成书后按书名读取 `WrittenBookContent`，用 `Filterable.raw()` 取得服务器返回的页面组件。
- `ContentVerifier` 逐页比较：去掉 `§` 格式码、`\r`、行尾空白和页面首尾空白。
- 失败时设置 `forceWriteCurrent`，暂停且不推进 `index`；resume 时绕过同名书去重，强制重写当前书。

### 自动恢复

- 失败重试等待按 `retryDelayTicks × writeAttempts` 递增，上限 600 tick。
- 3 次失败后若 `autoRecover=true`，进入 `RECOVERY_WAIT`：
  1. 长等待 `recoveryWaitTicks`；
  2. `useItem` 打开书本页，5 tick 后关闭且不写入；
  3. 再等 30 tick；
  4. 重新 `useItem` 并发送写入包。
- 每本书仅一轮；再次失败进入 `CONFIRM` 暂停。`resume` 会重置恢复标记，允许再试一轮。

### 进度持久化

- 路径：`<gamedir>/autobook/state/<planHash>.json`。
- `planHash`：`SHA-256(jobName + 每本标题 + 页数 + 全部页面内容)`，任一内容变化都会生成新指纹。
- 保存时机：任务开始、每完成一本、暂停、停止、全部完成。
- `forceRewrite`：内容校验失败时为 `true`，resume 时绕过同名书去重并强制重写当前书；完成一本后自动清零。
- `verifiedBooks`：内容校验通过的累计本数，随进度保存并在 resume 时恢复。
- 恢复条件：指纹一致且 `0 < nextIndex < 总本数`；否则 `/autobook resume` 会提示改用 `start`。
- 原子写入：先写 `.tmp`，再替换目标文件。

示例：

```json
{
  "version": 1,
  "jobName": "三体1",
  "sourceHash": "f2d3e621...",
  "planHash": "9c1e...",
  "nextIndex": 2,
  "completedBooks": 2,
  "verifiedBooks": 2,
  "totalBooks": 12,
  "totalPages": 1195,
  "forceRewrite": false,
  "updatedAt": "2026-10-25T22:10:00+08:00"
}
```

### 暂停类型

| 类型 | 触发 | 恢复方式 |
| --- | --- | --- |
| `SUPPLY` | 背包没有空的书与笔 | 自动：拾取到空书后继续 |
| `MANUAL` | `/autobook pause`，或库存多次无法就位 | `/autobook resume` |
| `CONFIRM` | 连续 3 次未获确认，且自动恢复也未成功 | 人工右键打开并关闭书本页面后 `/autobook resume` |
| `VERIFY` | 成书页数与文本校验失败 | 移除问题书后 `/autobook resume`，强制重写 |

`/autobook pause` 在 `SETTLE`/`FIND_BOOK` 立即生效；正在写当前书时会等该书完成后再暂停，避免产生半成品。

## 约束

- 每本最多 100 页；每页最多 1023 字符，`§` 格式码不占宽度。
- 书名最长 32 字符（`titleBase` 建议不超过 24）。
- 写入包是原版 `ServerboundEditBookPacket`，不模拟键盘、不自动点击 UI。
- 内容校验比较客户端收到的成书页文本，忽略 `§` 格式码与空白差异；不做服务端存储层面的逐字节校验。
- 跨章节打包、`pageLimit`、`breakAtSentence` 变化都会改变分页边界，旧状态文件因 `planHash` 变化而无法续写。
- 自动恢复只模拟一轮打开/关闭书本页，不能绕过服务端的硬限制或权限问题。

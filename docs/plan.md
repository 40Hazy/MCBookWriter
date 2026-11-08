# 项目计划与路线图

## 阶段总览

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| P0 | 项目脚手架、环境、仓库结构 | 已完成 |
| P1 | BookForge 文本流水线与 job 生成 | 已完成 |
| P2 | AutoBook 单本自动写入打通 | 已完成 |
| P3 | 多本循环、进度恢复、暂停/补给、文档 | 已完成（0.2.1） |
| P3.1 | 跨章节打包、慢速重试、重复检测 | 已完成（0.3.0） |
| P3.2 | 标点断书、每本页数配置 | 已完成（0.4.0） |
| P4 | 内容校验、失败自恢复、配置与发布 | 已完成（0.5.0） |
| P4.1 | LLM 核验与补丁（BookForge 0.2.0） | 已完成，DeepSeek 实测通过 |
| P4.2 | 电子书导入（EPUB/AZW3/MOBI/FB2/DOCX） | 已完成（BookForge 0.3.0） |
| P4.3 | LLM 质量校准、diff、全量三体1、游戏内验证 | 进行中：三体1 已验 3/13，剩余异常路径与配置验证 |
| P5 | 多书适配、任务队列、配置 UI、发布 | 已完成（1.21.5–1.21.11 + 26.1–26.2，0.10.0 统一运行流水线，P5.5 发布准备完成） |
| P6 | BookForge 桌面 GUI（导入/核验/补丁） | 已完成 G1–G5（BookForge 0.5.0） |
| P7 | 帮助、API key 管理与 AutoBook/BookForge 联动 | 进行中：P7.1–P7.3 与 P5.5 发布准备完成，P7.4 联动是下一步 |

## P0：脚手架

交付：

- `bookforge/`：Python 包、pytest、pyproject。
- `autobook/`：Fabric 1.21.8 模组、Gradle 8.14.2、Loom 1.10.5、JDK 21。
- `docs/`、`dist/`、`.gitignore`。

验证：Python 与 Java 项目均可独立构建。

## P1：文本流水线

交付：

- 编码识别（UTF-8/BOM/UTF-16/GB18030 猜测）。
- 规范化：换行、制表符、控制字符、NFC。
- 广告/网址/页码行清洗，保留台词引号。
- 章节识别与 12000 字符分段。
- `job.json` + `report.json`，JSON Schema 校验。
- CLI：`prepare`、`validate`。

验证：

- pytest 14 项通过。
- 三体1：35 章、36 段、1195 页、0 警告；非空白字符无损失；最长段估算 83 页。

## P2：单本写入

交付：

- `/autobook` 客户端命令：`plan`、`start`、`status`、`stop`。
- `PageLayout`：114 px / 14 行 / 1023 字符，`§` 零宽度。
- `BookPlanner`：按 `pageLimit` 续本，标题连续编号。
- 库存寻书、切换快捷栏、SWAP 移动。
- 写入时序：`useItem` → 5 tick → 关闭界面（不保存）→ 客户端预测 → 发送编辑包 → 40 tick 确认 → 最多 3 次重试。
- 中文任务名（greedy string）。

验证：

- Java 7 项测试通过。
- 实机：`AutoBookTest-01` 与 `三体1-01`（43 页）成功签名。
- 关键发现：服务端编辑会话由 `useItem` 创建且很快过期；手动打开/关闭书本页面可恢复失败尝试。

## P3：批量写入与可恢复运行

交付：

- `BookWriter` 遍历全部 `PlannedBook`，每本独立走完整写入时序。
- 进度持久化：`autobook/state/<planHash>.json`，每完成一本保存。
- `PlanDigest`：任务名 + 标题 + 页数 + 全部页面内容的 SHA-256，防止错误续写。
- 命令：新增 `resume`、`pause`；`stop` 保存进度。
- 暂停类型：`SUPPLY`（自动恢复）、`MANUAL`、`CONFIRM`（人工处理后恢复）。
- 空书耗尽自动暂停，每 20 tick 检测补给。
- 动作栏显示 `[当前/总数]` 进度。
- 主背包取书时优先换到空快捷栏槽，减少移动成书。
- `autobook/config.json`：`keepWrittenBooks`，可选写完即丢。
- 文档：README、架构、使用、任务格式、红石、计划、更新日志。

验证：

- Java 15 项测试通过（新增 StateStore、PlanDigest、跨段编号测试）。
- 构建 `autobook-0.2.1.jar` 并放入 `dist/`。
- 单本时序保持 0.1.4 行为不变。

验收标准：

1. 一次 `start` 可连续写入多本，书名与顺序正确。
2. 中途停止或游戏重启后，`resume` 从下一本继续，不重复已完成的书。
3. 空书耗尽自动暂停，补给后自动继续。
4. 服务器未确认时最多重试 3 次，然后暂停并给出人工处理提示。
5. 原有单本成功路径不回归。

### P3.1：稳定性与资源优化（0.3.0）

针对实机反馈的两个问题：

1. **短章节单独成书浪费空书**
   - `BookPlanner` 改为跨 segment 连续打包，装满 `pageLimit` 再开新书。
   - 三体1 由 36 本降至约 12 本。
2. **印刷过快导致卡书/找不到书/重复印书/界面未关闭**
   - 默认时序放慢并全部可配置：`settleTicks`、`inventoryWaitTicks`、`confirmWaitTicks`、`retryDelayTicks`。
   - 库存切换超时改为回到寻书阶段重试，默认 3 次后才暂停。
   - 写入确认改为“主手成书或背包内同书名/同页数成书”，并在每本开始前跳过已签名书。
   - 写入后意外弹出的书本编辑界面会被自动关闭。
   - 重试前回到 `FIND_BOOK` 复查，避免把已签名的书再次印刷。

验证：

- Java 17 项测试通过（新增跨段打包用例）。
- 构建 `autobook-0.3.0.jar` 并放入 `dist/`。
- 注意：打包方式变化会使旧 `planHash` 失效，0.2.x 进度不能续写。

### P3.2：标点断书与页数配置（0.4.0）

针对实机反馈“分书截断句子”：

- 新增 `SentenceBreaks`，识别句末标点与右引号/右括号。
- `BookPlanner` 在超过上限时向前回退，优先选择句子完整结束的页作为书末页。
- 回退窗口受限（约 20 页、至少保留 60% 页数），避免产生过短的“补空书”。
- 只调整书边界，不改变页内排版与总页数。
- 新增配置：`pageLimit`（0 = 使用 job）、`breakAtSentence`（默认开）。
- 写入节奏相关字段保持可配置。

验证：

- Java 24 项测试通过（新增标点断句与页数覆盖用例）。
- 构建 `autobook-0.4.0.jar` 并放入 `dist/`。
- 修改页数/断句设置会改变 `planHash`，需要重新 `start`。

## P4：内容校验、自恢复与发布（0.5.0）

交付：

1. **内容校验**
   - `ContentVerifier` 逐页比较计划文本与服务器返回的成书页。
   - 忽略 `§` 格式码、CR、行尾与页面首尾空白。
   - 校验失败进入 `VERIFY` 暂停，不推进进度；resume 时强制重写当前书。
   - 可通过 `verifyContent` 或 job `options.verifyContent` 关闭/覆盖。
2. **失败自恢复**
   - 重试等待按尝试次数递增（上限 600 tick）。
   - 3 次失败后自动长等待，并模拟“打开/关闭书本页面”再重试。
   - 每本书一轮恢复；仍失败才进入 `CONFIRM` 暂停。
   - 库存切换仍保留多次重试与暂停兜底。
3. **配置与发布**
   - `/autobook config` 查看配置，`/autobook config <key> <value>` 修改并保存。
   - `job.json` 的 `options` 支持 `pageLimit`、`breakAtSentence`、`verifyContent` 每任务覆盖。
   - `scripts/build.ps1`：跑测试、构建、暂存 dist；带 `-GameDir` 时安装并校验 jar 版本、Fabric API、旧 jar 清理与目录创建。

验证：

- Java 29 项测试通过（新增 ContentVerifier 与 forceRewrite 持久化用例）。
- Python 40 项测试通过（含 LLM 核验/补丁离线用例）。
- `scripts/build.ps1` 实测可完成测试、构建并生成 `dist/autobook-0.5.0.jar`。
- 保持 0.1.4 的写入时序与 0.3/0.4 的打包、断句行为。

### P4.1：LLM 核验与补丁（BookForge 0.2.0）

交付：

- 新增 `bookforge/llm.py`：
  - OpenAI 兼容 `/chat/completions`，使用 `urllib`，不新增依赖；
  - 按 `max_chars` 分块，优先在换行处切分；
  - report 模式解析 `excerpt/message/suggestion`，patch 模式解析 `find/replace/confidence`；
  - 为每个 issue 记录 `segment/chunk/chunkStart/chunkEnd/chunkHash`；
  - 汇总 `summary`、`issues`、`errors`、`blocked`，报告不包含 API key。
- 新增 CLI：
  - `bookforge review <job.json> --mode report|patch`；
  - `bookforge apply-patch <job.json> --patch llm_patch.json`。
- 新增 `bookforge/patch.py` 本地硬校验：
  - `find` 唯一、`chunkHash` 匹配、置信度阈值、按类型长度上限、换行结构、重叠检测；
  - 输出 `reviewed/job.json`、`03_reviewed.txt`、`patch_apply.json`。
- 审核拦截处理：`blocked[]` 记录并继续其他块；`--strict` 将拦截计为失败。
- 新增 `bookforge/keys/llm_api_key.txt`（空）、`keys/llm_config.json`、`keys/glossary.txt`、`keys/glossary-三体1.txt`。
- 每本书独立 profile：按 `titleBase` 自动选择，支持不同的 `base_url/model/key_file/timeout/max_chars/max_tokens/temperature/thinking/glossary/style/min_confidence/max_delta`。
- `thinking` 可关闭推理模式；报告累计 `usage`（prompt/completion/reasoning/total tokens）。
- 报告写入 `settings` 与 `policy`；`apply-patch` 默认采用报告中的置信度与长度阈值。
- 只应用高置信度且通过本地校验的补丁；`ad` 类型不自动应用。

验证：

- pytest 54 项通过（LLM 使用假客户端，无网络）。
- DeepSeek 实测：`api.openai.com` 直连超时，`api.deepseek.com` 可连通。
- 非推理模式（`thinking=false`）实测：三体1 首块 4000 字，约 2655 输入 + 389 输出 tokens，`reasoning=0`，识别 8 处问题。
- patch 模式同块约 2830 输入 + 291 输出 tokens，生成 8 条补丁；dry-run 应用 7 条 high，拒绝 1 条 medium。
- 推理模式历史问题：8192 输出预算被 reasoning 用满、`content` 为空；`max_tokens=16384` + `max_chars=3000` 可成功。当前已默认关闭推理。
- 自动 profile 与无 profile 回退均实测通过。

## P4.2：电子书导入（BookForge 0.3.0）

目标：直接导入更多书本原本或已校订版本，扩大 LLM 抽样与验证样本。

交付：

- 新增 `bookforge/ebook.py`：
  - `.epub`：解析 container.xml/OPF/spine，按阅读顺序提取 XHTML 正文，跳过 nav 与疑似目录页。
  - `.fb2`：解析 XML 正文。
  - `.docx`：解析 `word/document.xml` 与 `docProps/core.xml`。
  - `.azw3/.mobi/.azw/.kf8/.prc`：优先 Calibre `ebook-convert --no-images`；无 Calibre 时用 Python `mobi` 库提取。
  - 拒绝加密 EPUB；Calibre/mobi 失败时提示可能受 DRM 保护，不处理 DRM 移除。
- `mobi>=0.4.1` 加入依赖，作为无 Calibre 环境下的回退。
- `bookforge prepare` 直接接受电子书：
  - `--title` 改为可选，省略时使用电子书元数据或文件名。
  - 新增 `--calibre` 指定 `ebook-convert` 路径。
  - 输出 `00_imported.txt` 与 `import.json`（原始格式、原始 SHA-256、标题/作者、字符数、警告）。
- 支持无 Calibre 时的清晰错误提示与安装说明。

验证：

- pytest 51 项通过（新增 EPUB/FB2/DOCX/Calibre 缺失用例）。
- EPUB 端到端实测：`prepare book.epub` 自动使用元数据标题，生成 2 章节 job，`import.json` 正确记录原始哈希。
- 真实《西游记》校注本 EPUB 实测：
  - 850,810 字符，101 章、112 段，0 条内容警告。
  - 识别并跳过目录页 `text/part0002.html`（123 个链接、100 个回目短行）；修复前会误生成 100 个 19 字短章节。
  - 使用 `--title 西游记` 覆盖元数据长标题，job 的 `titleBase` 为“西游记”。
  - 元数据作者为 “SoBooks”（站点名），未用于 job。
- 真实《西游记》MOBI/AZW3 实测（Python `mobi` 回退，Calibre 未安装）：
  - 三份 `00_imported.txt` 与 job 正文 SHA-256 完全一致。
  - 均为 850,810 字符、101 章、112 段、0 条内容警告。
  - MOBI 额外跳过 `part0104` 目录页，AZW3 跳过 `part0002`；不影响正文。
  - AZW3 元数据作者为“（明）吴承恩”，EPUB/MOBI 为“SoBooks”。
- Calibre 优先路径仍待有 Calibre 的环境验证；`mobi` 回退已覆盖当前需求。

## P4.3：LLM 质量校准与全量验证（下一步）

目标：把 LLM 核验从“单块可用”提升到“整书可信”，再进入正式改稿与游戏内印刷。

进展：

- `--sample N` 与 `diff.patch` 已实现；网络异常重试 3 次；报告问题上限提高到 5000。
- 三体1 抽样 3 块：32 条 high 补丁，31 条应用、1 条拒绝；高置信度约 94% 可信，2 条需人工判断。
- 三体1 全量报告：66/66 块、697 条问题、655 high、0 错误/拦截；165,564 tokens。
- 三体1 全量补丁：629 条；应用 600、拒绝 29（16 medium、11 find 不唯一、2 low）；36 段修改，diff 2,371 行。
- 西游记 抽样：收紧 prompt 后 report 10 条（9 low、1 high）；patch 2 条 high，其中 1 条 `近跅→近于` 需人工判断。
- 三体1 reviewed job 游戏内实测：已完成 3/13 本，内容校验通过（`verified`），无 `VERIFY`/`CONFIRM` 暂停；修正内容确认无误。
- 西游记实测发现通假字、古今异义等古籍现象被误报；已在 0.4.1 的 report/patch prompt 与西游记 profile `style` 中明确排除。
- 待办：P4.3 仅剩 VERIFY 失败路径与其余 0.5.0 配置项验证。

### 1. 抽样校准

- 新增 `bookforge review --sample N`：从全书均匀抽取 N 个块，而不是只跑开头。
- 对抽样结果人工标注真/假问题，统计 high 置信度补丁的误报率。
- 根据误报调整 prompt、`glossary`、`min_confidence`、`max_delta`。
- 验收标准：抽样中 high 置信度误报率低于 5%–10%；明显的 OCR 错字没有漏检。

### 2. 补丁 diff

- `apply-patch` 额外输出 `reviewed/diff.patch`（统一 diff），并保留 `patch_apply.json`。
- 目标：不用打开整本 `03_reviewed.txt` 也能逐条审阅所有已应用修改。
- 验收标准：diff 覆盖全部 applied 补丁；被拒绝项仍有原因记录。

### 3. 全量三体1

- 先 report 全量（约 66 块），处理 `blocked` 与 `errors`。
- 再 patch 全量，审阅 diff，应用补丁生成 reviewed job。
- 验收标准：report/patch 均为 0 错误；reviewed job 通过 schema 校验；页数与分页统计一致。

### 4. 游戏内验证

- 将 reviewed job 放入 `autobook/jobs/`，`/autobook start` 重新开始。
- 先印 2–3 本，检查签名、内容校验、失败自恢复与动作栏进度。
- 验收标准：2–3 本一次通过；日志出现 `verified`；无 `CONFIRM`/`VERIFY` 暂停。

### 5. 成本与模型

- 使用报告中的 `usage` 汇总整书 tokens，按 DeepSeek 价格表估算成本。
- 非推理模式已实测足够；若改用推理模式，需要重新评估 `max_tokens` 与费用。

## P5：多书适配与易用性

### P5.1 成本预估与 profile 向导

- `bookforge review --estimate`：只统计块数、抽样数与预估 tokens，不调用 API，先看费用再决定是否全量。
- `bookforge profile list/show`：查看当前 `llm_config.json` 的 profile、术语表与 key 状态。
- 多书接入流程：`prepare` → 建 profile（`glossary/style/max_chars/max_tokens/model`）→ `--sample` 校准 → 全量。
- 验收：不调用 API 即可得到整书块数与费用区间；新书 5 分钟内完成 profile 配置。

施工结果（2026-10-31，BookForge 0.4.1）：

- `review --estimate` 已实现，复用 `plan_review` 的抽样/截断逻辑，支持 `--mode`/`--sample`/`--limit`。
- `llm_config.json` 增加 `pricing`（输入/输出每百万 tokens 价格、低谷系数、币种）；未配置时只显示 tokens。
- `bookforge profile list` 与 `profile show <名字>` 已实现，显示模型、块大小、thinking、置信度、术语表条数与 key 状态。
- 三体1 实测：66 块、191,986 字符、约 154,791 tokens，费用约 CNY 0.17–0.33。
- pytest 62 项通过。

### P5.2 AutoBook 多任务队列

- 新命令：`/autobook queue add <job>`、`queue list`、`queue start`、`queue clear`。
- 队列状态保存到 `autobook/queue.json`，记录当前任务、已完成任务、每任务进度。
- 单本完成/跳过后自动推进到下一个 job；暂停/停止/断线后可从队列恢复。
- 队列中的单任务失败不阻塞后续任务：记录失败原因，继续或按配置暂停。
- 验收：两个 job 连续执行；中途退出后 `resume` 能从正确任务继续；不重复已签名书。

施工结果（2026-10-31，AutoBook 0.6.0）：

- 新增 `queue` 包：`QueueJob`、`QueueState`、`QueueStore`、`QueueRunner`；状态写入 `autobook/queue.json`。
- 新增 `/autobook queue add|list|start|clear`；`JobRunner` 统一 plan/start 的加载与分页逻辑。
- 一个任务完成或被跳过（已签名）后自动推进；`BookWriter` 的每本进度继续写入 `state/<planHash>.json`，队列恢复时按 `planHash` 续写。
- 单任务失败默认记录 `error` 并继续下一个；`queueStopOnFailure=true` 时暂停整个队列。
- `/autobook stop`、`start` 会退出队列模式；`pause` 只暂停当前任务，`resume` 后队列继续。
- 新增配置 `queueStopOnFailure`；重启后需手动 `queue start`，不会贸然自动开跑。
- JUnit 38 项通过（新增 QueueState/QueueStore 9 项）。

### P5.2.1 统一单本与队列流水线（AutoBook 0.10.0）

背景：单本命令直接驱动 `BookWriter`，多本走 `QueueRunner`，`stop`/`resume`/`queue clear` 语义重叠，用户难以判断当前状态。

设计：

- 运行级：`CREATED → PLANNING → QUEUING → RUNNING ⇄ PAUSED → COMPLETED`，另有 `FAILED`、`CANCELLED`。
- 任务级：`PENDING → QUEUED → RUNNING ⇄ PAUSED → COMPLETED`，另有 `FAILED`、`CANCELLED`。
- 单本只是“只有一个任务的运行”，不再维护两套流程。

命令：

- `add`、`start [job]`、`list`、`status`、`pause`、`resume`、`cancel [job]`、`stop`、`remove`、`retry`、`plan`。
- 语义区分：`pause` 可恢复；`cancel` 只取消任务；`stop` 终止整条运行；`remove` 删除未开始或已结束记录；`retry` 重新入队。
- 旧 `queue add/list/start` 保留为别名并提示弃用；`queue clear` 等价于 stop + 清空。

施工结果（2026-11-07）：

- 新增 `run` 包：`RunJob`、`RunState`、`RunStore`、`RunRunner`；删除旧 `queue` 包。
- `run.json` v2 保存运行与任务状态；启动时自动迁移旧 `queue.json` 并保留 `queue.json.bak`。
- 重启后 RUNNING 恢复为 PAUSED；`retry` 支持 FAILED/CANCELLED 任务重新入队。
- `BookWriter.Progress` 增加 `verifiedBooks`，运行列表可直接显示校验统计。
- JUnit 52 项通过（1.21.8 与 26.1.2 各一次）。
- 需要真实客户端验证完整状态流转与旧队列迁移。

### P5.3 AutoBook 游戏内配置 UI

- 在客户端增加配置界面（或可点击聊天菜单），可修改 `keepWrittenBooks`、`skipExistingBooks`、`verifyContent`、`autoRecover`、节奏参数。
- 复用 `/autobook config` 的保存逻辑，避免两套配置来源。
- 验收：界面修改后写回 `config.json`，下次 `start/resume` 生效；非法值给出提示。

施工结果（2026-11-07，AutoBook 0.7.0）：

- 新增 `/autobook ui` 与 `gui/AutoBookConfigScreen`：左侧开关按钮、右侧整数输入框，覆盖全部 13 个配置项。
- 保存时逐项调用 `AutoBookConfig.set`（复用范围/布尔校验）并写回 `config.json`；非法值在界面底部显示且不保存。
- 同时完成版本适配：删除未使用的 `BookEditScreenAccessor` mixin（1.21.5 不存在 `saveChanges`），代码已编译通过 1.21.5、1.21.6、1.21.7、1.21.8。
- `fabric.mod.json` 的 `minecraft` 依赖改为构建时注入，jar 与目标版本精确匹配；新增 `scripts/build-multi.ps1` 生成 1.21.5–1.21.8 的独立 jar。
- JUnit 42 项通过（新增配置校验 4 项）。
- 多版本构建产出 `dist/autobook-0.7.0-mc1.21.5/6/7/8.jar`，`fabric.mod.json` 的 `minecraft` 分别精确匹配。
- 配置界面与各版本 jar 仍需在对应客户端做一次打开/保存实测。

### P5.3.1 Minecraft 26.1.x 支持（AutoBook 0.8.0）

背景：26.1 是首个不再混淆的 Minecraft 版本，Mojang 不再提供 mappings；Fabric 改用 `net.fabricmc.fabric-loom`（unobfuscated）插件，Fabric API 名称同步调整。

施工结果：

- 新增独立工程 `autobook-26/`，使用 Loom 1.19.4（unobfuscated）、Gradle 9.8.2、JDK 25、Loader 0.20.1、Fabric API 0.155.3+26.1.2。
- 新增 version-specific compat 源集：
  - `src/main/java-21` 与 `src/main/java-26`：`ClientCompat`（动作栏、玩家名、背包点击）与 `ClientCommandsCompat`（`ClientCommandManager` vs `ClientCommands`）。
  - 配置界面按版本提供：1.21 用 `GuiGraphics/render`，26.1 用 `GuiGraphicsExtractor/extractRenderState`。
- `BookWriter` 改用 compat：`ClickType` → `ContainerInput`、`GameProfile.getName` → `name()`、`displayClientMessage` → `sendOverlayMessage`。
- `build-multi.ps1` 增加 26.1.2 目标，自动切换到 `autobook-26/` 工程。
- 编译与测试通过：1.21.8 与 26.1.2 各 42 项 JUnit；26.1.2 jar 元数据 `minecraft=26.1.2`、`java>=25`、`loader>=0.20.1`。
- 仍需在真实 26.1.2 客户端验证写书、内容校验与队列；当前只完成编译级适配。

### P5.3.2 `/autobook ui` 修复（AutoBook 0.8.1）

- 现象：1.21.8 / 1.21.5 输入 `/autobook ui` 没有界面。
- 原因：聊天命令执行后聊天界面关闭，覆盖了命令中直接 `setScreen` 打开的配置界面。
- 修复：新增 `gui/UiScreens`，把打开请求延迟到下一个客户端 tick，并等待当前界面关闭。
- 新增 `AutoBookCommandTreeTest`，验证 `ui` 与队列/配置子命令已注册。
- JUnit 43 项通过（1.21.8、26.1.2）。

### P5.3.3 数据目录迁移到游戏目录（AutoBook 0.8.3）

- 现象：用户放入 mod 并重启后找不到 `config/autobook/`，不清楚 data 目录位置。
- 改为 `<游戏目录>/autobook/`，与 `mods/` 同级；客户端初始化时自动创建 `jobs/`、`state/` 与默认 `config.json`。
- 首次启动自动迁移旧 `config/autobook/`：只复制新目录中不存在的文件，不覆盖已有内容，保留旧目录。
- 新增 `AutoBookPaths` 统一路径；`StateStore`、`QueueStore`、`JobLoader`、`AutoBookConfig` 全部改用该路径。
- `scripts/build.ps1 -GameDir` 与 BookForge GUI“安装到 autobook/jobs”同步调整。
- JUnit 43 项通过（1.21.8、26.1.2）；pytest 69 项通过。
- 待真实客户端确认自动创建与旧目录迁移。

### P5.4 更深入的成书校验（AutoBook 0.9.0）

- 在现有逐页文本校验基础上，增加整书页数与内容哈希摘要。
- 记录每本书的 `verified` 统计；可选抽样回读已签名书。
- 验收：能检测页数缺失、页面截断、内容替换；失败进入 `VERIFY` 暂停。

施工结果（2026-11-07）：

- `ContentVerifier.digest(pages)` 对规范化后的整书页面计算 SHA-256；`Result` 增加 `expectedDigest` / `actualDigest`。
- 校验成功日志记录整书摘要，失败日志同时输出计划与实际摘要，便于排查页数缺失、截断、替换。
- `RunState` 增加 `verifiedBooks`；每次校验成功后累计并写入 `state/<planHash>.json`，`resume` 时恢复。
- JUnit 47 项通过（新增摘要 3 项、进度计数 1 项；1.21.8 与 26.1.2 各一次）。
- 待真实客户端确认摘要日志与恢复计数。

### P5.5 发布

- GitHub Release / Modrinth 发布流程；一键构建脚本增加版本校验与校验和。
- 文档、示例 job、安装说明随版本发布。
- 验收：从 release 包安装后能跑通测试任务；版本号与 jar/README/CHANGELOG 一致。

施工结果（2026-11-07）：

- 新增 `scripts/release.ps1` 一键发布构建：
  - 版本一致性校验：`autobook`/`autobook-26` 的 `gradle.properties`、`bookforge/__init__.py`、`pyproject.toml`、README、CHANGELOG 不一致即中止。
  - 测试：pytest、JUnit（1.21.8 与 26.1.2 各一次）；随后 `build-multi.ps1` 构建 1.21.5–1.21.11 与 26.1–26.2 九个 jar，`build-gui.ps1` 打包 GUI。
  - 产物验收：每个 jar 的 `fabric.mod.json` 版本与 `depends.minecraft` 精确匹配文件名，且包含帮助类 `HelpText`（P7.1 帮助纳入发布验收）。
  - 密钥验收（P7.2 纳入发布验收）：GUI 打包不含非空 `llm_api_key.txt`；扫描默认 key 与 `llm_config.json` 中 global/profiles 配置的所有 `key_file`，确认发布包无明文 key。
  - 组包：`dist/release/MCBookWriter-<版本>/`，含 jar×9、`BookForge-<版本>-windows.zip`、README/CHANGELOG/INSTALL.txt/RELEASE_NOTES.md（从 CHANGELOG 提取当前版本段落）、docs、examples；生成 `checksums-sha256.txt` 与整包 zip。
  - 安装验收：发布包内示例 job 通过 `bookforge validate`，并检查样例不少于 4 段。
- 新增 `docs/release.md`：GitHub Release / Modrinth 发布流程、分阶段验收清单（构建/客户端试跑/分发）与已知风险表。
- 新增 `docs/examples/sample_job.json` 与可复现源文本 `sample_source.txt`：
  - 由 `bookforge prepare --title 样例 --page-limit 5` 真实生成，4 章 4 段、约 1800 字、估算 14 页，预期 3 本。
  - 覆盖跨章节续本、对话多层引号、省略号/破折号/问号叠用、英文与数字混排、段落首尾空白。
- usage.md 修正构建产物版本号（0.9.0 → 0.11.0）并补充 release.ps1；README 增加发布说明。
- 修复：CHANGELOG 合并重复的 `BookForge 0.6.0` 段落；`INSTALL.txt` 版本列表按实际 `-Versions` 生成。
- 无功能版本变更：AutoBook 保持 0.11.0、BookForge 保持 0.6.0。
- 待办：按 `docs/release.md` 4.2 在 1.21.8 与 26.1.2 真实客户端各试跑一次样例（重点核对本数与断句）；GitHub/Modrinth 账号侧发布操作。

### 推荐施工顺序

1. P5.1 成本预估（小，先做）。
2. P6 G1/G2（GUI 导入 + LLM 报告）。
3. P5.2 多任务队列。
4. P5.3 游戏内配置 UI 与 26.1.x 适配。
5. P5.4/P5.5 与 P6 G3–G5。
6. P7.2 API key 管理 → P7.1 AutoBook 帮助 → P7.3 BookForge 帮助 → P5.5 发布 → P7.4 联动。

## P6：BookForge 桌面 GUI 设计

目标：让非命令行用户也能完成“导入电子书 → 生成 job → LLM 核验 → 补丁审阅 → 安装到游戏目录”的闭环。

### 技术选型

- Python 3.11+ + **PySide6（Qt 6）**，作为可选依赖：`pip install -e ".[gui]"`，入口 `bookforge-gui`。
- 复用现有核心函数（`pipeline.prepare_document`、`ebook.extract_ebook`、`llm.review_job`、`patch.apply_patches`），不复制业务逻辑；Calibre 仍作为外部工具调用。
- 打包：PyInstaller one-folder exe；`keys` 只带空模板，不打包 API key。

### 代码结构

```text
bookforge/gui/
  __init__.py
  app.py            # QApplication + main()
  main_window.py    # 主窗口、表单、摘要、日志
  workers.py        # PrepareWorker/ReviewWorker/ApplyWorker/ConnectionWorker
  models.py         # 问题/补丁表格模型
  settings.py       # profile/config 编辑、测试连接、安装 job
bookforge/workflow.py  # CLI/GUI 共用 prepare_input
```

- `workflow.prepare_input` 统一处理电子书导入、`00_imported.txt`、`import.json`、`prepare_document`，CLI 与 GUI 共用。
- GUI 只负责界面、线程与错误展示，不在界面层重复导入/分段逻辑。

### 本轮施工（G1）

- 输入文件/输出目录/书名/每本页数/单段字符数。
- 文件选择、自动填充输出目录与书名。
- “导入并生成 job”按钮；后台 `PrepareWorker` 执行，UI 不冻结。
- 摘要：格式、标题、作者、字符数、章节/段/预估页数、导入警告。
- 书名超过 24 字符（job schema 上限）时直接给出中文错误。
- 日志面板、错误对话框、输出路径展示。
- `bookforge-gui` 入口与 `[gui]` 可选依赖。
- 验收：选择西游记 EPUB，点击生成，显示 101 章/112 段/1 条目录警告；输出 job/report/import 文件。

施工结果（2026-10-31）：

- BookForge 0.4.0；新增 `bookforge/workflow.py`（`prepare_input` / `PrepareOutcome`），CLI 与 GUI 共用导入与生成逻辑。
- 新增 `bookforge/gui/`：`app.py`、`main_window.py`、`workers.py`。
- `pyproject.toml` 增加 `gui = ["PySide6-Essentials>=6.7"]` 与 `bookforge-gui` 入口。
- offscreen 端到端实测：西游记 EPUB → 101 章、112 段、最大预估 84 页、1 条目录页警告，GUI 摘要与日志正常。
- 新增 `tests/test_workflow.py`（txt/EPUB/超长书名）；pytest 57 项通过。

### G2–G5 施工结果（BookForge 0.5.0）

- **G2 LLM report**：新增“LLM 核验”页，支持 report/patch、抽样、逐块进度、取消、问题表格与 token 统计；`review_job` 增加 `progress`/`cancel` 回调。
- **G3 patch 审阅**：新增“补丁审阅”页，默认勾选 high 置信度，可逐条勾选；应用选中补丁后生成 `reviewed/job.json`、`03_reviewed.txt`、`diff.patch`、`patch_apply.json`，并显示 diff 与被拒绝原因。
- **G4 配置**：新增“配置”页，编辑全局/每本书 profile 并写回 `llm_config.json`；显示 key 状态；测试连接；把 job 安装到游戏 `autobook/jobs/`；用 QSettings 记住最近路径。
- **G5 打包**：新增 `BookForge.spec` 与 `scripts/build-gui.ps1`，已实际构建 `dist/gui/BookForge/BookForge.exe`；`job.schema.json` 打包路径已适配 PyInstaller，keys 只带配置/术语表模板，不打包真实 key。
- 验证：pytest 69 项通过；offscreen GUI 4 个标签页可创建；补丁 apply 端到端生成 reviewed job 与 diff；打包版可启动。

### 界面结构

```text
┌────────────────────────────────────────────────────┐
│ 输入文件 [................................] [浏览]  │
│ 输出目录 [................................] [浏览]  │
│ 书名 [........]  每本页数 [100]  段上限 [12000]     │
│ [导入并生成 job]  [LLM 报告]  [LLM 补丁]  [停止]    │
├────────────────────────────────────────────────────┤
│ 摘要：101 章 / 112 段 / 预估约 9 本 / 导入警告 1     │
│ 进度条 [############--------]  当前块 12/220        │
│ 日志：............................................  │
├────────────────────────────────────────────────────┤
│ 概览 | 问题列表 | 补丁审阅 | 配置                   │
└────────────────────────────────────────────────────┘
```

### 标签页

1. **概览**
   - 电子书元数据（格式、标题、作者、字符数）。
   - 导入警告（目录页跳过、DRM/Calibre 错误、编码兜底）。
   - 章节/段/预估页数、书名长度警告。
   - 输出文件链接：`job.json`、`report.json`、`import.json`、`00_imported.txt`。
2. **问题列表**
   - report 模式的 issues 表格：段、章节、页码/块、类型、置信度、原文、说明、建议。
   - 按类型/置信度过滤；导出 JSON/CSV。
3. **补丁审阅**
   - patch 模式表格：`find`、`replace`、置信度、原因、应用复选框。
   - 默认只勾选 high；选中后显示 diff 预览。
   - “应用选中补丁”生成 reviewed job；显示 applied/rejected 原因。
   - 不提供“全部自动应用”。
4. **配置**
   - profile 下拉框（按书名自动选中）；编辑 `model/max_chars/max_tokens/temperature/thinking/glossary/style/min_confidence/max_delta`。
   - API key 状态只显示“已配置/未配置”，不回显内容。
   - “测试连接”只发一条最小请求；“保存”写回 `llm_config.json`。
   - “安装到游戏目录”：复制 job 到 `autobook/jobs/`（可选）。

### 线程与取消

- `PrepareWorker`、`ReviewWorker`、`ApplyWorker` 使用 `QThread`/`QRunnable`，通过信号发送 log/progress/result/error。
- LLM 循环在每个块之间检查 `threading.Event` 取消标记；取消后保留已完成块的报告。
- GUI 主线程不做网络/文件重活；Calibre/LLM 超时与错误显示在日志和对话框。

### 安全与约束

- 补丁不自动应用；默认 high 置信度，必须经过表格勾选与 diff 预览。
- 不显示、不记录、不打包 API key；报告沿用已有的 key 脱敏规则。
- 不处理 DRM；遇到加密 EPUB 或 Calibre 失败时只提示。
- 覆盖输出目录前二次确认；所有生成文件路径可见、可打开。

### 阶段

- **G1**：文件选择、标题/输出目录、导入并生成 job、摘要与日志。（已完成）
- **G2**：LLM report、进度/取消、issues 表格、token/费用统计。（已完成）
- **G3**：LLM patch、补丁勾选、apply、diff 预览与 rejected 原因。（已完成）
- **G4**：profile/配置编辑、测试连接、安装到游戏目录、最近项目。（已完成）
- **G5**：PyInstaller 打包、图标/版本信息、安装说明。（exe 已构建；自定义图标待补）

### 验收标准

- 不打开命令行即可导入 EPUB，显示 101 章/112 段/目录警告，并生成 job。
- LLM 运行有进度与取消；问题表可过滤、导出。
- 补丁可逐条勾选，应用前看到 diff，应用后生成 reviewed job。
- 全程 UI 不冻结；错误信息包含可操作提示（Calibre、DRM、key、网络、截断）。
- 打包版不包含任何 key 或用户书稿。

### 非目标

- 不做游戏内叠加界面（AutoBook 配置 UI 属于 P5）。
- 不做服务端/多人协作。
- 不做 DRM 移除、自动出版或未经审阅的全书自动改稿。

## P7：帮助、密钥管理与工具链联动

目标：降低首次使用门槛，补齐 API key 管理，并让 BookForge 与 AutoBook 形成可观察、可校验的闭环。

### P7.1 AutoBook 游戏内帮助（AutoBook 0.11.0）

- `/autobook help`：命令分组、状态机简表、首次使用流程、当前运行提示。
- `/autobook help <topic>`：`start`、`run`、`config`、`verify`、`recover`、`job`、`cancel` 等主题。
- `/autobook ui` 增加“说明”入口：分页滚动文本 + 返回按钮；1.21 与 26.1 各一份渲染实现。
- 帮助文本集中到 `HelpText`，带版本号（从 Fabric 模组元数据读取），命令与界面共用，避免两套说明。
- 无运行或命令报错时，提示 `/autobook help`。
- 验收：所有命令与 stop/cancel/remove/retry 语义都有说明；UI 说明页在常用 GUI 缩放下可读；命令树测试覆盖 `help` 与主题参数。

施工结果（2026-11-07，AutoBook 0.11.0）：

- 新增 `help/HelpText`：概览与 start/run/job/cancel/config/verify/recover 主题，支持中文别名；版本号从 Fabric 模组元数据读取。
- 新增 `/autobook help` 与 `/autobook help <主题>`；命令错误时提示查看帮助。
- 配置界面底部新增“说明”按钮；新增 `AutoBookHelpScreen`（1.21/26.1 两套渲染），按宽度换行、上一页/下一页/返回。
- JUnit 55 项通过（新增 HelpText 3 项；1.21.8 与 26.1.2 各一次）。
- 待真实客户端验证帮助页分页与返回。

### P7.2 BookForge API key 管理（BookForge 0.6.0）

- GUI“配置”页新增密钥区：密码框输入、保存/更新、清除、测试连接、掩码预览（仅显示首尾各 4 位）与来源（文件/环境变量/profile）。
- 支持每本书 profile 的 `key_file`，GUI 字段与 `llm_config.json` 同步；默认 `keys/llm_api_key.txt`。
- CLI：`bookforge key status`、`bookforge key set`（从 stdin/交互输入，避免命令行历史泄露）、`bookforge key clear`、`bookforge key test`。
- 安全：不打印、不写日志/报告、不打包真实 key；原子写入；POSIX 下尽量设置 600 权限；保留 `BOOKFORGE_LLM_KEY_FILE` 兼容。
- 验收：不手动编辑文件即可完成配置/更换/清除/测试；状态命令只显示来源、掩码与文件路径；profile 使用不同 key 时测试连接正确。

施工结果（2026-11-07，BookForge 0.6.0）：

- 新增 `bookforge/keymanagement.py`：key 路径解析、掩码、原子保存/清除、最小连接测试。
- CLI 新增 `bookforge key status|set|clear|test`；`set` 默认交互输入，`--file` 从文件读取。
- GUI“配置”页新增 API key 区（密码框、保存、清除、测试连接、掩码/来源显示）；profile 支持 `key_file`。
- POSIX key 文件尝试 600 权限；空 `key_file` 自动从 profile/全局配置移除。
- pytest 77 项通过；打包 exe 已随 P7.3 重新构建并验证。

### P7.3 BookForge 帮助中心（BookForge 0.6.0）

- 新增“帮助”标签页（离线 HTML）：快速开始、支持格式、LLM 核验流程、补丁安全规则、密钥配置、安装到游戏、常见错误、版本与路径信息。
- 关键控件补充 tooltip；提供“打开配置目录”“打开日志目录”“打开游戏目录”按钮。
- 帮助内容内置在代码中，不依赖外部网页；打包 exe 可离线查看。
- 验收：GUI 与 CLI 用户都能从界面找到完整流程；帮助页覆盖 P7.2 的 key 管理与 P7.4 的联动说明。

施工结果（2026-11-07）：

- 新增 `gui/help_content.py`：`build_help_html` 生成完整离线 HTML（内置 CSS，无 img/script/link/外部 href）；
  `build_path_info` 动态生成版本、Python、keys 目录、llm_config/key/glossary 实际路径、key 状态（掩码）与游戏目录表格。
- `main_window.py` 新增第 5 个“帮助”标签页（QTextBrowser，`setOpenExternalLinks(False)`）；
  切换到该页时自动刷新路径信息；三个打开目录按钮（配置目录不存在时自动创建；日志目录缺失时回退到游戏目录；未设置游戏目录时提示并跳转“配置”页）。
- 生成/核验/补丁/配置各页关键控件补充 tooltip。
- pytest 82 项通过（新增 test_gui_help 5 项：必备章节、离线无外部资源、版本/路径、HTML 转义、空游戏目录）。
- `scripts/build-gui.ps1` 重新打包，BookForge.exe 启动正常（帮助内容随代码进入 PYZ，无额外数据文件）。
- usage.md（2.2 节改为 5 个标签页）、README、CHANGELOG 已同步。

### P7.4 AutoBook ↔ BookForge 文件级联动

设计原则：只通过 `autobook/` 下的文件契约联动，不引入网络服务；`run.json` 由 AutoBook 独占写入，BookForge 只读。

1. **任务元数据**
   - BookForge 安装 job 时同时写 `autobook/jobs/<title>.meta.json`：
     `schema`、`titleBase`、`bookCount`、`totalPages`、`pageLimit`、`reviewed`、`llmApplied`、`sourceHash`、`generatedAt`、`generatorVersion`。
   - AutoBook `/autobook jobs` 列出已安装任务及“已校订/未校订、书数、页数、更新时间”；缺失 meta 时回退到直接读取 job。
2. **运行状态快照**
   - AutoBook 在状态变化及节流周期内原子写入 `autobook/status.json`（v1）：
     `runStatus`、`currentJob`、`nextIndex`、`completedBooks`、`totalBooks`、`verifiedBooks`、`reason`、`updatedAt`。
   - BookForge 新增“游戏联动”区：读取 status.json 只读展示进度；显示 AutoBook jar 版本并提示与 job/schema 不兼容的情况。
3. **安装与校验**
   - BookForge 安装前校验 job schema、书名长度与目标目录；同名任务可覆盖并保留 `.bak`。
   - 可选“一键安装并启动说明”：安装后提示在游戏内执行 `/autobook add <任务名>`。
4. **兼容与容错**
   - meta/status 均为独立 schema v1，未知字段忽略；文件缺失或损坏时降级，不影响模组启动。
   - 两边分别用 fixture 做单元测试：meta 解析、status 读取、版本不匹配、损坏文件。
- 版本：AutoBook 0.12.0、BookForge 0.7.0。
- 验收：GUI 安装后 `/autobook jobs` 能显示元数据；游戏内运行进度能在 GUI 中刷新看到；版本不匹配有明确提示；保留旧 job（无 meta）仍可运行。

### 施工顺序与版本安排

1. **P7.2 API key 管理**：涉及安全与发布阻塞项，先做；与 P7.3 合并为 BookForge 0.6.0。
2. **P7.1 AutoBook 帮助**：AutoBook 0.11.0，独立于联动，先行可用。
3. **P7.3 BookForge 帮助中心**：与 P7.2 同版本发布，形成完整 GUI 引导。
4. **P5.5 发布准备**：在 P7.1–P7.3 完成后执行，把帮助与密钥管理纳入发布验收。
5. **P7.4 联动**：AutoBook 0.12.0 + BookForge 0.7.0；可作为发布前最后一项或紧随发布后的增强。

总体验收：

| 项 | 标准 |
| --- | --- |
| 帮助 | 新用户不查文档即可从 `/autobook help` 或 GUI 帮助页完成首次导入→安装→运行 |
| 密钥 | 全程无需手工编辑 key 文件；任何界面/日志/报告都不出现明文 key |
| 联动 | 安装的任务带元数据、运行进度可观察、版本不匹配可提示，且不影响旧 job 兼容 |

### 非目标（P7）

- 不提供云端账号或跨设备同步。
- 不引入网络 API 做联动，只使用 `autobook/` 下的文件契约。
- BookForge 不写 `run.json`，不代替游戏内 start/pause/stop。

## P5.6：Minecraft 版本适配（1.21.11 与 26.1 / 26.1.1 / 26.2）

目标：在不改变功能版本号的前提下，把 AutoBook 的构建目标扩展到 1.21.11 与 26.x 全系列。

- 1.21.11：Java 21、Fabric API `0.141.6+1.21.11`、Loader `0.20.1`。
- 26.1 / 26.1.1：Java 25、Fabric API `0.155.3+26.1.2`、Loader `0.20.1`。
- 26.2：Java 25、Fabric API `0.161.0+26.2`、Loader `0.20.1`。

关键改动：

- 新增 `compat/ScreenCompat`（`java-21` 直接访问、`java-26` 反射）：26.2 把界面状态从 `Minecraft` 移到 `Gui`，统一后界面代码无需分叉。
- `ClientCompat.playerName` 改用 `Player.getName().getString()`：1.21.11 的 authlib 中 `GameProfile` 为 record。
- `build-multi.ps1` 对 `autobook-26` 工程按目标版本改写四个依赖字段与 `java_release`。

验收状态：

- 四个新 jar 编译与打包通过（`dist/autobook-0.11.0-mc1.21.11` / `-mc26.1` / `-mc26.1.1` / `-mc26.2`）。
- 待办：四个版本真实客户端试跑（写书、内容校验、`/autobook ui` 与帮助页），见 `docs/release.md` 4.2。

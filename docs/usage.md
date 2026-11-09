# 使用手册

## 1. 环境准备

- Minecraft Java 版 1.21.5–1.21.11 或 26.1–26.2（每个版本使用对应的 AutoBook jar 与 Fabric API）
- Fabric Loader（1.21.5 需 0.16.10+；1.21.6–1.21.8 需 0.16.13+；1.21.11 需 0.17.3+；26.x 需 0.18.4+）
- Fabric API（1.21.5/1.21.6 用 0.128.2，1.21.7 用 0.129.0，1.21.8 用 0.136.1，1.21.11 用 0.141.6+1.21.11，26.1/26.1.1/26.1.2 用 0.155.3+26.1.2，26.2 用 0.161.0+26.2）
- Java 21（1.21.x）；Java 25（26.x）
- Python 3.11+（仅预处理需要）

AutoBook 是**客户端模组**，服务器不需要安装。

## 2. 生成 job.json

```powershell
cd MCBookWriter\bookforge
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

bookforge prepare "D:\books\三体1.txt" --title 三体1 --out work\三体1 --verify

# 电子书可直接导入；--title 省略时使用元数据或文件名
bookforge prepare "D:\books\三体1.epub" --out work\三体1 --verify
bookforge prepare "D:\books\三体1.azw3" --calibre "C:\Program Files\Calibre2\ebook-convert.exe" --out work\三体1
```

### 2.0 支持的输入格式

| 格式 | 处理方式 |
| --- | --- |
| `.txt` / `.md` | 直接读取并按编码识别 |
| `.epub` | 原生解析 OPF/spine，按阅读顺序提取 XHTML 正文，跳过 nav 与疑似目录页 |
| `.fb2` | 原生解析 XML |
| `.docx` | 原生解析 `word/document.xml` |
| `.azw3` / `.mobi` / `.azw` / `.kf8` / `.prc` | 优先 Calibre 转 EPUB；无 Calibre 时用 Python `mobi` 库提取 |

- Calibre 可选但推荐；未安装时自动使用 Python `mobi` 库（已作为项目依赖）。也可用 `--calibre` 指定路径。
- 仅支持无 DRM 的文件；本项目不处理 DRM 移除。EPUB 加密条目、Calibre 转换失败或 mobi 解析失败会直接报错。
- 电子书输入会在输出目录生成：
  - `00_imported.txt`：提取出的正文，供检查和重新预处理。
  - `import.json`：原始文件、格式、原始 SHA-256、标题、作者、字符数与导入警告。
  - 典型警告：`跳过疑似目录页: ...`、编码兜底、缺少 EPUB 条目。

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--title` | 书名基名；省略时使用电子书元数据或文件名 |
| `--out` | 输出目录，默认 `work/<输入文件名>` |
| `--calibre` | `ebook-convert` 路径；用于 AZW3/MOBI/AZW/KF8 |
| `--page-limit` | 每本页数上限，默认 100，范围 1–100 |
| `--max-segment-chars` | 单段最大字符数，默认 12000 |
| `--verify` | 打印校验警告 |
| `--strict` | 存在警告时以退出码 3 结束 |

校验已有任务：

```powershell
bookforge validate work\三体1\job.json
```

## 2.1 LLM 核验与补丁（可选）

两种模式：

- `report`：只输出问题报告，不改动正文。
- `patch`：输出 `find/replace` 补丁，不自动应用；由 `apply-patch` 做本地硬校验后生成新的 job。

### 准备

1. API key（三选一）：

   - **GUI**：打开“配置”页 → API key 区输入 → “保存密钥”；可“清除密钥”或“测试连接”。界面只显示掩码，不回显明文。
   - **CLI**：
     ```powershell
     bookforge key set            # 交互输入，不回显
     bookforge key set --file D:\secure\key.txt
     bookforge key status         # 只显示来源、掩码与路径
     bookforge key test
     bookforge key clear
     ```
   - **手动文件**：`bookforge\keys\llm_api_key.txt`。

   默认文件为空时 `review` 会跳过并生成跳过报告，不会发起请求。可用 `BOOKFORGE_LLM_KEY_FILE` 指定其他 key 文件；profile 也支持 `key_file`。优先级：命令行 > 环境变量 > profile > 全局配置 > 默认文件。任何界面、日志与报告都不会输出明文 key。

2. 服务配置 `bookforge\keys\llm_config.json`：

   ```json
   {
     "base_url": "https://api.deepseek.com",
     "model": "deepseek-flash",
     "timeout": 120,
     "max_chars": 4000,
     "temperature": 0,
     "max_tokens": 8192,
     "thinking": false,
     "glossary": "keys/glossary.txt",
     "min_confidence": "high",
     "pricing": {
       "currency": "CNY",
       "inputPerMillion": 2.0,
       "outputPerMillion": 3.0,
       "offpeakFactor": 0.5
     },
     "max_delta": {"typo": 2},
     "profiles": {
       "三体1": {
         "glossary": "keys/glossary-三体1.txt",
         "style": "本书为中文科幻小说《三体1》。保留作者用词、语序、科技术语与人物名；不要统一标点风格。",
         "max_chars": 4000,
         "max_tokens": 8192,
         "thinking": false
       }
     }
   }
   ```

   `base_url` 需指向 OpenAI 兼容的根路径；换服务商时同时修改 `model`。

   `pricing` 仅用于 `--estimate` 的费用估算，按每百万 tokens 的输入/输出价格与低谷折扣系数计算；价格以服务商为准，可随时修改。

3. 术语表：
   - `keys/glossary.txt`：全局术语。
   - `keys/glossary-三体1.txt`：按书专用术语。

4. 也可用环境变量：`BOOKFORGE_LLM_KEY_FILE`、`BOOKFORGE_LLM_BASE_URL`、`BOOKFORGE_LLM_MODEL`。

### 报告模式

```powershell
# 只估算块数与费用，不调用 API
bookforge review work\三体1\job.json --estimate
bookforge review work\三体1\job.json --estimate --mode patch --sample 3

# 只核验前 2 块，确认接口与费用
bookforge review work\三体1\job.json --limit 2

# 从全书首/中/尾均匀抽 3 块做质量校准
bookforge review work\三体1\job.json --sample 3 --mode report

# 全量问题报告
bookforge review work\三体1\job.json --mode report
```

### 补丁模式与 apply-patch

```powershell
# 小规模试跑
bookforge review work\三体1\job.json --mode patch --limit 2

# 全量生成补丁
bookforge review work\三体1\job.json --mode patch

# 查看将应用/拒绝哪些补丁
bookforge apply-patch work\三体1\job.json --patch work\三体1\llm_patch.json --out work\三体1\reviewed --dry-run

# 正式应用
bookforge apply-patch work\三体1\job.json --patch work\三体1\llm_patch.json --out work\三体1\reviewed
```

`apply-patch` 输出：

| 文件 | 说明 |
| --- | --- |
| `job.json` | 应用补丁后的新任务，`options.llmApplied=true` |
| `03_reviewed.txt` | 各段文本拼接后的审阅稿 |
| `diff.patch` | 统一 diff，逐条查看已应用修改 |
| `patch_apply.json` | 已应用/被拒绝的补丁与原因 |

本地硬校验规则：

- `find` 必须在目标块中逐字存在且唯一，`chunkHash` 必须与当前 job 一致。
- 默认使用补丁报告中的 `policy.minConfidence`；`--min-confidence` 可覆盖。
- 长度阈值来自 `policy.maxDelta`，可在 profile 中按书调整。
- 按类型限制长度变化：typo ≤2 字符、missing/extra ≤30、garbled ≤40、punctuation ≤10。
- 除 `punctuation` 外，不允许改变换行数量。
- 补丁之间不能重叠；`ad` 类型不会自动应用。
- 被拒绝的补丁写入 `patch_apply.json`；`--strict` 在有拒绝时返回 3。

### 常用参数

| 参数 | 说明 |
| --- | --- |
| `--mode` | `report`（默认）或 `patch` |
| `--profile` | 每本书的 profile 名；默认使用 job 的 `titleBase` |
| `--out` | 报告路径；默认 `llm_report.json` 或 `llm_patch.json` |
| `--limit` | 最多核验前 N 块；与 `--sample` 互斥 |
| `--sample` | 从全书均匀抽取 N 块（首/中/尾等距）；与 `--limit` 互斥 |
| `--estimate` | 只统计块数、字符数、预估 tokens 与费用，不调用 API；可与 `--sample`/`--limit`/`--mode` 组合 |
| `--max-chars` | 每块最大字符数，默认读取配置 |
| `--temperature` | 采样温度，默认读取配置 |
| `--max-tokens` | 输出上限，默认读取配置 |
| `--thinking` / `--no-thinking` | 启用/禁用推理模式，默认读取配置 |
| `--glossary` | 术语表路径；默认读取 profile/全局配置 |
| `--key-file` | 临时指定 key 文件 |
| `--base-url` / `--model` | 临时覆盖服务配置 |
| `--strict` | 有问题/错误/拦截时返回 3 |

### 每本书独立配置（profiles）

`llm_config.json` 的 `profiles` 按书名（job 的 `titleBase`）配置，未匹配时使用全局配置。也可用 `--profile` 显式指定；显式指定不存在的 profile 会报错。

profile 可覆盖：

| 字段 | 说明 |
| --- | --- |
| `base_url` / `model` | 不同书可用不同服务或模型 |
| `key_file` | 不同服务可使用不同 key 文件 |
| `timeout` / `max_chars` / `max_tokens` | 控制单块大小、超时与输出上限 |
| `thinking` | `false` 关闭推理模式；`true` 启用（reasoning tokens 计入输出预算） |
| `temperature` | 采样温度，校对建议 0 |
| `glossary` | 本书专用术语表 |
| `style` | 追加到 system prompt 的本书要求 |
| `min_confidence` / `max_delta` | apply-patch 的默认置信度与长度阈值；`max_delta` 与全局合并，同名键以 profile 为准 |

优先级：命令行参数 > 环境变量 > profile > 全局配置 > 内置默认。

查看配置：

```powershell
bookforge profile list
bookforge profile show 西游记
```

`profile list` 显示全局与每本书的 model、max_chars、max_tokens、thinking、min_confidence、术语表条数与 key 状态；`profile show <名字>` 显示单个 profile 的完整字段。两者都不会输出 API key 内容。

古籍/校注本注意：报告与补丁 prompt 已明确不把通假字、古今字、古今异义、古汉语语法与文学修辞当错误；西游记 profile 的 `style` 也重复强调这一点。修订后如仍有误报，优先补充该书的 `style`，而不是放宽全局 `min_confidence`。

注意：当前配置 `thinking=false`，非推理模式已实测足够：三体1 每块约 2655 输入 + 389 输出 tokens，`reasoning=0`。若改为 `thinking=true`，reasoning tokens 会占用输出预算，需要把 `max_tokens` 加大到 16384 左右。

### 报告字段

- `mode`：`report` 或 `patch`。
- `settings`：`profile`、`baseUrl`、`model`、`maxChars`、`temperature`、`maxTokens`、`thinking`、`style`。
- `policy`：`minConfidence` 与 `maxDelta`，供 `apply-patch` 使用。
- `usage`：`promptTokens`、`completionTokens`、`reasoningTokens`、`totalTokens`。
- `summary`：段数、计划块数、实际块数、抽样数、选中块数、问题数、错误数、拦截数、是否跳过。
- `issues[]`：`segment`、`chapter`、`chunk`、`chunkStart`、`chunkEnd`、`chunkHash`、`type`、`confidence`。
  - report 模式带 `excerpt`、`message`、`suggestion`。
  - patch 模式带 `find`、`replace`、`reason`。
- `blocked[]`：被内容审核拦截的块。
- `errors[]`：接口或解析失败的块。
- 报告中不会写入 API key。

### 审核拦截与错误

- `blocked` 块会跳过并继续处理其他块，不会中断全量核验；需要人工复核或改用已获批准的通道。
- 不要用字符替换、拆字、编码转换等方式规避审核；这违反服务条款，也会破坏文本。
- `finish_reason=length` 表示输出被截断，应减小 `--max-chars` 或增大服务端输出上限。
- 网络连接异常（含 `RemoteDisconnected`）会自动重试 3 次；仍失败才记录为错误并停止。

### 注意

- 默认按配置的 `max_chars` 切块；三体1 profile 为 4000 字，约 66 块，即约 66 次请求。非推理模式每块约 3k tokens，成本明显低于推理模式。
- 补丁不会自动应用；只应用高置信度且通过本地校验的修改。
- 使用 reviewed job 会改变 AutoBook 的 `planHash`，需要在游戏内重新 `/autobook start`。
- 该核验针对书稿文本；AutoBook 0.5.0 的内容校验针对签名后的成书页，两者互补。

## 2.2 桌面 GUI（可选）

不想用命令行时，可安装 GUI 依赖并启动：

```powershell
cd MCBookWriter\bookforge
pip install -e ".[gui]"
bookforge-gui
```

也可以直接运行 `.\.venv\Scripts\python.exe -m bookforge.gui.app`。

当前版本（BookForge 0.7.1）的 GUI 包含 6 个标签页：

1. **生成**
   - 选择输入文件（txt/epub/azw3/mobi/fb2/docx 等）与输出目录。
   - 可填书名；留空时使用电子书元数据或文件名。
   - 设置每本页数与单段最大字符数；后台线程执行，界面不冻结。
   - 显示格式、作者、字符数、章节/段/预估页数、导入警告与输出路径。
2. **LLM 核验**
   - 选择 job.json，模式为 `report` 或 `patch`，可设置抽样块数。
   - 显示逐块进度、问题/错误/拦截数、tokens；表格展示问题或补丁。
   - 支持取消；patch 完成后自动填充“补丁审阅”页。
3. **补丁审阅**
   - 加载或自动接收 `llm_patch.json`；默认只勾选 high 置信度。
   - 可逐条勾选/取消，应用选中补丁。
   - 显示统一 diff、被拒绝补丁原因，并生成 `reviewed/job.json`、`diff.patch`、`patch_apply.json`。
4. **上架到游戏**
   - 顶部按 ① 选 job.json 与游戏目录 → ② 安装 → ③ 游戏内 add/start → ④ 查看状态 的顺序给出提示。
   - 把 job.json 安装到游戏目录的 `autobook/jobs/`；同时写入 `<任务名>.meta.json` 并校验 schema、书名与目录，同名覆盖保留 `.bak`。
   - “运行状态（只读）”区：切换到该页或点击“刷新联动状态”时读取 `autobook/status.json`，显示运行状态、进度、校验本数、更新时间与 AutoBook jar 版本；版本过低或当前 job 不兼容时给出提示。
5. **配置**
   - 选择全局或每本书 profile，编辑 `model/base_url/max_chars/max_tokens/temperature/thinking/min_confidence/glossary/style/key_file`。
   - API key 区：输入后“保存密钥”、清除密钥、测试连接；只显示掩码、来源与文件路径。
   - 保存写回 `keys/llm_config.json`；“测试连接”发送一条最小请求。
   - 记住最近使用的输入/输出/游戏路径。
   - 游戏内 `/autobook ui` 配置界面底部有“说明”按钮，可打开分页帮助页。
6. **帮助**
   - 离线内置 HTML：快速开始、支持格式、LLM 核验流程、补丁安全规则、密钥配置、安装到游戏、常见错误。
   - “版本与路径信息”区动态显示版本号、Python、配置/密钥/术语表实际路径、key 状态（掩码）与当前游戏目录；切换到该页自动刷新。
   - 提供“打开配置目录”“打开日志目录”（游戏 logs）“打开游戏目录”三个按钮。
   - 内容完全内置在代码中，不访问网络；打包版 exe 可离线查看。
   - 各页关键控件均有 tooltip，悬停即可查看用途。

打包为独立程序：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-gui.ps1 -InstallDeps
# 产物：dist\gui\BookForge\BookForge.exe
```

打包版把配置与术语表放在 `BookForge\_internal\keys`；可直接在 GUI 配置页保存密钥，或把 `llm_api_key.txt` 放到该目录。程序不会打包真实 key。

注意：

- 书名超过 24 字符会被拒绝（job schema 上限，AutoBook 还会追加 `-NN`）。
- “应用补丁”只应用勾选且通过本地硬校验的补丁；被拒绝项会列在界面中。
- 缺少 PySide6 时源码启动会提示安装命令；打包版无需额外安装 Python。

## 3. 安装任务与模组

```text
%APPDATA%\.minecraft\
├─ mods\autobook-0.13.0.jar
└─ autobook\
   ├─ jobs\三体1.json
   ├─ jobs\三体1.meta.json （BookForge 安装时写入，可选）
   ├─ status.json          （AutoBook 0.12.0 起自动写入）
   ├─ config.json          （首次启动自动生成）
   ├─ run.json             （首次 add 时生成；旧 queue.json 会自动迁移）
   └─ state\               （进度文件）
```

- 将 `dist/autobook-0.13.0.jar` 放入 `mods/`（对应 Minecraft 1.21.8）。
- 其他 Minecraft 版本：运行 `scripts/build-multi.ps1`，从 `dist/` 选择 `autobook-0.13.0-mc<版本>.jar`。当前支持 1.21.5、1.21.6、1.21.7、1.21.8、1.21.11、26.1、26.1.1、26.1.2、26.2。
- 推荐用 BookForge GUI 的“安装任务到游戏目录”：安装前会校验 job schema、书名长度与游戏目录，并同时写入 `<任务名>.meta.json`；同名覆盖会保留 `<任务名>.json.bak`。
- 也可将生成的 `job.json` 复制为 `autobook/jobs/三体1.json`；手工复制的旧 job 没有 meta，`/autobook jobs` 仍会列出，只是书数/页数显示为未知。
- 也可直接把 `dist/jobs/autobook-test.json` 复制过去做连通性测试。

任务名即文件名（不含 `.json`）。命令支持中文任务名。

安装完成后，在游戏内执行 `/autobook add <任务名>`，再 `/autobook start`。运行期间 AutoBook 会原子写入 `autobook/status.json`；在 BookForge“上架到游戏”页的“运行状态（只读）”区点击“刷新联动状态”即可查看进度、校验本数与 jar 版本。BookForge 只读该文件，不写 `run.json`，也不代替游戏内 start/pause/stop。

游戏内操作也可不敲命令：

- `F8`：打开 AutoBook 配置界面（等同 `/autobook ui`），可在“选项 → 控制 → 按键绑定 → AutoBook”改键。
- `F9`：暂停 / 继续当前运行；没有运行任务时动作栏提示。
- 安装 Mod Menu 时，模组列表中的 AutoBook 会提供“配置”按钮，打开同一个配置界面（1.21.5 / 1.21.6 / 1.21.11 提供入口；1.21.7 / 1.21.8 与 26.x 暂无对应 Mod Menu 版本）。

发布前联调自测清单：

1. `mods/` 中只保留与当前游戏版本匹配的 0.13.0 jar；`/autobook jobs` 能列出 BookForge 安装的任务，并显示书数/页数与是否已校订。
2. `autobook/jobs/` 中任务同时存在 `.json` 与 `.meta.json`；对同一任务重复安装一次，确认生成 `.json.bak` 且任务仍可启动。
3. 游戏内 `start` 后，BookForge 刷新应显示运行状态、`已完成/总数` 与校验本数；`pause`/`resume`/`stop` 后状态随之变化。
4. 临时移走任务文件时，BookForge 应提示“当前任务缺失”，而不是崩溃或改写其他文件。
5. 换成低于 0.12.0 的旧 jar 时，BookForge 版本行应提示不支持联动，`/autobook jobs` 也不会出现。

## 4. 配置文件

`autobook/config.json`：

```json
{
  "keepWrittenBooks": false,
  "skipExistingBooks": true,
  "pageLimit": 0,
  "breakAtSentence": true,
  "verifyContent": true,
  "autoRecover": true,
  "recoveryWaitTicks": 200,
  "settleTicks": 15,
  "inventoryWaitTicks": 80,
  "confirmWaitTicks": 100,
  "retryDelayTicks": 120,
  "maxInventoryRetries": 3,
  "queueStopOnFailure": false
}
```

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `keepWrittenBooks` | `true` | `true`：成书留在背包；`false`：每本完成后立即整栈丢出，便于漏斗收集 |
| `skipExistingBooks` | `true` | 跳过背包中“书名+页数”都相同的成书，避免重复印刷 |
| `pageLimit` | `0` | 每本最多页数；`0` 表示使用 job.json 的 `pageLimit`，否则覆盖为 1–100 |
| `breakAtSentence` | `true` | 优先在句末标点处断书，避免一本书的结尾截断句子 |
| `verifyContent` | `true` | 签名后回读成书页数与文本，不一致时暂停 |
| `autoRecover` | `true` | 多次未确认时自动长等待并模拟打开/关闭书本页面后重试 |
| `recoveryWaitTicks` | `200` | 自动恢复前的等待 tick（20 tick = 1 秒） |
| `settleTicks` | `15` | 每本开始前的缓冲 tick，服务器慢可加大 |
| `inventoryWaitTicks` | `80` | 等待空书进入主手的 tick |
| `confirmWaitTicks` | `100` | 等待服务器确认成书的 tick |
| `retryDelayTicks` | `120` | 首次写失败后的等待 tick；后续按尝试次数递增 |
| `maxInventoryRetries` | `3` | 空书多次无法就位时的重试次数 |
| `queueStopOnFailure` | `false` | 队列中单个任务失败时：`false` 记录失败并继续下一个；`true` 暂停整个队列 |

每次 `/autobook plan`、`/autobook start` 或 `/autobook resume` 都会重新读取该文件，修改后无需重启；任务运行中修改则在下次开始/继续时生效。

### 标点断书与页数

- `breakAtSentence=true` 时，一本不会在句子中间结束：会在允许的页数窗口内向前回退，找到最近一个以 `。！？…` 等结尾的页作为本书最后一页。
- 为保证不会出现很短的“补空书”，回退最多约 20 页，并且一本书至少保留约 60% 的页数；找不到合适断点时才按上限切分。
- 该设置只影响**书与书**之间的切分，不改变页内排版和总页数。
- `pageLimit` 覆盖会同时改变书数与 `planHash`，因此修改后旧进度不能续写。
- 断句后的剩余页面会自动进入下一本，不会丢失。

### 内容校验

- `verifyContent=true`（默认）时，签名确认后会读取成书页，与计划逐页比较（忽略 `§` 格式码、行尾空白和 CR）。
- 通过：日志记录 `verified '<书名>' (N pages)`，继续下一本。
- 失败：进入 `VERIFY` 暂停，日志记录期望/实际页数、首个不一致页及片段；进度**不推进**。
- 恢复：移除有问题的书后 `/autobook resume`。恢复后会强制重写当前书，不会被去重逻辑跳过；即使重启游戏，`forceRewrite` 也会从进度文件恢复。
- 关闭校验：`/autobook config verifyContent false`。

### 自动恢复

- 单次写入失败后，等待时间按 `retryDelayTicks × 尝试次数` 递增。
- 连续 3 次未确认且 `autoRecover=true` 时：等待 `recoveryWaitTicks`（默认 200 tick = 10 秒），自动执行一次“打开并关闭书本页面”，然后重新写入。
- 每本书最多自动恢复一轮；仍失败才进入 `CONFIRM` 暂停，等待人工处理。
- 关闭自动恢复：`/autobook config autoRecover false`。

### 每任务覆盖

`job.json` 的 `options` 可覆盖计划参数：

```json
{
  "options": {
    "pageLimit": 80,
    "breakAtSentence": false,
    "verifyContent": true
  }
}
```

优先级：`job.options` > `config.json` > 内置默认。未设置的字段继续使用全局配置。

### 游戏内配置

```text
/autobook config                 查看当前配置
/autobook config <key> <value>   修改并保存到 config.json
/autobook ui                     打开图形配置界面
```

`/autobook ui` 会打开一个客户端配置界面：

- 左侧按钮切换开关项：`keepWrittenBooks`、`skipExistingBooks`、`breakAtSentence`、`verifyContent`、`autoRecover`、`queueStopOnFailure`。
- 右侧输入框修改整数项：`pageLimit`、`recoveryWaitTicks`、`settleTicks`、`inventoryWaitTicks`、`confirmWaitTicks`、`retryDelayTicks`、`maxInventoryRetries`。
- “保存并关闭”复用 `AutoBookConfig.set` 的范围/布尔校验，写回 `config.json`；非法值会在界面底部显示原因，且不会保存。
- 与命令行修改一样，下次 `plan`/`start`/`resume` 生效；运行中的任务不会即时改变时序。
- 队列激活时也可以打开，修改 `queueStopOnFailure` 后在下一次失败判定时生效。

例如：

```text
/autobook config confirmWaitTicks 140
/autobook config verifyContent false
```

保存后下次 `plan`/`start`/`resume` 生效。

## 5. 游戏内命令

```text
/autobook help                   查看帮助
/autobook help <主题>            查看单项：start/run/job/cancel/config/verify/recover
/autobook plan <任务名>          只预演，不改变运行状态
/autobook add <任务名>           加入当前运行（可添加多个任务）
/autobook start                  开始当前运行
/autobook start <任务名>         新建单任务运行并开始（等价于 add + start）
/autobook list                   查看运行与全部任务状态
/autobook jobs                   查看已安装任务与元数据（校订状态、书数、页数）
/autobook status                 查看当前任务、页数与校验统计
/autobook pause                  可恢复暂停
/autobook resume                 从暂停继续（也接受旧的 resume <任务名>）
/autobook cancel [任务名]        取消当前/指定任务，运行继续下一个
/autobook stop                   终止整条运行（CANCELLED，进度保留）
/autobook remove <任务名>        移除尚未开始的任务
/autobook retry <任务名>         把失败/已取消的任务重新入队
/autobook config [key] [value]   查看或修改配置
/autobook ui                     打开图形配置界面
```

示例输出（跨章节打包后，书数显著减少）：

```text
AutoBook 计划: 约 12 本, 1195 页
每本上限: 100 页, 标点断书: 开
内容校验: 开, 自动恢复: 开
空书需求: 约 12 本
第一本: 三体1-01 (100 页)
```

动作栏会持续显示形如 `[3/12] 写入 三体1-04 (尝试 1/3)` 的进度；自动恢复时会显示 `自动恢复: 等待 N 秒后重试`。

## 6. 推荐操作流程

1. 先跑测试任务，确认服务器接受成书：

   ```text
   /autobook plan autobook-test
   /autobook start autobook-test
   ```

2. 按 `/autobook plan` 显示的本数准备空的书与笔（打包后三体1约 12 本，不再需要 36 本）。
3. 关闭所有界面，站在安全位置。
4. `/autobook start 三体1`。
5. 运行期间不要打开背包、箱子或其他界面；模组会等待界面关闭。
6. 中途需要暂停：`/autobook pause`。若正在写某本书，会在该书完成后再停。
7. 继续：`/autobook resume`。
8. 查看进度：`/autobook status` 或 `/autobook list`。
9. 终止：`/autobook stop` 会把整条运行标记为 CANCELLED，进度文件保留；之后可 `/autobook start <任务名>` 重新开始。

## 7. 空书补给

空书不足时模组不会报错退出，而是进入 `SUPPLY` 暂停：

```text
[3/12] 缺少空的书与笔，补给后自动继续
```

把空的书与笔放进背包后，模组每 20 tick 检查一次，检测到即自动继续。红石方案见 [redstone.md](redstone.md)。

## 8. 断点续写

- 每完成一本、暂停、停止都会写入 `autobook/state/<planHash>.json`。
- `/autobook resume` 会重新生成计划并计算计划指纹：
  - 指纹一致且进度有效：从下一本继续。
  - 指纹不一致（书稿、分页、打包方式、任务名变化）：提示没有可恢复进度，需使用 `start`。
  - 任务已完成：提示使用 `start` 重新跑。
  - 兼容旧用法：`/autobook resume <任务名>` 仍可执行，但任务名必须与当前暂停任务一致。
- 删除对应 state 文件即可手动清空进度。

注意：同一书稿重新 `prepare` 时若内容、参数或 `--title` 有变化，`planHash` 会变化，旧进度不会被误用。

0.3.0 改为跨章节打包，书数与每本页数都会变化，因此 0.2.x 的旧进度无法续写。升级后建议移除旧版本印出的书，再用 `/autobook start` 重新开始。

0.4.0 起，修改 `pageLimit`、`breakAtSentence` 或书稿内容也会改变 `planHash`，同样需要重新 `start`。

0.5.0 起，`verifyContent`、`autoRecover`、`recoveryWaitTicks` 与节奏参数不改变 `planHash`，可以直接调整后继续。

进度只在服务端确认成书后推进。若在“已发送但未确认”的瞬间崩溃或强退，恢复时会通过“书名+页数”扫描识别已签名的书并跳过，避免重复印刷。

### 统一运行流水线（单本与多本）

单本只是“只有一个任务的运行”，不再有独立的单本/队列两套命令：

```text
/autobook add 三体1
/autobook add 西游记
/autobook list
/autobook start
```

运行状态：`CREATED → PLANNING → QUEUING → RUNNING ⇄ PAUSED → COMPLETED`，另有 `FAILED`、`CANCELLED`。
任务状态：`PENDING → QUEUED → RUNNING ⇄ PAUSED → COMPLETED`，另有 `FAILED`、`CANCELLED`。

行为：

- 运行状态保存在 `autobook/run.json`（v2），记录运行 `status`、`currentIndex` 与每个任务的 `status/nextIndex/totalBooks/totalPages/verifiedBooks/error`。
- 首次启动会自动把旧 `queue.json` 迁移为 `run.json`，旧文件保留为 `queue.json.bak`。
- `add` 会立即加载并分页任务，成功后任务进入 QUEUED；失败任务标记 FAILED 并记录原因。运行中或暂停时也可以 `add`，新任务会在当前任务之后执行。
- `start` 从当前任务开始；若该任务已有进度，会按 `planHash` 自动恢复。
- 一个任务完成后自动进入下一个；动作栏与日志显示当前任务进度。
- 单个任务失败时，默认记录 `error` 并继续下一个；`/autobook config queueStopOnFailure true` 时整条运行进入 FAILED。
- `pause`/`resume` 是可恢复挂起；`cancel` 只取消当前任务，运行继续下一个；`stop` 终止整条运行并保留进度。
- `remove` 可移除 PENDING/QUEUED 或已结束（FAILED/CANCELLED/COMPLETED）的记录；RUNNING/PAUSED 任务必须先 `cancel`。
- `retry` 把 FAILED/CANCELLED 任务重新置为 QUEUED；FAILED/CANCELLED 运行会回到 QUEUING。
- 游戏重启后运行不会自动开跑：RUNNING 恢复为 PAUSED，需要手动 `/autobook resume`。
- 修改某个 job 的内容或 `options` 会改变 `planHash`，该任务会从头开始；默认 `skipExistingBooks=true` 会跳过已签名的书。
- 旧命令 `queue add/list/start` 仍可用但会提示弃用；`queue clear` 等价于 stop + 清空任务。

示例 `run.json`：

```json
{
  "version": 2,
  "status": "paused",
  "currentIndex": 1,
  "reason": "",
  "jobs": [
    {"name": "三体1", "status": "completed", "nextIndex": 13, "completedBooks": 13, "totalBooks": 13, "totalPages": 1195, "verifiedBooks": 13, "error": ""},
    {"name": "西游记", "status": "paused", "nextIndex": 2, "completedBooks": 2, "totalBooks": 10, "totalPages": 850, "verifiedBooks": 2, "error": ""}
  ]
}
```

## 9. 故障处理

### 服务器未确认（CONFIRM 暂停）

现象：

```text
[1/12] 服务器未确认 三体1-01，请手动右键打开并关闭本书后 /autobook resume
```

处理：

1. 手持该书右键打开编辑界面。
2. 直接 Esc 关闭（不要修改内容）。
3. `/autobook resume`。

实测中服务器偶发不确认，重试通常在第 2 次成功。若开启 `autoRecover`，模组会先自动长等待并模拟一次打开/关闭书本页面；仍失败才进入此暂停。

### 内容校验失败（VERIFY 暂停）

现象：

```text
[2/12] 内容校验失败: 三体1-02 第 7 页，请移除该书后 /autobook resume
```

日志会记录期望页数、实际页数、首个不一致页以及两边的片段。处理：

1. 打开日志确认差异（例如服务器截断或过滤了内容）。
2. 移除这本有问题的书，或先放到箱子中保留。
3. `/autobook resume`，模组会强制重写当前书。

如果不希望暂停，可关闭校验：`/autobook config verifyContent false`。

### 自动恢复没有成功

- 自动恢复每本书只执行一轮；仍失败会进入 `CONFIRM` 暂停。
- 可加大等待：`/autobook config recoveryWaitTicks 400`（20 秒）。
- 确认服务器没有清理物品、限制写书或玩家处于异常状态。

### 运行中的任务失败

`/autobook list` 会在失败任务后显示原因，例如：

```text
> 2. 西游记 [失败] 3/10 本 - Job not found: .../西游记.json
```

处理：

1. 修复 job 文件或背包/空书问题。
2. `/autobook retry 西游记` 把该任务重新入队，然后 `/autobook start`（FAILED 运行会回到 QUEUING）。
3. 如果希望单个失败就中止整条运行：`/autobook config queueStopOnFailure true`；默认是记录失败后继续下一个任务。
4. 想跳过失败任务：`/autobook remove 西游记`；未开始任务也可直接移除，运行中任务需先 `cancel`。

### 游戏内修改配置

```text
/autobook config
/autobook config confirmWaitTicks 140
```

保存后下次 `plan`/`start`/`resume` 生效；运行中的任务不会即时改变时序。

### 一直提示“等待关闭界面”

关闭当前界面（包括背包、聊天）后模组会自动继续。书本编辑界面若在写入后意外出现，模组会自动关闭它，不需要手动处理。

### 空书一直无法就位

模组会回到“查找空的书与笔”重新整理，默认最多重试 3 次。仍失败会暂停并提示：

```text
无法把空书移到主手，请整理背包后 /autobook resume
```

整理背包、确保空书在快捷栏或主背包（不要只放副手）后执行 `/autobook resume`。

### 疑似重复印书

默认 `skipExistingBooks=true`，背包中“书名+页数”都相同的成书会被跳过。需要重新印一本时：

- 先把旧书移出背包，或
- 设置 `skipExistingBooks=false`（会失去自动去重保护）。

### 主手不是空的书与笔

可能被其他物品替换或空书被消耗。模组会进入错误状态，`/autobook status` 查看原因；处理后重新 `start` 或 `resume`。

### resume 提示没有进度

- 任务名必须与 `start` 时完全一致。
- 书稿或分页参数改变会导致指纹变化。
- 尚未完成任何一本时不会保存可恢复进度。

## 10. 限制

- 支持 Minecraft 1.21.5–1.21.11 与 26.1、26.1.1、26.1.2、26.2，每个版本使用对应 jar；1.21.4 及更早版本缺少当前使用的 Inventory API，暂不支持。
- 内容校验比较的是客户端收到的成书页文本，不做服务端存储层面的逐字节校验。
- 服务器若禁止原版写书/签名，模组无法绕过。
- 书本编辑界面的服务端会话有效期很短，`useItem` 后到发送编辑包的 5 tick 窗口不能随意放大；只能加大发送后的确认等待。
- 跨章节打包会让一本从章节中间开始，这是为了减少空书消耗。
- 自动恢复无法解决服务器端的硬限制或权限问题。

## 11. 构建与安装

一键构建（先跑 Python 与 Java 测试）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

为多个 Minecraft 版本分别构建（发布前默认只构建 1.21.8；其他版本显式指定）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-multi.ps1 -SkipTests
# 例：显式构建 1.21.11 与 26.2
# .\scripts\build-multi.ps1 -SkipTests -Versions @("1.21.11", "26.2")
```

产物：

- `dist/autobook-0.13.0.jar`：由 `build.ps1` 生成，对应 `gradle.properties` 当前版本（1.21.8）。
- `dist/autobook-0.13.0-mc<版本>.jar`：由 `build-multi.ps1` 生成，每个 jar 的 `fabric.mod.json` 精确匹配对应 Minecraft 版本。
- 26.x（26.1、26.1.1、26.1.2、26.2）使用独立的 `autobook-26/` 工程与 Loom 1.19.4（unobfuscated），需要 JDK 25 与 Gradle 9.8.2；1.21.x 仍以 Java 21 为目标。
- `build.ps1 -GameDir` 只安装当前 `gradle.properties` 对应版本（默认 1.21.8）；26.x 请手动复制 `dist/autobook-0.13.0-mc26.x.jar`。

发布构建（版本一致性校验、全部测试、多版本 jar、GUI 打包、验收与组包一次完成）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1
```

产物在 `dist/release/`（含全部 jar、GUI zip、文档、示例 job、校验和），发布流程与验收清单见 [release.md](release.md)。

构建并安装到游戏目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -GameDir "F:\Minecraft\.minecraft\versions\1.21.8-Fabric 0.17.3"
```

脚本会：

- 校验 `fabric.mod.json` 的版本与 jar 文件名一致；
- 移除旧的 `autobook-*.jar`，避免同 ID 模组冲突；
- 创建 `autobook/jobs`、`state`；
- 检查 `mods` 中是否存在 Fabric API；
- 输出已安装路径与任务数量。

# 任务格式（job.json）

AutoBook 读取的任务文件格式版本为 `1`，JSON Schema 见 [job.schema.json](job.schema.json)。

## 结构

```json
{
  "version": 1,
  "titleBase": "三体1",
  "pageLimit": 100,
  "sourceHash": "f2d3e6215795099370c2899551e868c916819232d15f335f9df53d41d73c923c",
  "createdAt": "2026-10-25T09:28:03.229106+00:00",
  "options": {
    "stripFormatting": false,
    "llmApplied": false
  },
  "segments": [
    {
      "index": 1,
      "chapter": "1. 疯狂年代",
      "text": "……正文……"
    }
  ]
}
```

## 字段说明

| 字段 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | integer | 是 | 固定为 `1` | 模组只接受版本 1 |
| `titleBase` | string | 是 | schema 1–24 字符 | 书名基名；加 `-NN` 后必须不超过 32 字符 |
| `pageLimit` | integer | 是 | 1–100 | 每本页数上限；超过则自动续本 |
| `sourceHash` | string | 是 | 64 位小写十六进制 | 原始 txt 的 SHA-256，用于追溯 |
| `createdAt` | string | 否 | ISO 8601 | 生成时间 |
| `options.stripFormatting` | boolean | 否 | — | 预留：是否剥离 `§` 格式码 |
| `options.llmApplied` | boolean | 否 | — | 预留：是否经过 LLM 校订 |
| `options.pageLimit` | integer | 否 | 1–100 | 覆盖模组的每本页数上限 |
| `options.breakAtSentence` | boolean | 否 | — | 覆盖模组的标点断书开关 |
| `options.verifyContent` | boolean | 否 | — | 覆盖模组的内容校验开关 |
| `segments` | array | 是 | 至少 1 项 | 正文分段 |
| `segments[].index` | integer | 是 | ≥ 1 | 段序号，从 1 开始 |
| `segments[].chapter` | string | 否 | — | 来源章节标题，仅用于报告/日志 |
| `segments[].text` | string | 是 | 非空 | 段落正文，可含 `\n` |

## 分段与分页关系

- BookForge 默认把超过 12000 字符的章节切分为多个 segment。
- AutoBook 在游戏内按字体像素宽度重新分页，与 BookForge 的估算页数无关。
- `pageLimit` 控制每个 `PlannedBook` 的页数。所有 segment 的页面会**连续装满**每本，不再按 segment 单独装订；短章节会与后续章节合并到同一本。
- 书名编号是**全局连续**的，跨 segment 不重置：`T-01`、`T-02`……
- 因此一本可能会从章节中间开始或结束，这是为了减少空书消耗。
- 模组的 `config.json` 可用 `pageLimit` 覆盖该值（`0` 表示使用 job.json），并可用 `breakAtSentence` 控制是否优先在句末标点处断书。
- `options` 中的 `pageLimit`、`breakAtSentence`、`verifyContent` 优先级高于 `config.json`；未设置的字段继续使用全局配置。

固定排版参数（与 Minecraft 1.21.8 一致）：

| 参数 | 值 |
| --- | --- |
| 每行最大宽度 | 114 px |
| 每页行数 | 14 |
| 每页最大字符数 | 1023 |
| 每本最大页数 | 100 |
| 书名最大长度 | 32 字符 |

## 生成与校验

```powershell
bookforge prepare input.txt --title 三体1 --out work\三体1 --verify
bookforge prepare input.epub --out work\三体1 --verify   # 可选：直接导入电子书
bookforge validate work\三体1\job.json
bookforge review work\三体1\job.json
```

- 电子书输入会额外生成 `00_imported.txt` 与 `import.json`；`import.json` 记录原始文件哈希、标题、作者与导入警告。
- `review` 需要 `keys/llm_api_key.txt`，按 job 的 `titleBase` 自动选择 `llm_config.json` 中的 profile，生成 `llm_report.json` 或 `llm_patch.json`，不会修改 job。
- `apply-patch` 生成新的 `reviewed/job.json`，并把 `options.llmApplied` 置为 `true`。
- key 为空时只生成跳过报告，不发起请求。

`prepare` 输出：

| 文件 | 说明 |
| --- | --- |
| `job.json` | 模组输入，已通过 schema 校验 |
| `report.json` | 源信息、编码、清洗统计、章节、分段、警告 |
| `01_normalized.txt` | 规范化后的文本 |
| `02_cleaned.txt` | 清洗后的正文 |

退出码：

| 码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | `validate` 校验失败 |
| 2 | 输入/处理错误（编码、空正文、schema 不合法等） |
| 3 | 使用了 `--strict` 且存在警告 |

## 警告类型

`report.json` 的 `warnings[].code`：

| code | 级别 | 含义 |
| --- | --- | --- |
| `no-chapters` | error | 没有识别到正文 |
| `title-too-long` | warning | `titleBase + 序号` 可能超过 32 字符 |
| `segment-over-page-limit` | warning | 估算页数超过 `pageLimit`，需要续本 |
| `high-removal-ratio` | warning | 清洗删除比例超过 20% |
| `large-content-loss` | warning | 非空白字符保留率低于 95% |
| `controls-removed` | info | 移除了控制字符 |
| `formatting-codes` | info | 文本含 `§` 格式码，需实机验证 |

## 实例

仓库内已有：

- `dist/jobs/autobook-test.json`：3 行 ASCII 诊断文本，用于验证服务器连通性。
- `dist/jobs/三体1.json`：35 章、36 段、1195 页、无警告。

三体1 报告摘要：

```json
{
  "chapters": 35,
  "segments": 36,
  "page_limit": 100,
  "max_estimated_pages": 83,
  "warnings": []
}
```

"""BookForge 帮助中心的离线 HTML 内容。

内容内置在代码中，不读取外部文件、不加载任何网络资源，
保证 PyInstaller 打包后的 exe 可离线查看。
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

from .. import __version__
from ..keymanagement import key_status, source_label
from ..llm import (
    BOOKFORGE_ROOT,
    DEFAULT_CONFIG_FILE,
    DEFAULT_GLOSSARY_FILE,
    DEFAULT_KEY_FILE,
)

_CSS = """
body { font-family: "Microsoft YaHei", "Segoe UI", sans-serif; font-size: 13px;
       color: #222; line-height: 1.55; }
h1 { font-size: 20px; color: #1a4a8a; border-bottom: 2px solid #1a4a8a;
     padding-bottom: 4px; }
h2 { font-size: 15px; color: #1a4a8a; margin-top: 18px; margin-bottom: 6px; }
code { font-family: Consolas, monospace; background: #f0f0f0; padding: 1px 4px; }
table { border-collapse: collapse; }
th, td { border: 1px solid #ccc; padding: 3px 8px; text-align: left; }
th { background: #eef3fa; }
ul, ol { margin-top: 4px; margin-bottom: 4px; }
li { margin-bottom: 2px; }
.note { color: #666; }
.warn { color: #a05000; }
"""

_HELP_BODY = r"""
<h1>BookForge 帮助</h1>
<p class="note">本帮助完全离线内置，不访问网络。按下方流程即可完成
“导入电子书 → 生成 job → LLM 核验 → 补丁审阅 → 安装到游戏”。</p>

<h2>1. 快速开始</h2>
<ol>
<li><b>生成</b>：在“生成”页选择书稿文件与输出目录，点击“导入并生成 job”。</li>
<li><b>核验</b>（可选）：在“LLM 核验”页选择 job.json，先用“抽样块数”小样本试跑，
确认质量后再全量。</li>
<li><b>补丁</b>（可选）：核验模式选“补丁”，完成后自动跳转到“补丁审阅”页；
勾选要应用的条目（默认只勾选 high 置信度），点击“应用选中补丁”，
得到 <code>reviewed/job.json</code> 与 <code>diff.patch</code>。</li>
<li><b>安装</b>：在“配置”页底部选择 job.json 与游戏目录，点击“安装到 autobook/jobs”。</li>
<li><b>游戏内</b>：执行 <code>/autobook add &lt;任务名&gt;</code>，然后
<code>/autobook start</code> 开始印刷。</li>
</ol>

<h2>2. 支持的输入格式</h2>
<table>
<tr><th>格式</th><th>处理方式</th></tr>
<tr><td>.txt / .md</td><td>直接读取，自动识别编码（UTF-8/BOM/UTF-16/GB18030）</td></tr>
<tr><td>.epub</td><td>原生解析，按阅读顺序提取正文，跳过目录页</td></tr>
<tr><td>.fb2</td><td>原生解析 XML</td></tr>
<tr><td>.docx</td><td>原生解析 word/document.xml</td></tr>
<tr><td>.azw3 / .mobi / .azw / .kf8 / .prc</td>
<td>优先调用 Calibre 转换；未安装时使用内置 Python 解析</td></tr>
</table>
<ul>
<li class="warn">仅支持无 DRM 的文件；加密或受 DRM 保护的内容会直接报错，本工具不移除 DRM。</li>
<li>电子书导入会在输出目录生成 <code>00_imported.txt</code>（提取的正文）与
<code>import.json</code>（原始格式、SHA-256、标题、作者、警告）。</li>
</ul>

<h2>3. LLM 核验流程</h2>
<ul>
<li><b>report（问题报告）</b>：只列出疑似错字/漏字/多字/乱码/标点问题，不改动正文。</li>
<li><b>patch（补丁）</b>：生成 <code>find/replace</code> 补丁文件，本身不改动正文；
由“补丁审阅”页或 CLI <code>apply-patch</code> 做本地硬校验后才生成新 job。</li>
<li>建议流程：先抽样 2–5 块人工确认误报率，再全量运行；费用可先用 CLI
<code>bookforge review --estimate</code> 预估。</li>
<li>每本书可以有独立 profile（按书名自动匹配），可配置 model、base_url、
max_chars、术语表（glossary）与风格说明（style）。</li>
<li>默认关闭 thinking（推理模式），避免输出预算被推理耗尽。</li>
</ul>

<h2>4. 补丁安全规则</h2>
<ul>
<li><code>find</code> 必须在目标块中逐字存在且唯一，<code>chunkHash</code> 必须与当前
job 一致，否则拒绝。</li>
<li>默认只应用 high 置信度；可在 profile 中调整 <code>min_confidence</code>。</li>
<li>按类型限制长度变化：typo ≤2 字符、missing/extra ≤30、garbled ≤40、
punctuation ≤10；可在 profile 的 <code>max_delta</code> 中调整。</li>
<li><code>ad</code> 类型（广告/推广语）不自动应用，需要人工处理。</li>
<li>重叠补丁会被拒绝；应用后输出 <code>diff.patch</code> 供逐条审阅，
被拒绝的条目附带原因。</li>
</ul>

<h2>5. 密钥配置</h2>
<ul>
<li>三种方式（任选其一）：
<ol>
<li>“配置”页的 API key 区：输入 → “保存密钥”，可“清除密钥”“测试连接”。</li>
<li>CLI：<code>bookforge key set / status / test / clear</code>。</li>
<li>手动编辑 <code>keys/llm_api_key.txt</code>。</li>
</ol></li>
<li>优先级：环境变量 <code>BOOKFORGE_LLM_KEY_FILE</code> &gt; profile 的 key_file
&gt; 全局 key_file &gt; 默认文件。</li>
<li>界面只显示掩码（如 <code>sk-1…wxyz</code>）；密钥不会写入日志、报告或 git。</li>
<li>未配置 key 时核验会跳过并生成“跳过报告”，不会发出网络请求。</li>
<li>打包版（exe）的密钥目录在 <code>BookForge\_internal\keys</code>。</li>
</ul>

<h2>6. 安装到游戏</h2>
<ul>
<li>安装把 job 复制到 <code>游戏目录\autobook\jobs\&lt;书名&gt;.json</code>。</li>
<li>“游戏目录”指包含 <code>mods/</code> 与 <code>config/</code> 的 Minecraft
目录（或版本隔离目录）。</li>
<li>需要客户端安装 AutoBook 模组与对应版本的 Fabric Loader / Fabric API；
服务器不需要安装。</li>
<li>游戏内常用命令：<code>/autobook add &lt;任务名&gt;</code>、
<code>/autobook start</code>、<code>/autobook pause</code>、
<code>/autobook resume</code>、<code>/autobook cancel</code>、
<code>/autobook list</code>、<code>/autobook help</code>。</li>
<li>印刷需要背包中有“书与笔”；耗尽会自动暂停，补给后自动继续。</li>
</ul>

<h2>7. 常见错误</h2>
<table>
<tr><th>现象</th><th>处理</th></tr>
<tr><td>连接超时 / 无法连接</td>
<td>检查 base_url 是否可达；api.openai.com 在国内通常不可直连，可改用
api.deepseek.com 并同步修改 model。</td></tr>
<tr><td>content 为空 / reasoning 用尽</td>
<td>关闭 thinking，或把 max_tokens 提高到 16384 并减小 max_chars。</td></tr>
<tr><td>blocked（审核拦截）</td>
<td>该块被服务商审核拦截，报告会记录并继续其他块；可调整文本或更换模型。</td></tr>
<tr><td>DRM / 加密 EPUB 报错</td>
<td>仅支持无 DRM 文件，请使用无 DRM 的来源。</td></tr>
<tr><td>job 无效 / titleBase 超长</td>
<td>书名基名不能超过 24 个字符。</td></tr>
<tr><td>游戏内 VERIFY / CONFIRM 暂停</td>
<td>成书内容与计划不一致或多次写入失败；人工检查后
<code>/autobook resume</code> 会重写当前书。</td></tr>
<tr><td>找不到空书</td>
<td>在快捷栏/背包放入“书与笔”，等待每 20 tick 一次的补给检测。</td></tr>
</table>

<h2>8. 版本与路径信息</h2>
{{PATH_INFO}}

<h2>9. 游戏联动</h2>
<ul>
<li>安装 job 时会同时写入 <code>autobook/jobs/&lt;书名&gt;.meta.json</code>，
记录书数、页数、是否已校订与生成器版本；同名覆盖会保留
<code>&lt;书名&gt;.json.bak</code>。</li>
<li>AutoBook 0.12.0 起会原子写入 <code>autobook/status.json</code>；
“配置”页的“游戏联动（只读）”区点击“刷新联动状态”即可查看运行进度、
校验本数与更新时间，并显示 mods/ 中的 AutoBook jar 版本。</li>
<li>游戏内用 <code>/autobook jobs</code> 查看已安装任务及元数据；缺少元数据的
旧 job 仍可正常运行，只是书数/页数显示为未知。</li>
<li>若提示 jar 版本过低、当前任务文件缺失或 job version 不兼容，请换用
BookForge 安装的 v1 job，并确认 AutoBook 版本不低于 0.12.0。</li>
</ul>
"""


def _path_row(label: str, value: object, extra: str = "") -> str:
    text = html.escape(str(value))
    suffix = f"（{html.escape(extra)}）" if extra else ""
    return f"<tr><td>{html.escape(label)}</td><td><code>{text}</code>{suffix}</td></tr>"


def build_path_info(game_dir: str = "") -> str:
    """生成“版本与路径信息”表格 HTML（动态内容）。"""
    rows = [
        _path_row("BookForge 版本", f"v{__version__}"),
        _path_row("Python", sys.version.split()[0]),
        _path_row("配置/密钥目录", BOOKFORGE_ROOT / "keys"),
        _path_row("服务配置", DEFAULT_CONFIG_FILE,
                  "存在" if DEFAULT_CONFIG_FILE.is_file() else "缺失"),
    ]
    try:
        status = key_status()
        key_extra = (
            f"已配置 {status.masked}（{source_label(status)}）"
            if status.configured
            else f"未配置（{source_label(status)}）"
        )
    except Exception:
        key_extra = "状态未知"
    rows.append(_path_row("API key 文件", DEFAULT_KEY_FILE, key_extra))
    rows.append(
        _path_row("全局术语表", DEFAULT_GLOSSARY_FILE,
                  "存在" if DEFAULT_GLOSSARY_FILE.is_file() else "缺失")
    )
    rows.append(
        _path_row(
            "游戏目录",
            game_dir.strip() or "未设置（在“配置”页选择游戏目录）",
        )
    )
    rows.append(
        _path_row("运行环境", "exe 打包" if getattr(sys, "frozen", False) else "源码")
    )
    return "<table>" + "".join(rows) + "</table>"


def build_help_html(game_dir: str = "") -> str:
    """完整帮助页 HTML；game_dir 用于“版本与路径信息”动态显示。"""
    body = _HELP_BODY.replace("{{PATH_INFO}}", build_path_info(game_dir))
    return f"<html><head><style>{_CSS}</style></head><body>{body}</body></html>"


__all__ = ["build_help_html", "build_path_info"]

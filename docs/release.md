# 发布流程

MCBookWriter 由两个组件组成，版本号独立：**AutoBook**（Fabric 模组）与 **BookForge**（Python 工具链）。一次发布同时携带两者当前版本。

## 1. 一键发布构建

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1
```

脚本依次执行：

1. **版本一致性校验**：`gradle.properties`（两个工程）、`__init__.py`、`pyproject.toml`、`README.md`、`CHANGELOG.md` 中的版本号必须一致，任一不符即中止。
2. **测试**：BookForge pytest、AutoBook JUnit（1.21.8 与 26.1.2 各一次）。
3. **构建**：`build-multi.ps1` 生成 1.21.5/1.21.6/1.21.7/1.21.8/1.21.11/26.1/26.1.1/26.1.2/26.2 九个 jar；`build-gui.ps1` 生成 PyInstaller GUI。
4. **产物验收**：每个 jar 的 `fabric.mod.json` 版本与 Minecraft 依赖精确匹配目标版本，且包含帮助类 `HelpText`。
5. **密钥验收**：GUI 打包不得包含非空 `llm_api_key.txt`；若源码 key 文件非空，扫描整个发布包确认无该明文。
6. **组包**：`dist/release/MCBookWriter-<AutoBook版本>/`，含全部 jar、`BookForge-<版本>-windows.zip`、`README.md`、`CHANGELOG.md`、`INSTALL.txt`、`RELEASE_NOTES.md`、`docs/`、`examples/sample_job.json`。
7. **安装验收**：用 BookForge CLI 对发布包内示例 job 执行 schema 校验。
8. **校验和**：生成 `checksums-sha256.txt`，并打包 `MCBookWriter-<版本>.zip`。

可选参数：`-SkipTests`（跳过测试）、`-SkipGui`（不打 GUI）、`-Versions`（自定义 Minecraft 版本列表）。

## 2. GitHub Release

1. 打标签：`git tag autobook-<版本>`（如 `autobook-0.11.0`），推送标签。
2. 新建 Release，标题 `MCBookWriter AutoBook <版本> / BookForge <版本>`。
3. 正文使用发布包中的 `RELEASE_NOTES.md`。
4. 上传资产：
   - `autobook-<版本>-mc*.jar`（9 个）
   - `BookForge-<版本>-windows.zip`
   - `checksums-sha256.txt`
   - 可选：`MCBookWriter-<版本>.zip` 整包
5. 发布后核对：下载任一 jar，与 `checksums-sha256.txt` 比对 SHA-256。

## 3. Modrinth

AutoBook 按 Minecraft 版本分别上传（Modrinth 单版本对应单文件）：

| 字段 | 值 |
| --- | --- |
| Project type | Mod |
| Loaders | Fabric |
| Versions | 每个 jar 选择对应 Minecraft 版本（1.21.5–1.21.11、26.1–26.2） |
| Environment | Client |
| Dependencies | Fabric API（required） |
| Version number | 与 jar 内 `fabric.mod.json` 一致 |
| Changelog | 对应版本的 CHANGELOG 段落 |

BookForge 是独立桌面工具，不上 Modrinth，只随 GitHub Release 分发。

## 4. 发布验收清单

### 4.1 构建与包内容（自动化，release.ps1 已覆盖）

- [ ] 版本一致性校验通过（`gradle.properties`×2、`__init__.py`、`pyproject.toml`、README、CHANGELOG）。
- [ ] pytest 全绿；JUnit 在 1.21.8 与 26.1.2 各跑一次全绿。
- [ ] 每个 jar 的 `fabric.mod.json` 版本与 `depends.minecraft` 精确匹配文件名，且包含 `HelpText.class`。
- [ ] GUI 打包 `_internal/keys` 中 `llm_api_key.txt` 不存在或为空。
- [ ] 发布包全文扫描（默认 key + `llm_config.json` 中所有 `key_file`）无明文 key。
- [ ] `examples/sample_job.json` 通过 `bookforge validate`，且不少于 4 段（防止样例退化为空壳）。
- [ ] `checksums-sha256.txt` 与每个文件实际 SHA-256 一致。

### 4.2 真实客户端试跑（人工，至少 1.21.8、1.21.11、26.1.2、26.2 各一次）

样例已固定为 `titleBase=样例`、`pageLimit=5`、4 章 4 段、共约 1800 字、估算 14 页，预期 **3 本**（断句回退可能使某本少 1 页）。

准备：3 本以上空书、一份书与笔、`examples/sample_job.json` 重命名为 `样例.json` 放入 `autobook/jobs/`。

- [ ] 放入 jar 后启动，`autobook/` 自动创建；`/autobook help` 可打开说明页并翻页返回。
- [ ] `/autobook plan 样例` 显示章节、段落与估算页数，不改变运行状态。
- [ ] `/autobook start 样例` 连续写出约 3 本，书名依次为 `样例-01`、`样例-02`、`样例-03`。
- [ ] 每本书末页结束在句末标点（检查对话与省略号段落，不在句中硬截断）。
- [ ] 日志出现 `verified '样例-0N'`，无 `VERIFY` / `CONFIRM` 暂停。
- [ ] `/autobook status` 的页数与校验计数与已写本数一致；动作栏显示 `[当前/总数]`。
- [ ] 中途 `/autobook pause` 后 `/autobook resume` 能从下一本继续，不重复已签名书。
- [ ] 游戏内“说明”页与 `/autobook help` 的文案、版本号正常显示（GUI 缩放非 100% 时也检查一次）。

### 4.3 分发

- [ ] GitHub Release 资产齐全：9 个 jar、`BookForge-<版本>-windows.zip`、`checksums-sha256.txt`，正文为 `RELEASE_NOTES.md`。
- [ ] Modrinth 每个 Minecraft 版本单独上传，Loader=Fabric、Environment=Client、依赖 Fabric API。
- [ ] 下载任一 jar 与校验和比对一致。

## 5. 已知风险与限制

| 风险 | 影响 | 现状与对策 |
| --- | --- | --- |
| 样例只做了离线校验，未在真实客户端跑过 | 样例预估值可能与实际页数有偏差 | 清单 4.2 必须在两种客户端各跑一次；若本数不同，同步更新 `INSTALL.txt` 与本节预期 |
| 样例 `pageLimit=5` 需要 3 本以上空书 | 空书不足会 `SUPPLY` 暂停 | 属预期行为；准备充足空书，或换 `--page-limit` 更大的 job |
| 修改 `pageLimit` / 断句开关会改变 `planHash` | 旧进度无法续写 | 发布说明与 usage 已注明；样例调整后必须删 `autobook/state/` 下旧进度 |
| 密钥扫描只覆盖默认 key 与配置里的 `key_file` | 若 key 只存在于环境变量 `BOOKFORGE_LLM_KEY_FILE`，扫描无法比对 | 环境变量形式不会进入发布包；打包只带空模板，风险可控 |
| GUI 密钥检查依赖 one-folder 结构（`_internal/keys`） | 若改成 one-file 打包，检查路径失效 | 当前 `BookForge.spec` 固定 one-folder；改打包方式时必须同步改 release.ps1 |
| `-Versions` 自定义后 `INSTALL.txt` 版本列表随之变化 | 与 README 中“支持版本”表述可能不一致 | INSTALL 已按实际构建列表生成；README 仍描述完整支持范围，属文档口径差异 |
| README 版本校验取首次匹配 | README 若把历史版本写在更前面会误判 | 保持“当前版本：**AutoBook x / BookForge y**”为首个版本号出现位置 |
| GitHub / Modrinth 发布仍需人工操作 | 脚本无法代发 | 按第 2、3 节执行；发布前先跑完整 release.ps1 |
| 26.2 将界面状态从 `Minecraft` 移到 `Gui`，模组用反射兼容 | 若后续版本再改方法名，`ScreenCompat` 会抛“当前 Minecraft 版本不支持界面切换” | 已在 26.2 编译通过；26.2 真机试跑时重点验证 `/autobook ui` 与帮助页返回；异常时先看日志 |
| 1.21.11 使用新版 authlib（`GameProfile` 为 record） | 旧写法 `getName()` 已编译失败，已改为 `Player.getName()` | 已编译通过；1.21.11 真机试跑需确认动作栏文字与玩家名相关提示正常 |
| 新增 1.21.11 / 26.1 / 26.1.1 / 26.2 目前只完成编译与打包 | 未做真机写书验证 | 按 4.2 清单补跑；未验证版本先在发布说明中标注“需客户端验证” |

# 书赫日报助手

参考「小黑日报助手」做出的自用版，核心闭环是：**定时截屏 → 前台应用/窗口识别 → 本地 AI 识别在干嘛 → 存本地库 → 面板查看 → 一键生成日报/周报/月报**。

- ✅ **可本地**：默认可走本地 [Ollama](https://ollama.com)，也支持 OpenAI-compatible `/v1` 网关（例如 Hermes），数据落在 `~/.xiaohei-riji`
- ✅ **跨平台**：Mac / Windows（`mss` 截图 + `sqlite3`），支持主显示器、指定显示器或全部显示器采集，并在面板里查看已连接显示器
- ✅ **省算力**：支持启动后自动后台记录；画面没明显变化就跳过识别，闲置自动暂停
- ✅ **隐私控制**：有独立「隐私保护」面板；默认隐私模式下截图分析后即删，只保留文字记录；也可手动关闭隐私模式后设置截图留存、保留天数、采集间隔、闲置暂停、活动分类、排除应用、敏感关键词，并清理已保存截图
- ✅ **权限引导**：面板内检测 macOS 屏幕录制/辅助功能权限，并可跳转系统设置
- ✅ **可回溯**：支持历史日期、分类分布、应用记录、应用用时、时段热力图、小时分布、月历热力、效率洞察、近 30 天趋势、时间线详情、活动补记/修正/删除、关键词搜索和结构化导出
- ✅ **报告更准**：日报/周报/月报生成时会带上分类分布、应用用时估算、连续工作段落、今日备注/明日计划、自定义报告模板/临时要求和原始时间线
- ✅ **可追问**：可围绕当天、近 7 天或近 30 天本地记录继续问 AI，聊天历史同样只保存在本地 SQLite
- ✅ **易恢复**：有独立「历史报告」入口；支持本地 zip 备份，报告可编辑、保存、复制、导出 Markdown、单份/批量归档和删除
- ✅ **项目上下文**：可在「接入 Agent」里显式配置项目目录，追问日报助手会读取少量安全文本文件，与本地活动记录一起回答问题
- ✅ **自动日报**：可设置每天固定时间自动生成并归档日报，也可在设置页立即生成一次，并显示计划时间、上次生成日期和运行状态
- ✅ **可诊断**：有独立「接入 Agent」入口；可保存本地模型网关配置，并一键测试连通性，确认目标模型是否可见；记录器异常会在侧栏和健康卡里直接标红
- ✅ **有帮助**：有独立「帮助」入口，集中展示快速开始、工作原理、隐私边界、当前状态、权限设置、模型测试、数据目录和日志目录
- ✅ **桌面可用**：可打包成原生 macOS 窗口 `.app`，面板内可直接打开已安装应用；也支持菜单栏常驻、开始/暂停记录、立即记录当前屏幕、打开报告/数据目录
- ✅ **小窗可用**：面板支持窄窗口响应式布局，概览、搜索、补记和时间线会自动改单列

## 安装

```bash
pip install -r requirements.txt
```

装并启动 Ollama，拉好两个模型（一个看图、一个写字）：

```bash
ollama pull qwen2.5vl:7b   # 视觉模型：识别截图
ollama pull qwen2.5:7b     # 文本模型：写报告
```

> 想换模型：设环境变量 `RIJI_VISION_MODEL` / `RIJI_TEXT_MODEL` 即可。

如果要走 Hermes / OpenAI-compatible 网关：

```bash
export RIJI_LLM_PROVIDER=openai
export RIJI_OPENAI_BASE_URL=http://localhost:55021/v1
export RIJI_OPENAI_MODEL=gpt-5.5
export RIJI_OPENAI_API_KEY=你的本地网关 key

python -m riji watch
```

Finder 双击 `.app` 或菜单栏常驻不会继承终端环境变量。可以把本地网关配置写入用户目录：

```bash
python -m riji write-env \
  --base-url http://localhost:55021/v1 \
  --model gpt-5.5 \
  --api-key 你的本地网关key \
  --force
```

在 macOS 上，`--api-key` 会写入系统钥匙串，`env.sh` 只保存网关地址、模型名等非敏感配置；非 macOS 环境可按 `env.sh` 注释手动填写 `RIJI_OPENAI_API_KEY`。

## 用法

```bash
# 1) 后台开始记录（截图 + 识别，Ctrl+C 停）
python -m riji watch

# 2) 打开本地可视化面板
python -m riji panel

# 2.1) macOS 原生桌面窗口
python -m riji desktop

# 2.2) macOS 菜单栏常驻（托盘体验）
python -m riji menubar

# 2.3) macOS 开机自启
python -m riji autostart install
python -m riji autostart status
python -m riji autostart uninstall

# 2.4) 生成可双击打开的 macOS .app（默认原生桌面窗口）
python -m riji write-env
python -m riji package-app --write-env
python -m riji package-app --portable  # 生成可拷贝到其他 Mac 的独立版
python -m riji package-dmg             # 生成 macOS DMG
python -m riji package-windows         # 生成 Windows 便携 zip 包

# 2.5) 安装到应用目录（默认 ~/Applications，不需要管理员权限）
python -m riji install-app --write-env
python -m riji install-app --portable  # 安装独立版
python -m riji install-app --target /Applications  # 如需系统级 Applications
# 安装后可在设置页确认“书赫日报助手.app”、Bundle ID 和桌面窗口状态

# 3) 看今天干了啥的分布
python -m riji stats

# 4) 生成报告
python -m riji report day              # 今天的日报
python -m riji report day --style okr  # 换 OKR 风格
python -m riji report week             # 最近 7 天周报
python -m riji report month            # 最近 30 天月报
```

## Windows 快速启动

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
$env:RIJI_LLM_PROVIDER = "openai"
$env:RIJI_OPENAI_BASE_URL = "http://localhost:55021/v1"
$env:RIJI_OPENAI_MODEL = "gpt-5.5"
$env:RIJI_OPENAI_API_KEY = "你的本地网关 key"
.venv\Scripts\python -m riji desktop
```

Windows 上 `desktop` 会启动本地面板并打开浏览器；截图采集使用 `mss`，前台窗口标题通过 Win32 API 获取。开机自启会写入当前用户的 Startup 文件夹。

也可以在 macOS 或 Windows 上生成便携包：

```bash
python -m riji package-windows --output dist
```

生成的 `shuhe-riji-windows-portable.zip` 解压后包含 `configure-model.cmd` 和 `start-shuhe-riji.cmd`。首次启动会在包内创建 `.venv` 并安装依赖。

双击 `.app` 默认打开独立桌面窗口；如果想生成菜单栏常驻版本，可加 `--mode menubar`。菜单栏里可以直接「开始/暂停记录」「立即记录当前屏幕」「打开报告目录」「打开数据目录」。

`--portable` 会把 `riji` 源码和当前 Python 依赖复制进 `.app/Contents/Resources`，适合拷贝到另一台同架构 macOS 电脑上试用。另一台电脑仍需要首次授权屏幕录制/辅助功能，并配置自己的模型网关和 API Key；如果要面向多人正式分发，还需要继续做签名、公证和 DMG/PKG 安装包。

风格可选：`标准` / `简洁` / `技术` / `okr` / `复盘` / `管理汇报`。面板里还可以添加自定义报告模板，格式为每行 `模板名=报告要求`；也可以填写临时报告要求，例如写给老板、突出风险、明日计划更具体等。
报告区的「追问日报助手」可以基于当天、近 7 天或近 30 天活动记录继续问问题，例如“今天主要产出是什么”“日报里该突出哪些风险”。聊天记录只写入本地 SQLite。

## 配置（环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| `RIJI_HOME` | `~/.xiaohei-riji` | 数据目录 |
| `RIJI_INTERVAL` | `120` | 截图间隔（秒） |
| `RIJI_CHANGE_THRESHOLD` | `0.04` | 画面变化阈值，低于则跳过识别 |
| `RIJI_IDLE_PAUSE` | `600` | 连续无变化判定为闲置（秒） |
| 面板设置：隐私模式 | 开启 | 开启后截图只用于当次 AI 分析，不留存原图，并自动清理历史截图 |
| `RIJI_KEEP_SHOTS` | `0` | 是否保留截图原图；隐私模式开启时会强制关闭留存 |
| 面板设置：截图保留天数 | `7` | 开启截图留存时自动清理超过该天数的截图，设 `0` 表示不自动清理 |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama 地址 |
| `RIJI_LLM_PROVIDER` | 自动 | `ollama` 或 `openai`；设置了 OpenAI base URL 时默认 `openai` |
| `RIJI_OPENAI_BASE_URL` / `OPENAI_BASE_URL` | 空 | OpenAI-compatible 地址，例如 `http://localhost:55021/v1` |
| `RIJI_OPENAI_API_KEY` / `OPENAI_API_KEY` | 空 | OpenAI-compatible 鉴权 key；macOS 可保存到系统钥匙串 |
| `RIJI_OPENAI_MODEL` | `gpt-5.5` | OpenAI-compatible 默认模型 |

面板里的运行时设置会保存到 `~/.xiaohei-riji/settings.json`，优先用于 Web 面板和 `watch` 采集循环。
启动后自动记录、活动分类和工作分类也保存在面板设置里：启动后自动记录用于让桌面窗口或菜单栏助手启动时直接进入后台记录状态；活动分类用于截图识别、搜索筛选、手动补记和记录修正；工作分类用于专注分、工作/休息筛选、小时分布和趋势工作占比。
自定义报告模板也会保存在面板设置里，并出现在手动生成报告和自动日报的模板下拉框中。
模型网关地址、模型名会保存到 `~/.xiaohei-riji/env.sh`，保存后当前面板会立即使用新地址和模型；macOS 上 API key 会优先保存到系统钥匙串，不会在面板回显，也不会明文写入 env.sh。

Finder 双击 `.app` 或开机自启时不会继承终端里的环境变量。先运行 `python -m riji write-env`，
必要时带上 `--api-key` 和 `--force`；macOS 会把 key 放到系统钥匙串，启动器会自动读取。

## 平台注意

- **macOS**：首次运行要在「系统设置 → 隐私与安全性 → 屏幕录制」里授权运行的终端。
  如果要读取前台应用和窗口标题，也需要在「辅助功能」里授权。
- **Windows**：一般免授权直接可用。

## 模块结构

| 文件 | 职责 |
|---|---|
| `capture.py` | 截图、压缩、帧间变化检测 |
| `window.py` | 抓取前台应用和窗口标题（macOS 需要辅助功能权限） |
| `settings.py` | 本地运行时设置 |
| `recognize.py` | 调本地视觉模型识别截图 → `{分类, 描述, 应用}` |
| `db.py` | SQLite 存储 |
| `report.py` | 汇总活动 + 调本地文本模型生成报告 |
| `daemon.py` | 后台采集循环 |
| `web.py` | 本地 Web 面板 + API + 后台记录线程 |
| `desktop.py` | macOS 原生 WebView 桌面窗口 |
| `menubar.py` | macOS 菜单栏常驻入口 |
| `autostart.py` | macOS LaunchAgent 开机自启管理 |
| `packager.py` | 生成轻量 macOS `.app` 包 |
| `cli.py` | 命令行入口 |

## 后续可加（继续对齐完整桌面助手体验）

- [x] 原生 macOS GUI 壳 + 可视化时间轴
- [x] 前台窗口标题抓取（让 `app` 字段更准，可少调几次视觉模型）
- [x] 主显示器 / 全部显示器采集范围切换
- [x] 开机自启 / 托盘常驻
- [x] 菜单栏快捷立即记录和打开本地目录
- [x] 报告一键导出 Markdown / 复制
- [x] 历史报告一键批量归档 Markdown
- [x] 自动日报定时生成和归档
- [x] 启动后自动进入后台记录
- [x] 历史记录搜索 / 手动补记 / 自定义活动分类 / 自定义工作分类 / 应用用时统计 / 小时分布 / 结构化导出 / 本地备份 / 截图保留天数
- [x] 面板窄窗口响应式布局
- [x] 报告素材加入应用用时和连续工作段落
- [x] 模型网关连通性测试
- [x] 面板内保存模型网关地址、模型名和本地 key
- [x] 报告预览编辑和保存
- [x] 每日备注 / 明日计划接入报告素材
- [x] 近 30 天趋势、月历热力和工作占比概览
- [x] 复盘/管理汇报模板和临时报告要求
- [x] 今日效率洞察、专注分和最长连续工作段
- [x] 基于本地活动记录的 AI 追问和本地聊天历史

# 安装书赫日报助手

下载页：

https://github.com/cuishuhe5-glitch/shuhe-riji/releases/tag/v0.1.0

## macOS

1. 下载 `shuhe-riji-macos-app.zip`。
2. 解压后得到 `书赫日报助手.app`。
3. 拖到 `Applications` 或 `~/Applications`。
4. 首次启动后，在系统设置里授权屏幕录制和辅助功能。
5. 打开设置页，确认模型网关和 API Key。

## Windows

1. 下载 `shuhe-riji-windows-portable.zip`。
2. 解压到一个固定目录。
3. 安装 Python 3.11 或更高版本，并勾选 Add python.exe to PATH。
4. 双击 `configure-model.cmd`，填写模型网关和 API Key。
5. 双击 `start-shuhe-riji.cmd` 启动。
6. 浏览器打开 `http://127.0.0.1:8765/` 后即可使用。

## 校验下载文件

下载 `SHA256SUMS` 后，可核对文件完整性。

macOS / Linux:

```bash
shasum -a 256 -c SHA256SUMS
```

Windows PowerShell:

```powershell
Get-FileHash .\shuhe-riji-windows-portable.zip -Algorithm SHA256
```

## 默认数据位置

- macOS: `~/.xiaohei-riji`
- Windows: `%USERPROFILE%\.xiaohei-riji`

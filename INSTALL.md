# 安装书赫日报助手

下载页：

https://github.com/cuishuhe5-glitch/shuhe-riji/releases/tag/v0.1.3

## macOS

1. 优先下载 `shuhe-riji-macos.dmg`。
2. 打开 DMG 后，把 `书赫日报助手.app` 拖到 `Applications` 或 `~/Applications`。
3. 如果下载的是 `shuhe-riji-macos-app.zip`，先解压再拖动 `.app`。
4. 首次启动后，在系统设置里授权屏幕录制和辅助功能。
5. 打开设置页，确认模型网关和 API Key。另一台电脑需要单独配置，不能沿用这台 Mac 的钥匙串。

## Windows

1. 如果 Release 里有 `shuhe-riji-windows-exe.zip`，优先下载它，解压后运行 `书赫日报助手.exe`。
2. 如果使用 `shuhe-riji-windows-portable.zip`，解压到一个固定目录。
3. 便携版需要安装 Python 3.11 或更高版本，并勾选 Add python.exe to PATH。
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

- macOS: `~/.shuhe-riji`
- Windows: `%USERPROFILE%\.shuhe-riji`

# 书赫日报助手发布说明

## 产物

- macOS: `书赫日报助手.app`
- Windows: `shuhe-riji-windows-portable.zip`

一键生成本地发布产物：

```bash
python scripts/release_local.py
```

输出：

- `dist/shuhe-riji-macos-app.zip`
- `dist/shuhe-riji-windows-portable.zip`

## macOS 独立版

```bash
python -m riji package-app --output dist --mode desktop --portable
```

生成后把 `dist/书赫日报助手.app` 发给同架构 macOS 用户。首次运行仍需要用户授权：

- 屏幕录制
- 辅助功能
- 模型网关和 API Key

正式公开分发前还需要签名、公证和 DMG/PKG。

## Windows 便携版

```bash
python -m riji package-windows --output dist
```

生成 `dist/shuhe-riji-windows-portable.zip`。用户解压后：

1. 安装 Python 3.11+，并勾选 Add python.exe to PATH。
2. 双击 `configure-model.cmd` 填写模型网关配置。
3. 双击 `start-shuhe-riji.cmd` 启动。
4. 打开 `http://127.0.0.1:8765/` 使用面板。

Windows 便携版首次启动会在解压目录下创建 `.venv` 并安装依赖。

## GitHub Release

当前 GitHub token 没有 `workflow` scope，因此 CI 文件暂存于 `docs/github-actions-ci.yml`。如果要启用 GitHub Actions：

```bash
mkdir -p .github/workflows
cp docs/github-actions-ci.yml .github/workflows/ci.yml
git add .github/workflows/ci.yml
git commit -m "Enable GitHub Actions CI"
git push
```

发布 Release 时上传：

- `dist/书赫日报助手.app` 压缩后的 zip 或 DMG
- `dist/shuhe-riji-windows-portable.zip`

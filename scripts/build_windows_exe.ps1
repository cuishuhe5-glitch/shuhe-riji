param(
  [string]$Output = "dist"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Dist = Join-Path $Root $Output
$Work = Join-Path $Dist "pyinstaller-work"
$Entry = Join-Path $Dist "windows_entry.py"
$ExeDist = Join-Path $Dist "windows-exe"

New-Item -ItemType Directory -Force -Path $Dist | Out-Null

@"
from riji import web

if __name__ == "__main__":
    web.run(host="127.0.0.1", port=8765, open_browser=True)
"@ | Set-Content -Encoding UTF8 -Path $Entry

python -m pip install --upgrade pip
python -m pip install -r (Join-Path $Root "requirements.txt")
python -m pip install -r (Join-Path $Root "requirements-build.txt")

python -m PyInstaller `
  --name "书赫日报助手" `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --distpath $ExeDist `
  --workpath $Work `
  --add-data "$($Root)\riji\static;riji\static" `
  --hidden-import "riji.__main__" `
  $Entry

Compress-Archive -Path (Join-Path $ExeDist "书赫日报助手") -DestinationPath (Join-Path $Dist "shuhe-riji-windows-exe.zip") -Force
Write-Host "Windows EXE package:" (Join-Path $Dist "shuhe-riji-windows-exe.zip")

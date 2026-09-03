param(
    [switch]$InstallBuildDependencies,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = if ($PythonPath) {
    $PythonPath
} else {
    Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}
$DistRoot = Join-Path $ProjectRoot "out\exe\dist"
$WorkRoot = Join-Path $ProjectRoot "out\exe\build"
$PortableDir = Join-Path $DistRoot "Format Agent Workbench"
$Archive = Join-Path $ProjectRoot "out\format-agent-workbench-windows-portable.zip"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "未找到 Python：$Python。请先建立项目虚拟环境，或使用 -PythonPath 指定解释器。"
}

if ($InstallBuildDependencies) {
    & $Python -m pip install -r (Join-Path $ProjectRoot "requirements-build.txt")
    if ($LASTEXITCODE -ne 0) { throw "安装打包依赖失败。" }
}

Push-Location $ProjectRoot
try {
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $DistRoot `
        --workpath $WorkRoot `
        (Join-Path $ProjectRoot "packaging\format-agent-workbench.spec")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败。" }
} finally {
    Pop-Location
}

foreach ($Name in @("README.md", "LICENSE", "PRIVACY.md", "SECURITY.md", "VERSION")) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Name) -Destination $PortableDir -Force
}
Copy-Item -LiteralPath (Join-Path $ProjectRoot "packaging\开始使用.txt") -Destination $PortableDir -Force

if (Test-Path -LiteralPath $Archive -PathType Leaf) {
    Remove-Item -LiteralPath $Archive -Force
}
Compress-Archive -LiteralPath $PortableDir -DestinationPath $Archive -CompressionLevel Optimal

$Bytes = (Get-Item -LiteralPath $Archive).Length
$Megabytes = [Math]::Round($Bytes / 1MB, 1)
Write-Host "构建完成 / Build complete: $Archive ($Megabytes MB)"
Get-FileHash -LiteralPath $Archive -Algorithm SHA256 | Format-List

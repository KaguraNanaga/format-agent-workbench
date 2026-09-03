$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPath = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

function Get-PythonLauncher {
    if (Get-Command "py.exe" -ErrorAction SilentlyContinue) {
        return @{ Command = "py.exe"; Prefix = @("-3") }
    }
    if (Get-Command "python.exe" -ErrorAction SilentlyContinue) {
        return @{ Command = "python.exe"; Prefix = @() }
    }
    throw "Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/windows/ and enable 'Add Python to PATH'."
}

Set-Location $ProjectRoot

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $Launcher = Get-PythonLauncher
    $VersionText = & $Launcher.Command @($Launcher.Prefix) -c "import sys; print('.'.join(map(str, sys.version_info[:3]))); raise SystemExit(sys.version_info < (3, 10))"
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.10 or newer is required. Detected: $VersionText"
    }

    Write-Host "Creating the local Python environment with Python $VersionText ..."
    & $Launcher.Command @($Launcher.Prefix) -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create .venv."
    }
}

Write-Host "Installing Format Agent Workbench dependencies ..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not update pip." }
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not install dependencies." }

$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.example"
if (-not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
    Write-Host "Created .env. The built-in demo needs no API Key; edit this file before using your own natural-language requirements."
}

Write-Host "Format Agent Workbench is ready."

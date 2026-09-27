param([Parameter(Mandatory=$true)][string]$Target, [string]$PythonPath = '')
$ErrorActionPreference = 'Stop'
try {
    if (-not $PythonPath -or -not (Test-Path $PythonPath)) {
        $PythonPath = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
        if (-not (Test-Path $PythonPath)) {
            $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
            if ($launcher) {
                $candidate = & $launcher.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
                if ($LASTEXITCODE -eq 0) { $PythonPath = $candidate }
            }
        }
        if (-not (Test-Path $PythonPath)) {
            if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
                throw 'Install Python 3.12 x64 from python.org, then retry Install speech engine.'
            }
            & winget.exe install --id Python.Python.3.12 --exact --scope user --source winget --accept-source-agreements --accept-package-agreements
            if ($LASTEXITCODE -ne 0) { throw 'Python setup failed.' }
            $PythonPath = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
        }
    }
    & $PythonPath -m venv $Target
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the private voice environment.' }
    $voicePython = Join-Path $Target 'Scripts\python.exe'
    & $voicePython -m pip --isolated install --disable-pip-version-check --only-binary=:all: --index-url https://pypi.org/simple piper-tts==1.8.0
    if ($LASTEXITCODE -ne 0) { throw 'Piper installation failed. Check internet access and Python compatibility.' }
    & $voicePython -c 'from piper import PiperVoice, SynthesisConfig'
    if ($LASTEXITCODE -ne 0) { throw 'Piper import check failed.' }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}

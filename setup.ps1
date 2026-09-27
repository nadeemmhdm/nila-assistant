$ErrorActionPreference = 'Stop'
try {
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'This release requires Windows x64 (Intel or AMD).'
    }
    $source = $PSScriptRoot
    $destination = Join-Path $env:LOCALAPPDATA 'Programs\LocalAssistant'
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    $binary = Join-Path $source 'LocalAssistant.exe'
    if (Test-Path $binary) {
        if ($source -ne $destination) { Copy-Item $binary $destination -Force }
        $target = Join-Path $destination 'LocalAssistant.exe'
        $arguments = 'gui'
    } else {
        function Find-Python {
            $candidates = @(
                (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
                (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
                (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe')
            )
            $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
            if ($launcher) {
                $found = & $launcher.Source -3 -c 'import sys; print(sys.executable)' 2>$null
                if ($LASTEXITCODE -eq 0) { $candidates += $found }
            }
            $command = Get-Command python.exe -ErrorAction SilentlyContinue
            if ($command -and $command.Source -notlike '*WindowsApps*') { $candidates += $command.Source }
            foreach ($candidate in $candidates) {
                if (Test-Path $candidate) {
                    & $candidate -c 'import sys, tkinter; assert sys.version_info >= (3, 10); assert sys.maxsize > 2**32' 2>$null
                    if ($LASTEXITCODE -eq 0) { return $candidate }
                }
            }
            return $null
        }
        $python = Find-Python
        if (-not $python) {
            Write-Host 'Python 3.12 with Tkinter is needed for the source edition.'
            $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
            if (-not $winget) { throw 'Install Python 3.12 x64 from https://www.python.org/downloads/windows/ (include Tcl/Tk), then run Setup.cmd again.' }
            $answer = Read-Host 'Install Python 3.12 for this user using winget? [Y/n]'
            if ($answer -match '^[nN]') { throw 'Python installation skipped.' }
            & $winget.Source install --id Python.Python.3.12 --exact --scope user --source winget --accept-source-agreements --accept-package-agreements
            if ($LASTEXITCODE -ne 0) { throw 'Python installation failed. Install Python manually and retry.' }
            $python = Find-Python
            if (-not $python) { throw 'Python was installed but could not be found. Reopen Setup.cmd.' }
        }
        if ($source -ne $destination) {
            foreach ($file in @('main.py','runtime.json','README.md','LICENSE','THIRD_PARTY.md','speech_worker.py','voice_setup.ps1')) { Copy-Item (Join-Path $source $file) $destination -Force }
            New-Item -ItemType Directory -Force -Path (Join-Path $destination 'assistant') | Out-Null
            Copy-Item (Join-Path $source 'assistant\*.py') (Join-Path $destination 'assistant') -Force
        }
        $target = $python
        $arguments = '"' + (Join-Path $destination 'main.py') + '" gui'
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Local Assistant.lnk'))
    $shortcut.TargetPath = $target
    $shortcut.Arguments = $arguments
    $shortcut.WorkingDirectory = $destination
    $shortcut.Save()
    Write-Host 'Installed. Opening setup: name your assistant, install runtime, add a model.'
    Start-Process -FilePath $target -ArgumentList $arguments -WorkingDirectory $destination
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

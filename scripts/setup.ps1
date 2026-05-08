#Requires -Version 5.1

param(
  [string]$Python = "python",
  [switch]$InstallAsr,
  [switch]$InstallVisual,
  [switch]$Login,
  [switch]$SmokeTest
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
  )
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $FilePath $($Arguments -join ' ')"
  }
}

function Get-PythonOutput {
  param([string]$Code)
  $output = & $Python -c $Code
  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed: $Code"
  }
  return ($output | Select-Object -First 1)
}

function Find-Bili {
  $candidates = New-Object System.Collections.Generic.List[string]

  $cmd = Get-Command bili -ErrorAction SilentlyContinue
  if ($cmd) {
    $candidates.Add($cmd.Source)
  }

  $scriptDir = Get-PythonOutput "import sysconfig; print(sysconfig.get_path('scripts') or '')"
  if ($scriptDir) {
    foreach ($name in @("bili.exe", "bili.cmd", "bili")) {
      $candidates.Add((Join-Path $scriptDir $name))
    }
  }

  $userBase = Get-PythonOutput "import site; print(getattr(site, 'USER_BASE', '') or '')"
  if ($userBase) {
    foreach ($name in @("bili.exe", "bili.cmd", "bili")) {
      $candidates.Add((Join-Path (Join-Path $userBase "Scripts") $name))
    }
  }

  if ($env:APPDATA) {
    $pythonRoot = Join-Path $env:APPDATA "Python"
    Get-ChildItem -Path $pythonRoot -Directory -Filter "Python*" -ErrorAction SilentlyContinue | ForEach-Object {
      foreach ($name in @("bili.exe", "bili.cmd", "bili")) {
        $candidates.Add((Join-Path $_.FullName "Scripts\$name"))
      }
    }
  }

  if ($env:LOCALAPPDATA) {
    $pythonRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"
    Get-ChildItem -Path $pythonRoot -Directory -Filter "Python*" -ErrorAction SilentlyContinue | ForEach-Object {
      foreach ($name in @("bili.exe", "bili.cmd", "bili")) {
        $candidates.Add((Join-Path $_.FullName "Scripts\$name"))
      }
    }
  }

  foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return (Resolve-Path -LiteralPath $candidate).Path
    }
  }

  return $null
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
  $versionOk = Get-PythonOutput "import sys; print(int(sys.version_info >= (3, 10)))"
  if ($versionOk -ne "1") {
    throw "Python 3.10+ is required."
  }

  Invoke-Checked $Python -m pip install --upgrade pip
  Invoke-Checked $Python -m pip install --user -r requirements.txt

  if ($InstallAsr) {
    Invoke-Checked $Python -m pip install --user -r requirements-asr.txt
  }

  if ($InstallVisual) {
    Invoke-Checked $Python -m pip install --user -r requirements-visual.txt
  }

  $bili = Find-Bili
  if (-not $bili) {
    throw "bili executable was not found after installing bilibili-cli."
  }
  Write-Host "bili executable: $bili"

  if ($Login) {
    Invoke-Checked $bili login
  }

  Invoke-Checked $Python tests\validate_repo.py

  if ($SmokeTest) {
    Invoke-Checked $Python tools\bili_video_material.py BV1g1dKBGEZv --out skill_test_output --depth quick --asr never --bili $bili
  }

  Write-Host "Setup completed."
}
finally {
  Pop-Location
}

# crossbrain one-line installer (Windows PowerShell 5.1+ / PowerShell 7)
#
#   irm https://raw.githubusercontent.com/imodoiepale/crossbrain/main/install.ps1 | iex
#
# Clones (or updates) the engine into ~\.crossbrain\engine, adds a `crossbrain` launcher to your user PATH,
# and installs skills, agents and instructions into every agent CLI it finds. Re-run to update.
# It never asks for or stores a credential.
$ErrorActionPreference = 'Stop'

$Repo   = if ($env:CROSSBRAIN_REPO) { $env:CROSSBRAIN_REPO } else { 'https://github.com/imodoiepale/crossbrain.git' }
$HomeD  = if ($env:CROSSBRAIN_HOME) { $env:CROSSBRAIN_HOME } else { Join-Path $HOME '.crossbrain' }
$Engine = Join-Path $HomeD 'engine'
$Bin    = Join-Path $HomeD 'bin'

function Say($m) { Write-Host "==> $m" -ForegroundColor Cyan }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git is required (winget install Git.Git)' }
$Py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Py) { $Py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $Py) { throw 'python 3.9+ is required (winget install Python.Python.3.12)' }

# Native commands write progress to stderr; don't let PowerShell 5.1 treat that as a failure.
$ErrorActionPreference = 'Continue'
if (Test-Path (Join-Path $Engine '.git')) {
  Say "updating $Engine"; & git -C $Engine pull --ff-only --quiet
} else {
  Say "cloning crossbrain into $Engine"
  New-Item -ItemType Directory -Force $HomeD | Out-Null
  & git clone --depth 1 --quiet $Repo $Engine
}
if (-not (Test-Path (Join-Path $Engine 'crossbrain.py'))) { throw "clone failed: $Engine" }

New-Item -ItemType Directory -Force $Bin | Out-Null
Set-Content -Path (Join-Path $Bin 'crossbrain.cmd') -Encoding ascii -Value "@echo off`r`n`"$Py`" `"$Engine\crossbrain.py`" %*"
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($userPath -split ';') -notcontains $Bin) {
  [Environment]::SetEnvironmentVariable('Path', "$userPath;$Bin", 'User')
  Say "added $Bin to your user PATH (open a new terminal to use 'crossbrain')"
}

& $Py (Join-Path $Engine 'crossbrain.py') install @args
& $Py (Join-Path $Engine 'crossbrain.py') doctor

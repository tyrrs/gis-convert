param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"

$RepoUrl = if ($env:GIS_CONVERT_REPO) { $env:GIS_CONVERT_REPO } else { "https://github.com/tyrrs/gis-convert.git" }
if ($env:GIS_CONVERT_HOME) {
  $InstallDir = $env:GIS_CONVERT_HOME
  $CleanupCheckout = $false
} else {
  $InstallDir = Join-Path ([System.IO.Path]::GetTempPath()) ("gis-convert-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $InstallDir | Out-Null
  $CleanupCheckout = $true
}

if ($env:GIS_CONVERT_KEEP_CHECKOUT -eq "1") {
  $CleanupCheckout = $false
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Error "bootstrap.ps1: git is required but was not found in PATH."
  exit 1
}

try {
  $GitDir = Join-Path $InstallDir ".git"
  $HasChildren = (Test-Path $InstallDir) -and $null -ne (Get-ChildItem -Force $InstallDir -ErrorAction SilentlyContinue | Select-Object -First 1)
  if (Test-Path $GitDir) {
    Write-Host "Updating existing gis-convert checkout: $InstallDir"
    git -C $InstallDir pull --ff-only
  } elseif ((Test-Path $InstallDir) -and $HasChildren) {
    Write-Error "bootstrap.ps1: $InstallDir exists but is not a git checkout. Set GIS_CONVERT_HOME to another directory or move the existing path."
    exit 1
  } else {
    Write-Host "Cloning gis-convert into: $InstallDir"
    git clone $RepoUrl $InstallDir
  }

  $InstallScript = Join-Path $InstallDir "install\install.ps1"
  & $InstallScript @RemainingArgs
  $ExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
  exit $ExitCode
} finally {
  if ($CleanupCheckout -and (Test-Path $InstallDir)) {
    Write-Host "Cleaning up temporary checkout: $InstallDir"
    Remove-Item -Recurse -Force $InstallDir
  }
}

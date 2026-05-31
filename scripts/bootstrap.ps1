param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"

$RepoUrl = if ($env:GIS_CONVERT_REPO) { $env:GIS_CONVERT_REPO } else { "https://github.com/tyrrs/gis-convert.git" }
$InstallDir = if ($env:GIS_CONVERT_HOME) { $env:GIS_CONVERT_HOME } else { Join-Path $HOME ".gis-convert" }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Error "bootstrap.ps1: git is required but was not found in PATH."
  exit 1
}

$GitDir = Join-Path $InstallDir ".git"
if (Test-Path $GitDir) {
  Write-Host "Updating existing gis-convert checkout: $InstallDir"
  git -C $InstallDir pull --ff-only
} elseif (Test-Path $InstallDir) {
  Write-Error "bootstrap.ps1: $InstallDir exists but is not a git checkout. Set GIS_CONVERT_HOME to another directory or move the existing path."
  exit 1
} else {
  Write-Host "Cloning gis-convert into: $InstallDir"
  git clone $RepoUrl $InstallDir
}

$InstallScript = Join-Path $InstallDir "scripts\install.ps1"
& $InstallScript @RemainingArgs

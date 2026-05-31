param(
  [string]$Install,
  [string]$Uninstall,
  [ValidateSet("user", "project")]
  [string]$Scope = "user",
  [string]$ProjectDir,
  [switch]$DryRun,
  [switch]$WithDeps,
  [switch]$DepsOnly,
  [switch]$Yes,
  [switch]$SkipDepsCheck,
  [switch]$RequireDeps,
  [switch]$Interactive,
  [switch]$NoInteractive,
  [switch]$Help
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallPy = Join-Path $ScriptDir "install.py"
$ArgsList = @()

if ($Help) { $ArgsList += "--help" }
if ($Install) { $ArgsList += @("--install", $Install) }
if ($Uninstall) { $ArgsList += @("--uninstall", $Uninstall) }
if ($Scope) { $ArgsList += @("--scope", $Scope) }
if ($ProjectDir) { $ArgsList += @("--project-dir", $ProjectDir) }
if ($DryRun) { $ArgsList += "--dry-run" }
if ($WithDeps) { $ArgsList += "--with-deps" }
if ($DepsOnly) { $ArgsList += "--deps-only" }
if ($Yes) { $ArgsList += "--yes" }
if ($SkipDepsCheck) { $ArgsList += "--skip-deps-check" }
if ($RequireDeps) { $ArgsList += "--require-deps" }
if ($Interactive) { $ArgsList += "--interactive" }
if ($NoInteractive) { $ArgsList += "--no-interactive" }

python $InstallPy @ArgsList

#!/usr/bin/env python3
"""Install gis-convert into supported agent tools."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_env import inspect_environment
from scripts.install_deps import build_install_plan, detect_platform, find_package_managers


SUPPORTED_TOOLS = [
    "codex",
    "claude-code",
    "qwen-code",
    "gemini-cli",
    "cursor",
    "copilot",
    "aider",
    "continue",
    "opencode",
    "windsurf",
]
REQUIRED_NATIVE_TOOLS = ["gdalinfo", "ogrinfo", "ogr2ogr", "proj"]
OPTIONAL_NATIVE_TOOLS = ["pdal"]
PYTHON_PACKAGES = {"pygeoconv": "pygeoconv>=1.0.1,<2"}


@dataclass(frozen=True)
class InstallContext:
    """Runtime settings for a gis-convert installation run."""

    repo_root: Path
    home: Path
    project_dir: Path
    scope: str
    dry_run: bool
    with_deps: bool
    deps_only: bool


@dataclass(frozen=True)
class InstallOperation:
    """One planned file or directory copy operation."""

    tool: str
    source: Path
    destination: Path
    kind: str
    description: str
    content: str | None = None


@dataclass(frozen=True)
class NativeDependencySummary:
    """Summary of required and optional native GIS dependency availability."""

    tools: dict[str, dict[str, object]]
    required_missing: list[str]
    optional_missing: list[str]
    python_packages: dict[str, dict[str, object]] = field(default_factory=dict)
    python_missing: list[str] = field(default_factory=list)

    @property
    def has_missing(self) -> bool:
        return bool(self.required_missing or self.optional_missing or self.python_missing)

    @property
    def has_required_missing(self) -> bool:
        return bool(self.required_missing)


def copy_directory(source: Path, destination: Path) -> None:
    """Copy a directory, replacing any existing destination."""

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "__pycache__",
            "*.egg-info",
            "*.pyc",
            ".DS_Store",
            "build",
            "dist",
        ),
    )


def copy_file(source: Path, destination: Path) -> None:
    """Copy a file, creating the destination directory first."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_minimal_skill_package(repo_root: Path, destination: Path) -> None:
    """Copy the minimal runtime skill package into an agent-specific location."""

    source_skill = repo_root / "skills" / "gis-convert" / "SKILL.md"
    if not source_skill.exists():
        raise FileNotFoundError(f"Missing canonical skill entry: {source_skill}")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    copy_file(source_skill, destination / "SKILL.md")
    for directory_name in ("scripts", "references"):
        copy_directory(repo_root / directory_name, destination / directory_name)
    required_files = [
        destination / "SKILL.md",
        destination / "scripts" / "gis_convert.py",
        destination / "scripts" / "check_env.py",
        destination / "references" / "format-support.md",
        destination / "references" / "3d-workflows.md",
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise RuntimeError("Minimal skill package is incomplete: " + ", ".join(missing))


def write_generated_file(destination: Path, content: str) -> None:
    """Write a generated adapter entry file."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def normalize_tool_name(name: str) -> str:
    """Normalize supported tool aliases into canonical names."""

    normalized = name.strip().lower()
    aliases = {
        "claude": "claude-code",
        "qwen": "qwen-code",
        "github-copilot": "copilot",
        "gemini": "gemini-cli",
    }
    return aliases.get(normalized, normalized)


def parse_tool_selection(
    selection: str | None,
    detected: dict[str, bool] | None = None,
) -> list[str]:
    """Parse a comma-separated tool selection into a deterministic supported list."""

    raw = selection
    if not raw:
        return []
    selected = [normalize_tool_name(part) for part in raw.split(",") if part.strip()]
    if not selected:
        return []
    if selected == ["all"]:
        return list(SUPPORTED_TOOLS)
    if selected == ["detected"]:
        detected_map = detected or {}
        return [tool for tool in SUPPORTED_TOOLS if detected_map.get(tool)]
    unknown = [tool for tool in selected if tool not in SUPPORTED_TOOLS]
    if unknown:
        raise ValueError(f"Unsupported tool(s): {', '.join(unknown)}. Supported: {', '.join(SUPPORTED_TOOLS)}")
    seen: set[str] = set()
    ordered: list[str] = []
    for tool in selected:
        if tool not in seen:
            ordered.append(tool)
            seen.add(tool)
    return ordered


def _command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def detect_tools(context: InstallContext) -> dict[str, bool]:
    """Detect which supported tools appear to be installed or configured."""

    return {
        "codex": bool(os.environ.get("CODEX_HOME")) or (context.home / ".codex").exists(),
        "claude-code": _command_exists("claude") or (context.home / ".claude").exists(),
        "qwen-code": _command_exists("qwen") or (context.home / ".qwen").exists() or (context.project_dir / ".qwen").exists(),
        "gemini-cli": _command_exists("gemini") or (context.home / ".gemini").exists(),
        "cursor": _command_exists("cursor") or (context.home / ".cursor").exists() or (context.project_dir / ".cursor").exists(),
        "copilot": _command_exists("code") or (context.home / ".github").exists() or (context.home / ".copilot").exists(),
        "aider": _command_exists("aider"),
        "continue": (context.home / ".continue").exists() or (context.project_dir / ".continue").exists(),
        "opencode": _command_exists("opencode") or (context.home / ".config" / "opencode").exists() or (context.project_dir / ".opencode").exists(),
        "windsurf": _command_exists("windsurf") or (context.home / ".codeium").exists() or (context.project_dir / ".windsurf").exists(),
    }


def summarize_native_dependencies(report: dict[str, object]) -> NativeDependencySummary:
    """Summarize required and optional native GIS tool availability."""

    raw_tools = report.get("tools", {})
    tools = raw_tools if isinstance(raw_tools, dict) else {}
    raw_packages = report.get("python_packages", {})
    python_packages = raw_packages if isinstance(raw_packages, dict) else {}
    required_missing = [name for name in REQUIRED_NATIVE_TOOLS if not tools.get(name, {}).get("available")]
    optional_missing = [name for name in OPTIONAL_NATIVE_TOOLS if not tools.get(name, {}).get("available")]
    python_missing = [name for name in PYTHON_PACKAGES if python_packages and not python_packages.get(name, {}).get("available")]
    return NativeDependencySummary(
        tools=tools,
        required_missing=required_missing,
        optional_missing=optional_missing,
        python_packages=python_packages,
        python_missing=python_missing,
    )


def print_native_dependency_report(summary: NativeDependencySummary) -> None:
    """Print a human-readable native GIS dependency status report."""

    print("Native GIS Dependencies:")
    for name in [*REQUIRED_NATIVE_TOOLS, *OPTIONAL_NATIVE_TOOLS]:
        status = summary.tools.get(name, {})
        marker = "ok" if status.get("available") else "missing"
        version = status.get("version") or "-"
        path = status.get("path") or "-"
        label = "required" if name in REQUIRED_NATIVE_TOOLS else "optional"
        print(f"  - {name} ({label}): {marker} version={version} path={path}")
    if summary.required_missing:
        print("Missing required native GIS dependencies: " + ", ".join(summary.required_missing))
    if summary.optional_missing:
        print("Missing optional point-cloud dependency: " + ", ".join(summary.optional_missing))
        print("  Point-cloud conversion for LAS/LAZ/E57/PLY requires PDAL.")
    if summary.python_packages:
        print("Python Packages:")
        for name, status in summary.python_packages.items():
            marker = "ok" if status.get("available") else "missing"
            version = status.get("version") or "-"
            print(f"  - {name}: {marker} version={version}")
    if summary.python_missing:
        print("Missing Python package dependency: " + ", ".join(summary.python_missing))
        print("  ESRIJSON output requires pygeoconv.")


def print_dependency_install_plan(dependency_group: str = "all", env_name: str = "gis-convert") -> None:
    """Print the recommended dependency installation plan for the current platform."""

    managers = find_package_managers(["mamba", "conda", "brew", "apt-get", "dnf", "yum", "pacman", "apk"])
    plan = build_install_plan(
        detect_platform(),
        strategy="auto",
        package_manager_paths=managers,
        env_name=env_name,
        dependency_group=dependency_group,
    )
    print("Recommended dependency install plan:")
    if plan.commands:
        for command in plan.commands:
            print("  " + shlex.join(command))
    for note in plan.notes:
        print("  Note: " + note)


def confirm_dependency_install(input_fn: Callable[[str], str] = input) -> bool:
    """Return true only when the user explicitly confirms dependency installation."""

    answer = input_fn("Install required native GIS dependencies now? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def confirm_optional_pdal_install(input_fn: Callable[[str], str] = input) -> bool:
    """Return true only when the user explicitly confirms optional PDAL installation."""

    answer = input_fn("PDAL is optional and only needed for LAS/LAZ/E57/PLY point-cloud conversion. Install PDAL now? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def confirm_python_dependency_install(input_fn: Callable[[str], str] = input) -> bool:
    """Return true only when the user explicitly confirms Python package installation."""

    answer = input_fn("pygeoconv is required for ESRIJSON output. Install Python package dependencies now? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _user_or_project(context: InstallContext, user_path: Path, project_path: Path) -> Path:
    return project_path if context.scope == "project" else user_path


def generated_entry_content(tool: str, package_dir: Path) -> str:
    """Return a small integration entry that points to the installed skill package."""

    skill_path = package_dir / "SKILL.md"
    if tool == "gemini-cli":
        return (
            'description = "Use gis-convert for GIS format conversion workflows."\n'
            'prompt = """\n'
            f"Read and follow the gis-convert skill at {skill_path}.\n"
            f"Use scripts and references from {package_dir} when needed.\n"
            'Do not install native GIS dependencies unless the user explicitly asks.\n'
            '"""\n'
        )
    if tool == "cursor":
        return (
            "---\n"
            "description: Use gis-convert for GIS format conversion and CRS workflows\n"
            "globs:\n"
            "alwaysApply: false\n"
            "---\n\n"
            f"Read and follow `{skill_path}`. Use the installed skill package at `{package_dir}`; do not assume user data directories contain `scripts/gis_convert.py`.\n"
        )
    if tool == "copilot":
        return (
            "# gis-convert\n\n"
            f"For GIS conversion tasks, follow `{skill_path}`. Use the installed package at `{package_dir}` for scripts and references.\n"
        )
    if tool == "aider":
        return f"read:\n  - {skill_path}\n  - {package_dir / 'references' / 'format-support.md'}\n"
    if tool == "continue":
        return (
            "# gis-convert\n\n"
            f"Follow `{skill_path}` for GIS conversion workflows. Use `{package_dir}` for bundled scripts and references.\n"
        )
    if tool == "opencode":
        return (
            "# gis-convert\n\n"
            f"Follow `{skill_path}` for GIS conversion workflows. Use `{package_dir}` for bundled scripts and references.\n"
        )
    if tool == "windsurf":
        return (
            "# gis-convert\n\n"
            f"When working on GIS conversion tasks, follow `{skill_path}` and use bundled resources under `{package_dir}`.\n"
        )
    if tool == "qwen-code":
        return (
            "# gis-convert\n\n"
            f"Follow `{skill_path}` for GIS conversion workflows. Use `{package_dir}` for bundled scripts and references.\n"
        )
    raise ValueError(f"No generated entry template for {tool}")


def add_skill_package_operation(operations: list[InstallOperation], tool: str, repo: Path, destination: Path, description: str) -> None:
    """Append a minimal skill package install operation."""

    operations.append(InstallOperation(tool, repo / "skills" / "gis-convert", destination, "skill-package", description))


def add_generated_entry_operation(operations: list[InstallOperation], tool: str, repo: Path, destination: Path, package_dir: Path, description: str) -> None:
    """Append a generated entry file operation for tools without native skill discovery."""

    operations.append(
        InstallOperation(
            tool,
            repo / "skills" / "gis-convert" / "SKILL.md",
            destination,
            "generated-file",
            description,
            generated_entry_content(tool, package_dir),
        )
    )


def build_tool_operations(tools: Iterable[str], context: InstallContext) -> list[InstallOperation]:
    """Build copy operations for selected tools."""

    repo = context.repo_root
    operations: list[InstallOperation] = []
    for tool in tools:
        if tool == "codex":
            codex_home = Path(os.environ.get("CODEX_HOME", str(context.home / ".codex")))
            add_skill_package_operation(operations, tool, repo, codex_home / "skills" / "gis-convert", "Codex skill package")
        elif tool == "claude-code":
            destination = _user_or_project(
                context,
                context.home / ".claude" / "skills" / "gis-convert",
                context.project_dir / ".claude" / "skills" / "gis-convert",
            )
            add_skill_package_operation(operations, tool, repo, destination, "Claude Code skill package")
        elif tool == "qwen-code":
            package_dir = _user_or_project(
                context,
                context.home / ".qwen" / "skills" / "gis-convert",
                context.project_dir / ".qwen" / "skills" / "gis-convert",
            )
            entry = _user_or_project(
                context,
                context.home / ".qwen" / "agents" / "gis-convert.md",
                context.project_dir / ".qwen" / "agents" / "gis-convert.md",
            )
            add_skill_package_operation(operations, tool, repo, package_dir, "Qwen Code skill package")
            add_generated_entry_operation(operations, tool, repo, entry, package_dir, "Qwen Code entry")
        elif tool == "gemini-cli":
            package_dir = context.home / ".gemini" / "skills" / "gis-convert"
            add_skill_package_operation(operations, tool, repo, package_dir, "Gemini CLI skill package")
            add_generated_entry_operation(operations, tool, repo, context.home / ".gemini" / "commands" / "gis-convert.toml", package_dir, "Gemini CLI command")
        elif tool == "cursor":
            package_dir = _user_or_project(
                context,
                context.home / ".cursor" / "skills" / "gis-convert",
                context.project_dir / ".cursor" / "skills" / "gis-convert",
            )
            entry = _user_or_project(
                context,
                context.home / ".cursor" / "rules" / "gis-convert.mdc",
                context.project_dir / ".cursor" / "rules" / "gis-convert.mdc",
            )
            add_skill_package_operation(operations, tool, repo, package_dir, "Cursor skill package")
            add_generated_entry_operation(operations, tool, repo, entry, package_dir, "Cursor rule")
        elif tool == "copilot":
            package_dir = _user_or_project(
                context,
                context.home / ".github" / "skills" / "gis-convert",
                context.project_dir / ".github" / "skills" / "gis-convert",
            )
            entry = _user_or_project(
                context,
                context.home / ".github" / "instructions" / "gis-convert.instructions.md",
                context.project_dir / ".github" / "instructions" / "gis-convert.instructions.md",
            )
            add_skill_package_operation(operations, tool, repo, package_dir, "GitHub Copilot skill package")
            add_generated_entry_operation(operations, tool, repo, entry, package_dir, "GitHub Copilot instructions")
        elif tool == "aider":
            package_dir = _user_or_project(
                context,
                context.home / ".aider" / "skills" / "gis-convert",
                context.project_dir / ".aider" / "skills" / "gis-convert",
            )
            entry = _user_or_project(
                context,
                context.home / ".aider.conf.yml",
                context.project_dir / ".aider.conf.yml",
            )
            add_skill_package_operation(operations, tool, repo, package_dir, "Aider skill package")
            add_generated_entry_operation(operations, tool, repo, entry, package_dir, "Aider config")
        elif tool == "continue":
            package_dir = _user_or_project(
                context,
                context.home / ".continue" / "skills" / "gis-convert",
                context.project_dir / ".continue" / "skills" / "gis-convert",
            )
            entry = _user_or_project(
                context,
                context.home / ".continue" / "rules" / "gis-convert-rule.md",
                context.project_dir / ".continue" / "rules" / "gis-convert-rule.md",
            )
            add_skill_package_operation(operations, tool, repo, package_dir, "Continue skill package")
            add_generated_entry_operation(operations, tool, repo, entry, package_dir, "Continue rule")
        elif tool == "opencode":
            package_dir = context.project_dir / ".opencode" / "skills" / "gis-convert"
            add_skill_package_operation(operations, tool, repo, package_dir, "OpenCode skill package")
            add_generated_entry_operation(operations, tool, repo, context.project_dir / ".opencode" / "agents" / "gis-convert.md", package_dir, "OpenCode project agent")
        elif tool == "windsurf":
            package_dir = context.project_dir / ".windsurf" / "skills" / "gis-convert"
            add_skill_package_operation(operations, tool, repo, package_dir, "Windsurf skill package")
            add_generated_entry_operation(operations, tool, repo, context.project_dir / ".windsurfrules", package_dir, "Windsurf project rules")
    return operations


def apply_operation(operation: InstallOperation, dry_run: bool) -> None:
    """Apply or print one install operation."""

    prefix = "DRY-RUN" if dry_run else "INSTALL"
    print(f"[{prefix}] {operation.tool}: {operation.description}")
    print(f"  {operation.source} -> {operation.destination}")
    if dry_run:
        return
    if operation.kind == "skill-package":
        copy_minimal_skill_package(operation.source.parents[1], operation.destination)
    elif operation.kind == "directory":
        operation.destination.parent.mkdir(parents=True, exist_ok=True)
        copy_directory(operation.source, operation.destination)
    elif operation.kind == "generated-file":
        if operation.content is None:
            raise RuntimeError(f"Generated operation has no content: {operation.destination}")
        write_generated_file(operation.destination, operation.content)
    else:
        copy_file(operation.source, operation.destination)


def apply_uninstall_operation(operation: InstallOperation, dry_run: bool) -> int:
    """Remove one installed integration when its target matches the expected type."""

    if not operation.destination.exists():
        print(f"[SKIP] {operation.tool}: {operation.description}")
        print(f"  missing: {operation.destination}")
        return 0
    prefix = "DRY-RUN" if dry_run else "UNINSTALL"
    print(f"[{prefix}] {operation.tool}: {operation.description}")
    print(f"  remove: {operation.destination}")
    if dry_run:
        return 0
    if operation.kind in {"directory", "skill-package"}:
        if not operation.destination.is_dir():
            print(f"install.py: refusing to remove non-directory target: {operation.destination}", file=sys.stderr)
            return 1
        shutil.rmtree(operation.destination)
        return 0
    if not operation.destination.is_file():
        print(f"install.py: refusing to remove non-file target: {operation.destination}", file=sys.stderr)
        return 1
    operation.destination.unlink()
    return 0


def run_dependency_install(context: InstallContext, yes: bool, dependency_group: str = "all") -> int:
    """Run the native GIS dependency installer when requested."""

    command = [
        sys.executable,
        str(context.repo_root / "scripts" / "install_deps.py"),
        "--apply",
        "--dependency-group",
        dependency_group,
    ]
    if yes:
        command.append("--yes")
    prefix = "DRY-RUN" if context.dry_run else "INSTALL"
    print(f"[{prefix}] dependencies: {shlex.join(command)}")
    if context.dry_run:
        return 0
    return subprocess.run(command, check=False).returncode


def print_python_dependency_install_plan() -> None:
    """Print the recommended Python package installation command."""

    command = [sys.executable, "-m", "pip", "install", *PYTHON_PACKAGES.values()]
    print("Recommended Python package install plan:")
    print("  " + shlex.join(command))


def run_python_dependency_install(context: InstallContext, yes: bool) -> int:
    """Install Python package dependencies required by runtime conversions."""

    command = [sys.executable, "-m", "pip", "install", *PYTHON_PACKAGES.values()]
    prefix = "DRY-RUN" if context.dry_run else "INSTALL"
    print(f"[{prefix}] python packages: {shlex.join(command)}")
    if context.dry_run:
        return 0
    if not yes:
        print("install.py: refusing to install Python packages without explicit confirmation.", file=sys.stderr)
        return 1
    return subprocess.run(command, check=False).returncode


def run_all_dependency_install(context: InstallContext, yes: bool) -> int:
    """Install native and Python dependency groups."""

    native_code = run_dependency_install(context, yes=yes, dependency_group="all")
    if native_code != 0:
        return native_code
    return run_python_dependency_install(context, yes=True)


def handle_native_dependencies(
    context: InstallContext,
    yes: bool,
    require_deps: bool,
    no_interactive: bool,
    input_fn: Callable[[str], str] = input,
    force_install: bool = False,
) -> int:
    """Inspect native dependencies and optionally install missing tools."""

    summary = summarize_native_dependencies(inspect_environment([*REQUIRED_NATIVE_TOOLS, *OPTIONAL_NATIVE_TOOLS]))
    print_native_dependency_report(summary)

    if not summary.has_missing and not force_install:
        return 0

    if force_install:
        print_dependency_install_plan("all")
        install_code = run_dependency_install(context, yes=yes, dependency_group="all")
        if install_code != 0:
            return install_code
        python_code = run_python_dependency_install(context, yes=True)
        if python_code != 0:
            return python_code
        if not context.dry_run:
            print("Native dependency installer finished. Verify with: python scripts/check_env.py")
        return 0

    if summary.has_required_missing:
        print_dependency_install_plan("required")
        should_install = False
        if yes:
            should_install = True
        elif context.dry_run:
            print("[DRY-RUN] required dependencies are missing; installer would ask for confirmation before installing.")
        elif no_interactive or not (sys.stdin.isatty() and sys.stdout.isatty()):
            print("Non-interactive mode: skipping required native dependency installation.")
        else:
            should_install = confirm_dependency_install(input_fn)

        if should_install:
            install_code = run_dependency_install(context, yes=True, dependency_group="required")
            if install_code != 0:
                return install_code
            if not context.dry_run:
                print("Native dependency installer finished. Verify with: python scripts/check_env.py")
        elif require_deps:
            print("Required native GIS dependencies are missing. Re-run with --yes, --with-deps, or install them manually.", file=sys.stderr)
            return 1
        else:
            print("Agent integration can still be installed, but GIS conversion is limited until required dependencies are installed.")
            print("Install later with: ./scripts/install.sh --deps-only")

    if summary.optional_missing:
        print("PDAL is optional and only needed for LAS/LAZ/E57/PLY point-cloud conversion.")
        should_install_pdal = False
        if yes:
            print_dependency_install_plan("optional-pdal")
            should_install_pdal = True
        elif context.dry_run:
            print_dependency_install_plan("optional-pdal")
            print("[DRY-RUN] optional PDAL is missing; installer would ask separately before installing it.")
        elif no_interactive or not (sys.stdin.isatty() and sys.stdout.isatty()):
            print_dependency_install_plan("optional-pdal")
            print("Non-interactive mode: skipping optional PDAL installation.")
        else:
            print_dependency_install_plan("optional-pdal")
            should_install_pdal = confirm_optional_pdal_install(input_fn)

        if should_install_pdal:
            install_code = run_dependency_install(context, yes=True, dependency_group="optional-pdal")
            if install_code != 0:
                return install_code
            if not context.dry_run:
                print("PDAL installer finished. Verify with: python scripts/check_env.py")
        else:
            print("Agent integration can still be installed. Point-cloud conversion is limited until PDAL is installed.")
    if summary.python_missing:
        print_python_dependency_install_plan()
        should_install_python = False
        if yes:
            should_install_python = True
        elif context.dry_run:
            print("[DRY-RUN] Python package dependencies are missing; installer would ask before installing them.")
        elif no_interactive or not (sys.stdin.isatty() and sys.stdout.isatty()):
            print("Non-interactive mode: skipping Python package dependency installation.")
        else:
            should_install_python = confirm_python_dependency_install(input_fn)

        if should_install_python:
            python_code = run_python_dependency_install(context, yes=True)
            if python_code != 0:
                return python_code
            if not context.dry_run:
                print("Python package installer finished. Verify with: python scripts/check_env.py")
        elif require_deps:
            print("Python package dependencies are missing. Re-run with --yes or install them manually.", file=sys.stderr)
            return 1
        else:
            print("Agent integration can still be installed. ESRIJSON output is limited until pygeoconv is installed.")
    return 0


def prompt_for_tools(detected: dict[str, bool]) -> list[str]:
    """Prompt for an interactive tool selection."""

    print("Select tools to install (comma-separated numbers, Enter for detected):")
    for index, tool in enumerate(SUPPORTED_TOOLS, start=1):
        marker = "*" if detected.get(tool) else " "
        print(f"  {index}. [{marker}] {tool}")
    answer = input("> ").strip()
    if not answer:
        return [tool for tool in SUPPORTED_TOOLS if detected.get(tool)]
    selected: list[str] = []
    for part in answer.split(","):
        index = int(part.strip())
        selected.append(SUPPORTED_TOOLS[index - 1])
    return selected


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the install.py argument parser."""

    parser = argparse.ArgumentParser(description="Install the gis-convert skill into supported agent tools.")
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument("--install", help="Install selected tools. Accepts a comma-separated list, all, or detected.")
    action_group.add_argument("--uninstall", help="Uninstall selected tools. Accepts a comma-separated list, all, or detected.")
    parser.add_argument("--scope", choices=["user", "project"], default="user", help="Install user-wide or into a project where supported.")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd(), help="Project directory for project-scoped integrations.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned operations without writing files or installing dependencies.")
    parser.add_argument("--with-deps", action="store_true", help="Also install GIS native dependencies and Python package dependencies.")
    parser.add_argument("--deps-only", action="store_true", help="Install only GIS dependencies, not agent integrations.")
    parser.add_argument("--yes", action="store_true", help="Confirm dependency commands that require elevated/system package access.")
    parser.add_argument("--skip-deps-check", action="store_true", help="Skip GDAL/PROJ/PDAL and Python package dependency detection.")
    parser.add_argument("--require-deps", action="store_true", help="Fail if required GIS dependencies are missing.")
    parser.add_argument("--interactive", action="store_true", help="Show an interactive tool selector.")
    parser.add_argument("--no-interactive", action="store_true", help="Disable interactive selection.")
    return parser


def main(argv: list[str] | None = None, input_fn: Callable[[str], str] | None = None) -> int:
    """CLI entrypoint for installing gis-convert into agent tools."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    context = InstallContext(
        repo_root=repo_root,
        home=Path(os.environ.get("HOME", str(Path.home()))),
        project_dir=args.project_dir.resolve(),
        scope=args.scope,
        dry_run=args.dry_run,
        with_deps=args.with_deps,
        deps_only=args.deps_only,
    )
    detected = detect_tools(context)
    uninstalling = args.uninstall is not None
    if uninstalling and (args.with_deps or args.deps_only or args.require_deps):
        parser.error("--uninstall cannot be combined with --with-deps, --deps-only, or --require-deps")

    if not uninstalling and not args.skip_deps_check:
        dep_code = handle_native_dependencies(
            context,
            yes=args.yes,
            require_deps=args.require_deps,
            no_interactive=args.no_interactive,
            input_fn=input_fn or input,
            force_install=context.with_deps or context.deps_only,
        )
        if dep_code != 0:
            return dep_code

    if args.skip_deps_check and context.deps_only:
        return run_all_dependency_install(context, yes=args.yes)
    if context.deps_only:
        return 0

    try:
        tools = parse_tool_selection(args.uninstall if uninstalling else args.install, detected=detected)
    except ValueError as exc:
        print(f"install.py: {exc}", file=sys.stderr)
        return 2

    if not tools and not uninstalling:
        if args.interactive or (not args.no_interactive and sys.stdin.isatty() and sys.stdout.isatty()):
            if input_fn is not None:
                original_input = __builtins__["input"] if isinstance(__builtins__, dict) else __builtins__.input
                try:
                    if isinstance(__builtins__, dict):
                        __builtins__["input"] = input_fn
                    else:
                        __builtins__.input = input_fn
                    tools = prompt_for_tools(detected)
                finally:
                    if isinstance(__builtins__, dict):
                        __builtins__["input"] = original_input
                    else:
                        __builtins__.input = original_input
            else:
                tools = prompt_for_tools(detected)
        else:
            tools = parse_tool_selection("detected", detected=detected)

    if not tools:
        print("No tools selected or detected. Use --install codex, --install all, or --interactive.")
        if context.with_deps:
            return run_all_dependency_install(context, yes=args.yes)
        return 0

    print("gis-convert uninstaller" if uninstalling else "gis-convert installer")
    print(f"Repository: {context.repo_root}")
    print(f"Scope: {context.scope}")
    print(f"Project: {context.project_dir}")
    print(f"Tools: {', '.join(tools)}")

    if uninstalling:
        result = 0
        for operation in build_tool_operations(tools, context):
            result = max(result, apply_uninstall_operation(operation, dry_run=context.dry_run))
        return result

    for operation in build_tool_operations(tools, context):
        apply_operation(operation, dry_run=context.dry_run)

    if args.skip_deps_check and context.with_deps:
        dep_code = run_all_dependency_install(context, yes=args.yes)
        if dep_code != 0:
            return dep_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

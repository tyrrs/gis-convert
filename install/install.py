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
from install.install_deps import build_install_plan, conda_env_exists, detect_platform, find_package_managers


REQUIRED_NATIVE_TOOLS = ["gdalinfo", "ogrinfo", "ogr2ogr", "proj"]
OPTIONAL_NATIVE_TOOLS = ["pdal"]
PYTHON_PACKAGES = {"pygeoconv": "pygeoconv>=1.0.1,<2"}
CONDA_ENV_NAME = "gis-convert"


@dataclass(frozen=True)
class AgentTarget:
    """A supported agent install target and its standard skill paths."""

    display_name: str
    project_path: str
    global_path: str
    aliases: tuple[str, ...] = ()
    detect_commands: tuple[str, ...] = ()
    detect_project_paths: tuple[str, ...] = ()
    detect_global_paths: tuple[str, ...] = ()
    detect_env_vars: tuple[str, ...] = ()


def agent_target(
    display_name: str,
    project_path: str,
    global_path: str,
    *,
    aliases: tuple[str, ...] = (),
    detect_commands: tuple[str, ...] = (),
    detect_project_paths: tuple[str, ...] = (),
    detect_global_paths: tuple[str, ...] = (),
    detect_env_vars: tuple[str, ...] = (),
) -> AgentTarget:
    """Create an agent target using paths relative to project and home roots."""

    return AgentTarget(
        display_name=display_name,
        project_path=project_path,
        global_path=global_path,
        aliases=aliases,
        detect_commands=detect_commands,
        detect_project_paths=detect_project_paths,
        detect_global_paths=detect_global_paths,
        detect_env_vars=detect_env_vars,
    )


AGENT_TARGETS: dict[str, AgentTarget] = {
    "aider-desk": agent_target("AiderDesk", ".aider-desk/skills", ".aider-desk/skills", detect_commands=("aider-desk",), detect_global_paths=(".aider-desk",)),
    "amp": agent_target("Amp", ".agents/skills", ".config/agents/skills", detect_commands=("amp",)),
    "kimi-cli": agent_target("Kimi Code CLI", ".agents/skills", ".config/agents/skills", detect_commands=("kimi", "kimi-cli")),
    "replit": agent_target("Replit", ".agents/skills", ".config/agents/skills", detect_commands=("replit",)),
    "universal": agent_target("Universal", ".agents/skills", ".config/agents/skills"),
    "antigravity": agent_target("Antigravity", ".agents/skills", ".gemini/antigravity/skills", detect_commands=("antigravity",), detect_global_paths=(".gemini/antigravity",)),
    "augment": agent_target("Augment", ".augment/skills", ".augment/skills", detect_commands=("augment",), detect_project_paths=(".augment",), detect_global_paths=(".augment",)),
    "bob": agent_target("IBM Bob", ".bob/skills", ".bob/skills", detect_commands=("bob",), detect_project_paths=(".bob",), detect_global_paths=(".bob",)),
    "claude-code": agent_target("Claude Code", ".claude/skills", ".claude/skills", aliases=("claude",), detect_commands=("claude",), detect_project_paths=(".claude",), detect_global_paths=(".claude",)),
    "openclaw": agent_target("OpenClaw", "skills", ".openclaw/skills", detect_commands=("openclaw",), detect_global_paths=(".openclaw",)),
    "cline": agent_target("Cline", ".agents/skills", ".agents/skills", detect_commands=("cline",)),
    "dexto": agent_target("Dexto", ".agents/skills", ".agents/skills", detect_commands=("dexto",)),
    "warp": agent_target("Warp", ".agents/skills", ".agents/skills", detect_commands=("warp",)),
    "codearts-agent": agent_target("CodeArts Agent", ".codeartsdoer/skills", ".codeartsdoer/skills", detect_commands=("codearts-agent", "codearts"), detect_project_paths=(".codeartsdoer",), detect_global_paths=(".codeartsdoer",)),
    "codebuddy": agent_target("CodeBuddy", ".codebuddy/skills", ".codebuddy/skills", detect_commands=("codebuddy",), detect_project_paths=(".codebuddy",), detect_global_paths=(".codebuddy",)),
    "codemaker": agent_target("Codemaker", ".codemaker/skills", ".codemaker/skills", detect_commands=("codemaker",), detect_project_paths=(".codemaker",), detect_global_paths=(".codemaker",)),
    "codestudio": agent_target("Code Studio", ".codestudio/skills", ".codestudio/skills", detect_commands=("codestudio",), detect_project_paths=(".codestudio",), detect_global_paths=(".codestudio",)),
    "codex": agent_target("Codex", ".agents/skills", ".codex/skills", detect_env_vars=("CODEX_HOME",), detect_global_paths=(".codex",)),
    "command-code": agent_target("Command Code", ".commandcode/skills", ".commandcode/skills", detect_commands=("command-code", "commandcode"), detect_project_paths=(".commandcode",), detect_global_paths=(".commandcode",)),
    "continue": agent_target("Continue", ".continue/skills", ".continue/skills", detect_project_paths=(".continue",), detect_global_paths=(".continue",)),
    "cortex": agent_target("Cortex Code", ".cortex/skills", ".snowflake/cortex/skills", detect_commands=("cortex",), detect_project_paths=(".cortex",), detect_global_paths=(".snowflake/cortex",)),
    "crush": agent_target("Crush", ".crush/skills", ".config/crush/skills", detect_commands=("crush",), detect_project_paths=(".crush",), detect_global_paths=(".config/crush",)),
    "cursor": agent_target("Cursor", ".agents/skills", ".cursor/skills", detect_commands=("cursor",), detect_project_paths=(".cursor",), detect_global_paths=(".cursor",)),
    "deepagents": agent_target("Deep Agents", ".agents/skills", ".deepagents/agent/skills", detect_commands=("deepagents",), detect_global_paths=(".deepagents",)),
    "devin": agent_target("Devin for Terminal", ".devin/skills", ".config/devin/skills", detect_commands=("devin",), detect_project_paths=(".devin",), detect_global_paths=(".config/devin",)),
    "droid": agent_target("Droid", ".factory/skills", ".factory/skills", detect_commands=("droid",), detect_project_paths=(".factory",), detect_global_paths=(".factory",)),
    "firebender": agent_target("Firebender", ".agents/skills", ".firebender/skills", detect_commands=("firebender",), detect_global_paths=(".firebender",)),
    "forgecode": agent_target("ForgeCode", ".forge/skills", ".forge/skills", detect_commands=("forgecode", "forge"), detect_project_paths=(".forge",), detect_global_paths=(".forge",)),
    "gemini-cli": agent_target("Gemini CLI", ".agents/skills", ".gemini/skills", aliases=("gemini",), detect_commands=("gemini",), detect_global_paths=(".gemini",)),
    "github-copilot": agent_target("GitHub Copilot", ".agents/skills", ".copilot/skills", aliases=("copilot",), detect_commands=("code",), detect_project_paths=(".github",), detect_global_paths=(".copilot", ".github")),
    "goose": agent_target("Goose", ".goose/skills", ".config/goose/skills", detect_commands=("goose",), detect_project_paths=(".goose",), detect_global_paths=(".config/goose",)),
    "hermes-agent": agent_target("Hermes Agent", ".hermes/skills", ".hermes/skills", detect_commands=("hermes-agent", "hermes"), detect_project_paths=(".hermes",), detect_global_paths=(".hermes",)),
    "junie": agent_target("Junie", ".junie/skills", ".junie/skills", detect_commands=("junie",), detect_project_paths=(".junie",), detect_global_paths=(".junie",)),
    "iflow-cli": agent_target("iFlow CLI", ".iflow/skills", ".iflow/skills", detect_commands=("iflow", "iflow-cli"), detect_project_paths=(".iflow",), detect_global_paths=(".iflow",)),
    "kilo": agent_target("Kilo Code", ".kilocode/skills", ".kilocode/skills", detect_commands=("kilo",), detect_project_paths=(".kilocode",), detect_global_paths=(".kilocode",)),
    "kiro-cli": agent_target("Kiro CLI", ".kiro/skills", ".kiro/skills", detect_commands=("kiro", "kiro-cli"), detect_project_paths=(".kiro",), detect_global_paths=(".kiro",)),
    "kode": agent_target("Kode", ".kode/skills", ".kode/skills", detect_commands=("kode",), detect_project_paths=(".kode",), detect_global_paths=(".kode",)),
    "mcpjam": agent_target("MCPJam", ".mcpjam/skills", ".mcpjam/skills", detect_commands=("mcpjam",), detect_project_paths=(".mcpjam",), detect_global_paths=(".mcpjam",)),
    "mistral-vibe": agent_target("Mistral Vibe", ".vibe/skills", ".vibe/skills", detect_commands=("mistral-vibe",), detect_project_paths=(".vibe",), detect_global_paths=(".vibe",)),
    "mux": agent_target("Mux", ".mux/skills", ".mux/skills", detect_commands=("mux",), detect_project_paths=(".mux",), detect_global_paths=(".mux",)),
    "opencode": agent_target("OpenCode", ".agents/skills", ".config/opencode/skills", detect_commands=("opencode",), detect_global_paths=(".config/opencode",)),
    "openhands": agent_target("OpenHands", ".openhands/skills", ".openhands/skills", detect_commands=("openhands",), detect_project_paths=(".openhands",), detect_global_paths=(".openhands",)),
    "pi": agent_target("Pi", ".pi/skills", ".pi/agent/skills", detect_commands=("pi",), detect_project_paths=(".pi",), detect_global_paths=(".pi",)),
    "qoder": agent_target("Qoder", ".qoder/skills", ".qoder/skills", detect_commands=("qoder",), detect_project_paths=(".qoder",), detect_global_paths=(".qoder",)),
    "qwen-code": agent_target("Qwen Code", ".qwen/skills", ".qwen/skills", aliases=("qwen",), detect_commands=("qwen",), detect_project_paths=(".qwen",), detect_global_paths=(".qwen",)),
    "rovodev": agent_target("Rovo Dev", ".rovodev/skills", ".rovodev/skills", detect_commands=("rovodev", "rovo"), detect_project_paths=(".rovodev",), detect_global_paths=(".rovodev",)),
    "roo": agent_target("Roo Code", ".roo/skills", ".roo/skills", detect_commands=("roo",), detect_project_paths=(".roo",), detect_global_paths=(".roo",)),
    "tabnine-cli": agent_target("Tabnine CLI", ".tabnine/agent/skills", ".tabnine/agent/skills", detect_commands=("tabnine", "tabnine-cli"), detect_project_paths=(".tabnine",), detect_global_paths=(".tabnine",)),
    "trae": agent_target("Trae", ".trae/skills", ".trae/skills", detect_commands=("trae",), detect_project_paths=(".trae",), detect_global_paths=(".trae",)),
    "trae-cn": agent_target("Trae CN", ".trae/skills", ".trae-cn/skills", detect_commands=("trae-cn",), detect_global_paths=(".trae-cn",)),
    "windsurf": agent_target("Windsurf", ".windsurf/skills", ".codeium/windsurf/skills", detect_commands=("windsurf",), detect_project_paths=(".windsurf",), detect_global_paths=(".codeium", ".codeium/windsurf")),
    "zencoder": agent_target("Zencoder", ".zencoder/skills", ".zencoder/skills", detect_commands=("zencoder",), detect_project_paths=(".zencoder",), detect_global_paths=(".zencoder",)),
    "neovate": agent_target("Neovate", ".neovate/skills", ".neovate/skills", detect_commands=("neovate",), detect_project_paths=(".neovate",), detect_global_paths=(".neovate",)),
    "pochi": agent_target("Pochi", ".pochi/skills", ".pochi/skills", detect_commands=("pochi",), detect_project_paths=(".pochi",), detect_global_paths=(".pochi",)),
    "adal": agent_target("AdaL", ".adal/skills", ".adal/skills", detect_commands=("adal",), detect_project_paths=(".adal",), detect_global_paths=(".adal",)),
}
SUPPORTED_TOOLS = list(AGENT_TARGETS)
TOOL_ALIASES = {alias: tool for tool, target in AGENT_TARGETS.items() for alias in target.aliases}


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

    if destination.is_symlink():
        destination.unlink()
    elif destination.exists():
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
    if destination.is_symlink():
        destination.unlink()
    elif destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    copy_file(source_skill, destination / "SKILL.md")
    for script_name in ("gis_convert.py", "check_env.py"):
        copy_file(repo_root / "scripts" / script_name, destination / "scripts" / script_name)
    copy_directory(repo_root / "references", destination / "references")
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
    return TOOL_ALIASES.get(normalized, normalized)


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

    detected: dict[str, bool] = {}
    for tool, target in AGENT_TARGETS.items():
        detected[tool] = (
            any(os.environ.get(name) for name in target.detect_env_vars)
            or any(_command_exists(command) for command in target.detect_commands)
            or any((context.home / path).exists() for path in target.detect_global_paths)
            or any((context.project_dir / path).exists() for path in target.detect_project_paths)
        )
    return detected


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
    if tool == "github-copilot":
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


def _relative_path(root: Path, relative: str) -> Path:
    return root / Path(relative)


def skill_package_destination(tool: str, context: InstallContext) -> Path:
    """Return the standard skill package directory for one agent target."""

    target = AGENT_TARGETS[tool]
    if context.scope == "project":
        base = _relative_path(context.project_dir, target.project_path)
    elif tool == "codex" and os.environ.get("CODEX_HOME"):
        base = Path(os.environ["CODEX_HOME"]) / "skills"
    else:
        base = _relative_path(context.home, target.global_path)
    return base / "gis-convert"


def generated_entry_destination(tool: str, context: InstallContext) -> tuple[Path, str] | None:
    """Return the optional generated integration entry for tools that need one."""

    if tool == "qwen-code":
        return (
            _user_or_project(
                context,
                context.home / ".qwen" / "agents" / "gis-convert.md",
                context.project_dir / ".qwen" / "agents" / "gis-convert.md",
            ),
            "Qwen Code entry",
        )
    if tool == "gemini-cli":
        return (
            _user_or_project(
                context,
                context.home / ".gemini" / "commands" / "gis-convert.toml",
                context.project_dir / ".gemini" / "commands" / "gis-convert.toml",
            ),
            "Gemini CLI command",
        )
    if tool == "cursor":
        return (
            _user_or_project(
                context,
                context.home / ".cursor" / "rules" / "gis-convert.mdc",
                context.project_dir / ".cursor" / "rules" / "gis-convert.mdc",
            ),
            "Cursor rule",
        )
    if tool == "github-copilot":
        return (
            _user_or_project(
                context,
                context.home / ".github" / "instructions" / "gis-convert.instructions.md",
                context.project_dir / ".github" / "instructions" / "gis-convert.instructions.md",
            ),
            "GitHub Copilot instructions",
        )
    if tool == "aider":
        return (
            _user_or_project(
                context,
                context.home / ".aider.conf.yml",
                context.project_dir / ".aider.conf.yml",
            ),
            "Aider config",
        )
    if tool == "continue":
        return (
            _user_or_project(
                context,
                context.home / ".continue" / "rules" / "gis-convert-rule.md",
                context.project_dir / ".continue" / "rules" / "gis-convert-rule.md",
            ),
            "Continue rule",
        )
    if tool == "opencode":
        return (
            _user_or_project(
                context,
                context.home / ".config" / "opencode" / "agents" / "gis-convert.md",
                context.project_dir / ".opencode" / "agents" / "gis-convert.md",
            ),
            "OpenCode agent",
        )
    if tool == "windsurf":
        return (
            _user_or_project(
                context,
                context.home / ".windsurfrules",
                context.project_dir / ".windsurfrules",
            ),
            "Windsurf rules",
        )
    return None


def dedupe_operations(operations: Iterable[InstallOperation]) -> list[InstallOperation]:
    """Remove duplicate destination operations while preserving the first target."""

    deduped: list[InstallOperation] = []
    seen: set[tuple[str, Path]] = set()
    for operation in operations:
        key = (operation.kind, operation.destination)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(operation)
    return deduped


def build_tool_operations(tools: Iterable[str], context: InstallContext) -> list[InstallOperation]:
    """Build copy operations for selected tools."""

    repo = context.repo_root
    operations: list[InstallOperation] = []
    for tool in tools:
        target = AGENT_TARGETS[tool]
        package_dir = skill_package_destination(tool, context)
        add_skill_package_operation(operations, tool, repo, package_dir, f"{target.display_name} skill package")
        generated_entry = generated_entry_destination(tool, context)
        if generated_entry is not None:
            entry, description = generated_entry
            add_generated_entry_operation(operations, tool, repo, entry, package_dir, description)
    return dedupe_operations(operations)


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
        if operation.destination.is_symlink():
            operation.destination.unlink()
            return 0
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
        str(context.repo_root / "install" / "install_deps.py"),
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


def python_dependency_conda_path() -> str | None:
    """Return a conda or mamba executable when the gis-convert environment exists."""

    managers = find_package_managers(["mamba", "conda"])
    conda = managers.get("mamba") or managers.get("conda")
    if conda and conda_env_exists(CONDA_ENV_NAME, conda):
        return conda
    return None


def build_python_dependency_install_command() -> list[str]:
    """Build the command used to install Python runtime packages."""

    conda = python_dependency_conda_path()
    if conda:
        return [conda, "run", "-n", CONDA_ENV_NAME, "python", "-m", "pip", "install", *PYTHON_PACKAGES.values()]
    return [sys.executable, "-m", "pip", "install", *PYTHON_PACKAGES.values()]


def python_dependency_verify_command() -> str:
    """Return the recommended command for checking installed Python packages."""

    conda = python_dependency_conda_path()
    if conda:
        return shlex.join([conda, "run", "-n", CONDA_ENV_NAME, "python", "scripts/check_env.py"])
    return shlex.join([sys.executable, "scripts/check_env.py"])


def print_python_dependency_install_plan() -> None:
    """Print the recommended Python package installation command."""

    command = build_python_dependency_install_command()
    print("Recommended Python package install plan:")
    print("  " + shlex.join(command))


def run_python_dependency_install(context: InstallContext, yes: bool) -> int:
    """Install Python package dependencies required by runtime conversions."""

    command = build_python_dependency_install_command()
    prefix = "DRY-RUN" if context.dry_run else "INSTALL"
    print(f"[{prefix}] python packages: {shlex.join(command)}")
    if context.dry_run:
        return 0
    if not yes:
        print("install.py: refusing to install Python packages without explicit confirmation.", file=sys.stderr)
        return 1
    if command[0] == sys.executable:
        pip_check = subprocess.run([sys.executable, "-m", "pip", "--version"], text=True, capture_output=True, check=False)
        if pip_check.returncode != 0:
            print(
                "install.py: current Python does not provide pip. Install pip for this Python, "
                "or install dependencies with conda so pygeoconv can be installed into the gis-convert environment.",
                file=sys.stderr,
            )
            return pip_check.returncode
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
            print(f"Native dependency installer finished. Verify with: {python_dependency_verify_command()}")
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
                print(f"Native dependency installer finished. Verify with: {python_dependency_verify_command()}")
        elif require_deps:
            print("Required native GIS dependencies are missing. Re-run with --yes, --with-deps, or install them manually.", file=sys.stderr)
            return 1
        else:
            print("Agent integration can still be installed, but GIS conversion is limited until required dependencies are installed.")
            print("Install later with: ./install/install.sh --deps-only")

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
                print(f"PDAL installer finished. Verify with: {python_dependency_verify_command()}")
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
                print(f"Python package installer finished. Verify with: {python_dependency_verify_command()}")
        elif require_deps:
            print("Python package dependencies are missing. Re-run with --yes or install them manually.", file=sys.stderr)
            return 1
        else:
            print("Agent integration can still be installed. ESRIJSON output is limited until pygeoconv is installed.")
    return 0


def prompt_for_tools(detected: dict[str, bool], input_fn: Callable[[str], str] = input) -> list[str]:
    """Prompt for an interactive tool selection."""

    interactive_order = ["claude-code", *[tool for tool in SUPPORTED_TOOLS if tool != "claude-code"]]
    detected_tools = [tool for tool in interactive_order if detected.get(tool)]
    if not detected_tools:
        print("No installed agents were detected.")
        print("Use --install claude-code, --install codex, or --install all to choose a target explicitly.")
        return []

    print("Detected agents:")
    for index, tool in enumerate(detected_tools, start=1):
        print(f"  {index}. {tool}")
    print("")

    while True:
        answer = input_fn("Select agents to install (comma-separated numbers, a=all, q=cancel, Enter=all): ").strip().lower()
        if answer in {"", "a", "all"}:
            return detected_tools
        if answer in {"q", "quit"}:
            return []

        selected: list[str] = []
        seen: set[int] = set()
        invalid = False
        for part in answer.split(","):
            value = part.strip()
            if not value.isdigit():
                invalid = True
                break
            index = int(value)
            if index < 1 or index > len(detected_tools) or index in seen:
                invalid = True
                break
            seen.add(index)
            selected.append(detected_tools[index - 1])
        if selected and not invalid:
            return selected
        print("Invalid selection. Enter numbers from the list, separated by commas, or q to cancel.")


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

    try:
        tools = parse_tool_selection(args.uninstall if uninstalling else args.install, detected=detected)
    except ValueError as exc:
        print(f"install.py: {exc}", file=sys.stderr)
        return 2

    if not tools and not uninstalling and not context.deps_only:
        if args.interactive or (not args.no_interactive and sys.stdin.isatty() and sys.stdout.isatty()):
            tools = prompt_for_tools(detected, input_fn=input_fn or input)
        else:
            print("No interactive terminal is available, so no agent was selected.", file=sys.stderr)
            print("Run ./install/install.sh in a terminal, or pass --install <agent|detected|all>.", file=sys.stderr)
            return 2

    if not tools and not context.deps_only:
        print("No tools selected or detected. Use --install claude-code, --install codex, --install all, or --interactive.")
        return 0

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

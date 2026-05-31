#!/usr/bin/env python3
"""Cross-platform dependency installer planner for gis-convert."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


CONDA_PACKAGES = [
    "python=3.11",
    "gdal",
    "proj",
    "pdal",
    "pyproj",
    "geopandas",
    "shapely",
    "fiona",
]
CONDA_REQUIRED_PACKAGES = ["python=3.11", "gdal", "proj", "pyproj", "geopandas", "shapely", "fiona"]
CONDA_EXISTING_ENV_REQUIRED_PACKAGES = ["gdal", "proj", "pyproj", "geopandas", "shapely", "fiona"]
CONDA_OPTIONAL_PDAL_PACKAGES = ["pdal"]
BREW_REQUIRED_PACKAGES = ["gdal", "proj"]
BREW_OPTIONAL_PDAL_PACKAGES = ["pdal"]


@dataclass(frozen=True)
class PlatformInfo:
    """Normalized operating system information used to choose install commands."""

    system: str
    machine: str
    release: str
    os_release_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "system": self.system,
            "machine": self.machine,
            "release": self.release,
            "os_release_id": self.os_release_id,
        }


@dataclass(frozen=True)
class InstallPlan:
    """Install commands and notes for one dependency installation strategy."""

    strategy: str
    commands: list[list[str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "commands": self.commands,
            "notes": self.notes,
            "requires_confirmation": self.requires_confirmation,
        }


def read_os_release_id(path: Path = Path("/etc/os-release")) -> str | None:
    """Read Linux distribution ID from /etc/os-release when available."""

    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("ID="):
            return line.split("=", 1)[1].strip().strip('"').lower()
    return None


def detect_platform(
    system: str | None = None,
    machine: str | None = None,
    release: str | None = None,
    os_release_id: str | None = None,
) -> PlatformInfo:
    """Return normalized platform details with optional overrides for tests."""

    resolved_system = system or platform.system()
    resolved_machine = machine or platform.machine()
    resolved_release = release or platform.release()
    resolved_os_release_id = os_release_id
    if resolved_system == "Linux" and resolved_os_release_id is None:
        resolved_os_release_id = read_os_release_id()
    return PlatformInfo(
        system=resolved_system,
        machine=resolved_machine,
        release=resolved_release,
        os_release_id=resolved_os_release_id,
    )


def find_package_managers(names: Iterable[str]) -> dict[str, str]:
    """Locate package manager executables by name."""

    found: dict[str, str] = {}
    for name in names:
        path = shutil.which(name)
        if path:
            found[name] = path
    return found


def package_names_for_group(group: str, existing_conda_env: bool = False, system_package_manager: str | None = None) -> list[str]:
    """Return dependency package names for a required/optional/all group."""

    if system_package_manager == "brew":
        required = BREW_REQUIRED_PACKAGES
        optional = BREW_OPTIONAL_PDAL_PACKAGES
    else:
        required = CONDA_EXISTING_ENV_REQUIRED_PACKAGES if existing_conda_env else CONDA_REQUIRED_PACKAGES
        optional = CONDA_OPTIONAL_PDAL_PACKAGES
    if group == "required":
        return list(required)
    if group == "optional-pdal":
        return list(optional)
    if group == "all":
        if system_package_manager == "brew":
            return [*required, *optional]
        if existing_conda_env:
            return [*required, *optional]
        return list(CONDA_PACKAGES)
    raise ValueError(f"Unsupported dependency group: {group}")


def conda_env_exists(env_name: str, conda_path: str | None = None) -> bool:
    """Return true when a conda environment appears to exist locally."""

    path_candidate = Path(conda_path).resolve().parents[1] / "envs" / env_name if conda_path else None
    if path_candidate and path_candidate.exists():
        return True
    return False


def _conda_command(
    package_manager_paths: dict[str, str],
    env_name: str,
    dependency_group: str,
    existing_env: bool,
) -> list[str] | None:
    conda = package_manager_paths.get("mamba") or package_manager_paths.get("conda")
    if not conda:
        return None
    packages = package_names_for_group(dependency_group, existing_conda_env=existing_env)
    if existing_env:
        return [conda, "install", "-n", env_name, "-c", "conda-forge", *packages, "-y"]
    return [conda, "create", "-n", env_name, "-c", "conda-forge", *packages, "-y"]


def _linux_system_plan(system: PlatformInfo, package_manager_paths: dict[str, str], dependency_group: str) -> InstallPlan:
    distro = (system.os_release_id or "").lower()
    if dependency_group == "optional-pdal":
        base_apt = ["pdal"]
        base_dnf = ["pdal"]
        base_yum = ["pdal"]
        base_pacman = ["pdal"]
        base_apk = ["pdal"]
    else:
        pdal_packages = ["pdal"] if dependency_group == "all" else []
        base_apt = ["gdal-bin", "libgdal-dev", "proj-bin", "libproj-dev", "python3-gdal", *pdal_packages]
        base_dnf = ["gdal", "gdal-devel", "proj", "proj-devel", "python3-gdal", *pdal_packages]
        base_yum = ["gdal", "gdal-devel", "proj", "proj-devel", *pdal_packages]
        base_pacman = ["gdal", "proj", *pdal_packages]
        base_apk = ["gdal", "gdal-dev", "proj", "proj-dev", *pdal_packages]
    if distro in {"debian", "ubuntu", "linuxmint", "pop"} and "apt-get" in package_manager_paths:
        return InstallPlan(
            strategy="system",
            commands=[
                [
                    "sudo",
                    package_manager_paths["apt-get"],
                    "install",
                    *base_apt,
                ]
            ],
            notes=["APT packages do not include every optional GDAL/PDAL driver. Use conda-forge for best coverage."],
            requires_confirmation=True,
        )
    if distro in {"fedora"} and "dnf" in package_manager_paths:
        return InstallPlan(
            strategy="system",
            commands=[["sudo", package_manager_paths["dnf"], "install", *base_dnf]],
            notes=["Install PDAL separately if your distribution repository provides it."],
            requires_confirmation=True,
        )
    if distro in {"rhel", "centos", "rocky", "almalinux"} and "yum" in package_manager_paths:
        return InstallPlan(
            strategy="system",
            commands=[["sudo", package_manager_paths["yum"], "install", *base_yum]],
            notes=["Enable EPEL or an OSGeo repository when GDAL/PDAL packages are missing."],
            requires_confirmation=True,
        )
    if distro in {"arch", "manjaro"} and "pacman" in package_manager_paths:
        return InstallPlan(
            strategy="system",
            commands=[["sudo", package_manager_paths["pacman"], "-S", *base_pacman]],
            requires_confirmation=True,
        )
    if distro in {"alpine"} and "apk" in package_manager_paths:
        return InstallPlan(
            strategy="system",
            commands=[["sudo", package_manager_paths["apk"], "add", *base_apk]],
            notes=["PDAL availability varies on Alpine; prefer conda-forge if point-cloud conversion is required."],
            requires_confirmation=True,
        )
    return InstallPlan(
        strategy="manual",
        notes=[
            f"No supported Linux package manager plan was found for distribution '{distro or 'unknown'}'.",
            "Install via conda-forge for the most reliable GDAL/PROJ/PDAL setup.",
        ],
    )


def build_install_plan(
    system: PlatformInfo,
    strategy: str = "auto",
    package_manager_paths: dict[str, str] | None = None,
    env_name: str = "gis-convert",
    dependency_group: str = "all",
    conda_env_exists: bool | None = None,
) -> InstallPlan:
    """Build an installation plan without executing it."""

    managers = package_manager_paths or {}
    if strategy in {"auto", "conda"}:
        conda_path = managers.get("mamba") or managers.get("conda")
        existing_env = conda_env_exists if conda_env_exists is not None else globals()["conda_env_exists"](env_name, conda_path)
        conda_command = _conda_command(managers, env_name, dependency_group, existing_env)
        if conda_command:
            action_note = (
                f"Activate the existing environment with: conda activate {env_name}"
                if existing_env
                else f"Activate the environment after installation with: conda activate {env_name}"
            )
            return InstallPlan(
                strategy="conda",
                commands=[conda_command],
                notes=[
                    action_note,
                    "This is the recommended cross-platform path for GDAL/PROJ/PDAL.",
                ],
            )
        if strategy == "conda":
            return InstallPlan(strategy="manual", notes=["Conda/Mamba was requested but no conda or mamba executable was found."])

    if strategy in {"auto", "system"} and system.system == "Darwin":
        brew = managers.get("brew")
        if brew:
            packages = package_names_for_group(dependency_group, system_package_manager="brew")
            return InstallPlan(
                strategy="system",
                commands=[[brew, "install", *packages]],
                notes=["Homebrew is convenient on macOS, but conda-forge usually gives more reproducible Python bindings."],
            )
        return InstallPlan(strategy="manual", notes=["Homebrew was not found. Install Homebrew first or use conda-forge."])

    if strategy in {"auto", "system"} and system.system == "Linux":
        return _linux_system_plan(system, managers, dependency_group)

    if system.system == "Windows":
        return InstallPlan(
            strategy="manual",
            notes=[
                "Conda/Mamba is the recommended Windows path: conda create -n gis-convert -c conda-forge python=3.11 gdal proj pdal pyproj geopandas shapely fiona -y",
                "OSGeo4W is the preferred system-level fallback. Run gis-convert from OSGeo4W Shell or add its bin directory to PATH.",
                "vcpkg, winget, and choco are advanced options and are not used automatically.",
            ],
        )

    return InstallPlan(strategy="manual", notes=[f"Unsupported platform: {system.system}. Use conda-forge if available."])


def apply_plan(plan: InstallPlan, assume_yes: bool = False) -> int:
    """Execute an install plan only after explicit confirmation."""

    if not plan.commands:
        print("No executable install commands are available for this plan.", file=sys.stderr)
        return 1
    if plan.requires_confirmation and not assume_yes:
        print("This plan uses elevated/system package commands. Re-run with --yes to confirm.", file=sys.stderr)
        return 2
    for command in plan.commands:
        print("+ " + " ".join(command))
        subprocess.run(command, check=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for dependency installation planning."""

    parser = argparse.ArgumentParser(description="Plan or apply gis-convert native dependency installation.")
    parser.add_argument("--strategy", choices=["auto", "conda", "system"], default="auto")
    parser.add_argument("--env-name", default="gis-convert")
    parser.add_argument("--dependency-group", choices=["required", "optional-pdal", "all"], default="all")
    parser.add_argument("--apply", action="store_true", help="Execute the generated install commands.")
    parser.add_argument("--yes", action="store_true", help="Confirm commands that require elevated/system package access.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    managers = find_package_managers(["mamba", "conda", "brew", "apt-get", "dnf", "yum", "pacman", "apk"])
    system = detect_platform()
    plan = build_install_plan(
        system,
        strategy=args.strategy,
        package_manager_paths=managers,
        env_name=args.env_name,
        dependency_group=args.dependency_group,
    )
    payload = {"platform": system.to_dict(), "package_managers": managers, "plan": plan.to_dict()}

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Platform: {system.system} {system.release} ({system.machine})")
        print(f"Strategy: {plan.strategy}")
        for command in plan.commands:
            print("Command: " + " ".join(command))
        for note in plan.notes:
            print("Note: " + note)
        if not args.apply:
            print("Dry run only. Re-run with --apply to execute commands.")

    if args.apply:
        return apply_plan(plan, assume_yes=args.yes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

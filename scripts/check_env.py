#!/usr/bin/env python3
"""Environment inspection for gis-convert native GIS dependencies."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ToolStatus:
    """Availability and version information for one external tool."""

    name: str
    path: str | None
    version: str | None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.path is not None and self.error is None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
            "version": self.version,
            "available": self.available,
            "error": self.error,
        }


@dataclass(frozen=True)
class DriverStatus:
    """Read/write capability for one GDAL/OGR driver."""

    name: str
    read: bool
    write: bool
    raw_flags: str
    description: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "read": self.read,
            "write": self.write,
            "raw_flags": self.raw_flags,
            "description": self.description,
        }


@dataclass(frozen=True)
class PackageStatus:
    """Availability and version information for one Python package."""

    name: str
    version: str | None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.version is not None and self.error is None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "available": self.available,
            "error": self.error,
        }


VERSION_ARGS = {
    "gdalinfo": ["--version"],
    "ogr2ogr": ["--version"],
    "ogrinfo": ["--version"],
    "proj": [],
    "pdal": ["--version"],
}
PYTHON_PACKAGES = ["pygeoconv"]


def run_command(command: list[str]) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, and stderr."""

    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def inspect_tool(name: str) -> ToolStatus:
    """Inspect one executable on PATH."""

    path = shutil.which(name)
    if not path:
        return ToolStatus(name=name, path=None, version=None, error="not found")
    args = VERSION_ARGS.get(name, ["--version"])
    command = [path, *args] if args else [path]
    try:
        code, stdout, stderr = run_command(command)
    except OSError as exc:
        return ToolStatus(name=name, path=path, version=None, error=str(exc))
    version = stdout.splitlines()[0] if stdout else stderr.splitlines()[0] if stderr else None
    if code != 0 and not version:
        return ToolStatus(name=name, path=path, version=None, error=f"version command exited with {code}")
    return ToolStatus(name=name, path=path, version=version)


def parse_ogrinfo_formats(output: str) -> dict[str, DriverStatus]:
    """Parse `ogrinfo --formats` output into read/write driver statuses."""

    formats: dict[str, DriverStatus] = {}
    pattern = re.compile(r"^\s*(?P<name>.+?)\s+-.*?\((?P<flags>[^)]*)\):\s*(?P<description>.+)$")
    for line in output.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        flags = match.group("flags")
        name = match.group("name").strip()
        formats[name] = DriverStatus(
            name=name,
            read="r" in flags,
            write="w" in flags,
            raw_flags=flags,
            description=match.group("description").strip(),
        )
    return formats


def inspect_ogr_drivers(ogrinfo_path: str | None = None) -> dict[str, DriverStatus]:
    """Return current OGR driver capabilities, or an empty map if unavailable."""

    path = ogrinfo_path or shutil.which("ogrinfo")
    if not path:
        return {}
    code, stdout, stderr = run_command([path, "--formats"])
    if code != 0:
        print(f"Could not inspect OGR formats: {stderr}", file=sys.stderr)
        return {}
    return parse_ogrinfo_formats(stdout)


def inspect_python_package(name: str) -> PackageStatus:
    """Inspect one importable Python package by distribution name."""

    try:
        version = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return PackageStatus(name=name, version=None, error="not found")
    return PackageStatus(name=name, version=version)


def inspect_environment(tool_names: Iterable[str] | None = None, package_names: Iterable[str] | None = None) -> dict[str, object]:
    """Inspect platform details, native tools, and OGR drivers."""

    names = list(tool_names or ["gdalinfo", "ogrinfo", "ogr2ogr", "proj", "pdal"])
    packages = list(package_names or PYTHON_PACKAGES)
    tools = {name: inspect_tool(name).to_dict() for name in names}
    python_packages = {name: inspect_python_package(name).to_dict() for name in packages}
    drivers = {name: status.to_dict() for name, status in inspect_ogr_drivers().items()}
    return {
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        "tools": tools,
        "python_packages": python_packages,
        "ogr_drivers": drivers,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for dependency and driver inspection."""

    parser = argparse.ArgumentParser(description="Inspect GDAL/OGR, PROJ, and PDAL availability.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--require", nargs="*", default=[], help="Tool names that must be available.")
    args = parser.parse_args(argv)

    report = inspect_environment()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        platform_info = report["platform"]
        print(
            f"Platform: {platform_info['system']} {platform_info['release']} "
            f"({platform_info['machine']}), Python {platform_info['python']}"
        )
        print("Tools:")
        for tool in report["tools"].values():
            marker = "ok" if tool["available"] else "missing"
            print(f"  - {tool['name']}: {marker} path={tool['path']} version={tool['version']}")
        print("Python packages:")
        for package in report["python_packages"].values():
            marker = "ok" if package["available"] else "missing"
            print(f"  - {package['name']}: {marker} version={package['version']}")
        print(f"OGR drivers: {len(report['ogr_drivers'])}")

    missing = [name for name in args.require if not report["tools"].get(name, {}).get("available")]
    if missing:
        print("Missing required tools: " + ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

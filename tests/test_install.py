import os
import subprocess
import sys
from pathlib import Path

from scripts.install import (
    InstallContext,
    SUPPORTED_TOOLS,
    build_tool_operations,
    confirm_dependency_install,
    confirm_optional_pdal_install,
    confirm_python_dependency_install,
    detect_tools,
    handle_native_dependencies,
    summarize_native_dependencies,
    parse_tool_selection,
)


MINIMAL_PACKAGE_FILES = [
    "SKILL.md",
    "scripts/gis_convert.py",
    "scripts/check_env.py",
    "references/format-support.md",
    "references/3d-workflows.md",
]
EXCLUDED_PACKAGE_PATHS = [
    "README.md",
    "README.zh-CN.md",
    ".git",
    "tests",
    "adapters",
    "agents",
    "commands",
    "skills",
]


def make_context(tmp_path, dry_run=True, scope="user"):
    repo_root = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    project_dir = tmp_path / "project"
    home.mkdir()
    project_dir.mkdir()
    return InstallContext(
        repo_root=repo_root,
        home=home,
        project_dir=project_dir,
        scope=scope,
        dry_run=dry_run,
        with_deps=False,
        deps_only=False,
    )


def assert_minimal_skill_package(package_dir):
    for relative_path in MINIMAL_PACKAGE_FILES:
        assert (package_dir / relative_path).exists(), relative_path
    for relative_path in EXCLUDED_PACKAGE_PATHS:
        assert not (package_dir / relative_path).exists(), relative_path


def test_parse_tool_selection_accepts_comma_list():
    assert parse_tool_selection("codex,claude-code") == ["codex", "claude-code"]


def test_parse_tools_expands_all_in_supported_order():
    assert parse_tool_selection("all") == [
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


def test_detected_selection_uses_detected_tool_set(tmp_path):
    context = make_context(tmp_path)
    detected = {"codex": True, "claude-code": False, "cursor": True}

    assert parse_tool_selection("detected", detected=detected) == ["codex", "cursor"]


def test_dry_run_builds_codex_and_claude_operations_without_writing(tmp_path):
    context = make_context(tmp_path, dry_run=True)

    operations = build_tool_operations(["codex", "claude-code"], context)

    destinations = [operation.destination for operation in operations]
    assert context.home / ".codex" / "skills" / "gis-convert" in destinations
    assert context.home / ".claude" / "skills" / "gis-convert" in destinations
    assert {operation.kind for operation in operations} == {"skill-package"}
    assert not (context.home / ".codex").exists()
    assert not (context.home / ".claude").exists()


def test_project_scope_uses_project_directory_for_claude_and_cursor(tmp_path):
    context = make_context(tmp_path, dry_run=True, scope="project")

    operations = build_tool_operations(["claude-code", "cursor"], context)

    destinations = [operation.destination for operation in operations]
    assert context.project_dir / ".claude" / "skills" / "gis-convert" in destinations
    assert context.project_dir / ".cursor" / "rules" / "gis-convert.mdc" in destinations


def test_actual_install_copies_codex_skill_to_temp_home(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env.pop("CODEX_HOME", None)

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/install.py",
            "--install",
            "codex",
            "--no-interactive",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert_minimal_skill_package(tmp_path / "home" / ".codex" / "skills" / "gis-convert")


def test_actual_install_all_writes_minimal_packages_for_every_tool(tmp_path):
    home = tmp_path / "home"
    project_dir = tmp_path / "project"
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CODEX_HOME", None)

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/install.py",
            "--install",
            "all",
            "--skip-deps-check",
            "--no-interactive",
            "--project-dir",
            str(project_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    package_dirs = {
        "codex": home / ".codex" / "skills" / "gis-convert",
        "claude-code": home / ".claude" / "skills" / "gis-convert",
        "qwen-code": home / ".qwen" / "skills" / "gis-convert",
        "gemini-cli": home / ".gemini" / "skills" / "gis-convert",
        "cursor": home / ".cursor" / "skills" / "gis-convert",
        "copilot": home / ".github" / "skills" / "gis-convert",
        "aider": home / ".aider" / "skills" / "gis-convert",
        "continue": home / ".continue" / "skills" / "gis-convert",
        "opencode": project_dir / ".opencode" / "skills" / "gis-convert",
        "windsurf": project_dir / ".windsurf" / "skills" / "gis-convert",
    }
    assert set(package_dirs) == set(SUPPORTED_TOOLS)
    for package_dir in package_dirs.values():
        assert_minimal_skill_package(package_dir)


def test_uninstall_removes_codex_skill_from_temp_home(tmp_path):
    home = tmp_path / "home"
    skill_dir = home / ".codex" / "skills" / "gis-convert"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test", encoding="utf-8")
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CODEX_HOME", None)

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/install.py",
            "--uninstall",
            "codex",
            "--no-interactive",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "UNINSTALL" in result.stdout
    assert not skill_dir.exists()


def test_uninstall_dry_run_does_not_remove_codex_skill(tmp_path):
    home = tmp_path / "home"
    skill_dir = home / ".codex" / "skills" / "gis-convert"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test", encoding="utf-8")
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CODEX_HOME", None)

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/install.py",
            "--uninstall",
            "codex",
            "--dry-run",
            "--no-interactive",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "DRY-RUN" in result.stdout
    assert skill_dir.exists()


def test_uninstall_missing_target_succeeds_with_skip(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env.pop("CODEX_HOME", None)

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/install.py",
            "--uninstall",
            "codex",
            "--no-interactive",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "SKIP" in result.stdout


def test_uninstall_refuses_wrong_target_type(tmp_path):
    home = tmp_path / "home"
    target = home / ".codex" / "skills" / "gis-convert"
    target.parent.mkdir(parents=True)
    target.write_text("not a directory", encoding="utf-8")
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CODEX_HOME", None)

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/install.py",
            "--uninstall",
            "codex",
            "--no-interactive",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "refusing to remove non-directory target" in result.stderr
    assert target.exists()


def test_dry_run_cli_does_not_create_files(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/install.py",
            "--install",
            "codex,claude-code",
            "--dry-run",
            "--no-interactive",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "DRY-RUN" in result.stdout
    assert not (tmp_path / "home").exists()


def test_old_tool_arguments_are_rejected():
    for old_arg in ("--tools", "--tool"):
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "scripts/install.py",
                old_arg,
                "codex",
            ],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 2
        assert "unrecognized arguments" in result.stderr


def test_install_and_uninstall_are_mutually_exclusive():
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/install.py",
            "--install",
            "codex",
            "--uninstall",
            "codex",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2


def test_uninstall_rejects_dependency_install_flags():
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/install.py",
            "--uninstall",
            "codex",
            "--with-deps",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "cannot be combined" in result.stderr


def test_detect_tools_uses_environment_and_project_markers(tmp_path):
    context = make_context(tmp_path)
    (context.home / ".claude").mkdir()
    (context.project_dir / ".cursor").mkdir()

    detected = detect_tools(context)

    assert detected["claude-code"] is True
    assert detected["cursor"] is True


def test_shell_wrapper_help_runs():
    result = subprocess.run(
        ["bash", "scripts/install.sh", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--install" in result.stdout
    assert "--uninstall" in result.stdout
    assert "--tools" not in result.stdout


def test_powershell_wrapper_contains_install_parameters():
    text = (Path(__file__).resolve().parents[1] / "scripts" / "install.ps1").read_text(encoding="utf-8")

    assert "Install" in text
    assert "Uninstall" in text
    assert "Tools" not in text
    assert "Tool" not in text
    assert "install.py" in text


def test_dependency_summary_splits_required_and_optional_missing():
    report = {
        "tools": {
            "gdalinfo": {"available": True, "path": "/bin/gdalinfo", "version": "GDAL 3.9"},
            "ogrinfo": {"available": False, "path": None, "version": None},
            "ogr2ogr": {"available": False, "path": None, "version": None},
            "proj": {"available": True, "path": "/bin/proj", "version": "Rel. 9.4"},
            "pdal": {"available": False, "path": None, "version": None},
        }
    }

    summary = summarize_native_dependencies(report)

    assert summary.required_missing == ["ogrinfo", "ogr2ogr"]
    assert summary.optional_missing == ["pdal"]
    assert summary.has_required_missing is True


def test_dependency_summary_detects_missing_python_package():
    report = {
        "tools": {
            "gdalinfo": {"available": True},
            "ogrinfo": {"available": True},
            "ogr2ogr": {"available": True},
            "proj": {"available": True},
            "pdal": {"available": True},
        },
        "python_packages": {"pygeoconv": {"available": False, "version": None}},
    }

    summary = summarize_native_dependencies(report)

    assert summary.required_missing == []
    assert summary.optional_missing == []
    assert summary.python_missing == ["pygeoconv"]
    assert summary.has_missing is True


def test_missing_only_pdal_does_not_count_as_required_missing():
    report = {
        "tools": {
            "gdalinfo": {"available": True},
            "ogrinfo": {"available": True},
            "ogr2ogr": {"available": True},
            "proj": {"available": True},
            "pdal": {"available": False},
        }
    }

    summary = summarize_native_dependencies(report)

    assert summary.required_missing == []
    assert summary.optional_missing == ["pdal"]
    assert summary.has_required_missing is False


def test_confirm_dependency_install_accepts_only_yes():
    assert confirm_dependency_install(lambda _: "y") is True
    assert confirm_dependency_install(lambda _: "yes") is True
    assert confirm_dependency_install(lambda _: "n") is False
    assert confirm_dependency_install(lambda _: "") is False


def test_confirm_optional_pdal_install_accepts_only_yes():
    assert confirm_optional_pdal_install(lambda _: "y") is True
    assert confirm_optional_pdal_install(lambda _: "yes") is True
    assert confirm_optional_pdal_install(lambda _: "") is False


def test_confirm_python_dependency_install_accepts_only_yes():
    assert confirm_python_dependency_install(lambda _: "y") is True
    assert confirm_python_dependency_install(lambda _: "yes") is True
    assert confirm_python_dependency_install(lambda _: "") is False


def test_cli_dry_run_prints_dependency_status_by_default(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/install.py",
            "--install",
            "codex",
            "--dry-run",
            "--no-interactive",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Native GIS Dependencies" in result.stdout


def test_cli_can_skip_dependency_check(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/install.py",
            "--install",
            "codex",
            "--dry-run",
            "--skip-deps-check",
            "--no-interactive",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Native GIS Dependencies" not in result.stdout


def test_help_mentions_dependency_check_flags():
    result = subprocess.run(
        [sys.executable, "-B", "scripts/install.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert "--skip-deps-check" in result.stdout
    assert "--require-deps" in result.stdout


def test_handle_dependencies_runs_required_install_after_yes(monkeypatch, tmp_path):
    context = make_context(tmp_path, dry_run=False)
    report = {
        "tools": {
            "gdalinfo": {"available": False},
            "ogrinfo": {"available": True},
            "ogr2ogr": {"available": True},
            "proj": {"available": True},
            "pdal": {"available": True},
        }
    }
    calls = []

    monkeypatch.setattr("scripts.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("scripts.install.print_dependency_install_plan", lambda dependency_group="all": None)
    monkeypatch.setattr("scripts.install.run_dependency_install", lambda ctx, yes, dependency_group="all": calls.append((ctx, yes, dependency_group)) or 0)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    code = handle_native_dependencies(context, yes=False, require_deps=False, no_interactive=False, input_fn=lambda _: "y")

    assert code == 0
    assert calls == [(context, True, "required")]


def test_handle_dependencies_skips_install_after_no(monkeypatch, tmp_path):
    context = make_context(tmp_path, dry_run=False)
    report = {
        "tools": {
            "gdalinfo": {"available": False},
            "ogrinfo": {"available": True},
            "ogr2ogr": {"available": True},
            "proj": {"available": True},
            "pdal": {"available": True},
        }
    }
    calls = []

    monkeypatch.setattr("scripts.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("scripts.install.print_dependency_install_plan", lambda dependency_group="all": None)
    monkeypatch.setattr("scripts.install.run_dependency_install", lambda ctx, yes, dependency_group="all": calls.append((ctx, yes, dependency_group)) or 0)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    code = handle_native_dependencies(context, yes=False, require_deps=False, no_interactive=False, input_fn=lambda _: "n")

    assert code == 0
    assert calls == []


def test_require_deps_fails_when_required_dependency_missing(monkeypatch, tmp_path):
    context = make_context(tmp_path, dry_run=False)
    report = {
        "tools": {
            "gdalinfo": {"available": False},
            "ogrinfo": {"available": True},
            "ogr2ogr": {"available": True},
            "proj": {"available": True},
            "pdal": {"available": True},
        }
    }

    monkeypatch.setattr("scripts.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("scripts.install.print_dependency_install_plan", lambda dependency_group="all": None)

    code = handle_native_dependencies(context, yes=False, require_deps=True, no_interactive=True)

    assert code == 1


def test_yes_skips_prompt_and_runs_dependency_install(monkeypatch, tmp_path):
    context = make_context(tmp_path, dry_run=False)
    report = {
        "tools": {
            "gdalinfo": {"available": True},
            "ogrinfo": {"available": True},
            "ogr2ogr": {"available": True},
            "proj": {"available": True},
            "pdal": {"available": False},
        }
    }
    calls = []

    monkeypatch.setattr("scripts.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("scripts.install.print_dependency_install_plan", lambda dependency_group="all": None)
    monkeypatch.setattr("scripts.install.run_dependency_install", lambda ctx, yes, dependency_group="all": calls.append((ctx, yes, dependency_group)) or 0)

    code = handle_native_dependencies(context, yes=True, require_deps=False, no_interactive=True)

    assert code == 0
    assert calls == [(context, True, "optional-pdal")]


def test_only_missing_pdal_does_not_install_by_default(monkeypatch, tmp_path):
    context = make_context(tmp_path, dry_run=False)
    report = {
        "tools": {
            "gdalinfo": {"available": True},
            "ogrinfo": {"available": True},
            "ogr2ogr": {"available": True},
            "proj": {"available": True},
            "pdal": {"available": False},
        }
    }
    calls = []

    monkeypatch.setattr("scripts.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("scripts.install.print_dependency_install_plan", lambda dependency_group="all": None)
    monkeypatch.setattr("scripts.install.run_dependency_install", lambda ctx, yes, dependency_group="all": calls.append((ctx, yes, dependency_group)) or 0)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    code = handle_native_dependencies(context, yes=False, require_deps=False, no_interactive=False, input_fn=lambda _: "n")

    assert code == 0
    assert calls == []


def test_only_missing_pdal_installs_optional_group_after_yes(monkeypatch, tmp_path):
    context = make_context(tmp_path, dry_run=False)
    report = {
        "tools": {
            "gdalinfo": {"available": True},
            "ogrinfo": {"available": True},
            "ogr2ogr": {"available": True},
            "proj": {"available": True},
            "pdal": {"available": False},
        }
    }
    calls = []

    monkeypatch.setattr("scripts.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("scripts.install.print_dependency_install_plan", lambda dependency_group="all": None)
    monkeypatch.setattr("scripts.install.run_dependency_install", lambda ctx, yes, dependency_group="all": calls.append((ctx, yes, dependency_group)) or 0)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    code = handle_native_dependencies(context, yes=False, require_deps=False, no_interactive=False, input_fn=lambda _: "y")

    assert code == 0
    assert calls == [(context, True, "optional-pdal")]


def test_missing_pygeoconv_installs_after_yes(monkeypatch, tmp_path):
    context = make_context(tmp_path, dry_run=False)
    report = {
        "tools": {
            "gdalinfo": {"available": True},
            "ogrinfo": {"available": True},
            "ogr2ogr": {"available": True},
            "proj": {"available": True},
            "pdal": {"available": True},
        },
        "python_packages": {"pygeoconv": {"available": False}},
    }
    calls = []

    monkeypatch.setattr("scripts.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("scripts.install.run_python_dependency_install", lambda ctx, yes: calls.append((ctx, yes)) or 0)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    code = handle_native_dependencies(context, yes=False, require_deps=False, no_interactive=False, input_fn=lambda _: "y")

    assert code == 0
    assert calls == [(context, True)]


def test_missing_pygeoconv_skips_in_non_interactive_mode(monkeypatch, tmp_path):
    context = make_context(tmp_path, dry_run=False)
    report = {
        "tools": {
            "gdalinfo": {"available": True},
            "ogrinfo": {"available": True},
            "ogr2ogr": {"available": True},
            "proj": {"available": True},
            "pdal": {"available": True},
        },
        "python_packages": {"pygeoconv": {"available": False}},
    }
    calls = []

    monkeypatch.setattr("scripts.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("scripts.install.run_python_dependency_install", lambda ctx, yes: calls.append((ctx, yes)) or 0)

    code = handle_native_dependencies(context, yes=False, require_deps=False, no_interactive=True)

    assert code == 0
    assert calls == []

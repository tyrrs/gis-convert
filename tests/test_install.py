import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from install.install import (
    AGENT_TARGETS,
    InstallContext,
    SUPPORTED_TOOLS,
    build_python_dependency_install_command,
    build_tool_operations,
    confirm_dependency_install,
    confirm_optional_pdal_install,
    confirm_python_dependency_install,
    detect_tools,
    handle_native_dependencies,
    main,
    prompt_for_tools,
    summarize_native_dependencies,
    parse_tool_selection,
    python_dependency_verify_command,
    print_python_dependency_install_plan,
    run_python_dependency_install,
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
    "install",
    "tests",
    "adapters",
    "agents",
    "commands",
    "skills",
    "scripts/__init__.py",
    "scripts/bootstrap.sh",
    "scripts/bootstrap.ps1",
    "scripts/install.sh",
    "scripts/install.ps1",
    "scripts/install.py",
    "scripts/install_deps.py",
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


def make_bootstrap_source_repo(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "source-repo"
    shutil.copytree(
        root,
        source,
        ignore=shutil.ignore_patterns(".git", ".DS_Store", ".idea", ".pytest_cache", "__pycache__"),
    )
    subprocess.run(["git", "init"], cwd=source, text=True, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=source, text=True, capture_output=True, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "fixture"],
        cwd=source,
        text=True,
        capture_output=True,
        check=True,
    )
    return source


def assert_minimal_skill_package(package_dir):
    for relative_path in MINIMAL_PACKAGE_FILES:
        assert (package_dir / relative_path).exists(), relative_path
    for relative_path in EXCLUDED_PACKAGE_PATHS:
        assert not (package_dir / relative_path).exists(), relative_path
    assert sorted(path.name for path in (package_dir / "scripts").iterdir()) == ["check_env.py", "gis_convert.py"]


def test_parse_tool_selection_accepts_comma_list():
    assert parse_tool_selection("codex,claude-code") == ["codex", "claude-code"]


def test_parse_tools_expands_all_in_supported_order():
    selected = parse_tool_selection("all")

    assert selected == SUPPORTED_TOOLS
    assert selected == list(AGENT_TARGETS)
    for tool in ["amp", "cline", "kiro-cli", "roo", "trae-cn", "adal"]:
        assert tool in selected


def test_parse_tool_selection_accepts_copilot_aliases():
    assert parse_tool_selection("github-copilot") == ["github-copilot"]
    assert parse_tool_selection("copilot") == ["github-copilot"]


def test_detected_selection_uses_detected_tool_set(tmp_path):
    context = make_context(tmp_path)
    detected = {"codex": True, "claude-code": False, "cursor": True}

    assert parse_tool_selection("detected", detected=detected) == ["codex", "cursor"]


def test_prompt_for_tools_lists_only_detected_and_accepts_multi_select(capsys):
    detected = {"codex": True, "claude-code": True, "cursor": False}

    selected = prompt_for_tools(detected, input_fn=lambda _: "1,2")

    assert selected == ["claude-code", "codex"]
    output = capsys.readouterr().out
    assert "Detected agents:" in output
    assert "codex" in output
    assert "claude-code" in output
    assert "cursor" not in output


def test_prompt_for_tools_enter_or_all_selects_detected():
    detected = {"codex": True, "claude-code": True, "cursor": False}

    assert prompt_for_tools(detected, input_fn=lambda _: "") == ["claude-code", "codex"]
    assert prompt_for_tools(detected, input_fn=lambda _: "a") == ["claude-code", "codex"]
    assert prompt_for_tools(detected, input_fn=lambda _: "all") == ["claude-code", "codex"]


def test_prompt_for_tools_quit_returns_empty_selection():
    assert prompt_for_tools({"claude-code": True}, input_fn=lambda _: "q") == []


def test_prompt_for_tools_retries_invalid_selection(capsys):
    answers = iter(["2", "1"])

    selected = prompt_for_tools({"claude-code": True}, input_fn=lambda _: next(answers))

    assert selected == ["claude-code"]
    assert "Invalid selection" in capsys.readouterr().out


def test_prompt_for_tools_without_detected_agents_returns_empty(capsys):
    selected = prompt_for_tools({"claude-code": False, "codex": False})

    assert selected == []
    output = capsys.readouterr().out
    assert "No installed agents were detected." in output
    assert "--install claude-code" in output


def test_dry_run_builds_codex_and_claude_operations_without_writing(tmp_path):
    context = make_context(tmp_path, dry_run=True)

    operations = build_tool_operations(["codex", "claude-code"], context)

    destinations = [operation.destination for operation in operations]
    assert context.home / ".codex" / "skills" / "gis-convert" in destinations
    assert context.home / ".claude" / "skills" / "gis-convert" in destinations
    assert {operation.kind for operation in operations} == {"skill-package"}
    assert {operation.source for operation in operations} == {context.repo_root / "skills" / "gis-convert"}
    assert not (context.home / ".codex").exists()
    assert not (context.home / ".claude").exists()


def test_project_scope_uses_project_directory_for_claude_and_cursor(tmp_path):
    context = make_context(tmp_path, dry_run=True, scope="project")

    operations = build_tool_operations(["claude-code", "cursor"], context)

    destinations = [operation.destination for operation in operations]
    assert context.project_dir / ".claude" / "skills" / "gis-convert" in destinations
    assert context.project_dir / ".agents" / "skills" / "gis-convert" in destinations
    assert context.project_dir / ".cursor" / "rules" / "gis-convert.mdc" in destinations


def test_project_scope_uses_vercel_standard_paths_for_new_agents(tmp_path):
    context = make_context(tmp_path, dry_run=True, scope="project")

    operations = build_tool_operations(["amp", "cline", "kiro-cli", "roo", "trae-cn", "adal"], context)
    destinations = {operation.destination for operation in operations if operation.kind == "skill-package"}

    assert context.project_dir / ".agents" / "skills" / "gis-convert" in destinations
    assert context.project_dir / ".kiro" / "skills" / "gis-convert" in destinations
    assert context.project_dir / ".roo" / "skills" / "gis-convert" in destinations
    assert context.project_dir / ".trae" / "skills" / "gis-convert" in destinations
    assert context.project_dir / ".adal" / "skills" / "gis-convert" in destinations


def test_shared_skill_package_destinations_are_deduped(tmp_path):
    context = make_context(tmp_path, dry_run=True, scope="project")

    operations = build_tool_operations(["amp", "kimi-cli", "replit", "cursor"], context)
    shared = context.project_dir / ".agents" / "skills" / "gis-convert"

    assert [operation.destination for operation in operations].count(shared) == 1


def test_actual_install_copies_codex_skill_to_temp_home(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env.pop("CODEX_HOME", None)

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "install/install.py",
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


def test_actual_install_all_writes_minimal_packages_for_every_tool(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project_dir = tmp_path / "project"
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CODEX_HOME", None)
    monkeypatch.delenv("CODEX_HOME", raising=False)

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "install/install.py",
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
    context = InstallContext(
        repo_root=Path(__file__).resolve().parents[1],
        home=home,
        project_dir=project_dir,
        scope="user",
        dry_run=False,
        with_deps=False,
        deps_only=False,
    )
    package_dirs = {
        operation.destination
        for operation in build_tool_operations(SUPPORTED_TOOLS, context)
        if operation.kind == "skill-package"
    }
    assert len(package_dirs) < len(SUPPORTED_TOOLS)
    for package_dir in package_dirs:
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
            "install/install.py",
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
            "install/install.py",
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
            "install/install.py",
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
            "install/install.py",
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


def test_uninstall_all_dry_run_succeeds_with_deduped_targets(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env.pop("CODEX_HOME", None)

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "install/install.py",
            "--uninstall",
            "all",
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
    assert "gis-convert uninstaller" in result.stdout


def test_dry_run_cli_does_not_create_files(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "install/install.py",
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


def test_main_without_install_prompts_before_dependency_check(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr("install.install.detect_tools", lambda context: {"claude-code": True, "codex": True})
    monkeypatch.setattr(
        "install.install.handle_native_dependencies",
        lambda *args, **kwargs: calls.append("deps") or 0,
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    code = main(
        ["--dry-run", "--project-dir", str(tmp_path / "project")],
        input_fn=lambda _: calls.append("prompt") or "1",
    )

    assert code == 0
    assert calls[:2] == ["prompt", "deps"]


def test_main_explicit_install_does_not_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr("install.install.detect_tools", lambda context: {"claude-code": True})
    monkeypatch.setattr("install.install.handle_native_dependencies", lambda *args, **kwargs: 0)
    monkeypatch.setattr("install.install.prompt_for_tools", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected prompt")))

    code = main(["--install", "claude-code", "--dry-run", "--project-dir", str(tmp_path / "project")])

    assert code == 0


def test_main_no_interactive_without_install_fails_without_silent_detected(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("install.install.detect_tools", lambda context: {"claude-code": True, "codex": False})
    monkeypatch.setattr(
        "install.install.handle_native_dependencies",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected dependency check")),
    )

    code = main(["--dry-run", "--no-interactive", "--project-dir", str(tmp_path / "project")])

    captured = capsys.readouterr()
    assert code == 2
    assert "No interactive terminal is available" in captured.err
    assert "--install <agent|detected|all>" in captured.err
    assert "Tools: claude-code" not in captured.out


def test_main_explicit_install_detected_still_uses_detected(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("install.install.detect_tools", lambda context: {"claude-code": True, "codex": False})
    monkeypatch.setattr("install.install.handle_native_dependencies", lambda *args, **kwargs: 0)

    code = main(["--install", "detected", "--dry-run", "--project-dir", str(tmp_path / "project")])

    assert code == 0
    assert "Tools: claude-code" in capsys.readouterr().out


def test_main_deps_only_does_not_prompt(monkeypatch):
    monkeypatch.setattr("install.install.prompt_for_tools", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected prompt")))

    code = main(["--deps-only", "--dry-run", "--skip-deps-check"])

    assert code == 0


def test_old_tool_arguments_are_rejected():
    for old_arg in ("--tools", "--tool"):
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "install/install.py",
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
            "install/install.py",
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
            "install/install.py",
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


def test_detect_tools_does_not_treat_shared_agents_directory_as_every_agent(tmp_path):
    context = make_context(tmp_path)
    (context.project_dir / ".agents" / "skills").mkdir(parents=True)

    detected = detect_tools(context)

    assert detected["amp"] is False
    assert detected["cline"] is False
    assert detected["universal"] is False


def test_shell_wrapper_help_runs():
    result = subprocess.run(
        ["bash", "install/install.sh", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--install" in result.stdout
    assert "--uninstall" in result.stdout
    assert "--tools" not in result.stdout


def test_install_commands_are_not_in_runtime_scripts_directory():
    root = Path(__file__).resolve().parents[1]

    for old_path in [
        "scripts/__init__.py",
        "scripts/bootstrap.sh",
        "scripts/bootstrap.ps1",
        "scripts/install.sh",
        "scripts/install.ps1",
        "scripts/install.py",
        "scripts/install_deps.py",
    ]:
        assert not (root / old_path).exists(), old_path
    for new_path in [
        "install/bootstrap.sh",
        "install/bootstrap.ps1",
        "install/install.sh",
        "install/install.ps1",
        "install/install.py",
        "install/install_deps.py",
    ]:
        assert (root / new_path).exists(), new_path


def test_bootstrap_help_runs():
    result = subprocess.run(
        ["bash", "install/bootstrap.sh", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "GIS_CONVERT_HOME" in result.stdout
    assert "GIS_CONVERT_KEEP_CHECKOUT" in result.stdout
    assert "bootstrap.sh" in result.stdout
    assert "--install claude-code" in result.stdout
    assert "--uninstall claude-code" in result.stdout
    assert "--uninstall all" in result.stdout
    assert "--install codex" not in result.stdout


def test_bootstrap_reconnects_install_stdin_to_tty_when_available():
    text = (Path(__file__).resolve().parents[1] / "install" / "bootstrap.sh").read_text(encoding="utf-8")

    assert "-r /dev/tty" in text
    assert "-t 1" in text
    assert "--no-interactive" in text
    assert './install/install.sh "$@" < /dev/tty' in text


def test_bootstrap_uses_temporary_checkout_and_cleans_it_up_by_default(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source_repo = make_bootstrap_source_repo(tmp_path)
    env = os.environ.copy()
    env.pop("GIS_CONVERT_HOME", None)
    env.pop("GIS_CONVERT_KEEP_CHECKOUT", None)
    env["HOME"] = str(tmp_path / "home")
    env["TMPDIR"] = str(tmp_path / "tmp")
    env["GIS_CONVERT_REPO"] = str(source_repo)
    Path(env["TMPDIR"]).mkdir()

    result = subprocess.run(
        [
            "bash",
            "install/bootstrap.sh",
            "--install",
            "codex",
            "--dry-run",
            "--skip-deps-check",
            "--no-interactive",
        ],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Cloning gis-convert into:" in result.stdout
    assert "Cleaning up temporary checkout:" in result.stdout
    match = re.search(r"Cleaning up temporary checkout: (.+)", result.stdout)
    assert match is not None
    assert not Path(match.group(1).strip()).exists()


def test_bootstrap_clones_then_updates_existing_checkout(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source_repo = make_bootstrap_source_repo(tmp_path)
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["GIS_CONVERT_HOME"] = str(tmp_path / "checkout")
    env["GIS_CONVERT_REPO"] = str(source_repo)

    command = [
        "bash",
        "install/bootstrap.sh",
        "--install",
        "codex",
        "--dry-run",
        "--skip-deps-check",
        "--no-interactive",
    ]
    first = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, check=False)
    second = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, check=False)

    assert first.returncode == 0, first.stderr
    assert "Cloning gis-convert into:" in first.stdout
    assert second.returncode == 0, second.stderr
    assert "Updating existing gis-convert checkout:" in second.stdout
    assert "[DRY-RUN] codex" in second.stdout


def test_powershell_bootstrap_contains_clone_update_and_install_logic():
    text = (Path(__file__).resolve().parents[1] / "install" / "bootstrap.ps1").read_text(encoding="utf-8")

    assert "GIS_CONVERT_HOME" in text
    assert "GIS_CONVERT_KEEP_CHECKOUT" in text
    assert "GIS_CONVERT_REPO" in text
    assert "git clone" in text
    assert "pull --ff-only" in text
    assert "Cleaning up temporary checkout:" in text
    assert "Remove-Item -Recurse -Force" in text
    assert "install.ps1" in text


def test_powershell_wrapper_contains_install_parameters():
    text = (Path(__file__).resolve().parents[1] / "install" / "install.ps1").read_text(encoding="utf-8")

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


def test_python_dependency_install_prefers_existing_conda_env(monkeypatch):
    monkeypatch.setattr("install.install.find_package_managers", lambda _: {"conda": "/opt/anaconda3/bin/conda"})
    monkeypatch.setattr("install.install.conda_env_exists", lambda env_name, conda_path=None: True)

    command = build_python_dependency_install_command()

    assert command == [
        "/opt/anaconda3/bin/conda",
        "run",
        "-n",
        "gis-convert",
        "python",
        "-m",
        "pip",
        "install",
        "pygeoconv>=1.0.1,<2",
    ]


def test_python_dependency_install_falls_back_to_current_python(monkeypatch):
    monkeypatch.setattr("install.install.find_package_managers", lambda _: {})

    command = build_python_dependency_install_command()

    assert command == [sys.executable, "-m", "pip", "install", "pygeoconv>=1.0.1,<2"]


def test_print_and_run_python_dependency_install_use_same_command(monkeypatch, tmp_path, capsys):
    context = make_context(tmp_path, dry_run=True)
    command = [
        "/opt/anaconda3/bin/conda",
        "run",
        "-n",
        "gis-convert",
        "python",
        "-m",
        "pip",
        "install",
        "pygeoconv>=1.0.1,<2",
    ]
    monkeypatch.setattr("install.install.build_python_dependency_install_command", lambda: command)

    print_python_dependency_install_plan()
    plan_output = capsys.readouterr().out
    result = run_python_dependency_install(context, yes=True)
    run_output = capsys.readouterr().out

    assert result == 0
    assert "conda run -n gis-convert python -m pip install 'pygeoconv>=1.0.1,<2'" in plan_output
    assert "conda run -n gis-convert python -m pip install 'pygeoconv>=1.0.1,<2'" in run_output


def test_python_dependency_verify_command_uses_conda_when_available(monkeypatch):
    monkeypatch.setattr("install.install.find_package_managers", lambda _: {"conda": "/opt/anaconda3/bin/conda"})
    monkeypatch.setattr("install.install.conda_env_exists", lambda env_name, conda_path=None: True)

    assert python_dependency_verify_command() == "/opt/anaconda3/bin/conda run -n gis-convert python scripts/check_env.py"


def test_cli_dry_run_prints_dependency_status_by_default(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "install/install.py",
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
            "install/install.py",
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
        [sys.executable, "-B", "install/install.py", "--help"],
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

    monkeypatch.setattr("install.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("install.install.print_dependency_install_plan", lambda dependency_group="all": None)
    monkeypatch.setattr("install.install.run_dependency_install", lambda ctx, yes, dependency_group="all": calls.append((ctx, yes, dependency_group)) or 0)
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

    monkeypatch.setattr("install.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("install.install.print_dependency_install_plan", lambda dependency_group="all": None)
    monkeypatch.setattr("install.install.run_dependency_install", lambda ctx, yes, dependency_group="all": calls.append((ctx, yes, dependency_group)) or 0)
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

    monkeypatch.setattr("install.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("install.install.print_dependency_install_plan", lambda dependency_group="all": None)

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

    monkeypatch.setattr("install.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("install.install.print_dependency_install_plan", lambda dependency_group="all": None)
    monkeypatch.setattr("install.install.run_dependency_install", lambda ctx, yes, dependency_group="all": calls.append((ctx, yes, dependency_group)) or 0)

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

    monkeypatch.setattr("install.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("install.install.print_dependency_install_plan", lambda dependency_group="all": None)
    monkeypatch.setattr("install.install.run_dependency_install", lambda ctx, yes, dependency_group="all": calls.append((ctx, yes, dependency_group)) or 0)
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

    monkeypatch.setattr("install.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("install.install.print_dependency_install_plan", lambda dependency_group="all": None)
    monkeypatch.setattr("install.install.run_dependency_install", lambda ctx, yes, dependency_group="all": calls.append((ctx, yes, dependency_group)) or 0)
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

    monkeypatch.setattr("install.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("install.install.run_python_dependency_install", lambda ctx, yes: calls.append((ctx, yes)) or 0)
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

    monkeypatch.setattr("install.install.inspect_environment", lambda _: report)
    monkeypatch.setattr("install.install.run_python_dependency_install", lambda ctx, yes: calls.append((ctx, yes)) or 0)

    code = handle_native_dependencies(context, yes=False, require_deps=False, no_interactive=True)

    assert code == 0
    assert calls == []

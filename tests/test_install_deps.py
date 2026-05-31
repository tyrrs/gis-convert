import platform

from install.install_deps import build_install_plan, detect_platform


def test_conda_plan_is_default_and_does_not_apply_commands():
    system = detect_platform(system="Darwin", machine="arm64", release="23.0.0")

    plan = build_install_plan(system, strategy="auto", package_manager_paths={"conda": "/opt/conda/bin/conda"})

    assert plan.strategy == "conda"
    assert plan.requires_confirmation is False
    assert plan.commands == [
        [
            "/opt/conda/bin/conda",
            "create",
            "-n",
            "gis-convert",
            "-c",
            "conda-forge",
            "python=3.11",
            "gdal",
            "proj",
            "pdal",
            "pyproj",
            "geopandas",
            "shapely",
            "fiona",
            "-y",
        ]
    ]


def test_macos_system_plan_uses_homebrew_when_available():
    system = detect_platform(system="Darwin", machine="x86_64", release="22.0.0")

    plan = build_install_plan(system, strategy="system", package_manager_paths={"brew": "/opt/homebrew/bin/brew"})

    assert plan.strategy == "system"
    assert plan.commands == [["/opt/homebrew/bin/brew", "install", "gdal", "proj", "pdal"]]


def test_macos_homebrew_required_plan_excludes_pdal():
    system = detect_platform(system="Darwin", machine="arm64", release="24.0.0")

    plan = build_install_plan(
        system,
        strategy="system",
        package_manager_paths={"brew": "/opt/homebrew/bin/brew"},
        dependency_group="required",
    )

    assert plan.commands == [["/opt/homebrew/bin/brew", "install", "gdal", "proj"]]


def test_macos_homebrew_optional_pdal_plan_installs_only_pdal():
    system = detect_platform(system="Darwin", machine="arm64", release="24.0.0")

    plan = build_install_plan(
        system,
        strategy="system",
        package_manager_paths={"brew": "/opt/homebrew/bin/brew"},
        dependency_group="optional-pdal",
    )

    assert plan.commands == [["/opt/homebrew/bin/brew", "install", "pdal"]]


def test_existing_conda_env_uses_install_not_create():
    system = detect_platform(system="Darwin", machine="arm64", release="24.0.0")

    plan = build_install_plan(
        system,
        strategy="conda",
        package_manager_paths={"conda": "/opt/anaconda3/bin/conda"},
        conda_env_exists=True,
    )

    assert plan.commands[0][:6] == ["/opt/anaconda3/bin/conda", "install", "-n", "gis-convert", "-c", "conda-forge"]
    assert "create" not in plan.commands[0]


def test_existing_conda_env_optional_pdal_installs_only_pdal():
    system = detect_platform(system="Darwin", machine="arm64", release="24.0.0")

    plan = build_install_plan(
        system,
        strategy="conda",
        package_manager_paths={"conda": "/opt/anaconda3/bin/conda"},
        dependency_group="optional-pdal",
        conda_env_exists=True,
    )

    assert plan.commands == [["/opt/anaconda3/bin/conda", "install", "-n", "gis-convert", "-c", "conda-forge", "pdal", "-y"]]


def test_linux_system_plan_uses_detected_debian_family():
    system = detect_platform(system="Linux", machine="x86_64", release="6.0.0", os_release_id="ubuntu")

    plan = build_install_plan(system, strategy="system", package_manager_paths={"apt-get": "/usr/bin/apt-get"})

    assert plan.requires_confirmation is True
    assert plan.commands == [
        [
            "sudo",
            "/usr/bin/apt-get",
            "install",
            "gdal-bin",
            "libgdal-dev",
            "proj-bin",
            "libproj-dev",
            "python3-gdal",
            "pdal",
        ]
    ]


def test_windows_plan_prefers_conda_and_mentions_osgeo4w_fallback():
    system = detect_platform(system="Windows", machine="AMD64", release="11")

    plan = build_install_plan(system, strategy="auto", package_manager_paths={})

    assert plan.strategy == "manual"
    assert "Conda/Mamba" in plan.notes[0]
    assert any("OSGeo4W" in note for note in plan.notes)


def test_detect_platform_defaults_to_runtime_values():
    system = detect_platform()

    assert system.system == platform.system()
    assert system.machine

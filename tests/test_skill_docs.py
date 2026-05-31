from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_skill_uses_skill_root_not_parent_relative_scripts_or_readme():
    text = (ROOT / "skills" / "gis-convert" / "SKILL.md").read_text(encoding="utf-8")

    assert "<skill-root>" in text
    assert "python <skill-root>/scripts/gis_convert.py" in text
    assert text.count("```bash") <= 1
    for argument in [
        "--input",
        "--output",
        "--from-format",
        "--to-format",
        "--source-crs",
        "--target-crs",
        "--layer",
        "--geometry-column",
        "--encoding",
        "--landtxt-meta",
        "--overwrite",
        "--validate-only",
        "--list-formats",
    ]:
        assert argument in text
    for format_value in ["esrijson", "csv", "land-boundary-txt", "gpkg", "shp", "dxf"]:
        assert format_value in text
    assert "Suffix Inference" in text
    assert "Error Handling" in text
    assert "../../scripts" not in text
    assert "README.md" not in text
    assert "./scripts/install.sh" not in text
    assert "conda create" not in text
    assert "pip install" not in text
    assert "brew install" not in text
    assert "ogr2ogr" not in text
    assert "pdal translate" not in text
    assert "ogrinfo -sql" not in text


def test_legacy_adapter_directories_are_not_part_of_repo():
    for legacy_path in ["adapters", "commands", "agents", "qwen-extension.json"]:
        assert not (ROOT / legacy_path).exists(), legacy_path


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    next_heading = text.find("\n## ", start + len(heading))
    if next_heading == -1:
        return text[start:]
    return text[start:next_heading]


def test_github_readmes_have_language_switch_format_tables_and_license():
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

    assert "English｜[简体中文](README.zh-CN.md)" in english
    assert "[English](README.md)｜简体中文" in chinese
    assert "Input formats -> gis-convert CLI -> Output formats" in english
    assert "输入格式 -> gis-convert CLI -> 输出格式" in chinese

    for text in [english, chinese]:
        assert "MIT License" in text
        assert "./scripts/install.sh --install codex" in text
        assert "./scripts/install.sh --uninstall codex" in text
        assert "python scripts/check_env.py" in text
        assert "python scripts/install_deps.py" in text
        assert "conda create -n gis-convert" not in text
        assert "apt-get" not in text
        assert "brew install gdal" not in text

    english_output = _section(english, "### Output Formats")
    chinese_output = _section(chinese, "### 输出格式")
    for output_section in [english_output, chinese_output]:
        assert "GeoJSON" in output_section
        assert "ESRIJSON" in output_section
        assert "CSV" in output_section
        assert "WKT" in output_section
        assert "DXF" in output_section
        assert "DWG" not in output_section
        assert "MDB" not in output_section
        assert "Personal GDB" not in output_section


def test_license_file_and_pyproject_metadata_are_mit():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert license_text.startswith("MIT License")
    assert "Copyright (c) 2026 gis-convert contributors" in license_text
    assert 'license = "MIT"' in pyproject

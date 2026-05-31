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
    assert "./install/install.sh" not in text
    assert "conda create" not in text
    assert "pip install" not in text
    assert "brew install" not in text
    assert "ogr2ogr" not in text
    assert "pdal translate" not in text
    assert "ogrinfo -sql" not in text


def test_legacy_adapter_directories_are_not_part_of_repo():
    for legacy_path in ["adapters", "commands", "agents", "qwen-extension.json", ".codex-plugin", ".claude-plugin"]:
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
    assert "Convert GIS data between WKT, GeoJSON, SHP, GDB" in english
    assert "在 WKT、GeoJSON、SHP、GDB" in chinese
    assert "<strong>Input formats</strong>" in english
    assert "<strong>Output formats</strong>" in english
    assert '<strong style="font-size: 2rem;">→</strong>' in english
    assert "<strong>输入格式</strong>" in chinese
    assert "<strong>输出格式</strong>" in chinese
    assert '<strong style="font-size: 2rem;">→</strong>' in chinese
    assert "| Format | Direction | Notes | Description |" in english
    assert "| 格式 | 方向 | 说明 | 描述 |" in chinese
    assert "| Format | Direction | Status | Notes |" not in english
    assert "| 格式 | 方向 | 状态 | 说明 |" not in chinese
    assert "Text and binary encodings for individual OGC geometries." in english
    assert "OGC 几何对象的文本和二进制编码。" in chinese
    assert "## Supported Agents" not in english
    assert "## 支持的 Agent" not in chinese
    assert english.index("Works with Claude Code") < english.index("## Quickstart") < english.index("## Format Flow")
    assert chinese.index("支持 Claude Code") < chinese.index("## 快速开始") < chinese.index("## 格式流程")
    assert "## Full Install with Dependency Checks" in english
    assert "## 完整安装（含依赖检测）" in chinese
    assert "## 带依赖检测的完整安装" not in chinese

    for text in [english, chinese]:
        assert "MIT License" in text
        assert "npx skills add tyrrs/gis-convert" in text
        assert "https://github.com/vercel-labs/skills#supported-agents" not in text
        assert " ".join(["Supported", "Agent", "List"]) not in text
        assert "支持的 " + "Agent 列表" not in text
        assert "| Agent | `--install` id |" not in text
        assert " ".join(["Project", "Path"]) not in text
        assert " ".join(["Global", "Path"]) not in text
        assert "<details>" in text
        assert "<summary>More</summary>" in text
    assert "Works with Claude Code, Codex, Cursor, OpenCode, Qwen Code, Gemini CLI, GitHub Copilot, Continue, and Windsurf." in english
    assert "支持 Claude Code、Codex、Cursor、OpenCode、Qwen Code、Gemini CLI、GitHub Copilot、Continue 和 Windsurf。" in chinese
    assert "Supports OpenCode, Claude Code, Codex, Cursor, and 51 more." not in english
    assert "支持 OpenCode、Claude Code、Codex、Cursor 以及另外 51 个 Agent。" not in chinese

    featured_agents = [
        "Claude Code",
        "Codex",
        "Cursor",
        "OpenCode",
        "Qwen Code",
        "Gemini CLI",
        "GitHub Copilot",
        "Continue",
        "Windsurf",
    ]
    for text in [english, chinese]:
        visible_agent_intro = text.split("<details>", 1)[0]
        hidden_agents = text.split("<details>", 1)[1].split("</details>", 1)[0]
        for agent in featured_agents:
            assert agent in visible_agent_intro
            assert agent not in hidden_agents
        for agent in ["AiderDesk", "Amp", "Kiro CLI", "Roo Code", "Trae CN", "AdaL"]:
            assert agent in hidden_agents

    for text in [english, chinese]:
        assert "curl -fsSL https://raw.githubusercontent.com/tyrrs/gis-convert/main/install/bootstrap.sh | bash" in text
        assert "irm https://raw.githubusercontent.com/tyrrs/gis-convert/main/install/bootstrap.ps1 | iex" in text
        assert "bash -s -- --install claude-code" not in text
        assert "bash -s -- --uninstall claude-code" in text
        assert "bash -s -- --uninstall all" in text
        assert "tyrr-hz/gis-convert" not in text
        assert "does not install GDAL/OGR, PROJ, PDAL" in text or "不会安装 GDAL/OGR、PROJ、PDAL" in text
        assert "detected agents" in text or "检测到的 Agent" in text
        assert "falls back to detected agents automatically" not in text
        assert "自动回退为安装检测到的 Agent" not in text
        assert "temporary" in text or "临时目录" in text
        assert "./install/install.sh\n```" in text
        assert "./install/install.sh --install claude-code" in text
        assert "./install/install.sh --install all" in text
        assert "./install/install.sh --install detected" in text
        assert "./install/install.sh --uninstall claude-code" in text
        assert "./install/install.sh --uninstall all" in text
        assert "./install/install.ps1 -Uninstall claude-code" in text
        assert "./install/install.ps1 -Uninstall all" in text
        assert "git clone https://github.com/tyrrs/gis-convert.git" in text
        assert "git clone https://github.com/tyrrs/gis-convert.git" in text
        assert "./install/install.ps1\n```" in text
        assert "Advanced checks" not in text
        assert "高级检查" not in text
        assert "npx gis-convert --install codex" not in text
        assert "detects local GDAL/OGR" not in text
        assert "maps output drivers from file suffixes" not in text
        assert "conda create -n gis-convert" not in text
        assert "apt-get" not in text
        assert "brew install gdal" not in text
        assert "## Dependency Check" not in text
        assert "## 依赖检查" not in text
        assert "[x]" in text
        assert "[ ]" in text
        assert "https://api.star-history.com/svg?repos=tyrrs/gis-convert&type=Date" in text
        assert "https://starmapper.bruniaux.com/tyrrs/gis-convert" in text
        assert "https://starmapper.bruniaux.com/api/map-image/tyrrs/gis-convert" in text

    english_flow = _section(english, "## Format Flow")
    chinese_flow = _section(chinese, "## 格式流程")
    for flow_section, output_heading in [(english_flow, "<strong>Output formats</strong>"), (chinese_flow, "<strong>输出格式</strong>")]:
        assert "GeoJSON" in flow_section
        assert "ESRIJSON" in flow_section
        assert "CSV" in flow_section
        assert "WKT" in flow_section
        assert "DXF" in flow_section
        output_side = flow_section.split(output_heading, 1)[1]
        assert "DWG" not in output_side
        assert "MDB" not in output_side
        assert "Personal GDB" not in output_side

    english_roadmap = _section(english, "## Roadmap")
    chinese_roadmap = _section(chinese, "## 路线图")
    assert "Implemented" in english_roadmap
    assert "Planned" in english_roadmap
    assert "DWG write support" in english_roadmap
    assert "MDB/Personal GDB write support" in english_roadmap
    assert "已实现" in chinese_roadmap
    assert "待实现" in chinese_roadmap
    assert "DWG 写入支持" in chinese_roadmap
    assert "MDB/Personal GDB 写入支持" in chinese_roadmap


def test_license_file_and_pyproject_metadata_are_mit():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert license_text.startswith("MIT License")
    assert "Copyright (c) 2026 " in license_text
    assert 'license = "MIT"' in pyproject

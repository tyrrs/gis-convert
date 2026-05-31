# gis-convert

English｜[简体中文](README.zh-CN.md)

`gis-convert` is an open-source Agent Skill and Python CLI for converting GIS data across practical vector, geodatabase, CAD exchange, point-cloud, and 3D GIS workflows. It detects local GDAL/OGR, PROJ, PDAL, and Python package support, maps output drivers from file suffixes, and reports clear fallbacks for formats that are proprietary or read-only in common environments.

## Quick Install

Install the skill into an agent:

```bash
git clone <repo-url>
cd gis-convert
./scripts/install.sh --install codex
```

Install multiple agents:

```bash
./scripts/install.sh --install codex,claude-code,qwen-code
```

Install agent integration and GIS dependencies together:

```bash
./scripts/install.sh --install codex --with-deps
```

If dependencies are already installed and you only want to add another agent:

```bash
./scripts/install.sh --install claude-code --skip-deps-check
```

Windows PowerShell:

```powershell
./scripts/install.ps1 -Install codex
```

Uninstall an agent integration without removing GIS dependencies:

```bash
./scripts/install.sh --uninstall codex
```

The installer copies only the minimal runtime package into agent directories:

```text
SKILL.md
scripts/
references/
```

## Dependency Check

Before real conversion work, check the local environment:

```bash
python scripts/check_env.py
```

To print an install plan for GDAL/OGR, PROJ, PDAL, and Python package dependencies:

```bash
python scripts/install_deps.py
```

The quick installer also checks dependencies by default. It asks before installing large native GIS dependencies. PDAL is optional and only needed for point-cloud conversion. `pygeoconv` is only needed for ESRIJSON output.

## Format Flow

`Input formats -> gis-convert CLI -> Output formats`

### Input Formats

| Category | Input formats | Notes |
|---|---|---|
| Text geometry | WKT, WKB | WKT has built-in lightweight handling for common geometry types. |
| Web vector | GeoJSON, TopoJSON, ESRIJSON | ESRIJSON reading depends on local driver/package support. |
| Desktop vector | SHP, MapInfo TAB/MIF, CSV WKT | CSV input expects a WKT geometry column, default `wkt`. |
| OGC/vector | GeoPackage, FlatGeobuf, GML, KML/KMZ, GPX, SQLite | Support depends on local GDAL/OGR drivers. |
| Geodatabase | FileGDB/OpenFileGDB, MDB/Personal GDB | MDB/Personal GDB is conditional and often read-only outside Windows/ODBC setups. |
| CAD/BIM | DXF, DWG, IFC | DXF is the preferred open CAD path. DWG/IFC depend on local optional toolchains. |
| Survey exchange | Land-boundary TXT | Supports the `[属性描述]` plus `[地块坐标]` land-boundary exchange style. |
| Point cloud | LAS, LAZ, E57, PLY | Requires PDAL. LAZ also depends on the local PDAL build. |
| Practical 3D | CityGML, 3D Tiles, I3S/SLPK, glTF/GLB, OBJ, DAE | Uses GDAL/OGR or dedicated adapters where available. |

### Output Formats

| Category | Output formats | Notes |
|---|---|---|
| Text geometry | WKT | Built-in output, one geometry per line. |
| Web vector | GeoJSON, TopoJSON, ESRIJSON | ESRIJSON output uses `pygeoconv`; `.json` defaults to GeoJSON unless `--to-format esrijson` is used. |
| Desktop vector | SHP, MapInfo TAB/MIF, CSV WKT | CSV output writes attribute columns plus a WKT geometry column. |
| OGC/vector | GeoPackage, FlatGeobuf, GML, KML/KMZ, GPX, SQLite | GeoPackage is the recommended portable default for attributes and CRS metadata. |
| Geodatabase | OpenFileGDB/FileGDB | Availability depends on the installed GDAL/OGR build. |
| CAD exchange | DXF | Preferred CAD output. GIS attributes may be simplified by the CAD format. |
| Survey exchange | Land-boundary TXT | Polygon and multipolygon output only. |
| Point cloud | LAS, LAZ, E57, PLY | Requires PDAL and local codec support. |

Formats shown only in the input table are conditional input workflows. Use DXF for CAD exchange, and use GeoPackage or OpenFileGDB for geodatabase-style output.

## CLI Usage

The CLI infers output format from the output file suffix. Use `--to-format` only when the suffix is ambiguous or you need an override.

```bash
python scripts/gis_convert.py \
  --input /absolute/input.shp \
  --output /absolute/output.gpkg \
  --target-crs EPSG:4326 \
  --overwrite
```

Useful commands:

```bash
python scripts/gis_convert.py --list-formats
python scripts/gis_convert.py --input input.geojson --output output.gpkg --validate-only
python scripts/gis_convert.py --input parcels.geojson --output parcels.txt --to-format land-boundary-txt
```

CRS defaults:

- If `--target-crs` is omitted, the input CRS is preserved.
- Use `--source-crs` when the input CRS is missing or wrong.
- If input CRS is missing and coordinates look like longitude/latitude, the CLI assigns `EPSG:4326`.

## Supported Agents

The installer supports:

`codex`, `claude-code`, `qwen-code`, `gemini-cli`, `cursor`, `copilot`, `aider`, `continue`, `opencode`, `windsurf`.

Use `--install all` for every supported integration, or `--install detected` for agents detected on the current machine.

## Development

Run tests:

```bash
python -m pytest -q
```

The deterministic tests do not require local GDAL/PDAL. Real native conversion support depends on the tools and drivers installed on the machine.

## License

This project is open source under the [MIT License](LICENSE). You may use, modify, and distribute it freely, provided the copyright and license notice are preserved.

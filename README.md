# gis-convert

English｜[简体中文](README.zh-CN.md)

Convert GIS data between WKT, GeoJSON, SHP, GDB, DXF, CSV, ESRIJSON, point clouds, and practical 3D formats.

It focuses on real, usable conversions across open GIS formats, with clear alternatives when proprietary formats need special toolchains.

Works with Claude Code, Codex, Cursor, OpenCode, Qwen Code, Gemini CLI, GitHub Copilot, Continue, and Windsurf.

<details>
<summary>More</summary>

AiderDesk, Amp, Kimi Code CLI, Replit, Universal, Antigravity, Augment, IBM Bob, OpenClaw, Cline, Dexto, Warp, CodeArts Agent, CodeBuddy, Codemaker, Code Studio, Command Code, Cortex Code, Crush, Deep Agents, Devin for Terminal, Droid, Firebender, ForgeCode, Goose, Hermes Agent, Junie, iFlow CLI, Kilo Code, Kiro CLI, Kode, MCPJam, Mistral Vibe, Mux, OpenHands, Pi, Qoder, Rovo Dev, Roo Code, Tabnine CLI, Trae, Trae CN, Zencoder, Neovate, Pochi, AdaL

</details>

## Quickstart

Install the skill with the standard Skills CLI:

```bash
npx skills add tyrrs/gis-convert
```

This is a skill-only install. It installs the `SKILL.md` package, but it does not install GDAL/OGR, PROJ, PDAL, or Python package dependencies.

## Full Install with Dependency Checks

Use the repository installer when you want dependency checks and optional dependency installation. The installer checks dependencies by default and asks before installing large native GIS dependencies.

Run the installer without an agent name to choose from detected agents interactively. The `curl | bash` installer reconnects to your terminal when one is available; in automation, pass `--install detected`, `--install all`, or a specific agent. The bootstrap checkout is temporary and is cleaned up after the installer finishes unless `GIS_CONVERT_HOME` is set.

macOS / Linux / WSL / Git Bash:

```bash
curl -fsSL https://raw.githubusercontent.com/tyrrs/gis-convert/main/install/bootstrap.sh | bash
```

Manual macOS / Linux install:

```bash
git clone https://github.com/tyrrs/gis-convert.git
cd gis-convert
./install/install.sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/tyrrs/gis-convert/main/install/bootstrap.ps1 | iex
```

Manual Windows install:

```powershell
git clone https://github.com/tyrrs/gis-convert.git
cd gis-convert
./install/install.ps1
```

Common options:

```bash
./install/install.sh --install claude-code,codex,qwen-code
./install/install.sh --install all
./install/install.sh --install detected
./install/install.sh --install claude-code --with-deps
./install/install.sh --install claude-code --skip-deps-check
./install/install.sh --uninstall claude-code
./install/install.sh --uninstall all
curl -fsSL https://raw.githubusercontent.com/tyrrs/gis-convert/main/install/bootstrap.sh | bash -s -- --uninstall claude-code
curl -fsSL https://raw.githubusercontent.com/tyrrs/gis-convert/main/install/bootstrap.sh | bash -s -- --uninstall all
```

PowerShell options:

```powershell
./install/install.ps1 -Uninstall claude-code
./install/install.ps1 -Uninstall all
```

## Format Flow

<table>
  <tr>
    <td valign="top">
      <strong>Input formats</strong>
      <table>
        <tr><td>WKT, WKB</td></tr>
        <tr><td>GeoJSON, TopoJSON, ESRIJSON</td></tr>
        <tr><td>SHP, MapInfo TAB/MIF, CSV WKT</td></tr>
        <tr><td>GeoPackage, FlatGeobuf, GML, KML/KMZ, GPX, SQLite</td></tr>
        <tr><td>FileGDB/OpenFileGDB, conditional MDB/Personal GDB input</td></tr>
        <tr><td>DXF, conditional DWG input</td></tr>
        <tr><td>Land-boundary TXT</td></tr>
        <tr><td>LAS, LAZ, E57, PLY</td></tr>
        <tr><td>CityGML, 3D Tiles, I3S/SLPK, glTF/GLB, OBJ, DAE</td></tr>
      </table>
    </td>
    <td align="center" valign="middle"><strong style="font-size: 2rem;">→</strong></td>
    <td valign="top">
      <strong>Output formats</strong>
      <table>
        <tr><td>WKT</td></tr>
        <tr><td>GeoJSON, TopoJSON, ESRIJSON</td></tr>
        <tr><td>SHP, MapInfo TAB/MIF, CSV WKT</td></tr>
        <tr><td>GeoPackage, FlatGeobuf, GML, KML/KMZ, GPX, SQLite</td></tr>
        <tr><td>OpenFileGDB/FileGDB</td></tr>
        <tr><td>DXF</td></tr>
        <tr><td>Land-boundary TXT</td></tr>
        <tr><td>LAS, LAZ, E57, PLY</td></tr>
        <tr><td>Practical 3D outputs where local adapters support them</td></tr>
      </table>
    </td>
  </tr>
</table>

## Format Reference

| Format | Direction | Notes | Description |
|---|---|---|---|
| WKT / WKB | Input + output | WKT output writes one geometry per line. | Text and binary encodings for individual OGC geometries. |
| GeoJSON / TopoJSON | Input + output | `.json` defaults to GeoJSON unless `--to-format esrijson` is used. | JSON formats for web mapping vector features and topology-preserving vector data. |
| ESRIJSON | Input + output | ESRIJSON output uses `pygeoconv`. | Esri's JSON geometry and feature representation used by ArcGIS services. |
| CSV WKT | Input + output | CSV uses a WKT geometry column named `wkt` by default. | Attribute table stored as CSV with geometry in a WKT column. |
| Land-boundary TXT | Input + output | Polygon and multipolygon output for land-boundary exchange. | Chinese land-boundary parcel exchange text format. |
| SHP | Input + output | Common desktop GIS exchange format. | Esri Shapefile vector dataset made of sidecar files. |
| GeoPackage / FlatGeobuf / SQLite | Input + output | GeoPackage is the recommended portable default. | Portable file-based geospatial databases and efficient vector containers. |
| OpenFileGDB / FileGDB | Input + output | Writing depends on the installed GDAL/OGR build. | Esri file geodatabase folders for multi-layer vector datasets. |
| DXF | Input + output | Preferred CAD exchange output. GIS attributes may be simplified. | CAD exchange format commonly used between GIS and drafting tools. |
| DWG | Conditional input | Write support is planned; output needs ODA, AutoCAD, RealDWG, or another dedicated toolchain. | Native AutoCAD drawing format. |
| MDB / Personal GDB | Conditional input | Write support is planned; output needs Windows ODBC/Access or another dedicated toolchain. | Microsoft Access based Esri Personal Geodatabase. |
| LAS / LAZ / E57 / PLY | Input + output | Implemented through PDAL. LAZ depends on local codec support. | Point-cloud formats for LiDAR scans and 3D point datasets. |
| CityGML / 3D Tiles / I3S / glTF / OBJ / DAE | Conditional input + output | Adapter-dependent practical 3D workflows. | 3D city, streaming scene, and model exchange formats. |

## Roadmap

| Implemented | Planned |
|---|---|
| [x] GeoJSON / WKT / CSV WKT | [ ] DWG write support |
| [x] ESRIJSON output | [ ] MDB/Personal GDB write support |
| [x] SHP / GPKG / OpenFileGDB | [ ] Richer 3D Tiles / I3S adapters |
| [x] DXF output | [ ] Raster workflows if later needed |
| [x] Land-boundary TXT |  |
| [x] LAS / LAZ / E57 / PLY through PDAL |  |
| [x] CRS assignment and reprojection |  |

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

## Star History

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=tyrrs/gis-convert&type=Date&theme=dark" />
  <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=tyrrs/gis-convert&type=Date" />
  <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=tyrrs/gis-convert&type=Date" />
</picture>

## Star Map

<p align="center">
  <a href="https://starmapper.bruniaux.com/tyrrs/gis-convert">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://starmapper.bruniaux.com/api/map-image/tyrrs/gis-convert?theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://starmapper.bruniaux.com/api/map-image/tyrrs/gis-convert?theme=light" />
      <img alt="StarMapper - see who stars this repo on a world map" src="https://starmapper.bruniaux.com/api/map-image/tyrrs/gis-convert" />
    </picture>
  </a>
</p>

## For Contributors

Use this check before submitting changes. It verifies the README, skill document, installer, and conversion CLI stay aligned:

```bash
python -m pytest -q
```

## License

This project is open source under the [MIT License](LICENSE). You may use, modify, and distribute it freely, provided the copyright and license notice are preserved.

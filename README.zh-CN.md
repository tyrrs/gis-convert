# gis-convert

[English](README.md)｜简体中文

`gis-convert` 是一个开源 Agent Skill 和 Python CLI，用于在常见矢量、地理数据库、CAD 交换、点云和实用三维 GIS 工作流之间转换数据。它会检测本机 GDAL/OGR、PROJ、PDAL 和 Python 包能力，根据输出文件后缀映射 driver，并在私有格式或只读格式不可写时给出明确替代方案。

## 一键安装

安装到某个 Agent：

```bash
git clone <repo-url>
cd gis-convert
./scripts/install.sh --install codex
```

安装到多个 Agent：

```bash
./scripts/install.sh --install codex,claude-code,qwen-code
```

同时安装 Agent 集成和 GIS 依赖：

```bash
./scripts/install.sh --install codex --with-deps
```

如果依赖已经装好，只是安装到另一个 Agent：

```bash
./scripts/install.sh --install claude-code --skip-deps-check
```

Windows PowerShell：

```powershell
./scripts/install.ps1 -Install codex
```

卸载 Agent 集成，不删除 GIS 依赖：

```bash
./scripts/install.sh --uninstall codex
```

安装器只会把最小运行包复制到 Agent 目录：

```text
SKILL.md
scripts/
references/
```

## 依赖检查

真实转换前，先检查当前环境：

```bash
python scripts/check_env.py
```

打印 GDAL/OGR、PROJ、PDAL 和 Python 包依赖的安装计划：

```bash
python scripts/install_deps.py
```

一键安装器默认也会检测依赖。缺少较大的原生 GIS 依赖时，它会先询问再安装。PDAL 是可选依赖，只影响点云转换；`pygeoconv` 只用于 ESRIJSON 输出。

## 格式流程

`输入格式 -> gis-convert CLI -> 输出格式`

### 输入格式

| 类型 | 输入格式 | 说明 |
|---|---|---|
| 文本几何 | WKT、WKB | WKT 对常见几何类型有内置轻量处理。 |
| Web 矢量 | GeoJSON、TopoJSON、ESRIJSON | ESRIJSON 读取取决于本机 driver 或包能力。 |
| 桌面矢量 | SHP、MapInfo TAB/MIF、CSV WKT | CSV 输入需要 WKT 空间列，默认列名为 `wkt`。 |
| OGC/矢量 | GeoPackage、FlatGeobuf、GML、KML/KMZ、GPX、SQLite | 支持能力取决于本机 GDAL/OGR driver。 |
| 地理数据库 | FileGDB/OpenFileGDB、MDB/Personal GDB | MDB/Personal GDB 是条件支持，在非 Windows/ODBC 环境中常见为只读或不可用。 |
| CAD/BIM | DXF、DWG、IFC | DXF 是优先推荐的开放 CAD 路径；DWG/IFC 依赖额外本地工具链。 |
| 勘测交换 | 勘测定界 TXT | 支持 `[属性描述]` 和 `[地块坐标]` 结构的国土交换格式。 |
| 点云 | LAS、LAZ、E57、PLY | 需要 PDAL；LAZ 还取决于本机 PDAL 编译能力。 |
| 实用三维 | CityGML、3D Tiles、I3S/SLPK、glTF/GLB、OBJ、DAE | 按可用 GDAL/OGR 或专用适配器处理。 |

### 输出格式

| 类型 | 输出格式 | 说明 |
|---|---|---|
| 文本几何 | WKT | 内置输出，每行一个几何。 |
| Web 矢量 | GeoJSON、TopoJSON、ESRIJSON | ESRIJSON 输出使用 `pygeoconv`；`.json` 默认是 GeoJSON，需要 ESRIJSON 时传 `--to-format esrijson`。 |
| 桌面矢量 | SHP、MapInfo TAB/MIF、CSV WKT | CSV 输出会写出属性列，并追加 WKT 空间列。 |
| OGC/矢量 | GeoPackage、FlatGeobuf、GML、KML/KMZ、GPX、SQLite | GeoPackage 是推荐的通用输出格式，能较好保存属性和 CRS 元数据。 |
| 地理数据库 | OpenFileGDB/FileGDB | 取决于当前 GDAL/OGR 构建是否支持写入。 |
| CAD 交换 | DXF | 推荐的 CAD 输出格式；CAD 格式可能简化 GIS 属性。 |
| 勘测交换 | 勘测定界 TXT | 仅支持面和多面输出。 |
| 点云 | LAS、LAZ、E57、PLY | 需要 PDAL 和本机 codec 支持。 |

只出现在输入表中的格式属于条件输入工作流。CAD 交换请使用 DXF；类似地理数据库的输出请使用 GeoPackage 或 OpenFileGDB。

## CLI 用法

CLI 默认根据输出文件后缀推断格式。只有后缀有歧义或需要覆盖时，才传 `--to-format`。

```bash
python scripts/gis_convert.py \
  --input /absolute/input.shp \
  --output /absolute/output.gpkg \
  --target-crs EPSG:4326 \
  --overwrite
```

常用命令：

```bash
python scripts/gis_convert.py --list-formats
python scripts/gis_convert.py --input input.geojson --output output.gpkg --validate-only
python scripts/gis_convert.py --input parcels.geojson --output parcels.txt --to-format land-boundary-txt
```

CRS 默认规则：

- 不传 `--target-crs` 时保留输入 CRS。
- 输入 CRS 缺失或错误时，用 `--source-crs` 指定。
- 输入 CRS 缺失且坐标看起来是经纬度时，CLI 默认赋 `EPSG:4326`。

## 支持的 Agent

安装器支持：

`codex`、`claude-code`、`qwen-code`、`gemini-cli`、`cursor`、`copilot`、`aider`、`continue`、`opencode`、`windsurf`。

使用 `--install all` 安装全部已支持集成，或使用 `--install detected` 只安装当前机器检测到的 Agent。

## 开发与验证

运行测试：

```bash
python -m pytest -q
```

确定性测试不要求本机安装 GDAL/PDAL。真实原生格式转换能力取决于当前机器安装的工具和 driver。

## 开源协议

本项目基于 [MIT License](LICENSE) 开源。你可以自由使用、修改和分发，但需要保留版权与许可声明。

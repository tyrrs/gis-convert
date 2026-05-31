# gis-convert

[English](README.md)｜简体中文

在 WKT、GeoJSON、SHP、GDB、DXF、CSV、ESRIJSON、点云和实用三维格式之间转换 GIS 数据。

重点覆盖可落地的开放 GIS 格式互转；遇到需要专有工具链的格式时，会给出明确替代路径。

支持 Claude Code、Codex、Cursor、OpenCode、Qwen Code、Gemini CLI、GitHub Copilot、Continue 和 Windsurf。

<details>
<summary>More</summary>

AiderDesk、Amp、Kimi Code CLI、Replit、Universal、Antigravity、Augment、IBM Bob、OpenClaw、Cline、Dexto、Warp、CodeArts Agent、CodeBuddy、Codemaker、Code Studio、Command Code、Cortex Code、Crush、Deep Agents、Devin for Terminal、Droid、Firebender、ForgeCode、Goose、Hermes Agent、Junie、iFlow CLI、Kilo Code、Kiro CLI、Kode、MCPJam、Mistral Vibe、Mux、OpenHands、Pi、Qoder、Rovo Dev、Roo Code、Tabnine CLI、Trae、Trae CN、Zencoder、Neovate、Pochi、AdaL

</details>

## 快速开始

使用标准 Skills CLI 安装：

```bash
npx skills add tyrrs/gis-convert
```

这是轻量 skill 安装。它只安装 `SKILL.md` 包，不会安装 GDAL/OGR、PROJ、PDAL 或 Python 包依赖。

## 完整安装（含依赖检测）

如果需要依赖检测和可选依赖安装，请使用本仓库安装器。安装器默认会检测依赖；缺少较大的原生 GIS 依赖时，它会先询问再安装。

不指定 Agent 名称时，安装器会交互式列出当前检测到的 Agent 供多选。`curl | bash` 安装器会在可用时重新连接到你的终端；自动化环境中请显式传 `--install detected`、`--install all` 或具体 Agent。bootstrap 拉取的仓库是临时目录，安装器结束后会自动清理；只有设置 `GIS_CONVERT_HOME` 时才会保留。

macOS / Linux / WSL / Git Bash：

```bash
curl -fsSL https://raw.githubusercontent.com/tyrrs/gis-convert/main/install/bootstrap.sh | bash
```

macOS / Linux 手动安装：

```bash
git clone https://github.com/tyrrs/gis-convert.git
cd gis-convert
./install/install.sh
```

Windows PowerShell：

```powershell
irm https://raw.githubusercontent.com/tyrrs/gis-convert/main/install/bootstrap.ps1 | iex
```

Windows 手动安装：

```powershell
git clone https://github.com/tyrrs/gis-convert.git
cd gis-convert
./install/install.ps1
```

常用选项：

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

PowerShell 选项：

```powershell
./install/install.ps1 -Uninstall claude-code
./install/install.ps1 -Uninstall all
```

## 格式流程

<table>
  <tr>
    <td valign="top">
      <strong>输入格式</strong>
      <table>
        <tr><td>WKT、WKB</td></tr>
        <tr><td>GeoJSON、TopoJSON、ESRIJSON</td></tr>
        <tr><td>SHP、MapInfo TAB/MIF、CSV WKT</td></tr>
        <tr><td>GeoPackage、FlatGeobuf、GML、KML/KMZ、GPX、SQLite</td></tr>
        <tr><td>FileGDB/OpenFileGDB、条件输入 MDB/Personal GDB</td></tr>
        <tr><td>DXF、条件输入 DWG</td></tr>
        <tr><td>勘测定界 TXT</td></tr>
        <tr><td>LAS、LAZ、E57、PLY</td></tr>
        <tr><td>CityGML、3D Tiles、I3S/SLPK、glTF/GLB、OBJ、DAE</td></tr>
      </table>
    </td>
    <td align="center" valign="middle"><strong style="font-size: 2rem;">→</strong></td>
    <td valign="top">
      <strong>输出格式</strong>
      <table>
        <tr><td>WKT</td></tr>
        <tr><td>GeoJSON、TopoJSON、ESRIJSON</td></tr>
        <tr><td>SHP、MapInfo TAB/MIF、CSV WKT</td></tr>
        <tr><td>GeoPackage、FlatGeobuf、GML、KML/KMZ、GPX、SQLite</td></tr>
        <tr><td>OpenFileGDB/FileGDB</td></tr>
        <tr><td>DXF</td></tr>
        <tr><td>勘测定界 TXT</td></tr>
        <tr><td>LAS、LAZ、E57、PLY</td></tr>
        <tr><td>本机适配器支持的实用三维输出</td></tr>
      </table>
    </td>
  </tr>
</table>

## 格式说明

| 格式 | 方向 | 说明 | 描述 |
|---|---|---|---|
| WKT / WKB | 输入 + 输出 | WKT 输出每行一个几何。 | OGC 几何对象的文本和二进制编码。 |
| GeoJSON / TopoJSON | 输入 + 输出 | `.json` 默认是 GeoJSON，需要 ESRIJSON 时传 `--to-format esrijson`。 | Web 地图常用的 JSON 矢量要素格式，以及保留拓扑关系的矢量格式。 |
| ESRIJSON | 输入 + 输出 | ESRIJSON 输出使用 `pygeoconv`。 | ArcGIS 服务常用的 Esri JSON 几何和要素表达。 |
| CSV WKT | 输入 + 输出 | CSV 默认使用名为 `wkt` 的 WKT 空间列。 | 属性表使用 CSV 存储，空间列使用 WKT 表达几何。 |
| 勘测定界 TXT | 输入 + 输出 | 面和多面要素的勘测定界交换格式。 | 国土勘测定界地块坐标交换文本格式。 |
| SHP | 输入 + 输出 | 常见桌面 GIS 交换格式。 | 由多个 sidecar 文件组成的 Esri Shapefile 矢量数据集。 |
| GeoPackage / FlatGeobuf / SQLite | 输入 + 输出 | GeoPackage 是推荐的通用输出格式。 | 便携式文件型地理数据库和高效矢量容器。 |
| OpenFileGDB / FileGDB | 输入 + 输出 | 写入能力取决于当前 GDAL/OGR 构建。 | Esri 文件地理数据库目录，适合存储多图层矢量数据。 |
| DXF | 输入 + 输出 | 推荐的 CAD 交换输出；GIS 属性可能被简化。 | GIS 与 CAD 制图软件之间常用的 CAD 交换格式。 |
| DWG | 条件输入 | 写入在路线图中；输出需要 ODA、AutoCAD、RealDWG 或其他专用工具链。 | AutoCAD 原生图形文件格式。 |
| MDB / Personal GDB | 条件输入 | 写入在路线图中；输出需要 Windows ODBC/Access 或其他专用工具链。 | 基于 Microsoft Access 的 Esri Personal Geodatabase。 |
| LAS / LAZ / E57 / PLY | 输入 + 输出 | 通过 PDAL 实现；LAZ 取决于本机 codec 支持。 | 用于 LiDAR 扫描和三维点数据集的点云格式。 |
| CityGML / 3D Tiles / I3S / glTF / OBJ / DAE | 条件输入 + 输出 | 取决于本机适配器的实用三维工作流。 | 三维城市模型、流式三维场景和通用模型交换格式。 |

## 路线图

| 已实现 | 待实现 |
|---|---|
| [x] GeoJSON / WKT / CSV WKT | [ ] DWG 写入支持 |
| [x] ESRIJSON 输出 | [ ] MDB/Personal GDB 写入支持 |
| [x] SHP / GPKG / OpenFileGDB | [ ] 更完整的 3D Tiles / I3S 适配器 |
| [x] DXF 输出 | [ ] 未来需要时扩展栅格工作流 |
| [x] 勘测定界 TXT |  |
| [x] 通过 PDAL 转换 LAS / LAZ / E57 / PLY |  |
| [x] CRS 赋值与重投影 |  |

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
      <img alt="StarMapper - 查看这个仓库的全球收藏分布" src="https://starmapper.bruniaux.com/api/map-image/tyrrs/gis-convert" />
    </picture>
  </a>
</p>

## 贡献者验证

提交改动前运行这条命令，用来确认 README、skill 文档、安装器和转换 CLI 仍然一致：

```bash
python -m pytest -q
```

## 开源协议

本项目基于 [MIT License](LICENSE) 开源。你可以自由使用、修改和分发，但需要保留版权与许可声明。

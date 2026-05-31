# Format Support Matrix

Support depends on locally installed GDAL/OGR, PROJ, PDAL, and optional proprietary bridges. Always run `python scripts/check_env.py --json` before promising a format.

| Family | Formats | Toolchain | Notes |
|---|---|---|---|
| Text geometry | WKT, WKB | GDAL/OGR, built-in WKT fallback | Built-in fallback covers simple POINT, LINESTRING, POLYGON to GeoJSON. |
| Web vector | GeoJSON, TopoJSON, EsriJSON | GDAL/OGR, pygeoconv | EsriJSON output uses pygeoconv instead of GDAL's often read-only ESRIJSON driver. |
| OGC/vector | GML, KML, KMZ, GPX, FlatGeobuf, GeoPackage | GDAL/OGR | GeoPackage is the preferred portable output for attributes and CRS metadata. |
| Desktop GIS | SHP, MapInfo TAB/MIF, CSV WKT | GDAL/OGR, built-in CSV WKT | CSV output writes attribute columns plus a WKT geometry column named `wkt` by default. |
| Survey exchange | Land-boundary survey TXT | Built-in parser/exporter | Uses `[属性描述]` and `[地块坐标]`; output supports polygon and multipolygon data. |
| Geodatabases | FileGDB, OpenFileGDB, MDB/Personal GDB | GDAL/OGR | FileGDB writing and MDB support depend on driver availability. |
| CAD | DXF, DWG | GDAL/OGR, ODA File Converter | Prefer DXF. DWG support is conditional and often needs ODA tooling. |
| Point cloud | LAS, LAZ, E57, PLY | PDAL | LAZ may require LASzip support in the PDAL build. |
| Practical 3D | CityGML, 3D Tiles, I3S/SLPK, glTF/GLB, OBJ, DAE | GDAL/OGR plus dedicated adapters | Check `references/3d-workflows.md` before conversion. |
| Raster optional | GeoTIFF, COG, IMG, NetCDF, HDF, ASCII Grid, MBTiles | GDAL | Raster conversion is documented as future expansion for this skill's first version. |

## CRS Defaults

- Prefer `EPSG:xxxx` for ordinary horizontal CRS conversion.
- Use WKT CRS or PROJ strings for advanced horizontal/vertical CRS.
- Warn before converting to a format that may drop vertical CRS, Z, or M values.

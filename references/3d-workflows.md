# 3D GIS Workflows

This skill treats 3D as several related workflows rather than one universal format family.

## Z-aware Vector Data

Use GDAL/OGR for GeoPackage, GeoJSON, WKT, GML, KML, and Shapefile when the driver preserves Z coordinates. Prefer GeoPackage for output when the user needs attributes, CRS metadata, and fewer legacy constraints.

Example:

```bash
python scripts/gis_convert.py --input input.geojson --output output.gpkg --to-format GPKG --target-crs EPSG:4326
```

## Point Clouds

Use PDAL for LAS, LAZ, E57, and PLY.

Example:

```bash
python scripts/gis_convert.py --input input.laz --output output.ply --to-format PLY
```

For classification, reprojection, thinning, tiling, or height normalization, create a PDAL pipeline JSON rather than using a single translate command.

## CityGML

CityGML is semantic 3D city data. Use GDAL/OGR when the local build supports the required GML profile. For rich semantic conversion into 3D Tiles or glTF, prefer specialized tools such as citygml-tools, 3DCityDB, or a Cesium pipeline.

## Cesium 3D Tiles

3D Tiles conversion usually needs dedicated tilers. Treat the workflow as model or point-cloud tiling, not a plain GDAL conversion. Validate target CRS, tile coordinate system, geometric error, and texture handling.

## Esri I3S / SLPK

I3S and SLPK support depends on specific tooling. Detect local capability first. If unsupported, recommend exporting through ArcGIS tooling or converting through an intermediate glTF/3D Tiles workflow when appropriate.

## glTF, GLB, OBJ, DAE

These are 3D model exchange formats, not complete GIS containers. They may lack full CRS metadata. Use sidecar metadata or a geospatial container when CRS preservation matters.

## DWG and DXF

Prefer DXF when possible. DWG requires a local driver or an external converter such as ODA File Converter. Always inspect the environment before promising DWG conversion.

#!/usr/bin/env python3
"""Unified GIS conversion CLI for the gis-convert skill."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_env import inspect_ogr_drivers


FORMAT_BY_EXTENSION = {
    ".csv": "CSV",
    ".dae": "DAE",
    ".dwg": "CAD",
    ".dxf": "DXF",
    ".e57": "E57",
    ".esrijson": "ESRIJSON",
    ".fgb": "FlatGeobuf",
    ".geojson": "GeoJSON",
    ".gjson": "GeoJSON",
    ".gml": "GML",
    ".gdb": "OpenFileGDB",
    ".glb": "GLB",
    ".gltf": "glTF",
    ".gpkg": "GPKG",
    ".gpx": "GPX",
    ".json": "GeoJSON",
    ".kml": "KML",
    ".kmz": "LIBKML",
    ".las": "LAS",
    ".laz": "LAZ",
    ".mdb": "PGeo",
    ".obj": "OBJ",
    ".ply": "PLY",
    ".shp": "ESRI Shapefile",
    ".slpk": "I3S",
    ".sqlite": "SQLite",
    ".topojson": "TopoJSON",
    ".txt": "LAND_BOUNDARY_TXT",
    ".wkb": "WKB",
    ".wkt": "WKT",
}

FORMAT_ALIASES = {
    "cad": "CAD",
    "csv": "CSV",
    "dwg": "CAD",
    "dxf": "DXF",
    "e57": "E57",
    "esri json": "ESRIJSON",
    "esrijson": "ESRIJSON",
    "fgb": "FlatGeobuf",
    "filegdb": "OpenFileGDB",
    "flatgeobuf": "FlatGeobuf",
    "gdb": "OpenFileGDB",
    "geojosn": "GeoJSON",
    "geojson": "GeoJSON",
    "geopackage": "GPKG",
    "gjson": "GeoJSON",
    "gml": "GML",
    "gpkg": "GPKG",
    "gpx": "GPX",
    "gt txt": "LAND_BOUNDARY_TXT",
    "gttxt": "LAND_BOUNDARY_TXT",
    "json": "GeoJSON",
    "kml": "KML",
    "kmz": "LIBKML",
    "land boundary txt": "LAND_BOUNDARY_TXT",
    "land boundary": "LAND_BOUNDARY_TXT",
    "landtxt": "LAND_BOUNDARY_TXT",
    "land-boundary-txt": "LAND_BOUNDARY_TXT",
    "las": "LAS",
    "laz": "LAZ",
    "libkml": "LIBKML",
    "mdb": "PGeo",
    "openfilegdb": "OpenFileGDB",
    "pgeo": "PGeo",
    "personal gdb": "PGeo",
    "personalgdb": "PGeo",
    "ply": "PLY",
    "shape": "ESRI Shapefile",
    "esri shapefile": "ESRI Shapefile",
    "esrishapefile": "ESRI Shapefile",
    "shapefile": "ESRI Shapefile",
    "shp": "ESRI Shapefile",
    "sqlite": "SQLite",
    "topojson": "TopoJSON",
    "txt": "LAND_BOUNDARY_TXT",
    "wkb": "WKB",
    "wkt": "WKT",
    "勘测定界txt": "LAND_BOUNDARY_TXT",
    "勘测定界": "LAND_BOUNDARY_TXT",
    "国土txt": "LAND_BOUNDARY_TXT",
}

POINT_CLOUD_FORMATS = {"LAS", "LAZ", "E57", "PLY"}
THREE_D_MODEL_FORMATS = {"GLB", "glTF", "OBJ", "DAE", "I3S", "3D Tiles"}
INTERNAL_INPUT_FORMATS = {"CSV", "LAND_BOUNDARY_TXT"}
INTERNAL_OUTPUT_FORMATS = {"CSV", "ESRIJSON", "LAND_BOUNDARY_TXT", "WKT"}
DRIVER_FALLBACKS = {
    "KML": ["KML", "LIBKML"],
}
DEFAULT_READ_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")
DEFAULT_GEOMETRY_COLUMN = "wkt"
PYGEOCONV_SPEC = "pygeoconv>=1.0.1,<2"

LANDTXT_DEFAULT_META = {
    "格式版本号": "1.0",
    "数据产生单位": "",
    "数据产生日期": "",
    "坐标系": "2000国家大地坐标系",
    "几度分带": "",
    "投影类型": "高斯克吕格",
    "计量单位": "米",
    "带号": "",
    "精度": "0.001",
}
LANDTXT_PROPERTY_ALIASES = {
    "地块编号": ("地块编号", "parcel_id", "id"),
    "地块名称": ("地块名称", "name"),
    "地块用途": ("地块用途", "land_use"),
    "地类编码": ("地类编码", "land_code"),
    "图幅号": ("图幅号", "map_sheet"),
    "地块面积": ("地块面积", "area"),
}


@dataclass(frozen=True)
class ConversionRequest:
    """Normalized conversion request used by command builders."""

    input_path: Path
    output_path: Path
    to_format: str | None = None
    from_format: str | None = None
    source_crs: str | None = None
    target_crs: str | None = None
    layer: str | None = None
    overwrite: bool = False
    geometry_column: str = DEFAULT_GEOMETRY_COLUMN
    encoding: str | None = None
    landtxt_meta: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class InputMetadata:
    """Lightweight metadata derived from an input vector dataset."""

    crs: str | None
    extent: tuple[float, float, float, float] | None


@dataclass(frozen=True)
class FeatureCollectionData:
    """GeoJSON features plus optional CRS and extent metadata."""

    features: list[dict[str, Any]]
    crs: str | None = None
    extent: tuple[float, float, float, float] | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def to_geojson(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": "FeatureCollection", "features": self.features}
        if self.crs:
            data["crs"] = {"type": "name", "properties": {"name": self.crs}}
        return data


def normalize_format(value: str | None) -> str | None:
    """Normalize user-facing format names and aliases to driver names."""

    if not value:
        return None
    cleaned = value.strip().lstrip(".")
    key = re.sub(r"[\s_-]+", " ", cleaned.lower()).strip()
    compact = key.replace(" ", "")
    return FORMAT_ALIASES.get(key) or FORMAT_ALIASES.get(compact) or FORMAT_ALIASES.get(cleaned.lower()) or cleaned


def infer_format(path: Path) -> str | None:
    """Infer a GIS format name from a path extension."""

    return FORMAT_BY_EXTENSION.get(path.suffix.lower())


def _normalized_request_formats(request: ConversionRequest) -> tuple[str | None, str | None]:
    from_format = normalize_format(request.from_format) or infer_format(request.input_path)
    to_format = normalize_format(request.to_format) or infer_format(request.output_path)
    return from_format, to_format


def _is_point_cloud_conversion(from_format: str | None, to_format: str | None) -> bool:
    return (from_format in POINT_CLOUD_FORMATS) or (to_format in POINT_CLOUD_FORMATS)


def build_conversion_command(
    request: ConversionRequest,
    ogr2ogr_path: str | None = None,
    pdal_path: str | None = None,
    input_metadata: InputMetadata | None = None,
) -> list[str]:
    """Build the native command for a conversion without executing it."""

    from_format, to_format = _normalized_request_formats(request)
    if not to_format:
        raise ValueError("Unable to infer output format. Pass --to-format explicitly.")
    if to_format in INTERNAL_OUTPUT_FORMATS:
        raise RuntimeError(f"{to_format} output is handled internally and does not use a native conversion command.")

    if _is_point_cloud_conversion(from_format, to_format):
        if not pdal_path:
            raise RuntimeError("PDAL is required for point-cloud conversion but was not found.")
        return [pdal_path, "translate", str(request.input_path), str(request.output_path)]

    if to_format in THREE_D_MODEL_FORMATS or from_format in THREE_D_MODEL_FORMATS:
        raise RuntimeError(
            "This 3D model workflow needs a dedicated adapter. See references/3d-workflows.md for supported toolchains."
        )

    if not ogr2ogr_path:
        raise RuntimeError("ogr2ogr is required for vector/raster conversion but was not found.")

    command = [ogr2ogr_path, "-f", to_format]
    if request.overwrite:
        command.append("-overwrite")
    if request.source_crs:
        command.extend(["-s_srs", request.source_crs])
    elif input_metadata and not input_metadata.crs and looks_like_geographic_extent(input_metadata.extent):
        command.extend(["-a_srs", "EPSG:4326"])
    if request.target_crs:
        command.extend(["-t_srs", request.target_crs])
    command.extend([str(request.output_path), str(request.input_path)])
    if request.layer:
        command.append(request.layer)
    return command


def import_ogr() -> Any:
    """Import GDAL/OGR bindings lazily so help and tests work without them."""

    try:
        from osgeo import ogr  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Python GDAL bindings are required for this operation.") from exc
    ogr.UseExceptions()
    return ogr, None


def import_pygeoconv() -> Any:
    """Import pygeoconv lazily so non-ESRIJSON workflows work without it."""

    try:
        import pygeoconv  # type: ignore
    except ImportError as exc:
        raise RuntimeError(f"{PYGEOCONV_SPEC} is required for ESRIJSON output. Install it with: python -m pip install \"{PYGEOCONV_SPEC}\"") from exc
    return pygeoconv


def _crs_to_identifier(spatial_ref: Any) -> str | None:
    if not spatial_ref:
        return None
    authority_name = spatial_ref.GetAuthorityName(None)
    authority_code = spatial_ref.GetAuthorityCode(None)
    if authority_name and authority_code:
        return f"{authority_name}:{authority_code}"
    text = spatial_ref.ExportToWkt()
    return text or None


def inspect_input_metadata(input_path: Path, layer_name: str | None = None) -> InputMetadata:
    """Inspect input CRS and extent when Python GDAL bindings are available."""

    ogr, _ = import_ogr()
    dataset = ogr.Open(str(input_path))
    if dataset is None:
        return InputMetadata(crs=None, extent=None)
    layer = dataset.GetLayerByName(layer_name) if layer_name else dataset.GetLayer(0)
    if layer is None:
        return InputMetadata(crs=None, extent=None)
    return InputMetadata(crs=_crs_to_identifier(layer.GetSpatialRef()), extent=layer.GetExtent())


def looks_like_geographic_extent(extent: tuple[float, float, float, float] | None) -> bool:
    """Return true when an extent looks like longitude/latitude coordinates."""

    if extent is None:
        return False
    min_x, max_x, min_y, max_y = extent
    return -180 <= min_x <= 180 and -180 <= max_x <= 180 and -90 <= min_y <= 90 and -90 <= max_y <= 90


def _format_driver_error(format_name: str) -> str:
    if format_name == "CAD":
        return "DWG/CAD writing is not supported by this GDAL build. Use DXF or a dedicated DWG toolchain."
    if format_name == "PGeo":
        return "MDB/Personal GDB writing requires a PGeo/ODBC driver. Use GPKG or OpenFileGDB instead."
    return f"OGR driver is missing or read-only: {format_name}"


def validate_driver_support(format_name: str | None, drivers: dict[str, Any] | None = None) -> list[str]:
    """Validate that an output driver exists and can write; return non-fatal warnings."""

    _, warnings = resolve_output_driver(format_name, drivers=drivers)
    return warnings


def resolve_output_driver(format_name: str | None, drivers: dict[str, Any] | None = None) -> tuple[str | None, list[str]]:
    """Resolve a requested output format to a writable local OGR driver."""

    if not format_name or format_name in INTERNAL_OUTPUT_FORMATS or format_name in POINT_CLOUD_FORMATS:
        return format_name, []
    if format_name in THREE_D_MODEL_FORMATS:
        raise RuntimeError("This 3D model workflow needs a dedicated adapter. See references/3d-workflows.md.")
    available_drivers = drivers if drivers is not None else inspect_ogr_drivers()
    candidates = DRIVER_FALLBACKS.get(format_name, [format_name])
    for candidate in candidates:
        status = available_drivers.get(candidate)
        if status and getattr(status, "write", False):
            warnings: list[str] = []
            if candidate != format_name:
                warnings.append(f"Using {candidate} driver for {format_name} output because {format_name} is unavailable or read-only.")
            if candidate == "DXF":
                warnings.append("DXF is a CAD exchange format; arbitrary GIS attribute fields may be dropped.")
            return candidate, warnings
    if format_name == "KML" and "LIBKML" in candidates:
        raise RuntimeError("KML/LIBKML writing is unavailable in this GDAL build. Use GeoJSON or GPKG instead.")
    raise RuntimeError(_format_driver_error(format_name))


def read_text_with_fallback(path: Path, encoding: str | None = None) -> str:
    """Read text using an explicit encoding or the supported fallback encodings."""

    encodings = (encoding,) if encoding else DEFAULT_READ_ENCODINGS
    errors: list[str] = []
    for candidate in encodings:
        try:
            return path.read_text(encoding=candidate)
        except UnicodeDecodeError as exc:
            errors.append(f"{candidate}: {exc}")
    raise UnicodeDecodeError("gis-convert", b"", 0, 1, "; ".join(errors))


def _write_json(path: Path, data: Any, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_coordinate_tuple(text: str) -> list[float]:
    values = [float(part) for part in re.split(r"\s+", text.strip()) if part]
    if len(values) < 2:
        raise ValueError("A coordinate must contain at least x and y values.")
    return values


def _parse_wkt_geometry(wkt: str) -> dict[str, Any]:
    cleaned = wkt.strip()
    match = re.match(r"^(?P<type>POINT|LINESTRING|POLYGON)\s*(?:Z|M|ZM)?\s*\((?P<body>.*)\)$", cleaned, re.IGNORECASE)
    if not match:
        raise ValueError("The lightweight WKT fallback supports POINT, LINESTRING, and POLYGON only.")
    geom_type = match.group("type").upper()
    body = match.group("body").strip()
    if geom_type == "POINT":
        return {"type": "Point", "coordinates": _parse_coordinate_tuple(body)}
    if geom_type == "LINESTRING":
        return {"type": "LineString", "coordinates": [_parse_coordinate_tuple(part) for part in body.split(",")]}
    rings = []
    for ring in re.findall(r"\(([^()]*)\)", body):
        rings.append([_parse_coordinate_tuple(part) for part in ring.split(",")])
    if not rings and body:
        rings.append([_parse_coordinate_tuple(part) for part in body.split(",")])
    return {"type": "Polygon", "coordinates": rings}


def _format_number(value: Any) -> str:
    number = float(value)
    return f"{number:.12g}"


def _format_coordinate(coordinate: list[Any] | tuple[Any, ...]) -> str:
    return " ".join(_format_number(value) for value in coordinate)


def geojson_geometry_to_wkt(geometry: dict[str, Any]) -> str:
    """Convert a GeoJSON geometry object to a WKT string."""

    geom_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geom_type == "Point":
        return f"POINT ({_format_coordinate(coordinates)})"
    if geom_type == "LineString":
        return "LINESTRING (" + ", ".join(_format_coordinate(point) for point in coordinates) + ")"
    if geom_type == "Polygon":
        rings = ["(" + ", ".join(_format_coordinate(point) for point in ring) + ")" for ring in coordinates]
        return "POLYGON (" + ", ".join(rings) + ")"
    if geom_type == "MultiPoint":
        return "MULTIPOINT (" + ", ".join("(" + _format_coordinate(point) + ")" for point in coordinates) + ")"
    if geom_type == "MultiLineString":
        lines = ["(" + ", ".join(_format_coordinate(point) for point in line) + ")" for line in coordinates]
        return "MULTILINESTRING (" + ", ".join(lines) + ")"
    if geom_type == "MultiPolygon":
        polygons = []
        for polygon in coordinates:
            rings = ["(" + ", ".join(_format_coordinate(point) for point in ring) + ")" for ring in polygon]
            polygons.append("(" + ", ".join(rings) + ")")
        return "MULTIPOLYGON (" + ", ".join(polygons) + ")"
    raise ValueError(f"Unsupported GeoJSON geometry for WKT export: {geom_type}")


def _iter_coordinate_values(geometry: dict[str, Any]) -> list[list[float]]:
    coordinates = geometry.get("coordinates")
    if coordinates is None:
        return []
    values: list[list[float]] = []

    def walk(item: Any) -> None:
        if isinstance(item, (list, tuple)) and item and all(isinstance(value, (int, float)) for value in item[:2]):
            values.append([float(item[0]), float(item[1])])
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                walk(child)

    walk(coordinates)
    return values


def _extent_from_features(features: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    points: list[list[float]] = []
    for feature in features:
        geometry = feature.get("geometry")
        if geometry:
            points.extend(_iter_coordinate_values(geometry))
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), max(xs), min(ys), max(ys)


def _geojson_crs_to_identifier(data: dict[str, Any]) -> str | None:
    crs = data.get("crs")
    if not isinstance(crs, dict):
        return None
    properties = crs.get("properties")
    if isinstance(properties, dict) and properties.get("name"):
        return str(properties["name"])
    return None


def _feature_collection_from_geojson(data: dict[str, Any]) -> FeatureCollectionData:
    data_type = data.get("type")
    if data_type == "FeatureCollection":
        features = list(data.get("features", []))
    elif data_type == "Feature":
        features = [data]
    else:
        features = [{"type": "Feature", "properties": {}, "geometry": data}]
    extent = _extent_from_features(features)
    return FeatureCollectionData(features=features, crs=_geojson_crs_to_identifier(data), extent=extent)


def _features_from_wkt_text(text: str) -> list[dict[str, Any]]:
    features = []
    for line in text.splitlines():
        wkt = line.strip()
        if not wkt:
            continue
        features.append({"type": "Feature", "properties": {}, "geometry": _parse_wkt_geometry(wkt)})
    return features


def convert_wkt_to_geojson(
    input_path: Path,
    output_path: Path,
    target_crs: str | None = None,
    overwrite: bool = False,
    encoding: str | None = None,
) -> None:
    """Convert a simple WKT geometry file to GeoJSON without native GDAL bindings."""

    text = read_text_with_fallback(input_path, encoding)
    features = _features_from_wkt_text(text)
    if not features:
        raise ValueError("WKT input contains no geometries.")
    feature_collection: dict[str, Any] = {"type": "FeatureCollection", "features": features}
    if target_crs:
        feature_collection["crs"] = {"type": "name", "properties": {"name": target_crs}}
    _write_json(output_path, feature_collection, overwrite=overwrite)


def _feature_properties_from_ogr(feature: Any) -> dict[str, Any]:
    definition = feature.GetDefnRef()
    properties: dict[str, Any] = {}
    for index in range(definition.GetFieldCount()):
        field_defn = definition.GetFieldDefn(index)
        name = field_defn.GetName()
        properties[name] = feature.GetField(index)
    return properties


def _load_features_from_ogr(input_path: Path, layer_name: str | None = None) -> FeatureCollectionData:
    ogr, _ = import_ogr()
    dataset = ogr.Open(str(input_path))
    if dataset is None:
        raise RuntimeError(f"Unable to open input dataset: {input_path}")
    layer = dataset.GetLayerByName(layer_name) if layer_name else dataset.GetLayer(0)
    if layer is None:
        raise RuntimeError(f"Unable to open input layer: {layer_name or 0}")
    features = []
    for feature in layer:
        geometry = feature.GetGeometryRef()
        geometry_data = json.loads(geometry.ExportToJson()) if geometry else None
        features.append({"type": "Feature", "properties": _feature_properties_from_ogr(feature), "geometry": geometry_data})
    return FeatureCollectionData(features=features, crs=_crs_to_identifier(layer.GetSpatialRef()), extent=layer.GetExtent())


def _load_features_via_ogr2ogr(input_path: Path, layer_name: str | None = None) -> FeatureCollectionData:
    """Use ogr2ogr to normalize any readable vector dataset to temporary GeoJSON."""

    ogr2ogr_path = shutil.which("ogr2ogr")
    if not ogr2ogr_path:
        return _load_features_from_ogr(input_path, layer_name)
    with tempfile.TemporaryDirectory(prefix="gis-convert-read-") as tmpdir:
        temp_geojson = Path(tmpdir) / "input.geojson"
        command = [ogr2ogr_path, "-f", "GeoJSON", str(temp_geojson), str(input_path)]
        if layer_name:
            command.append(layer_name)
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or f"ogr2ogr failed with exit code {completed.returncode}")
        data = json.loads(temp_geojson.read_text(encoding="utf-8"))
        return _feature_collection_from_geojson(data)


def load_feature_collection(request: ConversionRequest) -> FeatureCollectionData:
    """Load supported input formats into a GeoJSON FeatureCollection representation."""

    from_format, _ = _normalized_request_formats(request)
    if from_format == "GeoJSON":
        data = json.loads(read_text_with_fallback(request.input_path, request.encoding))
        return _feature_collection_from_geojson(data)
    if from_format == "WKT":
        features = _features_from_wkt_text(read_text_with_fallback(request.input_path, request.encoding))
        return FeatureCollectionData(features=features, extent=_extent_from_features(features))
    if from_format == "CSV":
        return load_csv_wkt(request.input_path, geometry_column=request.geometry_column, encoding=request.encoding)
    if from_format == "LAND_BOUNDARY_TXT":
        return load_land_boundary_txt(request.input_path, encoding=request.encoding)
    return _load_features_via_ogr2ogr(request.input_path, request.layer)


def export_vector_to_wkt(input_path: Path, output_path: Path, layer_name: str | None = None, overwrite: bool = False) -> None:
    """Export vector geometries to a plain one-WKT-per-line text file."""

    request = ConversionRequest(input_path=input_path, output_path=output_path, layer=layer_name, overwrite=overwrite)
    data = load_feature_collection(request)
    export_features_to_wkt(data, output_path, overwrite=overwrite)


def export_features_to_wkt(data: FeatureCollectionData, output_path: Path, overwrite: bool = False) -> None:
    """Export loaded features to a plain one-WKT-per-line text file."""

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for feature in data.features:
            geometry = feature.get("geometry")
            if geometry:
                handle.write(geojson_geometry_to_wkt(geometry))
                handle.write("\n")


def load_csv_wkt(input_path: Path, geometry_column: str = DEFAULT_GEOMETRY_COLUMN, encoding: str | None = None) -> FeatureCollectionData:
    """Load a CSV file that stores geometry in a WKT column."""

    text = read_text_with_fallback(input_path, encoding)
    rows = list(csv.DictReader(text.splitlines()))
    if rows and geometry_column not in rows[0]:
        raise ValueError(f"CSV input must contain WKT geometry column: {geometry_column}")
    features = []
    for row in rows:
        wkt = (row.get(geometry_column) or "").strip()
        if not wkt:
            continue
        properties = {key: value for key, value in row.items() if key != geometry_column}
        features.append({"type": "Feature", "properties": properties, "geometry": _parse_wkt_geometry(wkt)})
    return FeatureCollectionData(features=features, extent=_extent_from_features(features))


def export_features_to_csv(data: FeatureCollectionData, output_path: Path, geometry_column: str, encoding: str | None, overwrite: bool) -> None:
    """Export features to CSV with a WKT geometry column."""

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {output_path}")
    property_columns: list[str] = []
    for feature in data.features:
        for name in (feature.get("properties") or {}).keys():
            output_name = f"{geometry_column}_attr" if name == geometry_column else name
            if output_name not in property_columns:
                property_columns.append(output_name)
    fieldnames = [*property_columns, geometry_column]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding=encoding or "utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for feature in data.features:
            row: dict[str, Any] = {}
            for name, value in (feature.get("properties") or {}).items():
                output_name = f"{geometry_column}_attr" if name == geometry_column else name
                row[output_name] = "" if value is None else value
            geometry = feature.get("geometry")
            row[geometry_column] = geojson_geometry_to_wkt(geometry) if geometry else ""
            writer.writerow(row)


def _is_landtxt_header(parts: list[str]) -> bool:
    if "@" in parts:
        return True
    if len(parts) < 4:
        return False
    try:
        int(float(parts[0]))
        float(parts[1])
    except ValueError:
        return False
    return not _is_landtxt_coord(parts)


def _is_landtxt_coord(parts: list[str]) -> bool:
    if len(parts) < 4:
        return False
    try:
        int(float(parts[1]))
        float(parts[2])
        float(parts[3])
    except ValueError:
        return False
    return True


def _close_ring(points: list[list[float]]) -> list[list[float]]:
    if points and points[0] != points[-1]:
        return [*points, points[0]]
    return points


def _feature_from_landtxt_block(header: list[str], coords: list[list[str]]) -> dict[str, Any] | None:
    if not coords:
        return None
    properties = {
        "地块面积": header[1] if len(header) > 1 else "",
        "地块编号": header[2] if len(header) > 2 else "",
        "地块名称": header[3] if len(header) > 3 else "",
        "记录图形属性": header[4] if len(header) > 4 else "面",
        "图幅号": header[5] if len(header) > 5 else "",
        "地块用途": header[6] if len(header) > 6 else "",
        "地类编码": header[7] if len(header) > 7 else "",
    }
    rings_by_id: dict[int, list[list[float]]] = {}
    for parts in coords:
        ring_id = int(float(parts[1]))
        rings_by_id.setdefault(ring_id, []).append([float(parts[2]), float(parts[3])])
    rings = [_close_ring(rings_by_id[ring_id]) for ring_id in sorted(rings_by_id)]
    return {"type": "Feature", "properties": properties, "geometry": {"type": "Polygon", "coordinates": rings}}


def load_land_boundary_txt(input_path: Path, encoding: str | None = None) -> FeatureCollectionData:
    """Parse the land-boundary survey TXT exchange format."""

    text = read_text_with_fallback(input_path, encoding)
    section: str | None = None
    metadata: dict[str, str] = {}
    features: list[dict[str, Any]] = []
    current_header: list[str] = []
    current_coords: list[list[str]] = []

    def flush() -> None:
        nonlocal current_header, current_coords
        feature = _feature_from_landtxt_block(current_header, current_coords)
        if feature:
            features.append(feature)
        current_header = []
        current_coords = []

    for raw_line in text.splitlines():
        line = raw_line.strip().strip("{}")
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if section == "地块坐标":
                flush()
            section = line.strip("[]")
            continue
        if section == "属性描述" and "=" in line:
            key, value = line.split("=", 1)
            metadata[key.strip()] = value.strip()
            continue
        if section != "地块坐标":
            continue
        parts = [part.strip() for part in line.split(",")]
        if _is_landtxt_header(parts):
            flush()
            current_header = [part for part in parts if part != "@"]
        elif _is_landtxt_coord(parts):
            current_coords.append(parts)
    if section == "地块坐标":
        flush()
    return FeatureCollectionData(features=features, crs=metadata.get("坐标系"), extent=_extent_from_features(features), metadata=metadata)


def _property_value(properties: dict[str, Any], canonical_name: str, fallback: str = "") -> str:
    for name in LANDTXT_PROPERTY_ALIASES.get(canonical_name, (canonical_name,)):
        value = properties.get(name)
        if value not in (None, ""):
            return str(value)
    return fallback


def _ring_area(ring: list[list[Any]]) -> float:
    points = _close_ring([[float(point[0]), float(point[1])] for point in ring])
    if len(points) < 4:
        return 0.0
    total = 0.0
    for index in range(len(points) - 1):
        x1, y1 = points[index]
        x2, y2 = points[index + 1]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def _polygon_area(rings: list[list[list[Any]]]) -> float:
    if not rings:
        return 0.0
    area = _ring_area(rings[0])
    for ring in rings[1:]:
        area -= _ring_area(ring)
    return max(area, 0.0)


def _polygon_parts(geometry: dict[str, Any]) -> list[list[list[list[Any]]]]:
    geom_type = geometry.get("type")
    if geom_type == "Polygon":
        return [geometry.get("coordinates", [])]
    if geom_type == "MultiPolygon":
        return geometry.get("coordinates", [])
    raise ValueError("Land-boundary TXT output only supports Polygon and MultiPolygon geometries. Use CSV WKT or GeoJSON for points/lines.")


def export_features_to_land_boundary_txt(
    data: FeatureCollectionData,
    output_path: Path,
    metadata_overrides: dict[str, str],
    encoding: str | None,
    overwrite: bool,
) -> None:
    """Export polygon features to the land-boundary survey TXT exchange format."""

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {output_path}")
    metadata = {**LANDTXT_DEFAULT_META, **data.metadata, **metadata_overrides}
    lines = ["[属性描述]"]
    lines.extend(f"{key}={value}" for key, value in metadata.items())
    lines.append("")
    lines.append("[地块坐标]")
    parcel_index = 1
    for feature in data.features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry")
        if not geometry:
            continue
        for polygon in _polygon_parts(geometry):
            area = _property_value(properties, "地块面积") or f"{_polygon_area(polygon):.3f}"
            parcel_id = _property_value(properties, "地块编号", str(parcel_index))
            name = _property_value(properties, "地块名称", parcel_id)
            map_sheet = _property_value(properties, "图幅号")
            land_use = _property_value(properties, "地块用途")
            land_code = _property_value(properties, "地类编码")
            point_count = sum(len(_close_ring(ring)) for ring in polygon)
            lines.append(f"{point_count},{area},{parcel_id},{name},面,{map_sheet},{land_use},{land_code},@")
            point_index = 1
            for ring_index, ring in enumerate(polygon, start=1):
                for point in _close_ring(ring):
                    lines.append(f"J{point_index},{ring_index},{_format_number(point[0])},{_format_number(point[1])}")
                    point_index += 1
            parcel_index += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding=encoding or "utf-8")


def _parse_wkid(crs: str | None) -> int | None:
    if not crs:
        return None
    text = crs.strip()
    if text.isdigit():
        return int(text)
    match = re.match(r"^EPSG\s*:\s*(\d+)$", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _resolve_wkid(request: ConversionRequest, data: FeatureCollectionData) -> int:
    for crs in (request.target_crs, request.source_crs, data.crs):
        wkid = _parse_wkid(crs)
        if wkid is not None:
            return wkid
    if looks_like_geographic_extent(data.extent):
        return 4326
    raise RuntimeError("ESRIJSON output needs a WKID CRS. Pass --source-crs EPSG:<number> or --target-crs EPSG:<number>.")


def _normalize_pygeoconv_output(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _esri_geometry_type(geometry: dict[str, Any]) -> str | None:
    if {"x", "y"}.issubset(geometry):
        return "esriGeometryPoint"
    if "points" in geometry:
        return "esriGeometryMultipoint"
    if "paths" in geometry:
        return "esriGeometryPolyline"
    if "rings" in geometry:
        return "esriGeometryPolygon"
    return None


def export_features_to_esrijson(data: FeatureCollectionData, output_path: Path, request: ConversionRequest) -> None:
    """Export features to Esri JSON using pygeoconv."""

    wkid = _resolve_wkid(request, data)
    pygeoconv = import_pygeoconv()
    from_format, _ = _normalized_request_formats(request)
    if not data.features:
        payload: Any = {"geometryType": None, "spatialReference": {"wkid": wkid}, "features": []}
    elif from_format == "WKT" and len(data.features) == 1 and not data.features[0].get("properties"):
        wkt = geojson_geometry_to_wkt(data.features[0]["geometry"])
        payload = _normalize_pygeoconv_output(pygeoconv.wkt_to_esri_json(wkt, wkid=wkid))
    else:
        payload = _normalize_pygeoconv_output(pygeoconv.geojson_to_esri_json(data.to_geojson(), wkid=wkid))
        if isinstance(payload, list):
            payload = {
                "geometryType": _esri_geometry_type(payload[0]) if payload else None,
                "spatialReference": {"wkid": wkid},
                "features": [{"geometry": geometry} for geometry in payload],
            }
    _write_json(output_path, payload, overwrite=request.overwrite)


def _write_feature_collection_geojson(data: FeatureCollectionData, output_path: Path, request: ConversionRequest) -> None:
    if request.target_crs:
        data = FeatureCollectionData(features=data.features, crs=request.target_crs, extent=data.extent, metadata=data.metadata)
    _write_json(output_path, data.to_geojson(), overwrite=request.overwrite)


def _convert_internal_input_with_ogr(request: ConversionRequest, to_format: str) -> int:
    data = load_feature_collection(request)
    with tempfile.TemporaryDirectory(prefix="gis-convert-") as tmpdir:
        temp_geojson = Path(tmpdir) / "input.geojson"
        _write_json(temp_geojson, data.to_geojson(), overwrite=True)
        temp_request = replace(request, input_path=temp_geojson, from_format="GeoJSON", to_format=to_format)
        metadata = InputMetadata(crs=data.crs, extent=data.extent)
        resolved_to_format, warnings = resolve_output_driver(to_format)
        if resolved_to_format and resolved_to_format != to_format:
            temp_request = replace(temp_request, to_format=resolved_to_format)
        for warning in warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        command = build_conversion_command(
            temp_request,
            ogr2ogr_path=shutil.which("ogr2ogr"),
            pdal_path=shutil.which("pdal"),
            input_metadata=metadata,
        )
        print("+ " + " ".join(command))
        completed = subprocess.run(command, check=False)
        return completed.returncode


def parse_landtxt_meta(values: list[str] | None) -> dict[str, str]:
    """Parse repeated KEY=VALUE metadata overrides."""

    result: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"--landtxt-meta must use KEY=VALUE syntax: {value}")
        key, item_value = value.split("=", 1)
        result[key.strip()] = item_value.strip()
    return result


def validate_request(request: ConversionRequest) -> None:
    """Validate paths and format choices before executing a conversion."""

    if not request.input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {request.input_path}")
    if request.output_path.exists() and not request.overwrite:
        raise FileExistsError(f"Output already exists: {request.output_path}")
    from_format, to_format = _normalized_request_formats(request)
    if not from_format:
        raise ValueError("Unable to infer input format. Pass --from-format explicitly.")
    if not to_format:
        raise ValueError("Unable to infer output format. Pass --to-format explicitly.")
    if to_format not in INTERNAL_OUTPUT_FORMATS and not (from_format == "WKT" and to_format == "GeoJSON"):
        validate_driver_support(to_format)


def list_formats() -> int:
    """Print available OGR drivers as JSON."""

    drivers = inspect_ogr_drivers()
    print(json.dumps({name: driver.to_dict() for name, driver in drivers.items()}, indent=2, sort_keys=True))
    return 0


def run_conversion(request: ConversionRequest, validate_only: bool = False) -> int:
    """Validate and execute a GIS conversion request."""

    validate_request(request)
    from_format, to_format = _normalized_request_formats(request)
    if validate_only:
        print("Validation passed.")
        return 0
    if from_format == "WKT" and to_format == "GeoJSON":
        convert_wkt_to_geojson(
            request.input_path,
            request.output_path,
            target_crs=request.target_crs,
            overwrite=request.overwrite,
            encoding=request.encoding,
        )
        return 0
    if to_format in INTERNAL_OUTPUT_FORMATS:
        data = load_feature_collection(request)
        if to_format == "WKT":
            export_features_to_wkt(data, request.output_path, overwrite=request.overwrite)
        elif to_format == "CSV":
            export_features_to_csv(data, request.output_path, request.geometry_column, request.encoding, request.overwrite)
        elif to_format == "ESRIJSON":
            export_features_to_esrijson(data, request.output_path, request)
        elif to_format == "LAND_BOUNDARY_TXT":
            export_features_to_land_boundary_txt(data, request.output_path, request.landtxt_meta, request.encoding, request.overwrite)
        return 0
    if from_format in INTERNAL_INPUT_FORMATS:
        if to_format == "GeoJSON":
            _write_feature_collection_geojson(load_feature_collection(request), request.output_path, request)
            return 0
        return _convert_internal_input_with_ogr(request, to_format)

    resolved_to_format, warnings = resolve_output_driver(to_format)
    if resolved_to_format and resolved_to_format != to_format:
        request = replace(request, to_format=resolved_to_format)
    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    try:
        metadata = inspect_input_metadata(request.input_path, request.layer)
    except RuntimeError:
        metadata = InputMetadata(crs=None, extent=None)
    if not request.source_crs and metadata.crs is None and metadata.extent and not looks_like_geographic_extent(metadata.extent):
        print("Warning: input CRS is unknown. Pass --source-crs if the data is not already in the desired CRS.", file=sys.stderr)
    command = build_conversion_command(
        request,
        ogr2ogr_path=shutil.which("ogr2ogr"),
        pdal_path=shutil.which("pdal"),
        input_metadata=metadata,
    )
    print("+ " + " ".join(command))
    completed = subprocess.run(command, check=False)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for GIS format conversion."""

    parser = argparse.ArgumentParser(description="Convert GIS data between vector, point-cloud, and selected 3D exchange formats.")
    parser.add_argument("--input", type=Path, help="Input GIS file or dataset path.")
    parser.add_argument("--output", type=Path, help="Output GIS file or dataset path.")
    parser.add_argument("--from-format", help="Input format override, such as GeoJSON, WKT, CSV, or OpenFileGDB.")
    parser.add_argument("--to-format", help="Output format override, such as GPKG, ESRIJSON, CSV, or land-boundary-txt.")
    parser.add_argument("--source-crs", help="Source CRS, such as EPSG:3857.")
    parser.add_argument("--target-crs", help="Target CRS, such as EPSG:4326.")
    parser.add_argument("--layer", help="Layer name for multi-layer data sources.")
    parser.add_argument("--geometry-column", default=DEFAULT_GEOMETRY_COLUMN, help="CSV WKT geometry column name. Default: wkt.")
    parser.add_argument("--encoding", help="Encoding for TXT/CSV input or output. Read fallback: utf-8-sig, utf-8, gb18030.")
    parser.add_argument("--landtxt-meta", action="append", default=[], help="Land-boundary TXT metadata override in KEY=VALUE form.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output.")
    parser.add_argument("--validate-only", action="store_true", help="Validate request and dependencies without writing output.")
    parser.add_argument("--list-formats", action="store_true", help="List current OGR driver capabilities.")
    args = parser.parse_args(argv)

    if args.list_formats:
        return list_formats()
    if not args.input or not args.output:
        parser.error("--input and --output are required unless --list-formats is used.")
    try:
        landtxt_meta = parse_landtxt_meta(args.landtxt_meta)
    except ValueError as exc:
        parser.error(str(exc))
    request = ConversionRequest(
        input_path=args.input,
        output_path=args.output,
        to_format=args.to_format,
        from_format=args.from_format,
        source_crs=args.source_crs,
        target_crs=args.target_crs,
        layer=args.layer,
        overwrite=args.overwrite,
        geometry_column=args.geometry_column,
        encoding=args.encoding,
        landtxt_meta=landtxt_meta,
    )
    try:
        return run_conversion(request, validate_only=args.validate_only)
    except Exception as exc:
        print(f"gis-convert: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

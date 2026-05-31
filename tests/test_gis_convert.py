import csv
import json
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

from scripts.check_env import DriverStatus
from scripts.gis_convert import (
    ConversionRequest,
    FeatureCollectionData,
    InputMetadata,
    build_conversion_command,
    convert_wkt_to_geojson,
    export_features_to_csv,
    export_features_to_esrijson,
    export_features_to_land_boundary_txt,
    infer_format,
    load_csv_wkt,
    load_land_boundary_txt,
    normalize_format,
    parse_landtxt_meta,
    resolve_output_driver,
    run_conversion,
    validate_driver_support,
)


def test_infer_format_handles_common_gis_extensions():
    assert infer_format(Path("data.geojson")) == "GeoJSON"
    assert infer_format(Path("roads.shp")) == "ESRI Shapefile"
    assert infer_format(Path("city.gpkg")) == "GPKG"
    assert infer_format(Path("city.gdb")) == "OpenFileGDB"
    assert infer_format(Path("drawing.dxf")) == "DXF"
    assert infer_format(Path("drawing.dwg")) == "CAD"
    assert infer_format(Path("parcel.txt")) == "LAND_BOUNDARY_TXT"
    assert infer_format(Path("table.csv")) == "CSV"
    assert infer_format(Path("features.esrijson")) == "ESRIJSON"
    assert infer_format(Path("features.wkt")) == "WKT"
    assert infer_format(Path("cloud.laz")) == "LAZ"
    assert infer_format(Path("mesh.glb")) == "GLB"


def test_normalize_format_handles_aliases_and_typos():
    assert normalize_format("geojosn") == "GeoJSON"
    assert normalize_format(".geojson") == "GeoJSON"
    assert normalize_format("gdb") == "OpenFileGDB"
    assert normalize_format("filegdb") == "OpenFileGDB"
    assert normalize_format("dwg") == "CAD"
    assert normalize_format("mdb") == "PGeo"
    assert normalize_format("esri-shapefile") == "ESRI Shapefile"
    assert normalize_format("esrijson") == "ESRIJSON"
    assert normalize_format("land-boundary-txt") == "LAND_BOUNDARY_TXT"
    assert normalize_format("勘测定界txt") == "LAND_BOUNDARY_TXT"


def test_build_ogr2ogr_command_includes_crs_layer_and_overwrite():
    request = ConversionRequest(
        input_path=Path("input.geojson"),
        output_path=Path("output.gpkg"),
        to_format="GPKG",
        from_format="GeoJSON",
        source_crs="EPSG:3857",
        target_crs="EPSG:4326",
        layer="roads",
        overwrite=True,
    )

    command = build_conversion_command(request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal")

    assert command == [
        "/usr/bin/ogr2ogr",
        "-f",
        "GPKG",
        "-overwrite",
        "-s_srs",
        "EPSG:3857",
        "-t_srs",
        "EPSG:4326",
        "output.gpkg",
        "input.geojson",
        "roads",
    ]


def test_build_command_infers_driver_from_output_extension():
    request = ConversionRequest(input_path=Path("input.shp"), output_path=Path("output.geojson"))

    command = build_conversion_command(request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal")

    assert command[:3] == ["/usr/bin/ogr2ogr", "-f", "GeoJSON"]


def test_build_command_uses_explicit_format_over_output_extension():
    request = ConversionRequest(input_path=Path("input.shp"), output_path=Path("output.data"), to_format="GPKG")

    command = build_conversion_command(request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal")

    assert command[:3] == ["/usr/bin/ogr2ogr", "-f", "GPKG"]


def test_build_command_for_gdb_and_dxf_extensions():
    gdb_request = ConversionRequest(input_path=Path("input.shp"), output_path=Path("output.gdb"))
    dxf_request = ConversionRequest(input_path=Path("input.shp"), output_path=Path("output.dxf"))

    gdb_command = build_conversion_command(gdb_request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal")
    dxf_command = build_conversion_command(dxf_request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal")

    assert gdb_command[:3] == ["/usr/bin/ogr2ogr", "-f", "OpenFileGDB"]
    assert dxf_command[:3] == ["/usr/bin/ogr2ogr", "-f", "DXF"]


def test_wkt_output_is_internal_not_ogr_driver():
    request = ConversionRequest(input_path=Path("input.shp"), output_path=Path("output.wkt"))

    with pytest.raises(RuntimeError, match="handled internally"):
        build_conversion_command(request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal")


def test_esrijson_csv_and_landtxt_outputs_are_internal():
    for output in ["output.esrijson", "output.csv", "output.txt"]:
        request = ConversionRequest(input_path=Path("input.geojson"), output_path=Path(output))

        with pytest.raises(RuntimeError, match="handled internally"):
            build_conversion_command(request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal")


def test_build_pdal_command_for_point_cloud_formats():
    request = ConversionRequest(
        input_path=Path("input.laz"),
        output_path=Path("output.ply"),
        to_format="PLY",
        from_format="LAZ",
    )

    command = build_conversion_command(request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal")

    assert command == ["/usr/bin/pdal", "translate", "input.laz", "output.ply"]


def test_build_conversion_command_rejects_missing_pdal_for_point_cloud():
    request = ConversionRequest(input_path=Path("input.las"), output_path=Path("output.ply"), to_format="PLY")

    with pytest.raises(RuntimeError, match="PDAL"):
        build_conversion_command(request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path=None)


def test_driver_precheck_rejects_read_only_or_missing_formats():
    drivers = {
        "ESRIJSON": DriverStatus("ESRIJSON", read=True, write=False, raw_flags="rov", description="ESRIJSON"),
        "CAD": DriverStatus("CAD", read=True, write=False, raw_flags="rovs", description="AutoCAD Driver"),
    }

    assert validate_driver_support("ESRIJSON", drivers=drivers) == []
    with pytest.raises(RuntimeError, match="DXF"):
        validate_driver_support("CAD", drivers=drivers)
    with pytest.raises(RuntimeError, match="GPKG"):
        validate_driver_support("PGeo", drivers=drivers)


def test_driver_precheck_warns_for_dxf():
    drivers = {"DXF": DriverStatus("DXF", read=True, write=True, raw_flags="rw+v", description="AutoCAD DXF")}

    assert validate_driver_support("DXF", drivers=drivers) == [
        "DXF is a CAD exchange format; arbitrary GIS attribute fields may be dropped."
    ]


def test_kml_resolves_to_libkml_when_kml_driver_is_unavailable():
    drivers = {
        "KML": DriverStatus("KML", read=True, write=False, raw_flags="rov", description="KML"),
        "LIBKML": DriverStatus("LIBKML", read=True, write=True, raw_flags="rw+v", description="LIBKML"),
    }

    resolved, warnings = resolve_output_driver("KML", drivers=drivers)

    assert resolved == "LIBKML"
    assert warnings == ["Using LIBKML driver for KML output because KML is unavailable or read-only."]


def test_run_conversion_rejects_read_only_driver_before_subprocess(monkeypatch, tmp_path):
    source = tmp_path / "input.geojson"
    source.write_text("{}", encoding="utf-8")
    request = ConversionRequest(input_path=source, output_path=tmp_path / "output.dwg")
    monkeypatch.setattr(
        "scripts.gis_convert.inspect_ogr_drivers",
        lambda: {"CAD": DriverStatus("CAD", read=True, write=False, raw_flags="rov", description="CAD")},
    )
    monkeypatch.setattr("scripts.gis_convert.subprocess.run", lambda *args, **kwargs: pytest.fail("subprocess should not run"))

    with pytest.raises(RuntimeError, match="DWG"):
        run_conversion(request)


def test_run_conversion_uses_resolved_driver_for_kml_fallback(monkeypatch, tmp_path):
    source = tmp_path / "input.geojson"
    source.write_text("{}", encoding="utf-8")
    request = ConversionRequest(input_path=source, output_path=tmp_path / "output.kml")
    commands = []

    monkeypatch.setattr(
        "scripts.gis_convert.inspect_ogr_drivers",
        lambda: {"LIBKML": DriverStatus("LIBKML", read=True, write=True, raw_flags="rw+v", description="LIBKML")},
    )
    monkeypatch.setattr("scripts.gis_convert.inspect_input_metadata", lambda *_args, **_kwargs: InputMetadata(crs="EPSG:4326", extent=None))
    monkeypatch.setattr("scripts.gis_convert.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command, check=False):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("scripts.gis_convert.subprocess.run", fake_run)

    assert run_conversion(request) == 0
    assert commands[0][:3] == ["/usr/bin/ogr2ogr", "-f", "LIBKML"]


def test_crs_arguments_keep_source_by_default_and_allow_reprojection():
    request = ConversionRequest(input_path=Path("input.shp"), output_path=Path("output.gpkg"))
    reproject_request = ConversionRequest(
        input_path=Path("input.shp"),
        output_path=Path("output.gpkg"),
        source_crs="EPSG:3857",
        target_crs="EPSG:4326",
    )

    command = build_conversion_command(request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal")
    reproject_command = build_conversion_command(reproject_request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal")

    assert "-t_srs" not in command
    assert ["-s_srs", "EPSG:3857"] == reproject_command[3:5]
    assert ["-t_srs", "EPSG:4326"] == reproject_command[5:7]


def test_unknown_geographic_crs_adds_epsg_4326_assignment():
    request = ConversionRequest(input_path=Path("input.shp"), output_path=Path("output.gpkg"))
    metadata = InputMetadata(crs=None, extent=(100.0, 120.0, 20.0, 30.0))

    command = build_conversion_command(request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal", input_metadata=metadata)

    assert ["-a_srs", "EPSG:4326"] == command[3:5]


def test_unknown_projected_crs_is_not_guessed():
    request = ConversionRequest(input_path=Path("input.shp"), output_path=Path("output.gpkg"))
    metadata = InputMetadata(crs=None, extent=(300000.0, 320000.0, 2500000.0, 2600000.0))

    command = build_conversion_command(request, ogr2ogr_path="/usr/bin/ogr2ogr", pdal_path="/usr/bin/pdal", input_metadata=metadata)

    assert "-a_srs" not in command


def test_convert_wkt_point_to_geojson_preserves_z_coordinate(tmp_path):
    source = tmp_path / "point.wkt"
    target = tmp_path / "point.geojson"
    source.write_text("POINT Z (120.5 30.25 8.75)\n", encoding="utf-8")

    convert_wkt_to_geojson(source, target, target_crs="EPSG:4326", overwrite=False)

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"
    assert data["features"][0]["geometry"] == {
        "type": "Point",
        "coordinates": [120.5, 30.25, 8.75],
    }
    assert data["crs"]["properties"]["name"] == "EPSG:4326"


def test_convert_wkt_refuses_to_overwrite_without_flag(tmp_path):
    source = tmp_path / "point.wkt"
    target = tmp_path / "point.geojson"
    source.write_text("POINT (1 2)", encoding="utf-8")
    target.write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError):
        convert_wkt_to_geojson(source, target, overwrite=False)


def test_esrijson_wkt_output_uses_pygeoconv(monkeypatch, tmp_path):
    source = tmp_path / "point.wkt"
    target = tmp_path / "point.esrijson"
    source.write_text("POINT (120 30)", encoding="utf-8")
    calls = []

    def fake_wkt_to_esri_json(wkt, wkid=None):
        calls.append((wkt, wkid))
        return {"x": 120, "y": 30, "spatialReference": {"wkid": wkid}}

    monkeypatch.setattr("scripts.gis_convert.import_pygeoconv", lambda: SimpleNamespace(wkt_to_esri_json=fake_wkt_to_esri_json))

    code = run_conversion(ConversionRequest(input_path=source, output_path=target, target_crs="EPSG:4326"))

    assert code == 0
    assert calls == [("POINT (120 30)", 4326)]
    assert json.loads(target.read_text(encoding="utf-8"))["spatialReference"]["wkid"] == 4326


def test_esrijson_geojson_output_uses_pygeoconv(monkeypatch, tmp_path):
    source = tmp_path / "input.geojson"
    target = tmp_path / "output.json"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {"id": "1"}, "geometry": {"type": "Point", "coordinates": [120, 30]}}],
            }
        ),
        encoding="utf-8",
    )
    calls = []

    def fake_geojson_to_esri_json(data, wkid=None):
        calls.append((data, wkid))
        return {"geometryType": "esriGeometryPoint", "spatialReference": {"wkid": wkid}, "features": []}

    monkeypatch.setattr("scripts.gis_convert.import_pygeoconv", lambda: SimpleNamespace(geojson_to_esri_json=fake_geojson_to_esri_json))

    code = run_conversion(ConversionRequest(input_path=source, output_path=target, to_format="esrijson", target_crs="4326"))

    assert code == 0
    assert calls[0][1] == 4326
    assert calls[0][0]["features"][0]["properties"] == {"id": "1"}


def test_missing_pygeoconv_only_affects_esrijson(monkeypatch, tmp_path):
    source = tmp_path / "point.wkt"
    esri_target = tmp_path / "point.esrijson"
    geojson_target = tmp_path / "point.geojson"
    source.write_text("POINT (1 2)", encoding="utf-8")
    monkeypatch.setattr("scripts.gis_convert.import_pygeoconv", lambda: (_ for _ in ()).throw(RuntimeError("pygeoconv missing")))

    with pytest.raises(RuntimeError, match="pygeoconv"):
        run_conversion(ConversionRequest(input_path=source, output_path=esri_target, target_crs="EPSG:4326"))

    assert run_conversion(ConversionRequest(input_path=source, output_path=geojson_target, target_crs="EPSG:4326")) == 0


def test_export_features_to_csv_writes_properties_and_wkt(tmp_path):
    target = tmp_path / "output.csv"
    data = FeatureCollectionData(
        features=[
            {
                "type": "Feature",
                "properties": {"id": "1", "wkt": "attribute"},
                "geometry": {"type": "Point", "coordinates": [120.0, 30.0]},
            }
        ]
    )

    export_features_to_csv(data, target, "wkt", None, overwrite=False)

    rows = list(csv.DictReader(target.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["id"] == "1"
    assert rows[0]["wkt_attr"] == "attribute"
    assert rows[0]["wkt"] == "POINT (120 30)"


def test_csv_wkt_input_can_convert_to_geojson_with_custom_geometry_column(tmp_path):
    source = tmp_path / "input.csv"
    target = tmp_path / "output.geojson"
    source.write_text("id,geom_wkt\n1,POINT (120 30)\n", encoding="utf-8")

    code = run_conversion(ConversionRequest(input_path=source, output_path=target, geometry_column="geom_wkt"))

    assert code == 0
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["features"][0]["properties"] == {"id": "1"}
    assert data["features"][0]["geometry"]["coordinates"] == [120.0, 30.0]


def test_load_csv_wkt_requires_geometry_column(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("id,name\n1,a\n", encoding="utf-8")

    with pytest.raises(ValueError, match="WKT geometry column"):
        load_csv_wkt(source)


def test_parse_land_boundary_txt_to_polygon(tmp_path):
    source = tmp_path / "parcel.txt"
    source.write_text(
        "\n".join(
            [
                "[属性描述]",
                "坐标系=2000国家大地坐标系",
                "[地块坐标]",
                "5,100.000,DK001,测试地块,面,H50G001,建设用地,0701,@",
                "J1,1,0,0",
                "J2,1,10,0",
                "J3,1,10,10",
                "J4,1,0,10",
                "J5,1,0,0",
            ]
        ),
        encoding="gb18030",
    )

    data = load_land_boundary_txt(source, encoding="gb18030")

    assert data.metadata["坐标系"] == "2000国家大地坐标系"
    assert data.features[0]["properties"]["地块编号"] == "DK001"
    assert data.features[0]["geometry"]["coordinates"][0][0] == [0.0, 0.0]
    assert data.features[0]["geometry"]["coordinates"][0][-1] == [0.0, 0.0]


def test_export_features_to_land_boundary_txt_writes_metadata_and_polygon(tmp_path):
    target = tmp_path / "parcel.txt"
    data = FeatureCollectionData(
        features=[
            {
                "type": "Feature",
                "properties": {"parcel_id": "DK001", "name": "测试地块", "land_code": "0701"},
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]},
            }
        ]
    )

    export_features_to_land_boundary_txt(data, target, {"带号": "39"}, "gb18030", overwrite=False)

    text = target.read_text(encoding="gb18030")
    assert "[属性描述]" in text
    assert "带号=39" in text
    assert "5,100.000,DK001,测试地块,面,,,0701,@" in text
    assert "J1,1,0,0" in text


def test_land_boundary_txt_rejects_non_polygon(tmp_path):
    target = tmp_path / "parcel.txt"
    data = FeatureCollectionData(
        features=[{"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [0, 0]}}]
    )

    with pytest.raises(ValueError, match="Polygon"):
        export_features_to_land_boundary_txt(data, target, {}, None, overwrite=False)


def test_parse_landtxt_meta_requires_key_value():
    assert parse_landtxt_meta(["带号=39"]) == {"带号": "39"}
    with pytest.raises(ValueError, match="KEY=VALUE"):
        parse_landtxt_meta(["bad"])


def test_cli_script_runs_when_invoked_by_path(tmp_path):
    source = tmp_path / "point.wkt"
    target = tmp_path / "point.geojson"
    source.write_text("POINT Z (1 2 3)", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/gis_convert.py",
            "--input",
            str(source),
            "--output",
            str(target),
            "--target-crs",
            "EPSG:4326",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(target.read_text(encoding="utf-8"))["features"][0]["geometry"]["coordinates"] == [1.0, 2.0, 3.0]

from scripts.check_env import PackageStatus, ToolStatus, parse_ogrinfo_formats


def test_parse_ogrinfo_formats_extracts_read_write_capabilities():
    output = """
Supported Formats:
  ESRI Shapefile -vector- (rw+v): ESRI Shapefile
  GeoJSON -vector- (rw+v): GeoJSON
  OpenFileGDB -vector- (rov): ESRI FileGDB
  CAD -raster,vector- (ro): AutoCAD Driver
"""

    formats = parse_ogrinfo_formats(output)

    assert formats["ESRI Shapefile"].read is True
    assert formats["ESRI Shapefile"].write is True
    assert formats["OpenFileGDB"].read is True
    assert formats["OpenFileGDB"].write is False
    assert formats["CAD"].write is False


def test_tool_status_serializes_missing_tool():
    status = ToolStatus(name="pdal", path=None, version=None, error="not found")

    assert status.to_dict() == {
        "name": "pdal",
        "path": None,
        "version": None,
        "available": False,
        "error": "not found",
    }


def test_package_status_serializes_missing_package():
    status = PackageStatus(name="pygeoconv", version=None, error="not found")

    assert status.to_dict() == {
        "name": "pygeoconv",
        "version": None,
        "available": False,
        "error": "not found",
    }

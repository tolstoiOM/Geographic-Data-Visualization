from ..geo_processor import process_geojson_make_black


def test_process_geojson_make_black_feature_collection():
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [0, 0]}},
        ],
    }
    out = process_geojson_make_black(geojson)
    props = out["features"][0]["properties"]
    assert props["stroke"] == "#000000"
    assert props["fill"] == "#000000"
    assert props["marker-color"] == "#000000"
    assert props["processed_by"] == "test_processor"


def test_process_geojson_make_black_noop_for_feature():
    geojson = {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [0, 0]}}
    out = process_geojson_make_black(geojson)
    assert out == geojson

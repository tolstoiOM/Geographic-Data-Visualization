# python
# Datei: Geographic-Data-Visualization/backend/fastapi_app/geo_processor.py
import json
from typing import Dict, Any

def process_geojson_make_black(geojson: Dict[str, Any]) -> Dict[str, Any]:
    """
    Markiert alle Features 'schwarz' durch Hinzufügen/Überschreiben von
    gängigen Style-Properties.
    """
    if geojson.get("type") != "FeatureCollection":
        return geojson

    for feat in geojson.get("features", []):
        props = feat.setdefault("properties", {})
        # gängige Property-Namen setzen, damit verschiedene Viewer etwas sehen
        props["stroke"] = "#000000"
        props["fill"] = "#000000"
        props["marker-color"] = "#000000"
        # optional: kennzeichnen, dass verarbeitet wurde
        props["processed_by"] = "test_processor"

    return geojson

if __name__ == "__main__":
    # CLI: python geo_processor.py input.geojson output.geojson
    import sys
    if len(sys.argv) < 3:
        print("Usage: python geo_processor.py input.geojson output.geojson")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        gj = json.load(f)
    out = process_geojson_make_black(gj)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("Wrote", sys.argv[2])

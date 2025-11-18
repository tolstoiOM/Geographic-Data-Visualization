"""
Ein sehr einfaches "AI"-Processing-Modul.
Zweck: kleine, deterministiche Geometrie-/Attribut-Transformationen an GeoJSON
Die Implementierung bleibt absichtlich simpel (shapely wird verwendet).

Enthält folgende Skripte:
- convex_hull: berechnet die konvexe Hülle aller Polygon-Geometrien und gibt sie als neues Feature zurück
- add_centroids: berechnet Schwerpunkt-Punkte für Polygon-Features und fügt diese als neue Point-Features hinzu
- add_property: fügt allen Features eine Property `ai_note: 'augmented'` hinzu

Diese Module dienen als Prototyp / Platzhalter für spätere echte ML-Modelle.
"""
from typing import Dict, Any, List
import json
from shapely.geometry import shape, mapping, GeometryCollection
from shapely.ops import unary_union


def list_scripts() -> List[Dict[str, str]]:
    return [
        {"id": "convex_hull", "name": "Convex Hull", "description": "Fügt die konvexe Hülle als Feature hinzu"},
        {"id": "add_centroids", "name": "Add Centroids", "description": "Fügt Schwerpunkte (Punkte) für Polygon-Features hinzu"},
        {"id": "add_property", "name": "Add Property", "description": "Fügt property 'ai_note' zu allen Features hinzu"}
    ]


def process(geojson: Dict[str, Any], script_id: str) -> Dict[str, Any]:
    """Dispatch-Funktion: wendet das gewünschte Script an und liefert das augmentierte GeoJSON zurück."""
    if not geojson or geojson.get("type") not in ("FeatureCollection", "Feature"):
        raise ValueError("Invalid GeoJSON input")

    if script_id == "convex_hull":
        return _script_convex_hull(geojson)
    if script_id == "add_centroids":
        return _script_add_centroids(geojson)
    if script_id == "add_property":
        return _script_add_property(geojson)

    raise ValueError(f"Unknown script_id: {script_id}")


def _features_from_geojson(geojson: Dict[str, Any]):
    if geojson.get("type") == "FeatureCollection":
        return geojson.get("features", [])
    if geojson.get("type") == "Feature":
        return [geojson]
    return []


def _script_convex_hull(geojson: Dict[str, Any]) -> Dict[str, Any]:
    """Berechnet die konvexe Hülle aller Polygon-/MultiPolygon-Geometrien und fügt sie als neues Polygon-Feature hinzu."""
    features = _features_from_geojson(geojson)
    geoms = []
    for feat in features:
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            g = shape(geom)
        except Exception:
            continue
        # nur Polygon/Multipolygon/Line/Point sind erlaubt; wir sammeln alles
        geoms.append(g)

    if not geoms:
        # nichts zu tun
        out = dict(geojson)
        out.setdefault("features", features)
        return out

    merged = unary_union(geoms)
    hull = merged.convex_hull

    # Neues Feature anhängen
    hull_feature = {
        "type": "Feature",
        "properties": {"ai_script": "convex_hull"},
        "geometry": mapping(hull)
    }

    out = dict(geojson)
    if out.get("type") == "FeatureCollection":
        out = {"type": "FeatureCollection", "features": list(features) + [hull_feature]}
    else:
        out = {"type": "FeatureCollection", "features": list(features) + [hull_feature]}

    return out


def _script_add_centroids(geojson: Dict[str, Any]) -> Dict[str, Any]:
    """Berechnet den Schwerpunkt (centroid) für polygonale Features und fügt sie als Point-Features hinzu."""
    features = _features_from_geojson(geojson)
    new_features = list(features)

    for feat in features:
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            g = shape(geom)
        except Exception:
            continue
        # nur Polygonartige Geometrien behandeln
        if g.is_empty:
            continue
        centroid = g.centroid
        centroid_feature = {
            "type": "Feature",
            "properties": {"ai_script": "add_centroids", "source_id": feat.get("id")},
            "geometry": mapping(centroid)
        }
        new_features.append(centroid_feature)

    return {"type": "FeatureCollection", "features": new_features}


def _script_add_property(geojson: Dict[str, Any]) -> Dict[str, Any]:
    features = _features_from_geojson(geojson)
    out_feats = []
    for feat in features:
        f = dict(feat)
        props = dict(f.get("properties") or {})
        props["ai_note"] = "augmented"
        f["properties"] = props
        out_feats.append(f)
    return {"type": "FeatureCollection", "features": out_feats}


# Note: the CLI test harness was removed during cleanup. If you need a CLI,
# consider restoring it from version control or from backend/flask_app.bak.

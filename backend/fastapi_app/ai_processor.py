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
        {"id": "add_property", "name": "Add Property", "description": "Fügt property 'ai_note' zu allen Features hinzu"},
        {"id": "dominant_type_hull", "name": "Dominant Type Hull", "description": "Bestimmt den häufigsten Typ (z.B. residential) und fügt seine konvexe Hülle als Polygon-Feature hinzu"}
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
    if script_id == "dominant_type_hull":
        return _script_dominant_type_hull(geojson)

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


def _detect_feature_type(feature: Dict[str, Any]) -> str:
    """Bestimmt einen einfachen Typ für ein Feature basierend auf Properties (ähnlich zur Frontend-Logik).
    Rückgabewerte sind z.B. 'residential', 'commercial', 'industrial', 'education', 'healthcare',
    'religious', 'leisure', 'tourism', 'unknown', 'amenity', 'building', 'point'.
    """
    p = feature.get('properties') or {}
    # amenity
    if 'amenity' in p:
        a = str(p.get('amenity')).lower()
        if a in ('school', 'university'):
            return 'education'
        if a in ('hospital', 'clinic', 'doctors'):
            return 'healthcare'
        if a == 'place_of_worship':
            return 'religious'
        return 'amenity'
    # building
    if 'building' in p:
        b = str(p.get('building')).lower()
        if 'resid' in b or b in ('house', 'apartments'):
            return 'residential'
        if 'commer' in b or 'retail' in b or 'shop' in b:
            return 'commercial'
        if 'indust' in b:
            return 'industrial'
        if 'church' in b or 'cathedral' in b:
            return 'religious'
        return 'building'
    if p.get('shop') or p.get('office'):
        return 'commercial'
    if p.get('leisure'):
        return 'leisure'
    if p.get('tourism'):
        return 'tourism'
    if p.get('landuse'):
        if p.get('landuse') == 'residential':
            return 'residential'
        if p.get('landuse') == 'industrial':
            return 'industrial'
        if p.get('landuse') == 'commercial':
            return 'commercial'
        if p.get('landuse') in ('forest', 'park'):
            return 'leisure'

    geom = feature.get('geometry')
    if geom and geom.get('type') == 'Point':
        return 'point'

    return 'unknown'


def _script_dominant_type_hull(geojson: Dict[str, Any]) -> Dict[str, Any]:
    """Analysiert die Features, ermittelt den dominanten Typ und fügt die konvexe Hülle
    der Features dieses Typs als neues Polygon-Feature hinzu.
    """
    features = _features_from_geojson(geojson)
    if not features:
        return dict(geojson)

    # Optional: unterstütze ein Top-Level-Clip-Polygon. Erlaubte Keys: 'clip' oder 'clip_polygon'.
    clip_obj = geojson.get('clip') or geojson.get('clip_polygon')
    clip_shape = None
    if clip_obj:
        # clip kann entweder ein Feature ({type: 'Feature', geometry: {...}}) oder eine reine Geometry sein
        if isinstance(clip_obj, dict):
            if clip_obj.get('type') == 'Feature':
                clip_geom = clip_obj.get('geometry')
            else:
                # assume it's already a geometry
                clip_geom = clip_obj
            try:
                clip_shape = shape(clip_geom)
            except Exception:
                clip_shape = None

    # Optional: unterstütze eine Mindest-Flächen-Anteil (0..1), standard 0.0
    try:
        min_area_fraction = float(geojson.get('min_area_fraction', 0.0) or 0.0)
    except Exception:
        min_area_fraction = 0.0
    if min_area_fraction < 0.0:
        min_area_fraction = 0.0
    if min_area_fraction > 1.0:
        min_area_fraction = 1.0

    # Zähle Typen; wenn ein Clip vorhanden ist, berechne die Schnittmenge und
    # verwende die zugeschnittenen Geometrien zur Hüllberechnung.
    counts: Dict[str, int] = {}
    # store tuples (feature, clipped_geom_or_None)
    features_by_type: Dict[str, List[Any]] = {}
    for feat in features:
        fg = feat.get('geometry')
        if not fg:
            continue

        clipped_geom = None
        try:
            fg_shape = shape(fg)
        except Exception:
            continue

        if clip_shape:
            try:
                inter = fg_shape.intersection(clip_shape)
                if inter.is_empty:
                    continue
                # wenn min_area_fraction gesetzt, prüfen wir Anteil der Feature-Fläche
                if min_area_fraction > 0.0 and getattr(fg_shape, 'area', 0) and fg_shape.area > 0:
                    frac = inter.area / fg_shape.area
                    if frac < min_area_fraction:
                        continue
                clipped_geom = inter
            except Exception:
                # bei Problemen mit der Operation überspringen
                continue

        t = _detect_feature_type(feat)
        counts[t] = counts.get(t, 0) + 1
        features_by_type.setdefault(t, []).append((feat, clipped_geom))

    if not counts:
        return dict(geojson)

    # bestimme dominanten Typ
    dominant = max(counts.items(), key=lambda kv: kv[1])[0]

    # sammle Geometrien der dominanten Gruppe; wenn wir zugeschnittene Geometrien
    # haben, verwende diese (das stellt sicher, dass die Hülle im Clip bleibt).
    geoms = []
    for item in features_by_type.get(dominant, []):
        # item is (feat, clipped_geom_or_None)
        if isinstance(item, tuple) and len(item) == 2:
            feat_obj, clipped = item
        else:
            feat_obj, clipped = item, None

        if clipped is not None:
            try:
                if clipped.is_empty:
                    continue
                geoms.append(clipped)
                continue
            except Exception:
                # fallthrough to using original geometry
                pass

        geom = feat_obj.get('geometry')
        if not geom:
            continue
        try:
            g = shape(geom)
        except Exception:
            continue
        geoms.append(g)

    if not geoms:
        # kein Geomerieinhalt für dominanten Typ
        out = dict(geojson)
        out.setdefault('features', features)
        return out

    merged = unary_union(geoms)
    hull = merged.convex_hull

    # Wenn ein Clip-Polygon übergeben wurde, der Nutzer aber möchte, dass nur
    # genau der gezeichnete Bereich markiert wird, verwenden wir das Clip-Polygon
    # als Ergebnisfläche (anstatt einer evtl. größeren konvexen Hülle). Zudem
    # kennzeichnen wir die einzelnen Features innerhalb des Clips, die zum
    # dominanten Typ gehören, mit Properties.
    hull_geom = hull
    if clip_shape:
        # Nur verwenden, wenn es mindestens ein Feature des dominanten Typs gibt
        dominant_items = features_by_type.get(dominant, [])
        if dominant_items:
            hull_geom = clip_shape

            # Erzeuge neue Feature-Liste: nur Features, deren Geometrie vollständig
            # im Clip liegt und die dem dominanten Typ entsprechen, werden zurückgegeben
            new_features = []
            for feat in features:
                try:
                    fg = feat.get('geometry')
                    if not fg:
                        continue
                    fg_shape = shape(fg)
                    if not fg_shape.within(clip_shape):
                        continue
                    if _detect_feature_type(feat) != dominant:
                        continue

                    f = dict(feat)
                    props = dict(f.get('properties') or {})
                    props['ai_script'] = 'dominant_type_hull'
                    props['dominant_type'] = dominant
                    f['properties'] = props
                    new_features.append(f)
                except Exception:
                    continue

            out = {'type': 'FeatureCollection', 'features': new_features}
        else:
            # kein dominantes Feature im Clip — gib Original zurück
            out = dict(geojson)
            out.setdefault('features', features)
            return out
    else:
        hull_geom = hull
        out = dict(geojson)
        out.setdefault('features', features)

    hull_feature = {
        'type': 'Feature',
        'properties': {'ai_script': 'dominant_type_hull', 'dominant_type': dominant},
        'geometry': mapping(hull_geom)
    }

    # falls out bereits gesetzt ist (bei Clip-Fall), appendiere die Hull-Feature
    if out.get('type') == 'FeatureCollection':
        out = {'type': 'FeatureCollection', 'features': list(out.get('features', [])) + [hull_feature]}
    else:
        out = {'type': 'FeatureCollection', 'features': list(features) + [hull_feature]}

    return out


# Note: the CLI test harness was removed during cleanup. If you need a CLI,
# consider restoring it from version control or from backend/flask_app.bak.

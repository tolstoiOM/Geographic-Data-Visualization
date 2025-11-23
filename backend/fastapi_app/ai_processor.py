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
import urllib.request
import urllib.parse
import ssl
import json as _json
import logging


def _fetch_osm_features_for_bbox(minx, miny, maxx, maxy, timeout=60):
    """Query Overpass for nodes/ways/relations in bbox and return a GeoJSON FeatureCollection.
    bbox: minx,miny,maxx,maxy (lon/lat)
    Returns dict GeoJSON FeatureCollection or None on error.
    """
    try:
        # Overpass bbox format: south,west,north,east (lat/lon ordering)
        bbox = f"{miny},{minx},{maxy},{maxx}"
        q = f"[out:json][timeout:{int(timeout)}];(node({bbox});way({bbox});relation({bbox}););out geom;"
        url = 'https://overpass-api.de/api/interpreter'
        data = q.encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'User-Agent': 'GeoVizAI/1.0 (your-email@example.com)', 'Content-Type': 'application/x-www-form-urlencoded'})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            j = _json.loads(resp.read().decode('utf-8'))
            elems = j.get('elements', [])
            features = []
            for el in elems:
                try:
                    etype = el.get('type')
                    tags = el.get('tags') or {}
                    if etype == 'node' and el.get('lat') is not None and el.get('lon') is not None:
                        geom = {'type': 'Point', 'coordinates': [el.get('lon'), el.get('lat')]}
                    elif el.get('geometry'):
                        coords = [(pt['lon'], pt['lat']) for pt in el.get('geometry', [])]
                        if coords and coords[0] == coords[-1] and len(coords) >= 4:
                            geom = {'type': 'Polygon', 'coordinates': [coords]}
                        else:
                            geom = {'type': 'LineString', 'coordinates': coords}
                    else:
                        # skip elements without geometry
                        continue
                    props = dict(tags)
                    props['osm_type'] = etype
                    props['osm_id'] = el.get('id')
                    features.append({'type': 'Feature', 'properties': props, 'geometry': geom})
                except Exception:
                    continue
            return {'type': 'FeatureCollection', 'features': features}
    except Exception:
        return None


def list_scripts() -> List[Dict[str, str]]:
    return [
        {"id": "convex_hull", "name": "Convex Hull", "description": "Fügt die konvexe Hülle als Feature hinzu"},
        {"id": "add_centroids", "name": "Add Centroids", "description": "Fügt Schwerpunkte (Punkte) für Polygon-Features hinzu"},
        {"id": "add_property", "name": "Add Property", "description": "Fügt property 'ai_note' zu allen Features hinzu"},
        {"id": "dominant_type_hull", "name": "Dominant Type Hull", "description": "Bestimmt den häufigsten Typ (z.B. residential) und fügt seine konvexe Hülle als Polygon-Feature hinzu"},
        {"id": "place_enrich", "name": "Place Enrich", "description": "Ergänzt GeoJSON um Bezirk/Ort/Stadt/Land aus OpenStreetMap (Overpass/Nominatim)"}
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
        out = _script_dominant_type_hull(geojson)
        # post-processing: if caller requested OSM fetch, do it here (use hull bbox)
        try:
            if geojson.get('fetch_osm') and out and out.get('type') == 'FeatureCollection':
                feats = out.get('features', [])
                # find the hull feature we appended (ai_script == 'dominant_type_hull' and geometry present)
                hull_feat = None
                for f in reversed(feats):
                    try:
                        p = f.get('properties') or {}
                        if p.get('ai_script') == 'dominant_type_hull':
                            hull_feat = f
                            break
                    except Exception:
                        continue
                if hull_feat and hull_feat.get('geometry'):
                    try:
                        h = shape(hull_feat.get('geometry'))
                        minx, miny, maxx, maxy = h.bounds
                        # safety: skip big bbox
                        if (maxx - minx) * (maxy - miny) <= 1.0:
                            fetched = _fetch_osm_features_for_bbox(minx, miny, maxx, maxy)
                        else:
                            fetched = None
                    except Exception:
                        fetched = None
                else:
                    fetched = None

                if fetched:
                    out['osm_data'] = fetched
                    # build existing index
                    existing = set()
                    for f in out.get('features', []):
                        try:
                            p = f.get('properties') or {}
                            ot = p.get('osm_type')
                            oid = p.get('osm_id')
                            if ot and oid is not None:
                                existing.add(f"{ot}/{oid}")
                        except Exception:
                            continue
                    appended = 0
                    filters = geojson.get('osm_filters') or []
                    for ff in fetched.get('features', []):
                        try:
                            props = ff.get('properties') or {}
                            ot = props.get('osm_type')
                            oid = props.get('osm_id')
                            key = None
                            if ot and oid is not None:
                                key = f"{ot}/{oid}"
                            if key and key in existing:
                                continue
                            if filters and isinstance(filters, list):
                                ok = False
                                for fk in filters:
                                    if props.get(fk): ok = True; break
                                if not ok: continue
                            out.setdefault('features', []).append(ff)
                            appended += 1
                        except Exception:
                            continue
                    out['osm_appended_count'] = appended
                else:
                    out['osm_data'] = None
                    out['osm_appended_count'] = 0
        except Exception:
            pass
        return out

    if script_id == "place_enrich":
        return _script_place_enrich(geojson)

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
    # Some sources (frontend / OSM imports) nest tags under a `tags` object
    tags = p.get('tags') if isinstance(p.get('tags'), dict) else {}

    def _get(key: str):
        v = p.get(key)
        if v is None and isinstance(tags, dict):
            v = tags.get(key)
        return v

    # amenity
    a_val = _get('amenity')
    if a_val:
        a = str(a_val).lower()
        if a in ('school', 'university'):
            return 'education'
        if a in ('hospital', 'clinic', 'doctors'):
            return 'healthcare'
        if a == 'place_of_worship':
            return 'religious'
        return 'amenity'

    # building
    b_val = _get('building')
    if b_val:
        b = str(b_val).lower()
        if 'resid' in b or b in ('house', 'apartments'):
            return 'residential'
        if 'commer' in b or 'retail' in b or 'shop' in b:
            return 'commercial'
        if 'indust' in b:
            return 'industrial'
        if 'church' in b or 'cathedral' in b:
            return 'religious'
        return 'building'

    if _get('shop') or _get('office'):
        return 'commercial'
    if _get('leisure'):
        return 'leisure'
    if _get('tourism'):
        return 'tourism'
    lu = _get('landuse')
    if lu:
        if lu == 'residential':
            return 'residential'
        if lu == 'industrial':
            return 'industrial'
        if lu == 'commercial':
            return 'commercial'
        if lu in ('forest', 'park'):
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

    # Optional: unterstütze ein Districts-Layer (FeatureCollection oder Feature)
    districts_obj = geojson.get('districts') or geojson.get('districts_layer')
    districts_list = []
    if isinstance(districts_obj, dict):
        d_feats = []
        if districts_obj.get('type') == 'FeatureCollection':
            d_feats = districts_obj.get('features', [])
        elif districts_obj.get('type') == 'Feature':
            d_feats = [districts_obj]
        else:
            # assume it's a geometry ?? skip
            d_feats = []

        for idx, d in enumerate(d_feats):
            try:
                dgeom = d.get('geometry')
                if not dgeom:
                    continue
                dshape = shape(dgeom)
                dprops = d.get('properties') or {}
                # common property keys for district name and id
                name = dprops.get('name') or dprops.get('bezirk') or dprops.get('district') or dprops.get('NAME') or dprops.get('label') or d.get('id') or f'district_{idx}'
                did = dprops.get('id') or dprops.get('district_id') or d.get('id') or dprops.get('gid') or None
                districts_list.append({'name': str(name), 'id': did, 'shape': dshape, 'properties': dprops})
            except Exception:
                continue

    def _find_district(sobj):
        if not districts_list:
            return None
        try:
            # prefer a representative point (lies inside polygon)
            pt = sobj.representative_point()
        except Exception:
            try:
                pt = sobj.centroid
            except Exception:
                return None
        for d in districts_list:
            try:
                if d['shape'].contains(pt):
                    return {'name': d['name'], 'id': d.get('id'), 'properties': d.get('properties')}
            except Exception:
                try:
                    if d['shape'].intersects(sobj):
                        return {'name': d['name'], 'id': d.get('id'), 'properties': d.get('properties')}
                except Exception:
                    continue
        return None

    # human-readable german mapping for dominant types
    _GERMAN_TYPE_LABELS = {
        'residential': 'Wohngebiet',
        'commercial': 'Gewerbegebiet',
        'industrial': 'Industriegebiet',
        'education': 'Bildungsbereich',
        'healthcare': 'Gesundheitswesen',
        'religious': 'Religiös',
        'leisure': 'Freizeit',
        'tourism': 'Tourismus',
        'amenity': 'Sonstiges',
        'building': 'Gebäude',
        'point': 'Punkt',
        'unknown': 'Unbekannt'
    }

    def _label_for_type(t: str) -> str:
        if not t:
            return ''
        return _GERMAN_TYPE_LABELS.get(t, t)

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
    # prefer non-geometry-only types: if the dominant detected type is 'point'
    # but there are other non-'point' types present, prefer the most frequent
    # non-point type. This helps when input contains many point geometries
    # but semantic tags (e.g. 'building', 'landuse') exist on some features.
    if dominant == 'point':
        # find the most common non-point type
        non_point_items = [(k, v) for k, v in counts.items() if k != 'point']
        if non_point_items:
            # pick the non-point type with max count
            non_point_items.sort(key=lambda kv: kv[1], reverse=True)
            # only switch if the chosen non-point type has at least 1 count
            if non_point_items[0][1] > 0:
                dominant = non_point_items[0][0]

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
                    # include admin/district features even if they are not of the dominant type
                    props0 = feat.get('properties') or {}
                    def _is_admin_feature(p: Dict[str, Any]) -> bool:
                        if not p:
                            return False
                        if p.get('boundary') == 'administrative':
                            return True
                        if 'admin_level' in p:
                            return True
                        if 'bezirk' in p or 'district' in p:
                            return True
                        return False

                    # skip non-dominant, non-admin features
                    if _detect_feature_type(feat) != dominant and not _is_admin_feature(props0):
                        continue

                    f = dict(feat)
                    props = dict(f.get('properties') or {})
                    # annotate dominant-type features; keep admin features un-annotated except for district info
                    if _detect_feature_type(feat) == dominant:
                        props['ai_script'] = 'dominant_type_hull'
                        props['dominant_type'] = dominant
                    # add district info if districts layer provided
                    try:
                        dinfo = _find_district(fg_shape)
                        if dinfo:
                            props['district_name'] = dinfo.get('name')
                            if dinfo.get('id') is not None:
                                props['district_id'] = dinfo.get('id')
                    except Exception:
                        pass
                    # human-readable label for the dominant area (German)
                    try:
                        props['gebiet'] = _label_for_type(dominant)
                    except Exception:
                        pass
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
        # mark original features that match the dominant type and attach district if available
        new_features = []
        for feat in features:
            try:
                f = dict(feat)
                if _detect_feature_type(feat) == dominant:
                    props = dict(f.get('properties') or {})
                    props['ai_script'] = 'dominant_type_hull'
                    props['dominant_type'] = dominant
                    # attach district name if possible
                    try:
                        geom = f.get('geometry')
                        if geom and districts_list:
                            gshape = shape(geom)
                            dinfo = _find_district(gshape)
                            if dinfo:
                                props['district_name'] = dinfo.get('name')
                                if dinfo.get('id') is not None:
                                    props['district_id'] = dinfo.get('id')
                    except Exception:
                        pass
                    try:
                        props['gebiet'] = _label_for_type(dominant)
                    except Exception:
                        pass
                    f['properties'] = props
                new_features.append(f)
            except Exception:
                new_features.append(feat)

        out = {'type': 'FeatureCollection', 'features': new_features}

    hull_feature = {
        'type': 'Feature',
        'properties': {'ai_script': 'dominant_type_hull', 'dominant_type': dominant},
        'geometry': mapping(hull_geom)
    }

    # compute district for hull as well
    try:
        if districts_list and hull_geom is not None:
            dinfo = _find_district(hull_geom)
            if dinfo:
                hull_feature['properties']['district_name'] = dinfo.get('name')
                if dinfo.get('id') is not None:
                    hull_feature['properties']['district_id'] = dinfo.get('id')
    except Exception:
        pass
    try:
        hull_feature['properties']['gebiet'] = _label_for_type(dominant)
    except Exception:
        pass

    # If no district layer was provided and we still have no district info,
    # attempt to reverse-geocode the hull centroid via Nominatim to get an OSM-based
    # administrative name (conservative fallback; may return city/county names).
    def _nominatim_reverse(lat, lon):
        try:
            params = {'format': 'jsonv2', 'lat': str(lat), 'lon': str(lon), 'addressdetails': '1'}
            url = 'https://nominatim.openstreetmap.org/reverse?' + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={'User-Agent': 'GeoVizAI/1.0 (your-email@example.com)'})
            # allow default SSL context
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = resp.read()
                j = _json.loads(data.decode('utf-8'))
                addr = j.get('address') or {}
                # prefer district-like fields
                for key in ('suburb', 'city_district', 'borough', 'county', 'state_district', 'city'):
                    if addr.get(key):
                        return str(addr.get(key))
                # fallback to display_name
                if j.get('display_name'):
                    return str(j.get('display_name'))
        except Exception:
            return None
        return None

    try:
        if not districts_list and hull_geom is not None:
            try:
                # only attempt reverse-geocode when hull has area or at least a centroid
                c = hull_geom.representative_point() if hasattr(hull_geom, 'representative_point') else hull_geom.centroid
                if c and not c.is_empty:
                    lat = c.y
                    lon = c.x
                    nm = _nominatim_reverse(lat, lon)
                    if nm:
                        # only set if not already set
                        if not hull_feature['properties'].get('district_name'):
                            hull_feature['properties']['district_name'] = nm
                        # also set on features if missing
                        for f in out.get('features', []):
                            try:
                                props = f.get('properties') or {}
                                if not props.get('district_name'):
                                    props['district_name'] = nm
                                    f['properties'] = props
                            except Exception:
                                continue
            except Exception:
                pass
    except Exception:
        pass

    # Determine a general `place` for the GeoJSON: prefer district (if available),
    # otherwise use Nominatim address hierarchy (town/city/village/suburb/...)
    def _choose_place_from_nominatim(lat, lon):
        try:
            params = {'format': 'jsonv2', 'lat': str(lat), 'lon': str(lon), 'addressdetails': '1'}
            url = 'https://nominatim.openstreetmap.org/reverse?' + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={'User-Agent': 'GeoVizAI/1.0 (your-email@example.com)'})
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                j = _json.loads(resp.read().decode('utf-8'))
                addr = j.get('address') or {}
                # priority order for place selection
                for key, ptype in (('neighbourhood', 'neighbourhood'),
                                   ('suburb', 'suburb'),
                                   ('city_district', 'city_district'),
                                   ('borough', 'borough'),
                                   ('village', 'village'),
                                   ('town', 'town'),
                                   ('city', 'city'),
                                   ('county', 'county'),
                                   ('state', 'state')):
                    if addr.get(key):
                        return {'name': str(addr.get(key)), 'type': ptype, 'source': 'nominatim'}
                if j.get('display_name'):
                    return {'name': str(j.get('display_name')), 'type': 'display_name', 'source': 'nominatim'}
        except Exception:
            return None
        return None

    # compute place info and attach to hull and features if not already present
    place_info = None
    # prefer district_list (explicit layer) if present
    if districts_list:
        # pick first district that intersects hull
        try:
            for d in districts_list:
                try:
                    if hull_geom is not None and d['shape'].intersects(hull_geom):
                        place_info = {'name': d['name'], 'type': 'district', 'source': 'districts_layer', 'id': d.get('id')}
                        break
                except Exception:
                    continue
        except Exception:
            place_info = None

    if not place_info and hull_geom is not None:
        try:
            # use representative point for reverse-geocode
            rp = hull_geom.representative_point() if hasattr(hull_geom, 'representative_point') else hull_geom.centroid
            if rp and not rp.is_empty:
                # First try Overpass to get administrative boundaries (more reliable for districts)
                def _overpass_admin_lookup(hull):
                    try:
                        minx, miny, maxx, maxy = hull.bounds
                        # Overpass bbox expects south,west,north,east
                        bbox = f"{miny},{minx},{maxy},{maxx}"
                        q = f"[out:json][timeout:25];(relation[\"boundary\"=\"administrative\"][\"name\"]({bbox});way[\"boundary\"=\"administrative\"][\"name\"]({bbox}););out body;>;out skel qt;"
                        url = 'https://overpass-api.de/api/interpreter'
                        data = q.encode('utf-8')
                        req = urllib.request.Request(url, data=data, headers={'User-Agent': 'GeoVizAI/1.0 (your-email@example.com)'})
                        ctx = ssl.create_default_context()
                        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                            j = _json.loads(resp.read().decode('utf-8'))
                            elems = j.get('elements', [])
                            # elements may include relations/ways/nodes; we build geometries for relations/ways that have 'geometry'
                            candidates = []
                            for el in elems:
                                if el.get('type') in ('relation', 'way') and el.get('tags') and el.get('tags').get('name') and el.get('geometry'):
                                    coords = [(pt['lon'], pt['lat']) for pt in el.get('geometry', [])]
                                    try:
                                        # relations might be multipolygons; treat closed ring as polygon
                                        geom = None
                                        if coords and coords[0] == coords[-1]:
                                            # build polygon-like shape using shapely via shape() later if needed
                                            try:
                                                from shapely.geometry import Polygon
                                                geom = Polygon(coords)
                                            except Exception:
                                                geom = None
                                        else:
                                            try:
                                                from shapely.geometry import LineString
                                                geom = LineString(coords)
                                            except Exception:
                                                geom = None
                                        if geom is None: continue
                                        tags = el.get('tags') or {}
                                        admin_level = tags.get('admin_level')
                                        candidates.append({'id': el.get('id'), 'osm_type': el.get('type'), 'name': tags.get('name'), 'admin_level': int(admin_level) if admin_level and admin_level.isdigit() else None, 'shape': geom, 'tags': tags})
                                    except Exception:
                                        continue
                            # choose candidate that intersects hull and has highest admin_level (more specific)
                            best = None
                            for c in candidates:
                                try:
                                    if c['shape'].intersects(hull):
                                        if best is None:
                                            best = c
                                        else:
                                            # prefer higher admin_level (more specific). If none, prefer smaller area
                                            a1 = best.get('admin_level') or -1
                                            a2 = c.get('admin_level') or -1
                                            if a2 > a1:
                                                best = c
                                            else:
                                                try:
                                                    if c['shape'].area < best['shape'].area:
                                                        best = c
                                                except Exception:
                                                    pass
                                except Exception:
                                    continue
                            if best:
                                return {'name': best.get('name'), 'type': 'district', 'source': 'overpass', 'id': f"{best.get('osm_type')}/{best.get('id')}"}
                    except Exception:
                        return None
                    return None

                place_info = _overpass_admin_lookup(hull_geom)
                if not place_info:
                    place_info = _choose_place_from_nominatim(rp.y, rp.x)
        except Exception:
            place_info = None

    # attach place info to hull feature and to features if missing
    try:
        if place_info:
            # top-level place object
            out.setdefault('place', {})
            out['place'].update(place_info)
            # hull
            if place_info.get('name') and not hull_feature['properties'].get('place_name'):
                hull_feature['properties']['place_name'] = place_info.get('name')
            if place_info.get('type') and not hull_feature['properties'].get('place_type'):
                hull_feature['properties']['place_type'] = place_info.get('type')
            # features
            for f in out.get('features', []):
                try:
                    props = f.get('properties') or {}
                    if place_info.get('name') and not props.get('place_name'):
                        props['place_name'] = place_info.get('name')
                    if place_info.get('type') and not props.get('place_type'):
                        props['place_type'] = place_info.get('type')
                    f['properties'] = props
                except Exception:
                    continue
    except Exception:
        pass

    # If requested by the caller, fetch OSM data for the hull bbox and append missing features.
    try:
        if geojson.get('fetch_osm'):
            # compute bbox to query: use hull if available, else derive from input features
            try:
                if hull_geom is not None:
                    minx, miny, maxx, maxy = hull_geom.bounds
                else:
                    # derive bbox from input features
                    xs = []
                    ys = []
                    for f in features:
                        try:
                            g = shape(f.get('geometry'))
                            b = g.bounds
                            xs.extend([b[0], b[2]]); ys.extend([b[1], b[3]])
                        except Exception:
                            continue
                    if not xs or not ys:
                        raise Exception('no bbox')
                    minx, maxx = min(xs), max(xs)
                    miny, maxy = min(ys), max(ys)
                # safety: avoid extremely large areas
                # If bbox area (deg^2) > 1.0, skip to avoid huge queries
                if (maxx - minx) * (maxy - miny) > 1.0:
                    # too large, skip fetching
                    fetched = None
                else:
                    fetched = _fetch_osm_features_for_bbox(minx, miny, maxx, maxy)
            except Exception:
                fetched = None

            if fetched:
                # put raw fetched data into output so user can download
                out['osm_data'] = fetched

                # build index of existing OSM elements in the input (by osm_type/osm_id in properties)
                existing = set()
                for f in out.get('features', []):
                    try:
                        p = f.get('properties') or {}
                        ot = p.get('osm_type') or p.get('osm:datatype') or None
                        oid = p.get('osm_id') or p.get('osm:_id') or p.get('id') or None
                        if ot and oid is not None:
                            existing.add(f"{ot}/{oid}")
                    except Exception:
                        continue

                # append fetched features that are not present
                appended = 0
                for ff in fetched.get('features', []):
                    try:
                        props = ff.get('properties') or {}
                        ot = props.get('osm_type')
                        oid = props.get('osm_id')
                        key = None
                        if ot and oid is not None:
                            key = f"{ot}/{oid}"
                        if key and key in existing:
                            continue
                        # optionally filter by tags if client requested (osm_filters: list of keys)
                        filters = geojson.get('osm_filters') or []
                        if filters and isinstance(filters, list):
                            ok = False
                            for fk in filters:
                                if props.get(fk):
                                    ok = True; break
                            if not ok:
                                continue
                        # append to features
                        out.setdefault('features', [])
                        out['features'].append(ff)
                        appended += 1
                    except Exception:
                        continue
                out['osm_appended_count'] = appended
            else:
                out['osm_data'] = None
                out['osm_appended_count'] = 0
    except Exception:
        try:
            out['osm_data'] = None
            out['osm_appended_count'] = 0
        except Exception:
            pass

    # falls out bereits gesetzt ist (bei Clip-Fall), appendiere die Hull-Feature
    if out.get('type') == 'FeatureCollection':
        out = {'type': 'FeatureCollection', 'features': list(out.get('features', [])) + [hull_feature]}
    else:
        out = {'type': 'FeatureCollection', 'features': list(features) + [hull_feature]}

    # Wenn der Caller Place-Informationen erwartet (oder allgemein hilfreich),
    # reiche das Ergebnis durch das place_enrich-Skript, aber vermeide doppelte
    # Hull-Anhänge: wir benutzen _script_place_enrich auf einer minimalen Kopie
    try:
        if geojson.get('enrich_place') or geojson.get('ensure_place_fields'):
            try:
                enriched = _script_place_enrich({'type': 'FeatureCollection', 'features': out.get('features', [])})
                # copy top-level place and per-feature place_name/place_type if present
                if isinstance(enriched, dict) and enriched.get('place'):
                    out.setdefault('place', {})
                    out['place'].update(enriched.get('place') or {})
                if enriched.get('features'):
                    # merge per-feature props by geometry equality fallback to index
                    for idx, f in enumerate(out.get('features', [])):
                        try:
                            e = enriched.get('features')[idx]
                            if not e: continue
                            props = f.get('properties') or {}
                            eprops = e.get('properties') or {}
                            if eprops.get('place_name') and not props.get('place_name'):
                                props['place_name'] = eprops.get('place_name')
                            if eprops.get('place_type') and not props.get('place_type'):
                                props['place_type'] = eprops.get('place_type')
                            if eprops.get('district_id') and not props.get('district_id'):
                                props['district_id'] = eprops.get('district_id')
                            f['properties'] = props
                        except Exception:
                            continue
            except Exception:
                pass
    except Exception:
        pass

    return out


def _script_place_enrich(geojson: Dict[str, Any]) -> Dict[str, Any]:
    """Ergänzt GeoJSON mit Place/Location-Informationen (Bezirk/Ort/Stadt/Land).
    Strategie: wenn ein `districts`-Layer vorhanden ist, verwende diesen.
    Sonst: versuche Overpass (admin boundaries) innerhalb der Hülle, sonst Nominatim Reverse.
    Fügt top-level `place` und pro-Feature `place_name`/`place_type` sowie optional `district_name`/`district_id` hinzu.
    """
    features = _features_from_geojson(geojson)
    if not features:
        return dict(geojson)

    geoms = []
    for feat in features:
        try:
            g = shape(feat.get('geometry'))
            if g and not g.is_empty:
                geoms.append(g)
        except Exception:
            continue

    if not geoms:
        return dict(geojson)

    merged = unary_union(geoms)
    hull = merged.convex_hull

    # helper: Overpass admin search using bbox
    def _find_admin_overpass(hull_geom):
        try:
            minx, miny, maxx, maxy = hull_geom.bounds
            # bbox for overpass: south,west,north,east
            bbox = f"{miny},{minx},{maxy},{maxx}"
            q = f"[out:json][timeout:25];(relation[\"boundary\"]=\"administrative\"][\"name\"]({bbox});way[\"boundary\"]=\"administrative\"[\"name\"]({bbox}););out body;>;out skel qt;"
            url = 'https://overpass-api.de/api/interpreter'
            data = q.encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'User-Agent': 'GeoVizAI/1.0 (your-email@example.com)'})
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                j = _json.loads(resp.read().decode('utf-8'))
                elems = j.get('elements', [])
                best = None
                for el in elems:
                    try:
                        tags = el.get('tags') or {}
                        name = tags.get('name')
                        if not name:
                            continue
                        geom = None
                        if el.get('geometry'):
                            try:
                                coords = [(pt['lon'], pt['lat']) for pt in el.get('geometry', [])]
                                if coords and coords[0] == coords[-1] and len(coords) >= 4:
                                    from shapely.geometry import Polygon
                                    geom = Polygon(coords)
                                else:
                                    from shapely.geometry import LineString
                                    geom = LineString(coords)
                            except Exception:
                                geom = None
                        if geom is None:
                            continue
                        # check intersection
                        try:
                            if not geom.intersects(hull_geom):
                                continue
                        except Exception:
                            continue
                        admin_level = tags.get('admin_level')
                        cand = {'name': name, 'id': f"{el.get('type')}/{el.get('id')}", 'admin_level': int(admin_level) if admin_level and admin_level.isdigit() else None, 'shape': geom, 'tags': tags}
                        if best is None:
                            best = cand
                        else:
                            a1 = best.get('admin_level') or -1
                            a2 = cand.get('admin_level') or -1
                            if a2 > a1:
                                best = cand
                            else:
                                try:
                                    if cand['shape'].area < best['shape'].area:
                                        best = cand
                                except Exception:
                                    pass
                    except Exception:
                        continue
                if best:
                    return {'name': best.get('name'), 'type': 'district', 'source': 'overpass', 'id': best.get('id')}
        except Exception:
            return None
        return None

    # helper: nominatim reverse
    def _nominatim_place(hull_geom):
        try:
            rp = hull_geom.representative_point() if hasattr(hull_geom, 'representative_point') else hull_geom.centroid
            if not rp or rp.is_empty:
                return None
            lat = rp.y; lon = rp.x
            params = {'format': 'jsonv2', 'lat': str(lat), 'lon': str(lon), 'addressdetails': '1'}
            url = 'https://nominatim.openstreetmap.org/reverse?' + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={'User-Agent': 'GeoVizAI/1.0 (your-email@example.com)'})
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                j = _json.loads(resp.read().decode('utf-8'))
                addr = j.get('address') or {}
                for key, ptype in (('city_district','city_district'),('suburb','suburb'),('neighbourhood','neighbourhood'),('village','village'),('town','town'),('city','city'),('county','county'),('state','state')):
                    if addr.get(key):
                        return {'name': str(addr.get(key)), 'type': ptype, 'source': 'nominatim', 'country': addr.get('country'), 'country_code': addr.get('country_code')}
                if j.get('display_name'):
                    return {'name': str(j.get('display_name')), 'type': 'display_name', 'source': 'nominatim', 'country': addr.get('country'), 'country_code': addr.get('country_code')}
        except Exception:
            return None
        return None

    # run strategy
    place_info = None
    # 1) explicit districts layer
    districts_obj = geojson.get('districts') or geojson.get('districts_layer')
    if isinstance(districts_obj, dict):
        d_feats = districts_obj.get('features') if districts_obj.get('type') == 'FeatureCollection' else [districts_obj]
        for d in d_feats:
            try:
                dgeom = d.get('geometry')
                if not dgeom: continue
                dshape = shape(dgeom)
                if dshape.intersects(hull):
                    props = d.get('properties') or {}
                    name = props.get('name') or props.get('bezirk') or props.get('district')
                    did = props.get('id') or props.get('district_id') or d.get('id')
                    place_info = {'name': str(name) if name else None, 'type': 'district', 'source': 'districts_layer', 'id': did}
                    break
            except Exception:
                continue

    # 2) Overpass admin
    if not place_info:
        try:
            place_info = _find_admin_overpass(hull)
        except Exception:
            place_info = None

    # debug: report result of Overpass lookup
    try:
        print(f"[place_enrich] after overpass lookup, place_info={place_info}")
    except Exception:
        pass

    # 3) Nominatim fallback
    if not place_info:
        place_info = _nominatim_place(hull)

    # debug: report result of nominatim lookup
    try:
        print(f"[place_enrich] after nominatim lookup, place_info={place_info}")
    except Exception:
        pass

    # If still missing and caller requested to ensure place fields, forcibly
    # perform a longer Nominatim reverse and try to extract address fields.
    if not place_info and geojson.get('ensure_place_fields'):
        try:
            rp = hull.representative_point() if hasattr(hull, 'representative_point') else hull.centroid
            if rp and not rp.is_empty:
                lat = rp.y; lon = rp.x
                params = {'format': 'jsonv2', 'lat': str(lat), 'lon': str(lon), 'addressdetails': '1'}
                url = 'https://nominatim.openstreetmap.org/reverse?' + urllib.parse.urlencode(params)
                req = urllib.request.Request(url, headers={'User-Agent': 'GeoVizAI/1.0 (your-email@example.com)'})
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                    raw = resp.read().decode('utf-8')
                    try:
                        j = _json.loads(raw)
                    except Exception:
                        j = None
                    print(f"[place_enrich] ensure_place_fields nominatim raw={raw}")
                    if j:
                        addr = j.get('address') or {}
                        for key, ptype in (('neighbourhood','neighbourhood'),('suburb','suburb'),('city_district','city_district'),('borough','borough'),('village','village'),('town','town'),('city','city'),('county','county'),('state','state')):
                            if addr.get(key):
                                place_info = {'name': str(addr.get(key)), 'type': ptype, 'source': 'nominatim_force', 'country': addr.get('country'), 'country_code': addr.get('country_code')}
                                break
                        if not place_info and j.get('display_name'):
                            place_info = {'name': str(j.get('display_name')), 'type': 'display_name', 'source': 'nominatim_force', 'country': addr.get('country'), 'country_code': addr.get('country_code')}
        except Exception as e:
            try:
                print(f"[place_enrich] ensure_place_fields nominatim error: {e}")
            except Exception:
                pass

    # debug: final place_info before attaching
    try:
        print(f"[place_enrich] final place_info={place_info}")
    except Exception:
        pass

    # Additionally: if the computed place_info is a city (e.g. 'Wien') but
    # several features contain district-like names in their properties, prefer
    # the most common district derived from features. Also honor explicit
    # `prefer_district` flag in the input.
    try:
        prefer_district_flag = bool(geojson.get('prefer_district') or geojson.get('ensure_place_fields'))
    except Exception:
        prefer_district_flag = False
    try:
        # gather derived names/types from features
        derived_counts = {}
        derived_types = {}
        for f in features:
            try:
                d = _derive_place_from_props(f.get('properties') or {})
                if not d or not d.get('name'):
                    continue
                name = d.get('name')
                t = (d.get('type') or '').lower() if isinstance(d.get('type'), str) else None
                derived_counts[name] = derived_counts.get(name, 0) + 1
                if t:
                    derived_types[name] = t
            except Exception:
                continue
        if derived_counts:
            most_derived_name, most_derived_count = max(derived_counts.items(), key=lambda kv: kv[1])
            most_derived_type = derived_types.get(most_derived_name)
            # if derived type looks like a district, and either we explicitly prefer district
            # or the existing place_info is a city-level type, override place_info
            is_city_level = False
            try:
                ptype = (place_info.get('type') or '').lower() if place_info and isinstance(place_info.get('type'), str) else None
                if not ptype or ptype in ('city', 'town', 'display_name'):
                    is_city_level = True
            except Exception:
                is_city_level = True

            if most_derived_type and most_derived_type in ('district', 'city_district', 'suburb', 'neighbourhood', 'borough', 'bezirk') and (prefer_district_flag or is_city_level):
                place_info = {'name': most_derived_name, 'type': 'district', 'source': 'derived_from_features_override'}
                try:
                    print(f"[place_enrich] overriding place_info with derived district: {place_info}")
                except Exception:
                    pass
    except Exception:
        pass

    # If we still don't have place_info, try to derive the most common
    # place name/type from the input features' properties as a last-resort.
    if not place_info:
        try:
            name_counts = {}
            type_counts = {}
            for f in features:
                try:
                    p = f.get('properties') or {}
                    d = _derive_place_from_props(p)
                    if d and d.get('name'):
                        n = d.get('name')
                        name_counts[n] = name_counts.get(n, 0) + 1
                        if d.get('type'):
                            type_counts[d.get('type')] = type_counts.get(d.get('type'), 0) + 1
                except Exception:
                    continue
            if name_counts:
                # choose most common name and (if any) most common derived type
                most_name = max(name_counts.items(), key=lambda kv: kv[1])[0]
                most_type = None
                if type_counts:
                    most_type = max(type_counts.items(), key=lambda kv: kv[1])[0]
                place_info = {'name': most_name, 'type': most_type, 'source': 'derived_from_features'}
                try:
                    print(f"[place_enrich] derived place_info from features: {place_info}")
                except Exception:
                    pass
        except Exception:
            pass

    # Helper: try to derive place name/type from a feature's properties
    def _derive_place_from_props(p: Dict[str, Any]):
        if not p:
            return None
        # prefer district-like keys first, then fall back to general name keys
        for k in ('district', 'bezirk', 'city_district', 'suburb', 'neighbourhood', 'place_name', 'place', 'name', 'label', 'display_name', 'addr:suburb', 'addr:city'):
            v = p.get(k) or (p.get('tags') or {}).get(k)
            if v:
                # try to also find a sensible type
                t = None
                for tk in ('district', 'place_type', 'place', 'amenity', 'building', 'landuse', 'shop', 'leisure'):
                    tv = p.get(tk) or (p.get('tags') or {}).get(tk)
                    if tv:
                        t = str(tv)
                        break
                return {'name': str(v), 'type': t or None, 'source': 'props'}
        # no suitable name found
        return None

    # If we still don't have place_info, try to derive the most common
    # place name/type from the input features' properties as a last-resort.
    if not place_info:
        try:
            name_counts = {}
            type_counts = {}
            for f in features:
                try:
                    p = f.get('properties') or {}
                    d = _derive_place_from_props(p)
                    if d and d.get('name'):
                        n = d.get('name')
                        name_counts[n] = name_counts.get(n, 0) + 1
                        if d.get('type'):
                            type_counts[d.get('type')] = type_counts.get(d.get('type'), 0) + 1
                except Exception:
                    continue
            if name_counts:
                # choose most common name and (if any) most common derived type
                most_name = max(name_counts.items(), key=lambda kv: kv[1])[0]
                most_type = None
                if type_counts:
                    most_type = max(type_counts.items(), key=lambda kv: kv[1])[0]
                place_info = {'name': most_name, 'type': most_type, 'source': 'derived_from_features'}
                try:
                    print(f"[place_enrich] derived place_info from features: {place_info}")
                except Exception:
                    pass
        except Exception:
            pass

    # Prefer district-level place when possible: if current place_info is a city or generic,
    # attempt one targeted Nominatim reverse to extract district-like keys and replace.
    def _extract_district_from_nominatim_json(j):
        try:
            addr = j.get('address') or {}
            for key in ('city_district', 'suburb', 'borough', 'neighbourhood', 'district', 'bezirk'):
                if addr.get(key):
                    return {'name': str(addr.get(key)), 'type': key, 'source': 'nominatim_district'}
        except Exception:
            return None
        return None

    try:
        need_district = False
        if place_info:
            ptype = (place_info.get('type') or '').lower() if isinstance(place_info.get('type'), str) else None
            if not ptype or ptype in ('city', 'town', 'display_name'):
                need_district = True
        else:
            # no place_info at all -> try to extract district
            need_district = True

        if need_district and hull is not None:
            try:
                rp = hull.representative_point() if hasattr(hull, 'representative_point') else hull.centroid
                if rp and not rp.is_empty:
                    params = {'format': 'jsonv2', 'lat': str(rp.y), 'lon': str(rp.x), 'addressdetails': '1'}
                    url = 'https://nominatim.openstreetmap.org/reverse?' + urllib.parse.urlencode(params)
                    req = urllib.request.Request(url, headers={'User-Agent': 'GeoVizAI/1.0 (your-email@example.com)'})
                    ctx = ssl.create_default_context()
                    with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
                        j = _json.loads(resp.read().decode('utf-8'))
                        district_candidate = _extract_district_from_nominatim_json(j)
                        if district_candidate:
                            place_info = district_candidate
                            try:
                                print(f"[place_enrich] replaced place_info with district candidate: {place_info}")
                            except Exception:
                                pass
            except Exception:
                pass
    except Exception:
        pass

    out = dict(geojson)
    out.setdefault('features', list(features))

    # determine dominant type across input features (reuse _detect_feature_type)
    try:
        counts_dt = {}
        for f in features:
            try:
                dt = _detect_feature_type(f) or 'unknown'
                counts_dt[dt] = counts_dt.get(dt, 0) + 1
            except Exception:
                continue
        if counts_dt:
            dominant_dt = max(counts_dt.items(), key=lambda kv: kv[1])[0]
            if dominant_dt == 'point':
                non_point_items = [(k, v) for k, v in counts_dt.items() if k != 'point']
                if non_point_items:
                    non_point_items.sort(key=lambda kv: kv[1], reverse=True)
                    if non_point_items[0][1] > 0:
                        dominant_dt = non_point_items[0][0]
        else:
            dominant_dt = 'unknown'
    except Exception:
        dominant_dt = 'unknown'

    # small human-readable german mapping (local copy)
    _GERMAN_TYPE_LABELS_LOCAL = {
        'residential': 'Wohngebiet', 'commercial': 'Gewerbegebiet', 'industrial': 'Industriegebiet',
        'education': 'Bildungsbereich', 'healthcare': 'Gesundheitswesen', 'religious': 'Religiös',
        'leisure': 'Freizeit', 'tourism': 'Tourismus', 'amenity': 'Sonstiges', 'building': 'Gebäude',
        'point': 'Punkt', 'unknown': 'Unbekannt'
    }
    def _label_for_type_local(t: str) -> str:
        if not t:
            return ''
        return _GERMAN_TYPE_LABELS_LOCAL.get(t, t)

    # attach place to hull and features
    hull_feature = {'type': 'Feature', 'properties': {'ai_script': 'place_enrich', 'dominant_type': dominant_dt, 'gebiet': _label_for_type_local(dominant_dt)}, 'geometry': mapping(hull)}
    try:
        if place_info:
            out.setdefault('place', {})
            out['place'].update(place_info)
            if place_info.get('name'):
                hull_feature['properties']['place_name'] = place_info.get('name')
            if place_info.get('type'):
                hull_feature['properties']['place_type'] = place_info.get('type')
            if place_info.get('id'):
                hull_feature['properties']['district_id'] = place_info.get('id')
            if place_info.get('source'):
                hull_feature['properties']['place_source'] = place_info.get('source')
            # add to features if missing
            for f in out.get('features', []):
                try:
                    props = f.get('properties') or {}
                    # Prefer explicit district-like properties on the feature itself
                    derived = _derive_place_from_props(props)
                    if derived and derived.get('name') and derived.get('type') in ('district', 'city_district', 'suburb', 'neighbourhood', 'borough', 'bezirk'):
                        # overwrite place_name with the district from feature props
                        props['place_name'] = derived.get('name')
                        props['place_type'] = 'district'
                    else:
                        # fallback to hull-level place_info (only if not present or not district)
                        if place_info.get('name'):
                            # If caller explicitly requested district preference, avoid overriding district-like feature props
                            if not props.get('place_name'):
                                props['place_name'] = place_info.get('name')
                        if place_info.get('type') and not props.get('place_type'):
                            props['place_type'] = place_info.get('type')
                        if place_info.get('id') and not props.get('district_id'):
                            props['district_id'] = place_info.get('id')

                    # If still missing district and user requested strong district preference,
                    # attempt a targeted Nominatim reverse on the feature centroid to extract district keys.
                    prefer_district = bool(geojson.get('prefer_district') or geojson.get('ensure_place_fields'))
                    if prefer_district and (not props.get('place_name') or (props.get('place_type') or '').lower() not in ('district', 'city_district', 'suburb', 'neighbourhood', 'borough', 'bezirk')):
                        try:
                            geom = f.get('geometry')
                            if geom:
                                gshape = shape(geom)
                                rp = gshape.representative_point() if hasattr(gshape, 'representative_point') else gshape.centroid
                                if rp and not rp.is_empty:
                                    params = {'format': 'jsonv2', 'lat': str(rp.y), 'lon': str(rp.x), 'addressdetails': '1'}
                                    url = 'https://nominatim.openstreetmap.org/reverse?' + urllib.parse.urlencode(params)
                                    req = urllib.request.Request(url, headers={'User-Agent': 'GeoVizAI/1.0 (your-email@example.com)'})
                                    ctx = ssl.create_default_context()
                                    try:
                                        with urllib.request.urlopen(req, context=ctx, timeout=6) as resp:
                                            j = _json.loads(resp.read().decode('utf-8'))
                                            addr = j.get('address') or {}
                                            for key in ('city_district', 'suburb', 'borough', 'neighbourhood', 'district', 'bezirk'):
                                                if addr.get(key):
                                                    props['place_name'] = str(addr.get(key))
                                                    props['place_type'] = key
                                                    if j.get('display_name') and not props.get('district_id'):
                                                        props['district_id'] = j.get('osm_id') if j.get('osm_id') else None
                                                    break
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                    # also annotate features with dominant type if not present
                    if not props.get('dominant_type'):
                        props['dominant_type'] = dominant_dt
                    if not props.get('gebiet'):
                        try:
                            props['gebiet'] = _label_for_type_local(dominant_dt)
                        except Exception:
                            pass
                    f['properties'] = props
                except Exception:
                    continue
    except Exception:
        pass

    # If ensure_place_fields is requested, try per-feature heuristics for missing fields
    if geojson.get('ensure_place_fields'):
        try:
            print('[place_enrich] ensure_place_fields: filling missing place_name/place_type per feature')
            for f in out.get('features', []):
                try:
                    props = f.get('properties') or {}
                    # fill place_name
                    if not props.get('place_name'):
                        # try derive from props
                        derived = _derive_place_from_props(props)
                        if derived and derived.get('name'):
                            props['place_name'] = derived.get('name')
                    # fill place_type
                    if not props.get('place_type'):
                        derived = _derive_place_from_props(props)
                        if derived and derived.get('type'):
                            props['place_type'] = derived.get('type')
                        elif place_info and place_info.get('type'):
                            props['place_type'] = place_info.get('type')
                        else:
                            # fallback to dominant detected type
                            try:
                                props['place_type'] = dominant_dt if 'dominant_dt' in locals() else props.get('place_type')
                            except Exception:
                                pass
                    # ensure dominant_type/gebiet present
                    if not props.get('dominant_type'):
                        props['dominant_type'] = dominant_dt if 'dominant_dt' in locals() else props.get('dominant_type')
                    if not props.get('gebiet'):
                        try:
                            props['gebiet'] = _label_for_type_local(dominant_dt)
                        except Exception:
                            pass
                    f['properties'] = props
                except Exception:
                    continue
        except Exception:
            pass

    out['features'] = out.get('features', []) + [hull_feature]
    return out


# Note: the CLI test harness was removed during cleanup. If you need a CLI,
# consider restoring it from version control or from backend/flask_app.bak.

# main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import io
import json
import psycopg2
from psycopg2.extras import Json
# geopandas import removed from top-level to avoid heavy startup overhead
from urllib.parse import urlparse
import socket
import tempfile
import logging

app = FastAPI()

# basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('fastapi_app')

# Allow frontend (running on localhost:3000) to call this API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/health')
def health():
    return {"status": "ok"}


@app.get('/db-test')
def db_test(probe: bool = False):
    """Quick test: perform a short TCP connect to the DB host:port (fast) and then run SELECT 1 if reachable.

    This avoids long DNS resolution / connect hangs and gives a clearer error.
    """
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        return JSONResponse(status_code=400, content={"ok": False, "error": "DATABASE_URL not set"})

    parsed = urlparse(database_url)
    host = parsed.hostname
    port = parsed.port
    user = parsed.username or ""

    # If no probe requested, return parsed info immediately (avoid DNS/connect hangs)
    if not probe:
        return {"ok": True, "db_host": host, "db_port": port, "db_user": user, "note": "probe=false; set ?probe=true to perform TCP+DB checks"}

    if not host or not port:
        return JSONResponse(status_code=400, content={"ok": False, "error": "DATABASE_URL missing host or port", "db_host": host, "db_port": port})

    # quick TCP check with timeout to avoid long hangs
    sock_timeout = float(os.getenv('DB_SOCKET_TIMEOUT', '3'))
    try:
        sock = socket.create_connection((host, port), timeout=sock_timeout)
        sock.close()
    except Exception as e:
        return JSONResponse(status_code=502, content={"ok": False, "error": f"tcp connect failed: {e}", "db_host": host, "db_port": port, "db_user": user})

    # socket ok -> try full DB connect
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute('SELECT 1')
        res = cur.fetchone()
        conn.close()
        return {"ok": True, "result": res[0] if res else None, "db_host": host, "db_port": port, "db_user": user}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "db_host": host, "db_port": port, "db_user": user})


def get_db_conn():
    """Return a psycopg2 connection using DATABASE_URL.

    Parse the URL and pass a short connect_timeout so attempts fail fast if the host is unreachable.
    """
    database_url = os.getenv("DATABASE_URL")

    # If DATABASE_URL not present, fall back to hardcoded dev credentials
    if not database_url:
        # --- HARDCODED FALLBACK for local debugging ---
        host = os.getenv('DB_HOST', 'localhost')
        port = int(os.getenv('DB_PORT', '5432'))
        user = os.getenv('DB_USER', 'sepjuser')
        password = os.getenv('DB_PASSWORD', 'sepjpw')
        dbname = os.getenv('DB_NAME', 'sepjdb')
        connect_timeout = int(os.getenv('DB_CONNECT_TIMEOUT', '5'))
        return psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port, connect_timeout=connect_timeout)

    # parse url like postgresql://user:pass@host:port/dbname
    parsed = urlparse(database_url)
    dbname = parsed.path.lstrip('/') if parsed.path else None
    user = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port

    # use a short connect timeout to avoid long blocking when host is unreachable
    connect_timeout = int(os.getenv('DB_CONNECT_TIMEOUT', '5'))

    return psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port, connect_timeout=connect_timeout)


@app.get("/")
def read_root():
    return {"message": "Hello FastAPI"}


@app.post("/upload-geojson")
async def upload_geojson(file: UploadFile = File(...)):
    """Accept a GeoJSON file upload and store features into the PostGIS 'features' table.

    The uploaded file is streamed to a temporary file to avoid loading large files into memory.
    """
    if not file.filename or (not file.filename.lower().endswith(".geojson") and not (file.content_type and file.content_type.endswith("json"))):
        raise HTTPException(status_code=400, detail="Uploaded file is not a GeoJSON file")

    max_mb = int(os.getenv('MAX_UPLOAD_MB', '100'))
    max_bytes = max_mb * 1024 * 1024

    tmp_path = None
    try:
        logger.info(f"upload start: filename={file.filename} content_type={file.content_type} max_mb={max_mb}")
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            total = 0
            chunk_idx = 0
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)
                total += len(chunk)
                chunk_idx += 1
                if chunk_idx % 10 == 0:
                    logger.info(f"written {total} bytes to tmp file {tmp_path}")
                if total > max_bytes:
                    tmp.close()
                    raise HTTPException(status_code=413, detail=f"Uploaded file exceeds limit of {max_mb} MB")
        logger.info(f"finished upload, total_bytes={total}, parsing file {tmp_path}")
        # parse saved file
        try:
            with open(tmp_path, 'rb') as fh:
                data = json.load(fh)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON in uploaded file: {e}")

        # Support both FeatureCollection and single Feature
        features = []
        if data.get("type") == "FeatureCollection":
            features = data.get("features", [])
        elif data.get("type") == "Feature":
            features = [data]
        else:
            raise HTTPException(status_code=400, detail="GeoJSON must be a Feature or FeatureCollection")

        inserted = 0
        skipped_no_geom = 0
        skipped_invalid_geom = 0
        db_errors = []
        conn = None
        try:
            conn = get_db_conn()
            cur = conn.cursor()

            for idx, feat in enumerate(features):
                geom = feat.get("geometry")
                props = feat.get("properties") or {}

                if geom is None:
                    skipped_no_geom += 1
                    continue

                try:
                    from shapely.geometry import shape as _shape
                except Exception as e:
                    skipped_invalid_geom += 1
                    db_errors.append({"index": idx, "error": f"shapely import failed: {e}"})
                    continue

                try:
                    shapely_geom = _shape(geom)
                except Exception as e:
                    skipped_invalid_geom += 1
                    db_errors.append({"index": idx, "error": f"invalid geometry: {e}"})
                    continue

                centroid = shapely_geom.centroid
                bounds = shapely_geom.bounds
                area_m2 = shapely_geom.area

                insert_sql = (
                    "INSERT INTO features (properties, geom, centroid, bbox, area_m2) "
                    "VALUES (%s, ST_SetSRID(ST_GeomFromText(%s), 4326), ST_SetSRID(ST_GeomFromText(%s),4326), "
                    "ST_SetSRID(ST_MakeEnvelope(%s, %s, %s, %s),4326), %s)"
                )

                geom_wkt = shapely_geom.wkt
                centroid_wkt = centroid.wkt
                minx, miny, maxx, maxy = bounds

                try:
                    cur.execute(insert_sql, (
                        Json(props),
                        geom_wkt,
                        centroid_wkt,
                        minx, miny, maxx, maxy,
                        float(area_m2),
                    ))
                    inserted += 1
                except Exception as e:
                    db_errors.append({"index": idx, "error": str(e)})

            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise HTTPException(status_code=500, detail=f"database error: {e}")
        finally:
            if conn:
                conn.close()

        result = {
            "inserted": inserted,
            "skipped_no_geom": skipped_no_geom,
            "skipped_invalid_geom": skipped_invalid_geom,
            "db_errors": db_errors,
            "total_features": len(features),
        }

        return JSONResponse(result)
    finally:
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


@app.get("/features")
def list_features(limit: int = 20):
    """Return recent features as GeoJSON-like features for quick verification."""
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, properties, ST_AsGeoJSON(geom) as geomjson FROM features ORDER BY created_at DESC LIMIT %s",
            (limit,)
        )
        rows = cur.fetchall()
        features = []
        for r in rows:
            fid, props, geomjson = r
            features.append({
                "type": "Feature",
                "id": fid,
                "properties": props,
                "geometry": json.loads(geomjson) if geomjson else None,
            })

        return {"type": "FeatureCollection", "features": features}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

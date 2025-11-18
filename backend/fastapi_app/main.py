from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from geo_processor import process_geojson_make_black
from ai_processor import list_scripts as ai_list_scripts, process as ai_process
import os, json

app = FastAPI()

# --- CORS erlauben (für das Frontend) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # oder ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Datenbankverbindung ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sepjuser:sepjpw@database:5432/sepjdb")
engine = create_engine(DATABASE_URL, future=True)

@app.get("/")
async def root():
    return {"message": "FastAPI mit PostGIS läuft!"}


@app.get('/ai-scripts')
async def get_ai_scripts():
    """Gibt die verfügbaren kleinen AI-/Processing-Skripte zurück."""
    try:
        return {"scripts": ai_list_scripts()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/augment')
async def augment_geojson(script_id: str = Query(..., description='ID des AI-Skripts'), geojson: dict = Body(...)):
    """Augmentiert ein übergebenes GeoJSON mit dem ausgewählten Script und liefert das Ergebnis zurück."""
    try:
        if not geojson or geojson.get('type') not in ['FeatureCollection', 'Feature']:
            raise HTTPException(status_code=400, detail='Ungültiges GeoJSON')

        result = ai_process(geojson, script_id)
        return {"status": "success", "script_id": script_id, "geojson": result}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        print('❌ AI processing error:', traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-geojson")
async def upload_geojson(geojson: dict):
    """
    Erwartet ein GeoJSON Feature oder FeatureCollection und speichert
    jedes Feature in die Tabelle 'features' mit PostGIS-Geom.
    """
    try:
        gtype = geojson.get("type")
        if gtype not in ["Feature", "FeatureCollection"]:
            raise HTTPException(status_code=400, detail="Ungültiger GeoJSON-Typ")

        with engine.begin() as conn:
            if gtype == "FeatureCollection":
                count = 0
                for feature in geojson["features"]:
                    insert_feature(conn, feature)
                    count += 1
            else:
                insert_feature(conn, geojson)
                count = 1

        return {"status": "success", "inserted": count}

    except Exception as e:
        import traceback
        print("❌ Fehler beim Speichern:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Fehler beim Speichern: {e}")

def insert_feature(conn, feature):
    """
    Hilfsfunktion: Speichert ein einzelnes Feature in PostGIS.
    """

    geom = feature.get("geometry")
    props = feature.get("properties", {})

    if not geom:
        return # kein Geometry-Objekt

    sql = text("""
            INSERT INTO features (properties, geom)
            VALUES (CAST(:props AS jsonb), ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))
        """)

    # Speichere alle Properties als JSONB und Geometrie in ST_GeomFromGeoJSON()
    conn.execute(sql, {
        "props": json.dumps(props),
        "geom": json.dumps(geom)
    })

@app.post("/upload-geojson/process")
async def upload_geojson_with_process(
        geojson: dict = Body(...),
        process: bool = Query(True, description="Wenn true: verarbeite GeoJSON vor dem Speichern")
):
    """
    Wenn `process=true`, wird das GeoJSON zuerst durch `geo_processor` verändert.
    Danach werden die (verarbeiteten) Features wie bisher in die DB geschrieben.
    Die verarbeitete GeoJSON wird als JSON im Response-Body zurückgegeben.
    """
    try:
        # validieren einfacher Typen
        gtype = geojson.get("type")
        if gtype not in ["Feature", "FeatureCollection"]:
            raise HTTPException(status_code=400, detail="Ungültiger GeoJSON-Typ")

        # optional verarbeiten
        out_geojson = geojson
        if process and gtype == "FeatureCollection":
            out_geojson = process_geojson_make_black(geojson)

        # Speichern in DB wie in insert_feature (verwende vorhandene insert_feature)
        with engine.begin() as conn:
            if out_geojson.get("type") == "FeatureCollection":
                for feature in out_geojson.get("features", []):
                    insert_feature(conn, feature)
                count = len(out_geojson.get("features", []))
            else:
                insert_feature(conn, out_geojson)
                count = 1

        # Response: verarbeitete GeoJSON zurückgeben
        return {"status": "success", "inserted": count, "geojson": out_geojson}

    except Exception as e:
        import traceback
        print("❌ Fehler beim Verarbeiten/Speichern:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Fehler: {e}")

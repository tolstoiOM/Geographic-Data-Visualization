from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
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
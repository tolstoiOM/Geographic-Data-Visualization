-- create_tables.sql
-- PostGIS tables for storing features based on your example geojson

-- enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- features table: maps fields from geo_test.json to columns
CREATE TABLE IF NOT EXISTS features (
                                        id BIGSERIAL PRIMARY KEY,
                                        feature_id TEXT,
                                        fid INTEGER,
                                        fmzk_id BIGINT,
                                        f_klasse SMALLINT,
                                        lm SMALLINT,
                                        layer TEXT,
                                        bezug TEXT,
                                        klasse_sub SMALLINT,
                                        bw_geb_id BIGINT,
                                        bw_brk_id BIGINT,
                                        bw_son_id BIGINT,
                                        se_sdo_rowid BIGINT,
                                        se_anno_cad_data JSONB,
                                        rn_fid INTEGER,
                                        rn_objectid BIGINT,
                                        rn_bez TEXT,
                                        rn_zbez TEXT,
                                        rn_zgeb TEXT,
                                        rn_blk TEXT,
                                        rn_nutzung_code SMALLINT,
                                        rn_nutzung_level1 TEXT,
                                        rn_nutzung_level2 TEXT,
                                        rn_nutzung_level3 TEXT,
                                        rn_flaeche DOUBLE PRECISION,
                                        rn_se_anno_cad_data JSONB,

    -- keep the full original properties as JSONB for flexibility
                                        properties JSONB,

    -- geometry columns
                                        geom geometry(Geometry,4326),
                                        centroid geometry(Point,4326),
                                        bbox geometry(Geometry,4326),
                                        area_m2 DOUBLE PRECISION,

                                        created_at TIMESTAMPTZ DEFAULT now()
);

-- optional helper tables
CREATE TABLE IF NOT EXISTS collections (
                                           id SERIAL PRIMARY KEY,
                                           name TEXT NOT NULL,
                                           description TEXT,
                                           created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS layer_lookup (
                                            id SERIAL PRIMARY KEY,
                                            key TEXT UNIQUE,
                                            display_name TEXT,
                                            color TEXT,
                                            fill_opacity REAL DEFAULT 0.6,
                                            created_at TIMESTAMPTZ DEFAULT now()
);
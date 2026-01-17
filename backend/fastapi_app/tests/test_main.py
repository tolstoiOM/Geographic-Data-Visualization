import types

import pytest
from fastapi.testclient import TestClient

from .. import main


class _DummyBegin:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyEngine:
    def begin(self):
        return _DummyBegin()


def _client():
    return TestClient(main.app)


def test_root():
    client = _client()
    res = client.get("/")
    assert res.status_code == 200
    assert res.json().get("message")


def test_ai_scripts(monkeypatch):
    monkeypatch.setattr(main, "ai_list_scripts", lambda: [{"id": "demo", "name": "Demo"}])
    client = _client()
    res = client.get("/ai-scripts")
    assert res.status_code == 200
    body = res.json()
    assert "scripts" in body
    assert body["scripts"][0]["id"] == "demo"


def test_augment_invalid_geojson():
    client = _client()
    res = client.post("/augment?script_id=test", json={"type": "Invalid"})
    assert res.status_code == 400


def test_augment_success(monkeypatch):
    monkeypatch.setattr(main, "ai_process", lambda geojson, script_id: {"type": "FeatureCollection", "features": []})
    client = _client()
    res = client.post("/augment?script_id=convex_hull", json={"type": "FeatureCollection", "features": []})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["geojson"]["type"] == "FeatureCollection"


def test_ai_prompt_requires_prompt():
    client = _client()
    res = client.post("/ai/prompt", json={})
    assert res.status_code == 400


def test_ai_prompt_success(monkeypatch):
    monkeypatch.setattr(main, "process_prompt_with_gemini", lambda prompt, geojson=None: "ok")
    client = _client()
    res = client.post("/ai/prompt", json={"prompt": "hi"})
    assert res.status_code == 200
    assert res.json()["reply"] == "ok"


def test_upload_geojson_invalid_type():
    client = _client()
    res = client.post("/upload-geojson", json={"type": "Invalid"})
    assert res.status_code == 400


def test_upload_geojson_feature_collection(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "engine", _DummyEngine())
    monkeypatch.setattr(main, "insert_feature", lambda conn, feature: calls.append(feature))
    client = _client()
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [16.37, 48.21]}},
            {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [16.38, 48.22]}},
        ],
    }
    res = client.post("/upload-geojson", json=payload)
    assert res.status_code == 200
    assert res.json()["inserted"] == 2
    assert len(calls) == 2


def test_upload_geojson_process(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "engine", _DummyEngine())
    monkeypatch.setattr(main, "insert_feature", lambda conn, feature: calls.append(feature))

    def _proc(gj):
        gj = dict(gj)
        gj["_processed"] = True
        return gj

    monkeypatch.setattr(main, "process_geojson_make_black", _proc)

    client = _client()
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [16.37, 48.21]}},
        ],
    }
    res = client.post("/upload-geojson/process?process=true", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["inserted"] == 1
    assert body["geojson"]["_processed"] is True
    assert len(calls) == 1

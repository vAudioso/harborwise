"""End-to-end API smoke test (needs the trained models)."""
import pytest
from fastapi.testclient import TestClient

from harborwise.config import MODELS

pytestmark = pytest.mark.skipif(not (MODELS / "quantile_liner.joblib").exists(), reason="run `python -m pipeline.run_all` first")


@pytest.fixture(scope="module")
def client():
    from api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def busy_berth(client):
    occ = client.get("/occupied", params={"as_of": "2019-11-15T12:00:00"}).json()
    full = [o for o in occ if o["full"]]
    assert full, "expected at least one full berth at the demo time"
    return full[0]


def test_health_and_catalogue(client):
    assert client.get("/health").json()["status"] == "ok"
    ports = client.get("/ports").json()
    assert len(ports) > 100 and {"port_id", "portname", "lat", "lon"} <= set(ports[0])
    berths = client.get(f"/berths/{ports[0]['port_id']}").json()
    assert berths and "polygon" in berths[0] and "capacity" in berths[0]
    assert client.get("/berths/999999").status_code == 404


def test_predict_clearance(client, busy_berth):
    r = client.post("/predict/clearance", json={"berth_id": busy_berth["berth_id"], "as_of": "2019-11-15T12:00:00"})
    assert r.status_code == 200, r.text
    body = r.json()
    h = body["clearance_h"]
    assert body["status"] == "occupied" and 0 <= h["p25"] <= h["p50"] <= h["p90"]
    assert body["occupants"] and "remaining_h" in body["occupants"][0]
    assert body["confidence"] in {"high", "lower"}
    seg_of = {"cont": "liner", "crui": "liner", "tank": "other", "bulk": "other", "gcar": "other"}
    for o in body["occupants"]:
        assert o["model_segment"] == seg_of[o["vessel_type"]]
        assert o["confidence"] == ("high" if o["model_segment"] == "liner" else "lower")


def test_recommend(client, busy_berth):
    r = client.post("/recommend", json={"berth_id": busy_berth["berth_id"], "as_of": "2019-11-15T12:00:00",
                                        "vessel_type": "cont", "distance_nm": 180})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["recommended"]["total_cost_usd"] <= body["baseline_service_speed"]["total_cost_usd"] + 1e-6
    assert len(body["candidates"]) >= 3 and body["why"]


def test_validation_errors(client, busy_berth):
    assert client.post("/predict/clearance", json={"berth_id": busy_berth["berth_id"], "as_of": "2021-01-01T00:00:00"}).status_code == 422
    assert client.post("/predict/clearance", json={"berth_id": "nope", "as_of": "2019-11-15T12:00:00"}).status_code == 404
    assert client.post("/recommend", json={"berth_id": busy_berth["berth_id"], "vessel_type": "cont", "distance_nm": -5}).status_code == 422


def test_experiments_endpoint(client):
    rows = client.get("/experiments/runs", params={"task": "regression"}).json()
    assert rows and {"exp_id", "model", "mae"} <= set(rows[0])

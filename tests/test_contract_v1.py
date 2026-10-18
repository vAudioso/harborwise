"""The website's contract v1.0. These checks mirror the validators built into web/index.html,
so a response that passes here is one the website accepts."""
import math

import pytest
from fastapi.testclient import TestClient

from harborwise.config import MODELS

pytestmark = pytest.mark.skipif(not (MODELS / "quantile_liner.joblib").exists(), reason="run `python -m pipeline.run_all` first")

DEMO_VOYAGES = [  # the five voyages in the website
    ("HW-001", "Container vessel", 48, "houston", 630, 18.2),
    ("HW-002", "Container vessel", 33, "kingston", 480, 16.5),
    ("HW-003", "Bulk carrier", 29, "cartagena", 420, 14.8),
    ("HW-004", "Container vessel", 39, "colon", 570, 17.2),
    ("HW-005", "Tanker", 31, "sanjuan", 460, 15.8),
]


@pytest.fixture(scope="module")
def client():
    from api.main import app
    with TestClient(app) as c:
        yield c


def request(vid, vtype, daily, dest, dist, speed, **kw):
    body = {"schema_version": "1.0", "vessel_id": vid, "vessel_type": vtype, "daily_fuel_t": daily,
            "destination_port_id": dest, "distance_nm": dist, "baseline_speed_kn": speed,
            "speed_range": {"min_kn": 10, "max_kn": 22, "step_kn": 0.5}, "arrival_flexibility_h": 8,
            "max_late_risk": 0.2, "fuel_price_usd_t": 620, "planning_time_utc": "2019-11-15T12:00:00.000Z"}
    body.update(kw)
    return body


def finite_nonneg(*xs):
    return all(isinstance(x, (int, float)) and math.isfinite(x) and x >= 0 for x in xs)


def check_recommendation(c):  # = Hm() in the website
    assert c["schema_version"] == "1.0" and c["candidates"] and c["clearance"] and c["baseline"]
    q = c["clearance"]
    assert finite_nonneg(q["p25_h"], q["p50_h"], q["p90_h"]) and q["p25_h"] <= q["p50_h"] <= q["p90_h"]
    for d in c["candidates"]:
        assert finite_nonneg(d["speed_kn"], d["sailing_h"], d["wait_h"], d["fuel_t"], d["co2_t"]) and d["speed_kn"] > 0
        assert 0 <= d["late_risk"] <= 1 and isinstance(d["feasible"], bool)
        assert d["eta_utc"].endswith("Z")
    b = c["baseline"]
    assert finite_nonneg(b["fuel_t"], b["co2_t"], b["wait_h"], b["sailing_h"])
    if c["recommended_speed_kn"] is not None:
        assert any(abs(d["speed_kn"] - c["recommended_speed_kn"]) < 1e-3 and d["feasible"] for d in c["candidates"])


@pytest.mark.parametrize("voyage", DEMO_VOYAGES, ids=[v[0] for v in DEMO_VOYAGES])
def test_every_demo_voyage_gets_a_valid_recommendation(client, voyage):
    r = client.post("/recommendations", json=request(*voyage))
    assert r.status_code == 200, r.text
    body = r.json()
    check_recommendation(body)
    berth = body["berth"]
    assert berth["berth_id"] and berth["polygon"] and berth["why_chosen"]
    assert body["provenance"]["mode"] == "backend" and body["timing_ms"]["total"] > 0
    if voyage[3] in ("cartagena", "kingston", "sanjuan"):
        assert body["provenance"]["stand_in_port"] and "no ship positions" in body["explanation"]


def test_recommended_speed_is_cheapest_feasible(client):
    body = client.post("/recommendations", json=request(*DEMO_VOYAGES[0])).json()
    feasible = [d for d in body["candidates"] if d["feasible"]]
    assert body["recommended_speed_kn"] == min(feasible, key=lambda d: d["total_cost_usd"])["speed_kn"]
    assert body["risk_limit_applied"] >= 0.2


def test_bad_requests_are_rejected(client):
    assert client.post("/recommendations", json=request(*DEMO_VOYAGES[0], planning_time_utc="2024-01-01T00:00:00Z")).status_code == 422
    assert client.post("/recommendations", json=request(*DEMO_VOYAGES[0], destination_port_id="atlantis")).status_code == 404
    assert client.post("/recommendations", json=request("X", "Submarine", 10, "houston", 100, 12)).status_code == 422


def test_experiments_contract(client):  # = B_() in the website
    e = client.get("/experiments").json()
    assert e["schema_version"] == "1.0" and e["models"] and e["imbalance"] and e["calibration"]["bins"]
    for m in e["models"]:
        assert isinstance(m["name"], str) and finite_nonneg(m["mae_h"]) and (m["rmse_h"] is None or finite_nonneg(m["rmse_h"]))
    for i in e["imbalance"]:
        assert 0 <= i["pr_auc"] <= 1 and 0 <= i["recall"] <= 1
    for b in e["calibration"]["bins"]:
        assert 0 <= b["predicted"] <= 1 and 0 <= b["observed"] <= 1
    for f in e["figures"]:
        assert client.get(f).headers["content-type"] == "image/png"


def test_data_quality_contract(client):  # = R_() in the website
    d = client.get("/data-quality").json()
    assert d["schema_version"] == "1.0" and d["dataset"] and d["berth_match"] and d["record_definitions"]
    for x in d["duration_distribution"]["bins"] + d["visits_per_port"]["ports"]:
        assert finite_nonneg(x["count"])
    assert 0 <= d["berth_match"]["percent"] <= 100


def test_website_is_served(client):
    assert "HarborWise" in client.get("/app/").text
    assert client.get("/app/classic.html").status_code == 200
    assert client.get("/", follow_redirects=False).headers["location"] == "/app/"
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["runtime"]["platform"]
    assert client.get("/figures/../../README.md").status_code == 404


def test_site_addon_panels_have_their_data(client):
    """web/hw-extras.js shows confidence, ships alongside and the turnaround table from these fields."""
    page = client.get("/app/").text
    assert 'src="hw-extras.js"' in page and client.get("/app/hw-extras.js").status_code == 200
    body = client.post("/recommendations", json=request(*DEMO_VOYAGES[2])).json()  # occupied berth, lower confidence
    c = body["clearance"]
    assert c["confidence"] in {"high", "lower"} and c["capacity"] >= 1 and c["occupants"]
    for o in c["occupants"]:
        assert {"vessel_type", "arrival_time", "elapsed_h", "remaining_h", "confidence", "p_leaves_within_6h"} <= set(o)
        assert o["remaining_h"]["p25"] <= o["remaining_h"]["p50"] <= o["remaining_h"]["p90"]
    turn = client.get("/experiments").json()["turnaround_models"]
    assert {m["name"].split(" (")[0] for m in turn} >= {"Global median", "Port median", "Random Forest", "HistGradientBoosting", "GradientBoosting"}
    assert all(finite_nonneg(m["mae_h"], m["rmse_h"]) and 0 <= m["within_1h"] <= 1 for m in turn)

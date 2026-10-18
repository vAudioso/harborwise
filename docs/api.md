# API

Start the server with `make app` (or `make api`). The base address is `http://localhost:8000`, and every endpoint can be tried at **http://localhost:8000/docs**.

The API runs in **replay mode**: "now" is any moment in 2019. The API looks up which ships were alongside at that moment and predicts using only what was observable then.

## Website endpoints (contract v1.0)

These are what the website calls. They're defined in `api/contract_v1.py` and tested in `tests/test_contract_v1.py`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/recommendations` | Speed recommendation for one voyage |
| GET | `/experiments` | Test-set results for the Model Results page (liner segment) |
| GET | `/data-quality` | Dataset audit and counts |
| GET | `/figures/{name}.png` | Report figures |
| GET | `/health` | Status, and where the server is running |
| GET | `/app/` | The website |

### Example: recommend a speed

```bash
curl -s -X POST localhost:8000/recommendations -H 'content-type: application/json' -d '{
  "vessel_type": "Tanker",
  "daily_fuel_t": 31,
  "destination_port_id": "houston",
  "distance_nm": 150,
  "baseline_speed_kn": 15.8,
  "speed_range": {"min_kn": 10, "max_kn": 22, "step_kn": 0.5},
  "arrival_flexibility_h": 8,
  "max_late_risk": 0.2,
  "fuel_price_usd_t": 620,
  "planning_time_utc": "2019-11-15T12:00:00Z"
}'
```

| Request field | Meaning |
|---|---|
| `vessel_type` | `Container vessel`, `Cruise ship`, `Tanker`, `Bulk carrier` or `General cargo` |
| `daily_fuel_t` | Fuel per day at normal speed (tonnes) |
| `destination_port_id` | A website slug (`houston`, `colon`, `cartagena`, `kingston`, `sanjuan`), a port name from `GET /ports`, or a numeric port ID |
| `distance_nm` | Nautical miles to go |
| `baseline_speed_kn` | The ship's normal speed |
| `speed_range` | Speeds to consider |
| `arrival_flexibility_h` | How long the berth may stand free before the ship arrives without counting as "late" |
| `max_late_risk` | Highest acceptable chance of being late (0–1) |
| `planning_time_utc` | "Now", any time in 2019 |
| `berth_id` (optional) | A specific berth; otherwise the API picks one |

The response includes:
- `berth`: the chosen berth, its polygon, and why it was chosen
- `clearance`: the 25/50/90% times, the confidence, and every ship alongside
- `candidates`: every speed tested
- `recommended_speed_kn` and `baseline`
- `explanation`: a plain-English reason

**How the destination berth is picked:** a full berth used mainly by this ship type → a full berth of its segment → the most occupied berth of this type → the busiest berth.

**Stand-in ports:** Cartagena, Kingston and San Juan have no ship positions in the 2019 data, so the API uses the nearest port with berth data and says so in every response:
- Cartagena → Mamonal (same bay)
- Kingston → Port Esquivel
- San Juan → St Thomas

Ports outside the Caribbean and Gulf of Mexico return a clear 404.

## Other endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/ports` | The 159 ports with commercial berths |
| GET | `/berths/{port_id}` | Berths in a port, with capacity, median stay and polygon |
| GET | `/occupied?as_of=&port_id=` | Which berths are occupied at a moment |
| POST | `/predict/clearance` | `{berth_id, as_of}` → when a slot frees, plus a forecast for each ship alongside |
| POST | `/recommend` | `{berth_id, as_of, vessel_type, distance_nm, …}` → recommended speed for a specific berth |
| GET | `/vessel-profiles` | The fuel model's figures per ship type |
| GET | `/experiments/runs` | Every logged experiment run (filter with `task`, `exp_id`, `segment`) |
| GET | `/experiments/summary` | Test, simulation and turnaround summaries per segment |
| GET | `/info` | Service details |

## Running with Docker

After `make download-models` (or `make pipeline`):

```bash
docker build -t harborwise .
docker run -p 8000:8000 harborwise
```

The container respects the `PORT` environment variable, which most hosting platforms set.

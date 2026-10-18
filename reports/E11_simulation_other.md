# E11 — Arrival-speed simulation, other berths (tank, bulk, gcar occupants) (SIMULATED)

2,089 replayed scenarios from the test period (test (Nov–Dec 2019)). Each one: a real commercial ship is alongside a
single-slot berth; the next ship that really used that berth is on its way (service-speed ETA uniform 2–30 h (distance = ETA x service speed, max 400 nm)) and must pick a speed.
Outcomes are scored against the occupant's real departure time.

| Strategy | Mean speed (kn) | Mean wait at anchor (h) | Share that wait | Mean berth idle before arrival (h) | Fuel (t) | CO₂ (t) |
|---|---:|---:|---:|---:|---:|---:|
| Baseline: service speed | 13.5 | 23.7 | 71% | 3.1 | 45,153 | 140,608 |
| **HarborWise** | **10.5** | **20.4** | **64%** | **3.8** | **31,747** | **98,860** |
| Oracle (knows true departure) | 10.9 | 19.3 | 66% | 2.6 | 34,631 | 107,841 |

**Simulated effect of HarborWise vs baseline:** fuel −29.7%, CO₂ −41,747 t over the scenarios,
anchorage wait −14.2%, berth idle +0.77 h per call, ship's time to berth +0.77 h per call,
total cost −3.4%. Because ship time is valued so that service speed is optimal without congestion, these savings come from
avoiding waits (just-in-time arrival), not from generic slow steaming.
HarborWise captures 59% of the cost saving a perfect forecast would give.

| Incoming type | Scenarios | Baseline wait (h) | HarborWise wait (h) | Fuel saving |
|---|---:|---:|---:|---:|
| bulk | 380 | 36.6 | 32.3 | 34.2% |
| cont | 106 | 11.5 | 9.4 | 22.9% |
| crui | 37 | 9.7 | 6.9 | 31.3% |
| gcar | 391 | 21.4 | 19.0 | 17.5% |
| tank | 1175 | 21.9 | 18.4 | 31.3% |

**Sensitivity to how far out the ship is when it decides:**

| ETA window | Baseline mean wait (h) | Fuel saving | Wait reduction | Extra berth idle (h/call) | Cost saving | Share of oracle saving |
|---|---:|---:|---:|---:|---:|---:|
| main (ETA 2–30 h) | 23.7 | 29.7% | 14.2% | +0.77 | 3.4% | 59% |
| close in (ETA 2–12 h) | 30.3 | 35.4% | 8.9% | +0.32 | 3.5% | 81% |
| far out (ETA 12–48 h) | 17.5 | 23.6% | 19.1% | +1.12 | 2.7% | 44% |

**Assumptions (read before quoting any number):** fuel price $650/t; ship time valued at implied per vessel type (2 x service-speed daily fuel cost / 24);
berth-idle cost $500/h; cubic speed law, illustrative per-type profiles (harborwise/fuel.py). The incoming ship's distance is hypothetical, weather/currents/
port slot rules are ignored, and the data cannot measure real anchorage waits (Phase 1 audit §6). These are simulated savings.

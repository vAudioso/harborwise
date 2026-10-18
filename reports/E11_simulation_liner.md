# E11 — Arrival-speed simulation, liner berths (cont, crui occupants) (SIMULATED)

1,509 replayed scenarios from the test period (test (Nov–Dec 2019)). Each one: a real commercial ship is alongside a
single-slot berth; the next ship that really used that berth is on its way (service-speed ETA uniform 2–30 h (distance = ETA x service speed, max 400 nm)) and must pick a speed.
Outcomes are scored against the occupant's real departure time.

| Strategy | Mean speed (kn) | Mean wait at anchor (h) | Share that wait | Mean berth idle before arrival (h) | Fuel (t) | CO₂ (t) |
|---|---:|---:|---:|---:|---:|---:|
| Baseline: service speed | 16.9 | 4.2 | 35% | 6.8 | 66,400 | 206,771 |
| **HarborWise** | **15.3** | **3.3** | **29%** | **6.9** | **62,000** | **193,067** |
| Oracle (knows true departure) | 15.6 | 2.6 | 28% | 6.3 | 63,919 | 199,043 |

**Simulated effect of HarborWise vs baseline:** fuel −6.6%, CO₂ −13,704 t over the scenarios,
anchorage wait −21.2%, berth idle +0.03 h per call, ship's time to berth +0.03 h per call,
total cost −1.5%. Because ship time is valued so that service speed is optimal without congestion, these savings come from
avoiding waits (just-in-time arrival), not from generic slow steaming.
HarborWise captures 51% of the cost saving a perfect forecast would give.

| Incoming type | Scenarios | Baseline wait (h) | HarborWise wait (h) | Fuel saving |
|---|---:|---:|---:|---:|
| bulk | 13 | 2.2 | 1.9 | -0.3% |
| cont | 853 | 5.3 | 4.2 | 8.9% |
| crui | 501 | 2.7 | 2.1 | 5.7% |
| gcar | 87 | 3.0 | 2.6 | -10.0% |
| tank | 55 | 3.6 | 2.8 | 2.9% |

**Sensitivity to how far out the ship is when it decides:**

| ETA window | Baseline mean wait (h) | Fuel saving | Wait reduction | Extra berth idle (h/call) | Cost saving | Share of oracle saving |
|---|---:|---:|---:|---:|---:|---:|
| main (ETA 2–30 h) | 4.2 | 6.6% | 21.2% | +0.03 | 1.5% | 51% |
| close in (ETA 2–12 h) | 6.9 | 28.7% | 21.4% | +0.41 | 3.9% | 63% |
| far out (ETA 12–48 h) | 2.3 | 0.1% | 17.8% | -0.32 | 0.6% | 33% |

**Assumptions (read before quoting any number):** fuel price $650/t; ship time valued at implied per vessel type (2 x service-speed daily fuel cost / 24);
berth-idle cost $500/h; cubic speed law, illustrative per-type profiles (harborwise/fuel.py). The incoming ship's distance is hypothetical, weather/currents/
port slot rules are ignored, and the data cannot measure real anchorage waits (Phase 1 audit §6). These are simulated savings.

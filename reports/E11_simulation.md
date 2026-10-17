# E11 — Arrival-speed simulation (SIMULATED)

3,598 replayed scenarios from the test period (test (Nov–Dec 2019)). Each one: a real commercial ship is alongside a
single-slot berth; the next ship that really used that berth is on its way (service-speed ETA uniform 2–30 h (distance = ETA x service speed, max 400 nm)) and must pick a speed.
Outcomes are scored against the occupant's real departure time.

| Strategy | Mean speed (kn) | Mean wait at anchor (h) | Share that wait | Mean berth idle before arrival (h) | Fuel (t) | CO₂ (t) |
|---|---:|---:|---:|---:|---:|---:|
| Baseline: service speed | 14.9 | 15.5 | 56% | 4.6 | 111,473 | 347,126 |
| **HarborWise** | **12.5** | **13.1** | **49%** | **5.0** | **93,221** | **290,292** |
| Oracle (knows true departure) | 12.9 | 12.3 | 50% | 4.0 | 98,256 | 305,970 |

**Simulated effect of HarborWise vs baseline:** fuel −16.4%, CO₂ −56,834 t over the scenarios,
anchorage wait −15.4%, berth idle +0.47 h per call, ship's time to berth +0.47 h per call,
total cost −2.5%. Because ship time is valued so that service speed is optimal without congestion, these savings come from
avoiding waits (just-in-time arrival), not from generic slow steaming.
HarborWise captures 57% of the cost saving a perfect forecast would give.

| Incoming type | Scenarios | Baseline wait (h) | HarborWise wait (h) | Fuel saving |
|---|---:|---:|---:|---:|
| bulk | 393 | 34.1 | 29.7 | 33.4% |
| cont | 959 | 5.9 | 4.8 | 10.7% |
| crui | 538 | 3.3 | 2.5 | 8.1% |
| gcar | 478 | 17.9 | 15.7 | 15.1% |
| tank | 1230 | 21.5 | 18.0 | 30.6% |

**Sensitivity to how far out the ship is when it decides:**

| ETA window | Baseline mean wait (h) | Fuel saving | Wait reduction | Extra berth idle (h/call) | Cost saving | Share of oracle saving |
|---|---:|---:|---:|---:|---:|---:|
| main (ETA 2–30 h) | 15.5 | 16.4% | 15.4% | +0.47 | 2.5% | 57% |
| close in (ETA 2–12 h) | 20.5 | 31.6% | 10.8% | +0.34 | 3.7% | 73% |
| far out (ETA 12–48 h) | 11.1 | 10.3% | 19.1% | +0.57 | 1.6% | 40% |

**Assumptions (read before quoting any number):** fuel price $650/t; ship time valued at implied per vessel type (2 x service-speed daily fuel cost / 24);
berth-idle cost $500/h; cubic speed law, illustrative per-type profiles (harborwise/fuel.py). The incoming ship's distance is hypothetical, weather/currents/
port slot rules are ignored, and the data cannot measure real anchorage waits (Phase 1 audit §6). These are simulated savings.

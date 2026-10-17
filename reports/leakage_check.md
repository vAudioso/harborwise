# Leakage check: is every feature known at prediction time?

Prediction time t = arrival + elapsed hours. The label is departure − t.

| Feature | Why it is available at t |
|---|---|
| `elapsed_h` | Hours since this ship stopped alongside; observed directly. |
| `hour` | Hour of day (UTC) at prediction time. |
| `weekday` | Day of week at prediction time. |
| `month` | Month at prediction time. |
| `hurricane_season` | 1 if June–November at prediction time. |
| `arrival_hour` | Hour the ship stopped alongside; in the past at prediction time. |
| `vt_code` | Vessel type from the registry; static. |
| `port_occupancy` | Other commercial ships alongside in the port at t (arrived <= t, not yet left at t). |
| `berth_occupancy_others` | Other commercial ships alongside at the same berth at t. |
| `port_arrivals_24h_all` | All-vessel calls (incl. tugs/service craft) that started in the port in (t-24h, t]. |
| `port_departures_24h_comm` | Commercial ships that left the port in (t-24h, t]. |
| `port_arrivals_7d_comm` | Commercial ships that arrived in the port in (t-7d, t]. |
| `vessel_prev_visits` | Earlier 2019 visits by this ship (all ended before this arrival). |
| `vessel_prev_mean_log_stay` | Mean log1p stay of those earlier visits. |
| `vessel_prev_visits_port` | Earlier visits by this ship to this port. |
| `vessel_prev_mean_log_stay_port` | Mean log1p stay of earlier visits to this port. |
| `vessel_last_stay_port_h` | Length of this ship's previous stay in this port (ended before this arrival). |
| `vessel_median_stay_port_h` | Median of this ship's earlier stays in this port. |
| `hours_since_last_visit_port` | Hours since this ship last left this port (liner rotation). |
| `vessel_prev_visits_berth` | Earlier visits by this ship to this berth. |
| `vessel_median_stay_berth_h` | Median of this ship's earlier stays at this berth. |
| `med_total_berth_type` | Training-period median stay at this berth for this vessel type (fitted on train only). |
| `med_total_berth` | Training-period median stay at this berth (train only). |
| `med_total_port` | Training-period median stay in this port (train only). |
| `med_remaining_cp` | Training-period median remaining time at this berth/port/type for this elapsed time (train only). |
| `log_berth_train_visits` | log1p of training-period visits at this berth (train only). |

Excluded on purpose: `duration`, `ts_end`, `n_calls`, `confidence_min` (computed from the whole stay), `mmsi`, berth and port IDs as numbers (identifiers are only used to look up training-period medians).

Tests: `tests/test_features.py` recomputes congestion features using only data visible at t and checks they match.

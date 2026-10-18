# Turnaround time at arrival: model comparison (other ships: tank, bulk, gcar)

Predict how long a commercial ship will stay alongside, at the moment it berths. Train Jan–Aug (18,528 visits, stays over 7 days excluded), validation Sep–Oct (5,361), test Nov–Dec (5,672, scored once). Median turnaround in the test set: 34.9 h.

| Model | Test MAE (h) | Test RMSE (h) | Median abs. error (h) | Within 1 h | Within 3 h | Validation MAE (h) |
|---|---:|---:|---:|---:|---:|---:|
| Global median | 25.67 | 44.76 | 16.86 | 2.8% | 8.8% | 25.84 |
| Port median | 23.35 | 42.99 | 14.45 | 4.5% | 13.4% | 23.86 |
| Berth median (extra baseline) | 21.07 | 40.36 | 11.90 | 6.6% | 17.9% | 21.35 |
| **Random Forest** | 18.91 | 38.56 | 9.84 | 7.3% | 19.8% | 19.46 |
| HistGradientBoosting | 19.02 | 38.41 | 10.32 | 7.4% | 19.1% | 19.50 |
| GradientBoosting | 19.01 | 38.29 | 10.05 | 6.8% | 18.5% | 19.48 |

Best model (chosen on validation): **Random Forest** (log1p target).

## Best model by vessel type (test)

| type   |   rows |   mae |   median_abs_err |   within_1h |   median_stay_h |
|:-------|-------:|------:|-----------------:|------------:|----------------:|
| bulk   |    985 | 32.01 |            15.45 |        0.04 |           54.25 |
| gcar   |   1067 | 19.24 |             8.67 |        0.11 |           22.55 |
| tank   |   3620 | 15.24 |             9.01 |        0.07 |           34.14 |

## Why the MAE is not under 1 hour
Stays are long and highly variable (median about a day, with a long tail of multi-day stays). The data has no cargo volume, crane, labour or schedule information, which is what actually decides when a ship leaves. An average error of under an hour would need those inputs, or information from after arrival (which would be leakage). See the remaining-time model (E10 report): errors shrink as the stay goes on, because elapsed time is informative.

# Turnaround time at arrival: model comparison (liner ships: cont, crui)

Predict how long a commercial ship will stay alongside, at the moment it berths. Train Jan–Aug (13,864 visits, stays over 7 days excluded), validation Sep–Oct (3,429), test Nov–Dec (3,886, scored once). Median turnaround in the test set: 12.8 h.

| Model | Test MAE (h) | Test RMSE (h) | Median abs. error (h) | Within 1 h | Within 3 h | Validation MAE (h) |
|---|---:|---:|---:|---:|---:|---:|
| Global median | 8.13 | 15.79 | 4.24 | 9.5% | 33.7% | 8.52 |
| Port median | 7.06 | 14.59 | 3.69 | 21.2% | 44.1% | 7.46 |
| Berth median (extra baseline) | 6.60 | 14.18 | 3.22 | 23.8% | 48.1% | 6.92 |
| Random Forest | 5.31 | 12.63 | 2.60 | 26.5% | 54.7% | 5.53 |
| HistGradientBoosting | 5.21 | 12.48 | 2.45 | 29.0% | 55.6% | 5.47 |
| **GradientBoosting** | 5.20 | 12.33 | 2.48 | 28.4% | 55.3% | 5.44 |

Best model (chosen on validation): **GradientBoosting** (raw target, absolute loss).

## Best model by vessel type (test)

| type   |   rows |   mae |   median_abs_err |   within_1h |   median_stay_h |
|:-------|-------:|------:|-----------------:|------------:|----------------:|
| cont   |   2817 |  5.78 |             3.35 |        0.18 |           15.47 |
| crui   |   1069 |  3.67 |             0.82 |        0.56 |           10.14 |

## Why the MAE is not under 1 hour
Stays are long and highly variable (median about a day, with a long tail of multi-day stays). The data has no cargo volume, crane, labour or schedule information, which is what actually decides when a ship leaves. An average error of under an hour would need those inputs, or information from after arrival (which would be leakage). See the remaining-time model (E10 report): errors shrink as the stay goes on, because elapsed time is informative.

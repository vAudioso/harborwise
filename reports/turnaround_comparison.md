# Turnaround time at arrival: model comparison

Predict how long a commercial ship will stay alongside, at the moment it berths. Train Jan–Aug (32,392 visits, stays over 7 days excluded), validation Sep–Oct (8,790), test Nov–Dec (9,558, scored once). Median turnaround in the test set: 22.6 h.

| Model | Test MAE (h) | Test RMSE (h) | Median abs. error (h) | Within 1 h | Within 3 h | Validation MAE (h) |
|---|---:|---:|---:|---:|---:|---:|
| Global median | 21.32 | 39.11 | 12.66 | 4.1% | 11.1% | 21.86 |
| Port median | 17.67 | 35.90 | 9.20 | 9.2% | 23.1% | 18.55 |
| Berth median (extra baseline) | 15.56 | 33.17 | 7.18 | 13.3% | 29.7% | 16.04 |
| **Random Forest** | 13.38 | 30.89 | 5.56 | 15.2% | 34.1% | 14.10 |
| HistGradientBoosting | 13.50 | 31.06 | 5.83 | 15.9% | 33.6% | 14.23 |
| GradientBoosting | 13.52 | 30.95 | 5.82 | 15.2% | 33.5% | 14.24 |

Best model (chosen on validation): **Random Forest** (log1p target).

## Best model by vessel type (test)

| type   |   rows |   mae |   median_abs_err |   within_1h |   median_stay_h |
|:-------|-------:|------:|-----------------:|------------:|----------------:|
| bulk   |    985 | 32.21 |            15.6  |        0.05 |           54.25 |
| cont   |   2817 |  5.87 |             3.46 |        0.17 |           15.47 |
| crui   |   1069 |  3.9  |             0.91 |        0.52 |           10.14 |
| gcar   |   1067 | 19.3  |             8.55 |        0.11 |           22.55 |
| tank   |   3620 | 15.15 |             8.84 |        0.07 |           34.14 |

## Why the MAE is not under 1 hour
Stays are long and highly variable (median about a day, with a long tail of multi-day stays). The data has no cargo volume, crane, labour or schedule information, which is what actually decides when a ship leaves. An average error of under an hour would need those inputs, or information from after arrival (which would be leakage). See the remaining-time model (E10 report): errors shrink as the stay goes on, because elapsed time is informative.

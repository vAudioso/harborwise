# E10 — Final test report (Nov–Dec 2019, untouched until now)

Test rows: 39,164 checkpoints (ships alongside at 1/3/6/12/24 h). Models were chosen on Sep–Oct validation only.

## Remaining time until the berth clears (point forecast)

| Model | MAE (h) | RMSE (h) | Median abs. error (h) |
|---|---:|---:|---:|
| Global median × checkpoint | 21.76 | 40.64 | 12.96 |
| Port median × checkpoint | 18.67 | 37.88 | 9.85 |
| Berth median × checkpoint | 16.56 | 35.16 | 7.83 |
| **XGBoost tuned trial 16** | **14.55** | **32.48** | **6.64** |

The model is **12.1% better than the strongest baseline** on MAE. Without stays longer than 7 days the test MAE is 12.12 h.
Note: the earlier 9.09 h "port median" figure was for total port-call duration of all vessels at visit start, a different and easier target.

**Unseen ports** (31 ports held out of training entirely, 4,191 test rows): model MAE 17.44 h vs 15.78 h for the baseline (which falls back to vessel-type medians).

### Errors by vessel type
| vesseltype   |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|:-------------|-------:|------:|---------------:|---------------------:|------------------:|
| bulk         |   4683 | 31.83 |          36.35 |                47.85 |             12.43 |
| cont         |  10705 |  6.12 |           7.6  |                11.67 |             19.54 |
| crui         |   3357 |  4.45 |           5.94 |                 7.33 |             25.17 |
| gcar         |   4128 | 22.45 |          24.88 |                24.87 |              9.77 |
| tank         |  16291 | 15.21 |          16.83 |                28.29 |              9.58 |

### Errors by checkpoint (hours alongside)
|   elapsed_h |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|------------:|-------:|------:|---------------:|---------------------:|------------------:|
|           1 |   9421 | 13.33 |          15.54 |                21.92 |             14.23 |
|           3 |   9231 | 13.37 |          15.44 |                20.5  |             13.42 |
|           6 |   8907 | 13.55 |          15.51 |                18.43 |             12.65 |
|          12 |   7031 | 15.92 |          17.8  |                19.79 |             10.56 |
|          24 |   4574 | 19.34 |          21.03 |                19.55 |              8.04 |

### Errors at the 15 busiest test ports
|   port_id |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|----------:|-------:|------:|---------------:|---------------------:|------------------:|
|       353 |   5481 | 16.69 |          19.21 |                31.45 |             13.16 |
|       365 |   2851 | 19.16 |          20.82 |                31.27 |              7.99 |
|       129 |   2034 |  4.27 |           5.57 |                 9.29 |             23.4  |
|       294 |   1728 |  7.38 |           8.9  |                 9.89 |             17.09 |
|       284 |   1501 | 10.42 |          14.55 |                16.1  |             28.41 |
|       366 |   1203 | 18.96 |          19.8  |                32.98 |              4.22 |
|       295 |   1167 |  5.28 |           6.68 |                 9.06 |             20.89 |
|       341 |    973 | 18.3  |          20.6  |                33.45 |             11.19 |
|       357 |    973 | 16.09 |          16.93 |                36.45 |              4.96 |
|       383 |    896 | 18.6  |          21.55 |                19.95 |             13.69 |
|       281 |    879 |  6.63 |           8.42 |                12.98 |             21.2  |
|       335 |    857 | 33.26 |          35.72 |                24.32 |              6.9  |
|       300 |    805 | 16.19 |          17.23 |                20.33 |              6.06 |
|       338 |    802 | 12.29 |          13.18 |                22.69 |              6.77 |
|       128 |    775 | 14.73 |          18.3  |                12.17 |             19.49 |

Biggest misses (`E10_biggest_misses.csv`): 100% of the top 50 are stays over 7 days;
their median true remaining time is 428 h. These look like rare long lay-ups / repairs, not label errors.

## Clears within 6 h (classification)

Model: RandomForestClassifier | class_weight, isotonic-calibrated, threshold 0.30 (chosen on validation).
Positive rate on test: 14.7%.

| Precision | Recall | F1 | PR-AUC | Brier | ECE |
|---:|---:|---:|---:|---:|---:|
| 0.567 | 0.689 | 0.622 | 0.664 | 0.0765 | 0.0087 |

Confusion matrix: TP 3,971 · FP 3,034 · FN 1,795 · TN 30,364

## Clearance window (P25 / P50 / P90)

| | P25 | P50 | P90 | P25–P90 interval |
|---|---:|---:|---:|---:|
| Target coverage | 25% | 50% | 90% | 65% |
| Test coverage | 23.7% | 48.8% | 89.6% | 65.9% |

Median interval width: 29.6 h.

Figures: `reports/figures/`. Every number here is also in `E10_final_test.json` and `experiments/experiments.csv` (exp_id E10).

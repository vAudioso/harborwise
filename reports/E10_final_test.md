# E10 — Final test report (Nov–Dec 2019, untouched until now)

Test rows: 39,164 checkpoints (ships alongside at 1/3/6/12/24 h). Models were chosen on Sep–Oct validation only.

## Remaining time until the berth clears (point forecast)

| Model | MAE (h) | RMSE (h) | Median abs. error (h) |
|---|---:|---:|---:|
| Global median × checkpoint | 21.76 | 40.64 | 12.96 |
| Port median × checkpoint | 18.67 | 37.88 | 9.85 |
| Berth median × checkpoint | 16.56 | 35.16 | 7.83 |
| **XGBoost tuned trial 04** | **14.84** | **32.75** | **6.85** |

The model is **10.4% better than the strongest baseline** on MAE. Without stays longer than 7 days the test MAE is 12.39 h.
Note: the earlier 9.09 h "port median" figure was for total port-call duration of all vessels at visit start, a different and easier target.

**Unseen ports** (31 ports held out of training entirely, 4,191 test rows): model MAE 18.72 h vs 15.78 h for the baseline (which falls back to vessel-type medians).

### Errors by vessel type
| vesseltype   |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|:-------------|-------:|------:|---------------:|---------------------:|------------------:|
| bulk         |   4683 | 31.92 |          36.35 |                47.85 |             12.21 |
| cont         |  10705 |  6.32 |           7.6  |                11.67 |             16.83 |
| crui         |   3357 |  4.72 |           5.94 |                 7.33 |             20.52 |
| gcar         |   4128 | 22.91 |          24.88 |                24.87 |              7.94 |
| tank         |  16291 | 15.57 |          16.83 |                28.29 |              7.46 |

### Errors by checkpoint (hours alongside)
|   elapsed_h |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|------------:|-------:|------:|---------------:|---------------------:|------------------:|
|           1 |   9421 | 13.69 |          15.54 |                21.92 |             11.87 |
|           3 |   9231 | 13.66 |          15.44 |                20.5  |             11.49 |
|           6 |   8907 | 13.81 |          15.51 |                18.43 |             10.98 |
|          12 |   7031 | 16.17 |          17.8  |                19.79 |              9.17 |
|          24 |   4574 | 19.55 |          21.03 |                19.55 |              7.05 |

### Errors at the 15 busiest test ports
|   port_id |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|----------:|-------:|------:|---------------:|---------------------:|------------------:|
|       353 |   5481 | 17.15 |          19.21 |                31.45 |             10.73 |
|       365 |   2851 | 19.29 |          20.82 |                31.27 |              7.35 |
|       129 |   2034 |  4.45 |           5.57 |                 9.29 |             20.16 |
|       294 |   1728 |  7.76 |           8.9  |                 9.89 |             12.87 |
|       284 |   1501 | 10.81 |          14.55 |                16.1  |             25.72 |
|       366 |   1203 | 18.76 |          19.8  |                32.98 |              5.22 |
|       295 |   1167 |  5.71 |           6.68 |                 9.06 |             14.46 |
|       341 |    973 | 18.79 |          20.6  |                33.45 |              8.79 |
|       357 |    973 | 16.94 |          16.93 |                36.45 |             -0.09 |
|       383 |    896 | 19.31 |          21.55 |                19.95 |             10.39 |
|       281 |    879 |  6.61 |           8.42 |                12.98 |             21.53 |
|       335 |    857 | 34.42 |          35.72 |                24.32 |              3.65 |
|       300 |    805 | 16.4  |          17.23 |                20.33 |              4.82 |
|       338 |    802 | 12.55 |          13.18 |                22.69 |              4.78 |
|       128 |    775 | 15.41 |          18.3  |                12.17 |             15.79 |

Biggest misses (`E10_biggest_misses.csv`): 100% of the top 50 are stays over 7 days;
their median true remaining time is 428 h. These look like rare long lay-ups / repairs, not label errors.

## Clears within 6 h (classification)

Model: RandomForestClassifier | class_weight, isotonic-calibrated, threshold 0.29 (chosen on validation).
Positive rate on test: 14.7%.

| Precision | Recall | F1 | PR-AUC | Brier | ECE |
|---:|---:|---:|---:|---:|---:|
| 0.539 | 0.699 | 0.609 | 0.641 | 0.0789 | 0.0071 |

Confusion matrix: TP 4,032 · FP 3,442 · FN 1,734 · TN 29,956

## Clearance window (P25 / P50 / P90)

| | P25 | P50 | P90 | P25–P90 interval |
|---|---:|---:|---:|---:|
| Target coverage | 25% | 50% | 90% | 65% |
| Test coverage | 23.7% | 47.9% | 89.4% | 65.8% |

Median interval width: 31.0 h.

Figures: `reports/figures/`. Every number here is also in `E10_final_test.json` and `experiments/experiments.csv` (exp_id E10).

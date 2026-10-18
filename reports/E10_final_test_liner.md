# E10 — Final test report: liner ships (cont, crui), Nov–Dec 2019

Test rows: 14,062 checkpoints (ships alongside at 1/3/6/12/24 h). Models were chosen on Sep–Oct validation only.

## Remaining time until the berth clears (point forecast)

| Model | MAE (h) | RMSE (h) | Median abs. error (h) |
|---|---:|---:|---:|
| Global median × checkpoint | 8.53 | 16.83 | 5.16 |
| Port median × checkpoint | 7.30 | 15.63 | 3.78 |
| Berth median × checkpoint | 6.90 | 15.19 | 3.39 |
| **XGBoost tuned trial 20** | **5.60** | **13.22** | **2.80** |

The model is **18.9% better than the strongest baseline** on MAE. Without stays longer than 7 days the test MAE is 5.46 h.
Note: the earlier 9.09 h "port median" figure was for total port-call duration of all vessels at visit start, a different and easier target.

**Unseen ports** (16 ports held out of training entirely, 1,133 test rows): model MAE 12.44 h vs 15.40 h for the baseline (which falls back to vessel-type medians).

### Errors by vessel type
| vesseltype   |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|:-------------|-------:|------:|---------------:|---------------------:|------------------:|
| cont         |  10705 |  6.07 |           7.42 |                11.67 |             18.19 |
| crui         |   3357 |  4.1  |           5.24 |                 7.33 |             21.85 |

### Errors by checkpoint (hours alongside)
|   elapsed_h |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|------------:|-------:|------:|---------------:|---------------------:|------------------:|
|           1 |   3839 |  5.17 |           6.54 |                11.9  |             21.04 |
|           3 |   3774 |  5.14 |           6.48 |                10.13 |             20.71 |
|           6 |   3629 |  5.07 |           6.36 |                 7.51 |             20.29 |
|          12 |   2136 |  6.62 |           7.85 |                 7.6  |             15.64 |
|          24 |    684 | 10.18 |          11.1  |                 9.05 |              8.35 |

### Errors at the 15 busiest test ports
|   port_id |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|----------:|-------:|------:|---------------:|---------------------:|------------------:|
|       129 |   1687 |  4.35 |           5.44 |                 9.89 |             20.08 |
|       294 |   1173 |  4.57 |           5.78 |                 8.39 |             21.01 |
|       284 |   1137 |  5.9  |           8.93 |                13.1  |             33.95 |
|       295 |   1123 |  4.97 |           6.69 |                 9.05 |             25.81 |
|       281 |    753 |  4.18 |           4.96 |                12.42 |             15.6  |
|       353 |    617 |  9.01 |          10.08 |                23.47 |             10.61 |
|       128 |    502 |  6.95 |           7.32 |                 9.76 |              4.99 |
|       300 |    433 |  6.79 |           7.4  |                15.77 |              8.29 |
|       365 |    433 |  5.54 |           5.58 |                11.76 |              0.8  |
|       105 |    359 |  0.81 |           0.86 |                 6.66 |              5.89 |
|        76 |    356 | 10.61 |          12.01 |                 8.63 |             11.68 |
|         1 |    320 |  7.49 |          10.23 |                14.13 |             26.8  |
|       338 |    313 |  6.77 |           7.19 |                15.16 |              5.91 |
|        31 |    301 |  2.34 |           2.77 |                 7.33 |             15.36 |
|       335 |    291 | 11.88 |          12.53 |                14.57 |              5.21 |

Biggest misses (`E10_biggest_misses.csv`): 10% of the top 50 are stays over 7 days;
their median true remaining time is 130 h. These look like rare long lay-ups / repairs, not label errors.

## Clears within 6 h (classification)

Model: RandomForestClassifier | smote_tomek, isotonic-calibrated, threshold 0.35 (chosen on validation).
Positive rate on test: 25.2%.

| Precision | Recall | F1 | PR-AUC | Brier | ECE |
|---:|---:|---:|---:|---:|---:|
| 0.645 | 0.760 | 0.698 | 0.754 | 0.1079 | 0.0218 |

Confusion matrix: TP 2,692 · FP 1,482 · FN 851 · TN 9,037

## Clearance window (P25 / P50 / P90)

| | P25 | P50 | P90 | P25–P90 interval |
|---|---:|---:|---:|---:|
| Target coverage | 25% | 50% | 90% | 65% |
| Test coverage | 22.2% | 46.9% | 88.9% | 66.7% |

Median interval width: 11.3 h.

Figures: `reports/figures/`. Every number here is also in `E10_final_test.json` and `experiments/experiments.csv` (exp_id E10).

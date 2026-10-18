# E10 — Final test report: other ships (tank, bulk, gcar), Nov–Dec 2019

Test rows: 25,102 checkpoints (ships alongside at 1/3/6/12/24 h). Models were chosen on Sep–Oct validation only.

## Remaining time until the berth clears (point forecast)

| Model | MAE (h) | RMSE (h) | Median abs. error (h) |
|---|---:|---:|---:|
| Global median × checkpoint | 25.38 | 45.59 | 16.32 |
| Port median × checkpoint | 23.58 | 44.11 | 14.38 |
| Berth median × checkpoint | 21.50 | 41.56 | 12.26 |
| **XGBoost tuned trial 14** | **19.61** | **39.09** | **10.85** |

The model is **8.8% better than the strongest baseline** on MAE. Without stays longer than 7 days the test MAE is 16.02 h.
Note: the earlier 9.09 h "port median" figure was for total port-call duration of all vessels at visit start, a different and easier target.

**Unseen ports** (29 ports held out of training entirely, 3,076 test rows): model MAE 26.85 h vs 30.45 h for the baseline (which falls back to vessel-type medians).

### Errors by vessel type
| vesseltype   |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|:-------------|-------:|------:|---------------:|---------------------:|------------------:|
| bulk         |   4683 | 31.8  |          35.47 |                47.85 |             10.33 |
| gcar         |   4128 | 22.49 |          24.4  |                24.87 |              7.85 |
| tank         |  16291 | 15.38 |          16.75 |                28.29 |              8.19 |

### Errors by checkpoint (hours alongside)
|   elapsed_h |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|------------:|-------:|------:|---------------:|---------------------:|------------------:|
|           1 |   5582 | 18.97 |          21.11 |                34.63 |             10.15 |
|           3 |   5457 | 19.12 |          21.06 |                33.4  |              9.19 |
|           6 |   5278 | 19.4  |          21.28 |                31.52 |              8.8  |
|          12 |   4895 | 20.02 |          21.84 |                28.05 |              8.31 |
|          24 |   3890 | 20.97 |          22.55 |                21.93 |              7    |

### Errors at the 15 busiest test ports
|   port_id |   rows |   mae |   baseline_mae |   median_remaining_h |   improvement_pct |
|----------:|-------:|------:|---------------:|---------------------:|------------------:|
|       353 |   4864 | 17.86 |          20.41 |                32.72 |             12.48 |
|       365 |   2418 | 21.73 |          22.78 |                36.82 |              4.61 |
|       366 |   1196 | 19.58 |          19.72 |                33.17 |              0.68 |
|       341 |    973 | 18.58 |          20.6  |                33.45 |              9.83 |
|       357 |    973 | 16.28 |          16.93 |                36.45 |              3.81 |
|       383 |    703 | 19.8  |          23.04 |                24.04 |             14.03 |
|       359 |    676 | 18.85 |          19.62 |                30.5  |              3.94 |
|       350 |    675 | 13.54 |          14.19 |                28.81 |              4.54 |
|       377 |    606 | 23.9  |          24.21 |                45.5  |              1.26 |
|       352 |    604 | 14.5  |          14.79 |                31.09 |              1.98 |
|       335 |    566 | 43.78 |          44.77 |                37.19 |              2.21 |
|       294 |    555 | 12.9  |          13.92 |                23.89 |              7.32 |
|       316 |    515 | 20.44 |          23.31 |                18.4  |             12.3  |
|       338 |    489 | 16.57 |          16.76 |                31.73 |              1.12 |
|       355 |    445 | 14.44 |          16.08 |                32.87 |             10.24 |

Biggest misses (`E10_biggest_misses.csv`): 100% of the top 50 are stays over 7 days;
their median true remaining time is 432 h. These look like rare long lay-ups / repairs, not label errors.

## Clears within 6 h (classification)

Model: XGBClassifier | none, isotonic-calibrated, threshold 0.24 (chosen on validation).
Positive rate on test: 8.9%.

| Precision | Recall | F1 | PR-AUC | Brier | ECE |
|---:|---:|---:|---:|---:|---:|
| 0.433 | 0.573 | 0.494 | 0.493 | 0.0585 | 0.0066 |

Confusion matrix: TP 1,274 · FP 1,666 · FN 949 · TN 21,213

## Clearance window (P25 / P50 / P90)

| | P25 | P50 | P90 | P25–P90 interval |
|---|---:|---:|---:|---:|
| Target coverage | 25% | 50% | 90% | 65% |
| Test coverage | 25.1% | 49.7% | 89.9% | 64.9% |

Median interval width: 44.9 h.

Figures: `reports/figures/`. Every number here is also in `E10_final_test.json` and `experiments/experiments.csv` (exp_id E10).

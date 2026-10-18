# Data

## Source

**Iphar, C. et al. (2024).** *Port calls and vessel trajectory dataset in the Caribbean with accurate port quays survey.* Data in Brief. Zenodo record [10380638](https://zenodo.org/records/10380638), version 1.1.0, DOI [10.5281/zenodo.10380638](https://doi.org/10.5281/zenodo.10380638).

- **What:** 1.49 million port calls by 22,225 ships, 1,902 surveyed berths and 528 ports in the Caribbean and Gulf of Mexico, built from AIS ship-tracking messages in 2019.
- **Licence:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). You may use and share it non-commercially, with credit, under the same licence. The processed data and trained models in this project's GitHub release are derived from it and carry the same licence.

## Getting it

```bash
make download-data
```

This downloads `CSV.zip` from Zenodo (67 MB), checks its checksum, and puts the 13 CSV files in `data/raw/`. The files are pipe-delimited (`|`). They are not stored in the repository because they're too large.

## What one record means

| Record | Meaning |
|---|---|
| Port call | A stop below 0.5 knots within about 600 m of a surveyed quay. It's a stay alongside, not an anchorage wait. |
| Berth visit | Port calls matched to a berth polygon and merged when the gap is under 1 h. Commercial ships with confidence ≥ 0.5 only. |
| Checkpoint | A ship observed 1, 3, 6, 12 or 24 h after it berthed. The label is the hours left until it leaves. |
| Clearance quantile | The 25/50/90% times until a slot at the berth frees, from the planning time. |

The full audit is in `reports/phase1/PHASE1_AUDIT.md`. It covers what each column means, data-quality problems, how berths were matched, and why only commercial ships are used.

## From raw calls to training data

| Stage | Rows |
|---|---:|
| All port calls | 1,488,781 |
| With coordinates | 1,121,003 |
| Inside a berth polygon | 914,989 |
| Merged into visits | 781,632 |
| Commercial ships, confidence ≥ 0.5 | **51,729** (21,292 container and cruise) |

## Known gaps

- **Anchorage waits aren't recorded.** Only stops near quays are in the data.
- **Missing ship types:** about half the ships have no known type.
- **No positions for some big ports:** Cartagena, Kingston and San Juan have no ship positions, so their berths can't be matched.
- **Year cut-offs:** visits crossing the start or end of 2019 are cut off and excluded.

## Folders

| Folder | Contents | In git? |
|---|---|---|
| `data/raw/` | The 13 CSVs from Zenodo | No: `make download-data` |
| `data/processed/` | Visits, checkpoints, berths, ports, port calls, harbour-craft stops (Parquet) | Summaries only: `make download-models` or `make data` |
| `models/` | Trained models (`.joblib`) and their settings and scores (`.json`) | Settings only: `make download-models` or `make pipeline` |

# data/

| Folder | Contents | How to get it |
|---|---|---|
| `raw/` | The 13 CSV files of the 2019 Caribbean AIS dataset (pipe-delimited) | `make download-data` |
| `processed/` | Cleaned berth visits, checkpoints, berths, ports and port calls (Parquet), built from `raw/` | `make download-models`, or rebuild with `make data` |

The data files aren't stored in git because they're too large. Licence: CC BY-NC-SA 4.0. Details: [docs/data.md](../docs/data.md).

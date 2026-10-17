"""Phase 1 / BE1: data-quality profile of every raw CSV, before any cleaning.

Usage: python -m pipeline.phase1.profile_csvs data/raw reports/phase1
Writes <out_dir>/data_quality.json and <out_dir>/data_quality.md.
"""
import json
import sys
from pathlib import Path

import pandas as pd

# Columns that are identifiers or encoded geometry: report coverage only, never numeric stats.
ID_COLS = {"id", "mmsi", "port", "portid", "port_origin", "port_destination", "idtraj", "locode", "abbr"}
GEOM_COLS = {"geom"}
TIME_COLS = {"ts_start", "ts_end", "ts"}


def profile(path: Path) -> dict:
    df = pd.read_csv(path, sep="|", low_memory=False)
    n = len(df)
    non_id = [c for c in df.columns if c != "id"]
    out = {
        "file": path.name,
        "rows": n,
        "columns": len(df.columns),
        "exact_duplicate_rows_excl_id": int(df.duplicated(subset=non_id).sum()) if non_id else 0,
        "id_unique": bool(df["id"].is_unique) if "id" in df else None,
        "cols": {},
    }
    # areapresence has 365 daily code columns; summarise them as one block.
    day_cols = [c for c in df.columns if c.startswith("d_")]
    if day_cols:
        vals = df[day_cols].stack(future_stack=True)
        out["daily_columns"] = {
            "count": len(day_cols),
            "missing_pct": round(100 * vals.isna().mean(), 2),
            "top_codes": vals.value_counts().head(15).to_dict(),
        }
    for c in df.columns:
        if c in day_cols:
            continue
        s = df[c]
        info = {
            "dtype": str(s.dtype),
            "missing_pct": round(100 * s.isna().mean(), 3),
            "n_unique": int(s.nunique()),
        }
        if c in TIME_COLS:
            t = pd.to_datetime(s, errors="coerce")
            info["unparseable"] = int(t.isna().sum() - s.isna().sum())
            info["min"], info["max"] = str(t.min()), str(t.max())
        elif c in GEOM_COLS:
            info["ewkb_type_prefixes"] = s.dropna().str[:18].value_counts().head(5).to_dict()
        elif c in ID_COLS:
            pass
        elif pd.api.types.is_numeric_dtype(s):
            d = s.describe(percentiles=[0.01, 0.25, 0.5, 0.75, 0.99])
            info["stats"] = {k: (None if pd.isna(v) else round(float(v), 4)) for k, v in d.items()}
            info["n_zero"] = int((s == 0).sum())
            info["n_negative"] = int((s < 0).sum())
        else:
            info["top_values"] = s.value_counts().head(10).to_dict()
        out["cols"][c] = info
    return out


def to_md(profiles: list) -> str:
    lines = ["# Raw data-quality profile (before cleaning)", ""]
    lines.append("| File | Rows | Cols | Duplicate rows (excl. id) | id unique |")
    lines.append("|---|---:|---:|---:|---|")
    for p in profiles:
        lines.append(f"| {p['file']} | {p['rows']:,} | {p['columns']} | {p['exact_duplicate_rows_excl_id']:,} | {p['id_unique']} |")
    for p in profiles:
        lines += ["", f"## {p['file']}", "", "| Column | dtype | Missing % | Unique | Notes |", "|---|---|---:|---:|---|"]
        for c, i in p["cols"].items():
            note = ""
            if "stats" in i:
                st = i["stats"]
                note = (f"min {st['min']}, p1 {st['1%']}, median {st['50%']}, p99 {st['99%']}, max {st['max']}; "
                        f"zeros {i['n_zero']:,}, negatives {i['n_negative']:,}")
            elif "min" in i:
                note = f"{i['min']} → {i['max']}; unparseable {i['unparseable']}"
            elif "top_values" in i:
                note = ", ".join(f"{k}: {v:,}" for k, v in list(i["top_values"].items())[:6])
            elif "ewkb_type_prefixes" in i:
                note = "EWKB prefixes: " + ", ".join(i["ewkb_type_prefixes"])
            lines.append(f"| {c} | {i['dtype']} | {i['missing_pct']} | {i['n_unique']:,} | {note} |")
        if "daily_columns" in p:
            d = p["daily_columns"]
            lines.append(f"| d_01_01…d_12_31 ({d['count']} cols) | zone codes | {d['missing_pct']} | | "
                         + ", ".join(f"{k}: {v:,}" for k, v in list(d["top_codes"].items())[:8]) + " |")
    return "\n".join(lines) + "\n"


def main(data_dir=None, out_dir=None):
    data_dir = Path(data_dir or sys.argv[1])
    out_dir = Path(out_dir or sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    profiles = []
    for f in sorted(data_dir.glob("*.csv")):
        print("profiling", f.name, flush=True)
        profiles.append(profile(f))
    (out_dir / "data_quality.json").write_text(json.dumps(profiles, indent=2, default=str))
    (out_dir / "data_quality.md").write_text(to_md(profiles))


if __name__ == "__main__":
    main()

"""Run the whole backend pipeline in order (about 15–25 minutes on a laptop; --quick for ~5).

    python -m pipeline.run_all            # everything
    python -m pipeline.run_all --quick    # fewer trees / search trials, for a smoke run
    python -m pipeline.run_all --from train_quantile   # resume from a step
    python -m pipeline.run_all --from train_turnaround --segment liner
Single step for one segment:  HARBORWISE_SEGMENT=other python -m pipeline.train_regression
"""
import argparse
import time

from harborwise.config import SEGMENTS, set_segment

from pipeline import (build_dataset, build_features, evaluate, simulate, train_classification, train_quantile,
                      train_regression, train_turnaround)

STEPS = [
    ("build_dataset", lambda q: build_dataset.main()),             # BE1: raw CSVs -> berth visits (Phase 1–2)
    ("build_features", lambda q: build_features.main()),           # BE2: checkpoint dataset + leakage report
    # Steps below run once per segment: liner (container, cruise) then other (tank, bulk, gcar).
    ("train_turnaround", lambda q: train_turnaround.main()),       # BE2: turnaround at arrival, RF/HGB/GB vs medians
    ("train_regression", lambda q: train_regression.main(q)),      # BE2: E00–E07
    ("train_classification", lambda q: train_classification.main(q)),  # BE3: E08–E09
    ("train_quantile", lambda q: train_quantile.main()),           # BE3: clearance window
    ("evaluate", lambda q: evaluate.main()),                       # BE3: E10 final test
    ("simulate", lambda q: simulate.main(1000 if q else 4000)),    # BE4: E11 speed simulation
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--from", dest="start", choices=[s for s, _ in STEPS])
    ap.add_argument("--segment", choices=list(SEGMENTS), help="only this segment (default: all segments)")
    args = ap.parse_args()
    names = [s for s, _ in STEPS]
    first = names.index(args.start) if args.start else 0
    shared = {"build_dataset", "build_features"}
    for name, fn in STEPS[first:]:
        if name in shared:
            _run(name, fn, args.quick)
    for seg in ([args.segment] if args.segment else list(SEGMENTS)):
        set_segment(seg)
        for name, fn in STEPS[first:]:
            if name not in shared:
                _run(f"{name} [{seg}]", fn, args.quick)


def _run(label, fn, quick):
    t0 = time.perf_counter()
    print(f"\n=== {label} ===", flush=True)
    fn(quick)
    print(f"=== {label} done in {time.perf_counter() - t0:.0f}s ===", flush=True)


if __name__ == "__main__":
    main()

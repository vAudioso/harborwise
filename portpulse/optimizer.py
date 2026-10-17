"""Speed optimizer: choose the speed that minimises
    J(v) = F(v) + lambda * E[sailing + waiting time](v) + mu * E[berth idle before we arrive](v)

F is the fuel bill (voyage at speed v, plus auxiliaries while waiting at anchor). lambda is the
value of the ship's time. By default it is set to the value that makes the ship's service speed
optimal when no waiting is expected (d/dv [F(v) + lambda d/v] = 0 at v_service  =>
lambda = 2 x daily fuel cost at service speed / 24). So without congestion PortPulse
recommends service speed, and any saving it reports comes from avoiding waits (just-in-time
arrival), not from generic slow steaming. mu is the extra cost of an idle berth (slot risk).

The berth-clearance time C (hours from now) is uncertain. We turn the model's P25/P50/P90
into a sample from a piecewise-linear inverse CDF and evaluate every candidate speed against
the same sample, so the comparison between speeds is fair.
"""
from dataclasses import dataclass

import numpy as np

from portpulse.fuel import VesselProfile, anchor_fuel_t, co2_t, voyage_fuel_t

DEFAULT_FUEL_PRICE = 650.0   # USD per tonne (VLSFO, order of magnitude; adjustable)
DEFAULT_LAMBDA = None        # None -> implied from the vessel profile (see module docstring)
DEFAULT_MU = 500.0           # USD per hour the berth stands free before we arrive (risk of losing the slot)
N_SAMPLES = 4000


def samples_from_quantiles(p25: float, p50: float, p90: float, n: int = N_SAMPLES) -> np.ndarray:
    """Stratified sample (deterministic) from a piecewise-linear inverse CDF through the quantiles.

    Tails are extrapolated linearly: P0 = max(0, P25 - (P50 - P25)); P100 = P90 + 2 (P90 - P50).
    """
    p25, p50, p90 = sorted([max(0.0, p25), max(0.0, p50), max(0.0, p90)])
    knots_p = [0.0, 0.25, 0.5, 0.9, 1.0]
    knots_x = [max(0.0, p25 - (p50 - p25)), p25, p50, p90, p90 + 2 * (p90 - p50)]
    u = (np.arange(n) + 0.5) / n
    return np.interp(u, knots_p, knots_x)


def berth_free_samples(occupant_samples: list[np.ndarray], capacity: int, seed: int = 0) -> np.ndarray:
    """Hours until a slot frees, given each current occupant's departure sample.

    With k occupants and capacity c: free now if k < c, else when the (k - c + 1)-th occupant leaves.
    Occupants are treated as independent (each sample is shuffled with its own permutation).
    """
    k = len(occupant_samples)
    if k < capacity:
        return np.zeros(N_SAMPLES)
    rng = np.random.default_rng(seed)
    M = np.vstack([rng.permutation(s) for s in occupant_samples])
    return np.sort(M, axis=0)[k - capacity]


def implied_time_value(p: VesselProfile, fuel_price: float) -> float:
    """USD/h at which service speed is cost-optimal for an uncongested voyage."""
    return 2.0 * p.design_daily_fuel_t * fuel_price / 24.0


@dataclass
class Candidate:
    speed_kn: float
    sailing_h: float
    expected_wait_h: float
    p_wait: float
    expected_idle_h: float
    voyage_fuel_t: float
    anchor_fuel_t: float
    total_fuel_t: float
    co2_t: float
    fuel_cost_usd: float
    time_cost_usd: float
    idle_cost_usd: float
    total_cost_usd: float

    def as_dict(self):
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


def evaluate_speed(p: VesselProfile, distance_nm: float, speed_kn: float, clear_h: np.ndarray,
                   fuel_price=DEFAULT_FUEL_PRICE, lam=DEFAULT_LAMBDA, mu=DEFAULT_MU) -> Candidate:
    lam = implied_time_value(p, fuel_price) if lam is None else lam
    sail = distance_nm / speed_kn
    wait = np.maximum(0.0, clear_h - sail)
    idle = np.maximum(0.0, sail - clear_h)
    vf = voyage_fuel_t(p, speed_kn, distance_nm)
    af = anchor_fuel_t(p, float(wait.mean()))
    total = vf + af
    fc, tc, ic = total * fuel_price, lam * (sail + float(wait.mean())), mu * float(idle.mean())
    return Candidate(speed_kn, sail, float(wait.mean()), float((wait > 0).mean()), float(idle.mean()),
                     vf, af, total, co2_t(total), fc, tc, ic, fc + tc + ic)


def candidate_speeds(p: VesselProfile, speed_min: float | None, speed_max: float | None, step: float = 0.5):
    lo = max(p.min_speed_kn, speed_min) if speed_min else p.min_speed_kn
    hi = min(p.max_speed_kn, speed_max) if speed_max else p.max_speed_kn
    if lo > hi:
        raise ValueError(f"empty speed range: {lo}–{hi} kn (vessel limits {p.min_speed_kn}–{p.max_speed_kn} kn)")
    service = float(np.clip(p.design_speed_kn, lo, hi))
    speeds = np.unique(np.round(np.r_[np.arange(lo, hi + 1e-9, step), service], 2))
    return speeds, service


def recommend(p: VesselProfile, distance_nm: float, clear_h: np.ndarray, speed_min=None, speed_max=None,
              fuel_price=DEFAULT_FUEL_PRICE, lam=DEFAULT_LAMBDA, mu=DEFAULT_MU) -> dict:
    if distance_nm <= 0:
        raise ValueError("distance_nm must be positive")
    lam = implied_time_value(p, fuel_price) if lam is None else lam
    speeds, service = candidate_speeds(p, speed_min, speed_max)
    cands = [evaluate_speed(p, distance_nm, float(v), clear_h, fuel_price, lam, mu) for v in speeds]
    best = min(cands, key=lambda c: c.total_cost_usd)
    base = next(c for c in cands if c.speed_kn == service)
    return {"recommended": best, "baseline": base, "candidates": cands,
            "weights": {"fuel_price_usd_per_t": fuel_price, "lambda_usd_per_ship_h": round(lam, 2), "mu_usd_per_idle_h": mu}}


def explain(rec: dict, clearance_q: dict) -> list[str]:
    b, s = rec["recommended"], rec["baseline"]
    lines = [f"The berth is predicted to clear in {clearance_q['p25']:.1f}–{clearance_q['p90']:.1f} h "
             f"(P25–P90, median {clearance_q['p50']:.1f} h)."]
    if abs(b.speed_kn - s.speed_kn) < 1e-6:
        lines.append(f"Sailing at service speed ({s.speed_kn:g} kn) is already the cheapest option: "
                     "slowing down would mostly leave the berth idle.")
    elif b.speed_kn < s.speed_kn:
        lines.append(f"At service speed ({s.speed_kn:g} kn) the ship would arrive in {s.sailing_h:.1f} h and expect "
                     f"{s.expected_wait_h:.1f} h at anchor. Slowing to {b.speed_kn:g} kn arrives in {b.sailing_h:.1f} h, "
                     f"cuts the expected wait to {b.expected_wait_h:.1f} h and burns {s.total_fuel_t - b.total_fuel_t:.1f} t less fuel.")
    else:
        lines.append(f"Speeding up to {b.speed_kn:g} kn is worth it: the berth is likely free soon, and arriving at "
                     f"service speed would leave it idle for {s.expected_idle_h:.1f} h on average.")
    lines.append(f"Probability of still waiting at anchor on arrival: {b.p_wait:.0%}.")
    lines.append("Fuel and CO2 figures use the cubic speed law with illustrative per-type engine figures (simulated, not measured).")
    return lines

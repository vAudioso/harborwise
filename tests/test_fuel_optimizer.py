import numpy as np
import pytest

from portpulse.fuel import CO2_PER_T_FUEL, co2_t, daily_fuel_t, profile, voyage_fuel_t
from portpulse.optimizer import berth_free_samples, recommend, samples_from_quantiles


def test_cubic_law_and_voyage_fuel_scale_with_speed_squared():
    p = profile("cont")
    assert daily_fuel_t(p, p.design_speed_kn) == pytest.approx(p.design_daily_fuel_t)
    assert daily_fuel_t(p, p.design_speed_kn / 2) == pytest.approx(p.design_daily_fuel_t / 8)
    # Same distance at half speed: 1/8 the daily burn for twice the time -> 1/4 the fuel.
    assert voyage_fuel_t(p, 8.0, 200) == pytest.approx(voyage_fuel_t(p, 16.0, 200) / 4)
    assert co2_t(10) == pytest.approx(10 * CO2_PER_T_FUEL)


def test_unknown_vessel_type_rejected():
    with pytest.raises(ValueError):
        profile("submarine")


def test_samples_reproduce_quantiles():
    s = samples_from_quantiles(4, 10, 30)
    assert np.all(np.diff(s) >= 0)
    assert np.quantile(s, 0.25) == pytest.approx(4, abs=0.1)
    assert np.quantile(s, 0.5) == pytest.approx(10, abs=0.1)
    assert np.quantile(s, 0.9) == pytest.approx(30, abs=0.2)


def test_berth_free_samples_capacity():
    a, b = np.full(4000, 5.0), np.full(4000, 9.0)
    assert np.all(berth_free_samples([a], capacity=2) == 0)          # a slot is already free
    assert np.all(berth_free_samples([a, b], capacity=1) == 9.0)     # over capacity: both must leave
    assert np.all(berth_free_samples([a, b], capacity=2) == 5.0)     # full: first departure frees a slot


def test_optimizer_slows_down_when_berth_clears_late():
    p = profile("bulk")
    late = recommend(p, 150, samples_from_quantiles(30, 40, 60))
    soon = recommend(p, 150, samples_from_quantiles(0, 0.5, 2))
    assert late["recommended"].speed_kn < late["baseline"].speed_kn
    assert late["recommended"].total_fuel_t < late["baseline"].total_fuel_t
    assert soon["recommended"].speed_kn >= late["recommended"].speed_kn
    # The recommendation can never cost more than the baseline under the model's own distribution.
    for r in (late, soon):
        assert r["recommended"].total_cost_usd <= r["baseline"].total_cost_usd + 1e-6


def test_optimizer_respects_speed_range():
    r = recommend(profile("tank"), 100, samples_from_quantiles(20, 30, 50), speed_min=11, speed_max=12)
    assert all(11 <= c.speed_kn <= 12 for c in r["candidates"])
    with pytest.raises(ValueError):
        recommend(profile("tank"), 100, samples_from_quantiles(1, 2, 3), speed_min=20, speed_max=25)

"""Fuel and CO2 model per vessel type.

Main-engine fuel per day follows the cubic speed law (propulsion power ~ v^3), which is the
standard first-order model in the slow-steaming literature:
    daily_fuel(v) = design_daily_fuel * (v / design_speed) ** 3
    voyage_fuel(v, d) = daily_fuel(v) * (d / v) / 24          (so fuel per voyage ~ v^2)
Sources: Psaraftis & Kontovas (2013), "Speed models for energy-efficient maritime
transportation", Transportation Research Part C 26:331–351; IMO Fourth GHG Study (2020).

At anchor the main engine is off; auxiliary engines/boilers burn `anchor_daily_fuel`.
CO2 uses the IMO carbon factor for heavy fuel oil, 3.114 t CO2 per t fuel
(MEPC.308(73), 2018 EEDI guidelines).

The per-type defaults below are ILLUSTRATIVE mid-size values for ships calling in the Caribbean
(feeder container ships, product tankers, handysize bulkers, small cruise ships). They are
assumptions, not measurements: replace them with vessel-specific data when available. Every
saving reported by the simulation inherits these assumptions.
"""
from dataclasses import asdict, dataclass

CO2_PER_T_FUEL = 3.114  # t CO2 / t HFO, IMO MEPC.308(73)


@dataclass(frozen=True)
class VesselProfile:
    vesseltype: str
    label: str
    design_speed_kn: float     # service speed
    design_daily_fuel_t: float  # main engine at service speed, t/day
    anchor_daily_fuel_t: float  # auxiliaries/boilers while waiting at anchor, t/day
    min_speed_kn: float        # lowest sensible speed (engine/manoeuvring limit)
    max_speed_kn: float


PROFILES = {
    "cont": VesselProfile("cont", "Container ship (feeder)", 17.0, 45.0, 3.0, 10.0, 19.0),
    "tank": VesselProfile("tank", "Tanker (product/MR)", 13.5, 28.0, 4.0, 9.0, 15.0),
    "bulk": VesselProfile("bulk", "Bulk carrier (handysize)", 13.0, 24.0, 2.5, 9.0, 14.5),
    "gcar": VesselProfile("gcar", "General cargo", 12.5, 16.0, 2.0, 8.0, 14.0),
    "crui": VesselProfile("crui", "Cruise ship", 18.0, 120.0, 35.0, 10.0, 21.0),
}


def profile(vesseltype: str) -> VesselProfile:
    if vesseltype not in PROFILES:
        raise ValueError(f"unknown vessel type {vesseltype!r}; expected one of {sorted(PROFILES)}")
    return PROFILES[vesseltype]


def daily_fuel_t(p: VesselProfile, speed_kn: float) -> float:
    return p.design_daily_fuel_t * (speed_kn / p.design_speed_kn) ** 3


def voyage_fuel_t(p: VesselProfile, speed_kn: float, distance_nm: float) -> float:
    hours = distance_nm / speed_kn
    return daily_fuel_t(p, speed_kn) * hours / 24.0


def anchor_fuel_t(p: VesselProfile, wait_h: float) -> float:
    return p.anchor_daily_fuel_t * wait_h / 24.0


def co2_t(fuel_t: float) -> float:
    return fuel_t * CO2_PER_T_FUEL


def profiles_as_dicts():
    return [asdict(p) for p in PROFILES.values()]

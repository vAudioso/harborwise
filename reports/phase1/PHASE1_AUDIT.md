# PortPulse — Phase 1 audit (BE1)

**Question:** Can the port-call table be turned into berth visits that are reliable enough to predict "when will this berth be free"?

**Verdict: go, with a narrowed scope.** Yes for **commercial ships** (tankers, container, bulk, general cargo, cruise). These give **51,747 berth visits**, 6,218 ships, 159 ports and 131 berths with ≥100 visits. For commercial ships a berth polygon behaves like a single slot. **No** for the full table: 93% of matched calls are tugs, service craft or vessels with no known type. Their berth polygons are shared zones, not slots.

The data cannot measure **anchorage waiting time** directly (see §6). BE4's simulation must model the wait instead of reading it from history.

Source documentation: Iphar et al., *Port calls and vessel trajectory dataset in the Caribbean with accurate port quays survey*, Data in Brief 2024 ([PMC11237856](https://pmc.ncbi.nlm.nih.gov/articles/PMC11237856/)), Zenodo record 10380638.

Reproduce with:

```
python -m pipeline.phase1.profile_csvs data/raw reports/phase1
python -m pipeline.phase1.berth_audit  data/raw reports/phase1
```
(Both also run as part of `python -m pipeline.build_dataset`.)

Both run in about 15 s. All numbers below come from `berth_audit.json` and `data_quality.md`.

---

## 1. What one port-call record means

Per the dataset paper, confirmed against the data:

| Field | Meaning |
|---|---|
| `ts_start` / `ts_end` | The vessel's speed over ground drops below / rises above **0.5 kn**, using only AIS messages **within ~600 m of a surveyed quay or wharf**. The authors already merge raw calls split by short gaps. |
| `duration` | `ts_end − ts_start` in **seconds**. It matches for all but 173 rows. |
| `nb_mes` | AIS messages received during the stop. |
| `time_bef` / `time_aft` | Seconds from the call start (end) to the nearest message before (after) it, so it measures how uncertain the edge is. |
| `conf` | The authors' 0–1 credibility of the duration. They don't publish the formula. |
| `latitude` / `longitude` / `geom` | Mean position while stopped, in WGS84 (EPSG:4326). |
| `port` | Port-level ID. **There is no berth column.** The berth must be recovered spatially. |

**Answer to the key question:** a port call is a *stop alongside or near a quay*, at port level. It is **not** a stop at an anchorage, and it does not name a berth. Our point-in-polygon step recovers the berth (§3). Joined that way, `ts_start` / `ts_end` are a good proxy for **berth entry and exit**.

**Timezone:** not stated in the paper. Start-hour counts reach their minimum at 06–08 UTC (01–03 local time in the Caribbean) and peak between 12 and 23 UTC. That fits **UTC** timestamps, so treat them as UTC.

**Coverage:** calendar year 2019 only. Visits that cross the year boundary are cut off: 1,812 start in the first hour of 1 Jan and 2,222 end in the last hour of 31 Dec. These are flagged `flag_year_censored`.

## 2. Raw data quality

The full per-column table is in [data_quality.md](data_quality.md).

| Finding | Count | Action |
|---|---:|---|
| Port calls | 1,488,781 (22,225 vessels, 415 ports) | |
| Missing coordinates | 24.7% (367,778) | Can't be placed at a berth. Excluded from berth visits. |
| `conf == 0` | 166,162 (11%) | 87% of these have `nb_mes = 0` and 86% have no coordinates; median 10 min. **Exclude.** |
| `conf < 0.5` | 264,569 | Flagged `flag_low_conf` |
| Zero duration | 3,559 | Flagged, not deleted. Only 51 remain after berth matching. |
| Duration < 10 min | 114,690 | Mostly service craft (§4) |
| Duration > 7 days / > 30 days | 21,861 / 5,075 | Flagged `flag_gt_7d`, likely lay-ups. Not deleted. |
| `time_aft` missing | 60.5%, rising from 55% (Jan) to 65% (Sep) | Documented "where applicable". The end-edge uncertainty is often unknown. |
| Start or end edge uncertain by > 1 h | 4.65% / 2.8% | Flagged `flag_edge_uncertain_gt_1h` |
| Same vessel in two ports at once | 2,750 overlapping calls, all at different ports | Matches the paper's ~0.25% wrong-MMSI rate. Flagged `flag_overlap_prev`. |
| MMSI not 9 digits | 3,153 calls | Keep for now. Likely bad MMSIs. |
| Exact duplicate rows | 0 in port calls; 1 in berths | |
| Berth codes used twice | 11 codes (for example `129_18`, `335_26`) belong to **different polygons** | Key berths by `berth_key` = code + `#id` |
| Berth port names that differ from `ports.csv` | 16 names (for example *Port of Spain* vs *Port-of-Spain*) | Cosmetic. **Join on `portid`, never on name.** |

## 3. Geometry and berth matching (full table, not a sample)

- **CRS:** port calls, berths and ports all use EWKB with SRID **4326**. The port-call `geom` agrees with the lat/lon columns to within 7e-6°. ✅
- **Coverage:** 95.8% of calls are at the 251 ports (out of 528) that have berth polygons.
- **Match rate:** **82.67%** of calls with coordinates at berth ports fall inside a berth polygon, matching the 81.63% sample estimate. That is 914,989 calls, or 61.5% of all calls. Only 32 points fall inside two polygons.
- **Validation:** our matched call counts per berth correlate at **0.994** with the published `berths.number`, with a median ratio of exactly 1.00. So we reproduced the authors' own berth assignment.
- **Unmatched points:** 78,753 are within 50 m of a polygon and 150,018 within 200 m. A small buffer (for example 50 m) would recover many. That is BE2's call, and it is not applied here.
- **Polygon size** varies enormously: median 12,600 m², 90th percentile 345,000 m², max about 1.6 km². The largest "berths" are whole basins.

## 4. Who generates the calls (this decides the scope)

| Vessel type | Matched calls | Vessels | Median stay | Share of calls that are fragments |
|---|---:|---:|---:|---:|
| unknown (no registry type) | 531,354 | 7,632 | 3.1 h | 35% |
| serv (tugs, pilots, supply) | 277,392 | 2,827 | 4.2 h | 38% |
| iisl (inter-island) | 40,710 | 402 | 0.6 h | 28% |
| tank | 24,255 | 2,676 | 31.6 h | 8% |
| cont | 20,540 | 897 | 14.0 h | 8% |
| bulk | 7,333 | 2,064 | 49.7 h | 9% |
| gcar | 6,985 | 657 | 24.3 h | 8% |
| crui | 6,420 | 381 | 9.8 h | 4% |

Vessel types cover only 47% of vessels (42.7% of calls). The original and enriched tables don't overlap and don't conflict, and joining them causes no row explosion.

Most calls come from small craft that stop and start constantly around the harbour. PortPulse is about large ships waiting for a berth, so **BE2 and BE3 should train on commercial types only.** The unknown-type vessels behave like small craft (short stays, frequent fragments), though this is unverified, so they shouldn't be used as labels. We may still use them as a "harbour busyness" feature.

## 5. From calls to visits

**Split visits:** consecutive calls by the same vessel at the same berth are separated by a median gap of 1.19 h, and 10% are under 0.55 h. Merging at a 0.5 h threshold changes nothing, which confirms the authors already merge gaps under about 30 min. Effect of merging gaps below the threshold:

| Threshold | Visits (all) | Commercial visits | Commercial median stay | Commercial visits made of > 1 call |
|---|---:|---:|---:|---:|
| 0.5 h | 914,989 | 65,533 | 21.2 h | 0% |
| **1 h (chosen)** | 781,632 | 62,530 | 22.5 h | 3.5% |
| 2 h | 708,823 | 61,520 | 22.9 h | 4.1% |
| 3 h | 686,089 | 61,273 | 23.0 h | 4.3% |

Commercial visits barely change beyond 1 h, so the label is robust to this choice.

**Berth concurrency (is a polygon one slot?):**
- **All vessels:** the median berth has up to 3 vessels at once, and 331 berths are shared for more than half their occupied time. Not a slot.
- **Commercial only** (1 h merge, `conf ≥ 0.5`): **395 of 688 berths never host two commercial ships at once.** The median maximum is 1 and the 90th percentile is 3. ✅ For commercial ships, "the berth is free" is a meaningful binary for most berths. For the 138 berths shared more than 10% of the time, define clearance as "one slot frees". The per-berth list is in `berth_concurrency_commercial.csv`.

**Final commercial table** (`berth_visits_merged_1h.parquet`, filtered to commercial types and `conf ≥ 0.5`):
- 51,747 visits, 6,218 ships, 159 ports, 832 berths
- 263 berths with ≥ 50 visits and 131 with ≥ 100; the berths with ≥ 100 hold 63% of visits
- stay length: p10 7.6 h, median 23.1 h, p90 72.8 h, p99 204 h
- by type: bulk 54 h, tank 34 h, gcar 26 h, cont 15 h, cruise 10 h
- 3,400–4,900 visits a month, steady through the year, so the Jan–Aug / Sep–Oct / Nov–Dec chronological split works

## 6. What this dataset cannot do

1. **Measure anchorage waiting.** Port calls only cover stops within ~600 m of quays. `trajectories.csv` has one row per segment between stops (no positions), and `areapresence.csv` only gives daily sea-zone letters (a–g). Waiting at anchor is never recorded. Implications for the team:
   - **BE4:** the simulation must *derive* the wait from predicted clearance versus the simulated arrival time. It can't validate against real waits. Say so on the data-honesty slide.
   - **Optional:** stops outside berth polygons but inside the port (the 150k points within 200 m) could be studied as a waiting proxy. It's weak evidence.
2. **Distance to port and speed.** There are no positions in transit, so the speed optimizer's distance and speed inputs have to come from the user, or from `segments_port2port` geometry as a rough route length.
3. **Cargo or terminal operations.** There are no features for crane counts, tonnage or cargo, so the remaining-time model only has port, berth, vessel type, timing and congestion features.

## 7. Recommendations for the team

| To | Recommendation |
|---|---|
| **All** | The label is the commercial berth visit: `arrival_time` = speed falls below 0.5 kn inside the berth polygon, `departure_time` = speed rises above it, with gaps under 1 h merged. Timestamps are UTC. |
| **BE2** | Build checkpoints from `berth_visits_merged_1h.parquet`, filtered to `is_commercial & confidence_min ≥ 0.5`. Exclude `flag_year_censored`. Keep the `flag_gt_7d` rows but test with and without them. Use `berth_key`, never the bare code. Candidate congestion feature: count of all-vessel calls at the port in the past 24 h. |
| **BE3** | Visits are long (median 23 h), so "clears within 3 h" will be rare early in a visit. Choose N after BE2's checkpoint distribution exists. The imbalance experiments are justified. |
| **BE4** | Model the anchorage wait (see §6). For the 138 shared berths, treat capacity as 2+. |
| **FE2** | Data-honesty slide: 1.49 M calls → 915 k at a berth → 782 k visits → **51.7 k commercial visits**, with the reason for each drop. |

## Output files

| File | Contents |
|---|---|
| `data_quality.md` / `.json` | Raw profile of all 13 CSVs, before any change |
| `berth_audit.json` | Every number in this report |
| `berth_visits_candidate.parquet` | 914,989 matched calls (not merged) with all flags |
| `berth_visits_merged_1h.parquet` | 781,632 merged visits, all vessel types, with flags and `is_commercial` |
| `berth_concurrency.csv` / `berth_concurrency_commercial.csv` | Per-berth concurrency, all vessels and commercial only |

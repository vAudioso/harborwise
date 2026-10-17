# Raw data-quality profile (before cleaning)

| File | Rows | Cols | Duplicate rows (excl. id) | id unique |
|---|---:|---:|---:|---|
| areapresence.csv | 35,652 | 367 | 0 | True |
| berths.csv | 1,902 | 8 | 1 | True |
| port_traffic.csv | 528 | 43 | 0 | True |
| portcalls.csv | 1,488,781 | 13 | 0 | True |
| ports.csv | 528 | 9 | 0 | True |
| segments_port2port.csv | 9,969 | 12 | 0 | True |
| segments_port2territory.csv | 7,425 | 13 | 0 | True |
| trajectories.csv | 1,473,752 | 7 | 0 | True |
| ungt_cont_throughput.csv | 25 | 3 | 0 | None |
| ungt_country_portcalls.csv | 38 | 11 | 0 | None |
| ungt_country_portstats.csv | 333 | 11 | 0 | None |
| vesseltype_enriched.csv | 2,643 | 4 | 0 | True |
| vesseltype_original.csv | 12,476 | 3 | 0 | True |

## areapresence.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| id | int64 | 0.0 | 35,652 |  |
| mmsi | int64 | 0.0 | 35,652 |  |
| d_01_01…d_12_31 (365 cols) | zone codes | 76.37 | | f: 1,566,412, g: 621,996, e: 344,026, d: 328,984, ag: 37,851, a: 34,126, de: 23,157, ef: 19,160 |

## berths.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| id | int64 | 0.0 | 1,902 |  |
| portname | str | 0.0 | 247 | New Orleans: 99, Port Everglades: 50, Port of South Louisiana: 48, Willemstad: 45, Mobile: 44, Cartagena: 43 |
| portid | int64 | 0.0 | 251 |  |
| countrycode | str | 0.0 | 39 | USA: 686, MEX: 233, COL: 130, TTO: 110, VEN: 99, PAN: 74 |
| berth | str | 0.0 | 1,891 | 66_20: 2, 76_16: 2, 129_18: 2, 136_07: 2, 323_01: 2, 329_07: 2 |
| number | int64 | 0.0 | 741 | min 0.0, p1 9.0, median 119.0, p99 6182.46, max 33888.0; zeros 5, negatives 0 |
| inport | float64 | 0.0 | 1,829 | min 0.0, p1 0.0007, median 0.0213, p99 0.5971, max 0.9028; zeros 5, negatives 0 |
| geom | str | 0.0 | 1,901 | EWKB prefixes: 0106000020E6100000 |

## port_traffic.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| id | int64 | 0.0 | 528 |  |
| portname | str | 0.0 | 516 | Georgetown: 3, Oranjestad: 2, Charlestown: 2, St George s: 2, La Ceiba: 2, Santa Marta: 2 |
| country | str | 0.0 | 41 | Cuba: 68, United States of America: 67, Venezuela: 65, Colombia: 29, Panama: 23, Haiti: 23 |
| pc_total | int64 | 0.0 | 316 | min 0.0, p1 0.0, median 130.5, p99 33451.6, max 221754.0; zeros 113, negatives 0 |
| pc_bulk | int64 | 0.0 | 75 | min 0.0, p1 0.0, median 0.0, p99 384.22, max 2118.0; zeros 380, negatives 0 |
| pc_cont | int64 | 0.0 | 80 | min 0.0, p1 0.0, median 0.0, p99 1609.17, max 3014.0; zeros 433, negatives 0 |
| pc_crui | int64 | 0.0 | 85 | min 0.0, p1 0.0, median 0.0, p99 753.88, max 2246.0; zeros 396, negatives 0 |
| pc_gcar | int64 | 0.0 | 106 | min 0.0, p1 0.0, median 0.0, p99 410.49, max 773.0; zeros 320, negatives 0 |
| pc_iisl | int64 | 0.0 | 93 | min 0.0, p1 0.0, median 0.0, p99 3075.09, max 15727.0; zeros 387, negatives 0 |
| pc_serv | int64 | 0.0 | 195 | min 0.0, p1 0.0, median 2.0, p99 14858.51, max 39243.0; zeros 241, negatives 0 |
| pc_tank | int64 | 0.0 | 112 | min 0.0, p1 0.0, median 0.0, p99 878.05, max 6502.0; zeros 342, negatives 0 |
| uv_total | int64 | 0.0 | 195 | min 0.0, p1 0.0, median 17.0, p99 1391.64, max 4096.0; zeros 113, negatives 0 |
| uv_bulk | int64 | 0.0 | 65 | min 0.0, p1 0.0, median 0.0, p99 240.14, max 909.0; zeros 380, negatives 0 |
| uv_cont | int64 | 0.0 | 52 | min 0.0, p1 0.0, median 0.0, p99 163.11, max 421.0; zeros 433, negatives 0 |
| uv_crui | int64 | 0.0 | 51 | min 0.0, p1 0.0, median 0.0, p99 79.65, max 244.0; zeros 396, negatives 0 |
| uv_gcar | int64 | 0.0 | 59 | min 0.0, p1 0.0, median 0.0, p99 87.73, max 303.0; zeros 320, negatives 0 |
| uv_iisl | int64 | 0.0 | 24 | min 0.0, p1 0.0, median 0.0, p99 20.46, max 174.0; zeros 387, negatives 0 |
| uv_serv | int64 | 0.0 | 71 | min 0.0, p1 0.0, median 1.0, p99 215.36, max 668.0; zeros 241, negatives 0 |
| uv_tank | int64 | 0.0 | 82 | min 0.0, p1 0.0, median 0.0, p99 383.17, max 1477.0; zeros 342, negatives 0 |
| vk_total | int64 | 0.0 | 146 | min 0.0, p1 0.0, median 5.0, p99 787.01, max 2647.0; zeros 172, negatives 0 |
| vk_bulk | int64 | 0.0 | 65 | min 0.0, p1 0.0, median 0.0, p99 240.14, max 909.0; zeros 380, negatives 0 |
| vk_cont | int64 | 0.0 | 51 | min 0.0, p1 0.0, median 0.0, p99 162.11, max 421.0; zeros 435, negatives 0 |
| vk_crui | int64 | 0.0 | 45 | min 0.0, p1 0.0, median 0.0, p99 70.0, max 97.0; zeros 430, negatives 0 |
| vk_gcar | int64 | 0.0 | 57 | min 0.0, p1 0.0, median 0.0, p99 87.73, max 303.0; zeros 321, negatives 0 |
| vk_iisl | int64 | 0.0 | 10 | min 0.0, p1 0.0, median 0.0, p99 7.0, max 13.0; zeros 414, negatives 0 |
| vk_serv | int64 | 0.0 | 59 | min 0.0, p1 0.0, median 1.0, p99 126.03, max 298.0; zeros 263, negatives 0 |
| vk_tank | int64 | 0.0 | 82 | min 0.0, p1 0.0, median 0.0, p99 383.17, max 1477.0; zeros 346, negatives 0 |
| tt_total | int64 | 0.0 | 356 | min 0.0, p1 0.0, median 60168.0, p99 149529322.41, max 309117493.0; zeros 172, negatives 0 |
| tt_bulk | int64 | 0.0 | 146 | min 0.0, p1 0.0, median 0.0, p99 12864959.62, max 66751879.0; zeros 380, negatives 0 |
| tt_cont | int64 | 0.0 | 93 | min 0.0, p1 0.0, median 0.0, p99 46007755.96, max 176627134.0; zeros 435, negatives 0 |
| tt_crui | int64 | 0.0 | 96 | min 0.0, p1 0.0, median 0.0, p99 58329643.37, max 146213726.0; zeros 430, negatives 0 |
| tt_gcar | int64 | 0.0 | 204 | min 0.0, p1 0.0, median 0.0, p99 2369556.04, max 9837646.0; zeros 321, negatives 0 |
| tt_iisl | int64 | 0.0 | 114 | min 0.0, p1 0.0, median 0.0, p99 2686210.05, max 19307148.0; zeros 414, negatives 0 |
| tt_serv | int64 | 0.0 | 261 | min 0.0, p1 0.0, median 125.0, p99 5562895.2, max 33799158.0; zeros 263, negatives 0 |
| tt_tank | int64 | 0.0 | 180 | min 0.0, p1 0.0, median 0.0, p99 36439352.69, max 200399106.0; zeros 346, negatives 0 |
| ma_total | float64 | 32.576 | 56 | min 1.0, p1 3.0, median 13.0, p99 58.8, max 73.0; zeros 0, negatives 0 |
| ma_bulk | float64 | 71.97 | 23 | min 2.0, p1 2.0, median 8.0, p99 50.0, max 50.0; zeros 0, negatives 0 |
| ma_cont | float64 | 82.386 | 17 | min 2.0, p1 2.0, median 13.0, p99 40.72, max 49.0; zeros 0, negatives 0 |
| ma_crui | float64 | 81.439 | 26 | min 1.0, p1 1.97, median 17.5, p99 60.0, max 60.0; zeros 0, negatives 0 |
| ma_gcar | float64 | 60.795 | 44 | min 1.0, p1 6.06, median 12.0, p99 62.0, max 73.0; zeros 0, negatives 0 |
| ma_iisl | float64 | 78.409 | 36 | min 1.0, p1 1.0, median 19.0, p99 51.0, max 71.0; zeros 0, negatives 0 |
| ma_serv | float64 | 49.811 | 55 | min 1.0, p1 2.64, median 20.0, p99 56.0, max 68.0; zeros 0, negatives 0 |
| ma_tank | float64 | 65.53 | 21 | min 3.0, p1 3.0, median 12.0, p99 30.47, max 51.0; zeros 0, negatives 0 |

## portcalls.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| id | int64 | 0.0 | 1,488,781 |  |
| mmsi | int64 | 0.0 | 22,225 |  |
| port | int64 | 0.0 | 415 |  |
| ts_start | str | 0.0 | 1,448,638 | 2019-01-01 00:00:01 → 2019-12-31 23:59:53; unparseable 0 |
| ts_end | str | 0.0 | 1,447,324 | 2019-01-01 00:00:51 → 2019-12-31 23:59:59; unparseable 0 |
| nb_mes | int64 | 0.0 | 6,488 | min 0.0, p1 0.0, median 16.0, p99 1498.0, max 228461.0; zeros 145,072, negatives 0 |
| time_bef | float64 | 0.825 | 32,864 | min 1.0, p1 14.0, median 530.0, p99 28082.0, max 86400.0; zeros 0, negatives 0 |
| time_aft | float64 | 60.471 | 24,244 | min 1.0, p1 13.0, median 540.0, p99 34859.97, max 86324.0; zeros 0, negatives 0 |
| duration | int64 | 0.0 | 210,336 | min 0.0, p1 29.0, median 9059.0, p99 885353.2, max 31535658.0; zeros 3,559, negatives 0 |
| conf | float64 | 0.0 | 340,242 | min 0.0, p1 0.0, median 0.9913, p99 1.0, max 1.0; zeros 166,162, negatives 0 |
| latitude | float64 | 24.703 | 309,213 | min 4.8483, p1 9.3523, median 29.6204, p99 32.8492, max 34.0234; zeros 0, negatives 0 |
| longitude | float64 | 24.703 | 201,230 | min -97.9217, p1 -97.823, median -90.3143, p99 -60.8742, max -52.2649; zeros 0, negatives 1,121,003 |
| geom | str | 24.703 | 733,132 | EWKB prefixes: 0101000020E6100000 |

## ports.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| id | int64 | 0.0 | 528 |  |
| portname | str | 0.0 | 516 | Georgetown: 3, Oranjestad: 2, Charlestown: 2, St George s: 2, La Ceiba: 2, Santa Marta: 2 |
| countryname | str | 0.0 | 41 | Cuba: 68, United States of America: 67, Venezuela: 65, Colombia: 29, Panama: 23, Haiti: 23 |
| countrycode | str | 0.0 | 41 | CUB: 68, USA: 67, VEN: 65, COL: 29, PAN: 23, HTI: 23 |
| quay | float64 | 47.159 | 259 | min 13.0, p1 19.78, median 682.0, p99 24188.68, max 59384.0; zeros 0, negatives 0 |
| wharf | float64 | 17.992 | 337 | min 10.0, p1 15.32, median 254.0, p99 10231.12, max 79468.0; zeros 0, negatives 0 |
| offshore | float64 | 99.242 | 4 | min 101.0, p1 105.35, median 345.0, p99 820.36, max 832.0; zeros 0, negatives 0 |
| geom | str | 0.0 | 528 | EWKB prefixes: 0105000020E6100000 |
| locode | str | 85.795 | 74 |  |

## segments_port2port.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| id | int64 | 0.0 | 9,969 |  |
| port_origin | int64 | 0.0 | 399 |  |
| port_destination | int64 | 0.0 | 403 |  |
| number_all | int64 | 0.0 | 379 | min 1.0, p1 1.0, median 3.0, p99 516.32, max 5037.0; zeros 0, negatives 0 |
| number_bulk | int64 | 0.0 | 41 | min 0.0, p1 0.0, median 0.0, p99 11.0, max 148.0; zeros 8,695, negatives 0 |
| number_cont | int64 | 0.0 | 118 | min 0.0, p1 0.0, median 0.0, p99 51.0, max 493.0; zeros 9,086, negatives 0 |
| number_crui | int64 | 0.0 | 88 | min 0.0, p1 0.0, median 0.0, p99 33.0, max 272.0; zeros 8,654, negatives 0 |
| number_gcar | int64 | 0.0 | 58 | min 0.0, p1 0.0, median 0.0, p99 17.0, max 202.0; zeros 7,961, negatives 0 |
| number_iisl | int64 | 0.0 | 104 | min 0.0, p1 0.0, median 0.0, p99 31.32, max 5037.0; zeros 9,355, negatives 0 |
| number_serv | int64 | 0.0 | 156 | min 0.0, p1 0.0, median 0.0, p99 79.32, max 1837.0; zeros 7,767, negatives 0 |
| number_tank | int64 | 0.0 | 87 | min 0.0, p1 0.0, median 0.0, p99 35.32, max 280.0; zeros 7,421, negatives 0 |
| geom | str | 0.0 | 9,969 | EWKB prefixes: 0102000020E6100000 |

## segments_port2territory.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| id | int64 | 0.0 | 7,425 |  |
| port | int64 | 0.0 | 359 |  |
| country | str | 0.0 | 41 | USA: 487, COL: 338, DOM: 336, PRI: 312, TTO: 303, MEX: 299 |
| direction | int64 | 0.0 | 2 | min 0.0, p1 0.0, median 0.0, p99 1.0, max 1.0; zeros 3,723, negatives 0 |
| number_all | int64 | 0.0 | 523 | min 1.0, p1 1.0, median 4.0, p99 1689.64, max 13792.0; zeros 0, negatives 0 |
| number_bulk | int64 | 0.0 | 76 | min 0.0, p1 0.0, median 0.0, p99 26.0, max 327.0; zeros 6,247, negatives 0 |
| number_cont | int64 | 0.0 | 171 | min 0.0, p1 0.0, median 0.0, p99 120.0, max 893.0; zeros 6,198, negatives 0 |
| number_crui | int64 | 0.0 | 124 | min 0.0, p1 0.0, median 0.0, p99 75.0, max 886.0; zeros 5,667, negatives 0 |
| number_gcar | int64 | 0.0 | 89 | min 0.0, p1 0.0, median 0.0, p99 43.0, max 228.0; zeros 5,160, negatives 0 |
| number_iisl | int64 | 0.0 | 145 | min 0.0, p1 0.0, median 0.0, p99 174.52, max 7861.0; zeros 6,679, negatives 0 |
| number_serv | int64 | 0.0 | 192 | min 0.0, p1 0.0, median 0.0, p99 310.28, max 3066.0; zeros 5,807, negatives 0 |
| number_tank | int64 | 0.0 | 140 | min 0.0, p1 0.0, median 0.0, p99 94.0, max 1386.0; zeros 5,053, negatives 0 |
| geom | str | 0.0 | 7,425 | EWKB prefixes: 0102000020E6100000 |

## trajectories.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| id | int64 | 0.0 | 1,473,752 |  |
| idtraj | int64 | 0.0 | 83 |  |
| rankintraj | int64 | 0.0 | 4,374 | min 1.0, p1 1.0, median 171.0, p99 2256.0, max 4374.0; zeros 0, negatives 0 |
| mmsi | int64 | 0.0 | 19,464 |  |
| port_origin | int64 | 0.0 | 408 |  |
| port_destination | int64 | 0.0 | 409 |  |
| ts | str | 0.0 | 1,433,690 | 2019-01-01 00:00:01 → 2019-12-31 23:56:08; unparseable 0 |

## ungt_cont_throughput.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| country | str | 0.0 | 25 | Anguilla: 1, Bahamas: 1, Barbados: 1, Cayman Islands: 1, Colombia: 1, Costa Rica: 1 |
| abbr | str | 0.0 | 25 |  |
| teu | int64 | 0.0 | 25 | min 1950.0, p1 2931.36, median 177076.0, p99 43957556.72, max 55518878.0; zeros 0, negatives 0 |

## ungt_country_portcalls.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| country | str | 0.0 | 38 | Anguilla: 1, Antigua and Barbuda: 1, Aruba: 1, Bahamas: 1, Barbados: 1, Belize: 1 |
| abbr | str | 0.0 | 38 |  |
| allships | float64 | 2.632 | 37 | min 15.0, p1 38.76, median 1267.0, p99 191055.08, max 286139.0; zeros 0, negatives 0 |
| liq_bulk | float64 | 23.684 | 28 | min 19.0, p1 24.88, median 320.0, p99 17129.12, max 21727.0; zeros 0, negatives 0 |
| liq_petroleum_gas | float64 | 65.789 | 13 | min 9.0, p1 11.16, median 70.0, p99 1791.12, max 1971.0; zeros 0, negatives 0 |
| liq_natural_gas | float64 | 84.211 | 6 | min 3.0, p1 4.25, median 49.0, p99 640.65, max 663.0; zeros 0, negatives 0 |
| dry_bulk | float64 | 47.368 | 19 | min 13.0, p1 15.66, median 165.0, p99 12624.9, max 14941.0; zeros 0, negatives 0 |
| dry_breakbulk | float64 | 2.632 | 35 | min 15.0, p1 20.04, median 235.0, p99 4733.72, max 6713.0; zeros 0, negatives 0 |
| roro | float64 | 28.947 | 26 | min 11.0, p1 12.82, median 106.0, p99 5651.16, max 6648.0; zeros 0, negatives 0 |
| container | float64 | 18.421 | 30 | min 40.0, p1 42.4, median 248.0, p99 15005.9, max 19574.0; zeros 0, negatives 0 |
| passenger | float64 | 7.895 | 34 | min 30.0, p1 46.32, median 354.0, p99 143003.16, max 213902.0; zeros 0, negatives 0 |

## ungt_country_portstats.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| country | str | 0.0 | 37 | Anguilla: 9, Antigua and Barbuda: 9, Aruba: 9, Bahamas: 9, Barbados: 9, Belize: 9 |
| abbr | str | 0.0 | 37 |  |
| vesseltype | str | 0.0 | 9 | allships: 37, container: 37, dry_breakbulk: 37, dry_bulk: 37, liq_bulk: 37, liq_natural_gas: 37 |
| med_time | float64 | 48.048 | 110 | min 0.26, p1 0.2672, median 0.91, p99 5.8252, max 10.99; zeros 0, negatives 0 |
| avg_age | float64 | 29.429 | 34 | min 3.0, p1 7.0, median 15.0, p99 39.32, max 49.0; zeros 0, negatives 0 |
| avg_gt | float64 | 29.429 | 233 | min 1749.0, p1 2023.9, median 24906.0, p99 110946.12, max 172533.0; zeros 0, negatives 0 |
| max_gt | float64 | 29.429 | 140 | min 2191.0, p1 2935.5, median 66870.0, p99 228081.0, max 228081.0; zeros 0, negatives 0 |
| avg_dwt | float64 | 49.249 | 162 | min 2176.0, p1 2565.64, median 15305.0, p99 82840.52, max 87290.0; zeros 0, negatives 0 |
| max_dwt | float64 | 49.249 | 106 | min 3008.0, p1 3449.32, median 51224.0, p99 321789.28, max 322829.0; zeros 0, negatives 0 |
| avg_teu | float64 | 81.381 | 31 | min 286.0, p1 286.0, median 1639.0, p99 5323.0, max 5323.0; zeros 0, negatives 0 |
| max_teu | float64 | 81.381 | 26 | min 515.0, p1 515.0, median 3646.0, p99 19462.0, max 19462.0; zeros 0, negatives 0 |

## vesseltype_enriched.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| id | int64 | 0.0 | 2,643 |  |
| mmsi | int64 | 0.0 | 2,643 |  |
| vesseltype | str | 0.0 | 7 | serv: 2,066, iisl: 325, crui: 193, cont: 24, tank: 16, gcar: 10 |
| share | float64 | 0.0 | 803 | min 0.9, p1 0.9048, median 0.9956, p99 1.0, max 1.0; zeros 0, negatives 0 |

## vesseltype_original.csv

| Column | dtype | Missing % | Unique | Notes |
|---|---|---:|---:|---|
| id | int64 | 0.0 | 12,476 |  |
| mmsi | int64 | 0.0 | 12,476 |  |
| vesseltype | str | 0.0 | 7 | bulk: 4,301, tank: 4,153, cont: 1,349, serv: 1,196, gcar: 1,114, crui: 238 |

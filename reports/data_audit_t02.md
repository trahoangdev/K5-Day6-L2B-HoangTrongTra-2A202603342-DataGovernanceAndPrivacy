# Data & Provenance audit — t02

Input: `fixtures/t02_raw_qc` · reproduce with `python tools/data_audit.py --track t02`

## 1. Provenance

**Tất cả 14 track: 14 PASS, 0 FAIL.**

```
OK   · t01_coverage: 3 file hashed  [3 file text dễ hỏng vì CRLF: candidates.csv, holdout_candidates.csv, targets.csv]
OK   · t02_raw_qc: 97 file hashed  [1 file text dễ hỏng vì CRLF: images.csv]
OK   · t03_synthetic: 80 file hashed  [5 file text dễ hỏng vì CRLF: README_usability_rule.md, holdout_transformed.csv, objects.csv, +2 file khác]
OK   · t04_sensor_sync: 6 file hashed  [6 file text dễ hỏng vì CRLF: README_units.md, camera.csv, imu.csv, +3 file khác]
OK   · t05_near_duplicate: 121 file hashed  [1 file text dễ hỏng vì CRLF: images.csv]
OK   · t06_release_gate: 245 file hashed  [124 file text dễ hỏng vì CRLF: releases.csv, releases/candidates/r01/release_meta.json, releases/candidates/r02/release_meta.json, +121 file khác]
OK   · t07_redaction: 61 file hashed  [1 file text dễ hỏng vì CRLF: images.csv]
OK   · t08_deletion: 2 file hashed  [2 file text dễ hỏng vì CRLF: data_graph.json, requests.json]
OK   · t09_privacy_gate: 14 file hashed  [14 file text dễ hỏng vì CRLF: README_disclaimer.md, cases/CASE-01.json, cases/CASE-02.json, +11 file khác]
OK   · t10_domain_shift: 242 file hashed  [2 file text dễ hỏng vì CRLF: images.csv, model_predictions.csv]
OK   · t11_label_errors: 58 file hashed  [3 file text dễ hỏng vì CRLF: annotations.csv, images.csv, model_predictions.csv]
OK   · t12_vendor_batches: 2 file hashed  [2 file text dễ hỏng vì CRLF: acceptance_policy.yaml, batches.csv]
OK   · t13_rare_mining: 202 file hashed  [2 file text dễ hỏng vì CRLF: images.csv, pool_features.csv]
OK   · t14_auto_annotation: 64 file hashed  [4 file text dễ hỏng vì CRLF: images.csv, model_card_fixture.yaml, model_predictions_fixture.csv, +1 file khác]
```

Track đang làm (`t02`):

```
OK   · verify_manifest: all hashes match
WARN · CRLF fragility: 1 hashed text file(s) would break: ['images.csv']
```

## 2. Schema

```
OK   · columns present: image_id, path, camera_id, light, split
OK   · no null cells
OK   · image_id unique (96 rows)
```

## 3. Split

```
OK   · split is scene-disjoint (24 scenes)
WARN · eval strata with NO dev example (cannot calibrate a per-stratum threshold): cam_A/night
WARN · dev strata never seen at eval (calibration effort wasted): cam_A/dusk, cam_B/day
```

Images per (camera, light) × split:

| camera_id | light | dev | eval |
|---|---|---:|---:|
| cam_A | day | 24 | 20 |
| cam_A | dusk | 12 | 0 |
| cam_A | night | 0 | 8 |
| cam_B | day | 12 | 0 |
| cam_B | dusk | 4 | 4 |
| cam_B | night | 4 | 8 |

## 4. Image statistics

| camera_id | light | n | lap_median | lap_p10 | sat_mean | dark_mean | bright_mean |
|---|---|---:|---:|---:|---:|---:|---:|
| cam_A | day | 44 | 944.304 | 18.319 | 0.005 | 0.066 | 108.437 |
| cam_A | dusk | 12 | 777.316 | 285.56 | 0.001 | 0.053 | 87.103 |
| cam_A | night | 8 | 1578.123 | 248.098 | 0.0 | 0.254 | 29.097 |
| cam_B | day | 12 | 235.766 | 2.204 | 0.0 | 0.0 | 117.864 |
| cam_B | dusk | 8 | 174.464 | 10.741 | 0.0 | 0.201 | 71.991 |
| cam_B | night | 12 | 350.414 | 239.22 | 0.001 | 0.091 | 39.251 |

`lap_median` is the per-group sharpness level a global threshold would be compared against.

Per-image features written to `reports/data_stats_t02.csv`.

## 5. Verdict

`0 FAIL, 3 WARN`

# Internal dev comparison — NOT official heldout evaluation

56 dev images, internal AI-assisted labels; design observed this dev set. B=20, seed=42.
Review queue uses all 96 images; metrics first filter to 56 dev images.

Baseline: `baseline_internal_dev` (git 24807f8, seed 42) · PoC: `poc_internal_dev` (git 24807f8, seed 42)

| Metric (unit) | Slice | Baseline | PoC | Δ abs | Δ rel | Better | N |
|---|---|---|---|---|---|---|---|
| **Defect Recall@B** (GT defects in top-B / GT defects) | all | 0.5882 | 0.5882 | 0.0000 | +0.0% | higher | 56 |
| Precision@B (GT defects in top-B / B) | all | 1.0000 | 1.0000 | 0.0000 | +0.0% | higher | 56 |
| Defect-type accuracy (GT defects) (fraction) | all | 0.2647 | 0.9412 | 0.6765 | +255.6% | higher | 34 |
| False alarm in top-B (clean images in top-B / clean images) | light=day | 0.0000 | 0.0000 | 0.0000 | baseline=0 | lower | 36 |
| False alarm in top-B (clean images in top-B / clean images) | light=dusk | 0.0000 | 0.0000 | 0.0000 | baseline=0 | lower | 16 |
| False alarm in top-B (clean images in top-B / clean images) | light=night | 0.0000 | 0.0000 | 0.0000 | baseline=0 | lower | 4 |
| Runtime / 100 items (s) | all | 0.4068 | 0.8693 | | | lower | |

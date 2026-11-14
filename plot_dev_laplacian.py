
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from src.common.image_ops import load_rgb, laplacian_variance

# Project root
ROOT = Path(__file__).resolve().parent

# Dataset
DATA_DIR = ROOT / "fixtures" / "t02_raw_qc"

# Read image metadata
df = pd.read_csv(DATA_DIR / "images.csv")

# Only use dev split
dev = df[df["split"] == "dev"].copy()

# Calculate Laplacian Variance
results = []

for _, row in dev.iterrows():
    image_path = DATA_DIR / row["path"]

    img = load_rgb(image_path)
    variance = laplacian_variance(img)

    results.append({
        "image_id": row["image_id"],
        "laplacian_variance": variance
    })

result_df = pd.DataFrame(results)
values = result_df["laplacian_variance"].to_numpy()

# Statistics
print(f"Number of dev images: {len(values)}")
print(f"Min: {values.min():.4f}")
print(f"Max: {values.max():.4f}")
print(f"Mean: {values.mean():.4f}")
print(f"Median: {np.median(values):.4f}")

# Percentiles
percentiles = [10, 25, 50, 75, 90]
percentile_values = np.percentile(values, percentiles)

# Candidate thresholds based on dev distribution
candidate_percentiles = [10, 15, 20, 25]

print("\nTHRESHOLD CANDIDATES")
print("-" * 55)
print(f"{'Percentile':<15}{'Threshold':<15}{'Flagged images':<18}{'Percentage'}")

for p in candidate_percentiles:
    threshold = np.percentile(values, p)

    # Images with variance below threshold
    flagged = np.sum(values < threshold)
    percentage = flagged / len(values) * 100

    print(
        f"P{p:<14}"
        f"{threshold:<15.4f}"
        f"{flagged:<18}"
        f"{percentage:.2f}%"
    )

# Show the 20 lowest Laplacian Variance values
print("\n20 LOWEST LAPLACIAN VARIANCE VALUES")
print(
    result_df.sort_values("laplacian_variance")
    .head(20)
    .to_string(index=False)
)


print("\nPercentiles:")
for p, value in zip(percentiles, percentile_values):
    print(f"P{p}: {value:.4f}")

# Save feature values
output_dir = ROOT / "out" / "baseline"
output_dir.mkdir(parents=True, exist_ok=True)

result_df.to_csv(
    output_dir / "dev_laplacian_values.csv",
    index=False
)

# Plot histogram
plt.figure(figsize=(11, 6))

log_bins = np.logspace(
    np.log10(values.min()),
    np.log10(values.max()),
    21
)

plt.hist(
    values,
    bins=log_bins,
    edgecolor="black",
    alpha=0.75
)

for p, value in zip(percentiles, percentile_values):
    plt.axvline(
        value,
        linestyle="--",
        label=f"P{p} = {value:.2f}"
    )

plt.xscale("log")
plt.xlabel("Laplacian Variance (log scale)")
plt.ylabel("Number of images")
plt.title("Laplacian Variance Distribution - Dev Set")
plt.legend()
plt.grid(alpha=0.25)

plt.tight_layout()
plt.savefig(
    output_dir / "dev_laplacian_histogram.png",
    dpi=200
)
plt.show()

print("\nSaved results:")
print(output_dir / "dev_laplacian_values.csv")
print(output_dir / "dev_laplacian_histogram.png")

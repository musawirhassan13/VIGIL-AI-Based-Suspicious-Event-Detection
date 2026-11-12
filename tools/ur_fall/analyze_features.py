from dataset_loader import load_dataset
import numpy as np

FEATURES = [
    "HeightWidthRatio",
    "MajorMinorRatio",
    "BoundingBoxOccupancy",
    "MaxStdXZ",
    "HHmaxRatio",
    "H",
    "D",
    "P40"
]


def analyze_features():
    _, _, combined = load_dataset()

    binary = combined[
        combined["label"].isin([-1, 1])
    ].copy()

    print("\n========== FEATURE STATISTICS ==========")

    print(
        binary[FEATURES].describe().round(3).to_string()
    )

    print("\n========== FEATURES BY CLASS ==========")

    grouped = binary.groupby("label")[FEATURES].mean()

    print(grouped.round(3).to_string())

    print("\n========== NON-FINITE VALUES ==========")

    print(
        (~np.isfinite(binary[FEATURES])).sum()
    )

if __name__ == "__main__":
    analyze_features()
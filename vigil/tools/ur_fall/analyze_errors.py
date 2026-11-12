
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from config import PROCESSED_DIR


FEATURES = [
    "HeightWidthRatio",
    "MajorMinorRatio",
    "BoundingBoxOccupancy",
    "MaxStdXZ",
    "HHmaxRatio",
    "H",
    "D",
    "P40",
]


def analyze_errors():
    train = pd.read_csv(PROCESSED_DIR / "train.csv")
    test = pd.read_csv(PROCESSED_DIR / "test.csv")

    X_train = train[FEATURES]
    y_train = train["label"]

    X_test = test[FEATURES]
    y_test = test["label"]

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        class_weight="balanced",
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    results = test.copy()
    results["predicted"] = model.predict(X_test)

    # False Positive: actual 0, predicted 1
    false_positives = results[
        (results["label"] == 0) &
        (results["predicted"] == 1)
    ]

    # False Negative: actual 1, predicted 0
    false_negatives = results[
        (results["label"] == 1) &
        (results["predicted"] == 0)
    ]

    print("\n========== ERROR ANALYSIS ==========")

    print("\nFalse Positives:", len(false_positives))
    print("False Negatives:", len(false_negatives))

    print("\n========== FALSE POSITIVE SEQUENCES ==========")
    if len(false_positives):
        print(
            false_positives.groupby("sequence")
            .size()
            .sort_values(ascending=False)
        )
    else:
        print("No false positives.")

    print("\n========== FALSE NEGATIVE SEQUENCES ==========")
    if len(false_negatives):
        print(
            false_negatives.groupby("sequence")
            .size()
            .sort_values(ascending=False)
        )
    else:
        print("No false negatives.")

    print("\n========== ERROR DETAILS ==========")

    error_rows = pd.concat(
        [
            false_positives.assign(error_type="False Positive"),
            false_negatives.assign(error_type="False Negative"),
        ]
    ).sort_values(["sequence", "frame"])

    columns = [
        "sequence",
        "frame",
        "label",
        "predicted",
        "error_type",
    ]

    print(error_rows[columns].to_string(index=False))

    output_path = PROCESSED_DIR / "error_analysis.csv"
    error_rows.to_csv(output_path, index=False)

    print("\nSaved error details to:", output_path)
    print("\n========== ANALYSIS COMPLETE ==========")


if __name__ == "__main__":
    analyze_errors()

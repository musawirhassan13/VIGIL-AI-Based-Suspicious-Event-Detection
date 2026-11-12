
import joblib
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

from config import PROCESSED_DIR

MODEL_PATH = PROCESSED_DIR / "best_fall_posture_model.joblib"
TEST_PATH = PROCESSED_DIR / "test.csv"


def evaluate():
    model = joblib.load(MODEL_PATH)
    test_df = pd.read_csv(TEST_PATH)

    features = [
        "HeightWidthRatio",
        "MajorMinorRatio",
        "BoundingBoxOccupancy",
        "MaxStdXZ",
        "HHmaxRatio",
        "H",
        "D",
        "P40",
    ]

    X_test = test_df[features]
    y_test = test_df["label"]

    predictions = model.predict(X_test)

    print("\n========== SAVED MODEL EVALUATION ==========")

    print("\nAccuracy:")
    print(round(accuracy_score(y_test, predictions), 4))

    print("\nClassification Report:")
    print(
        classification_report(
            y_test,
            predictions,
            target_names=["Not Lying", "Lying"],
            zero_division=0,
        )
    )

    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, predictions))

    print("\n========== EVALUATION COMPLETE ==========")


if __name__ == "__main__":
    evaluate()

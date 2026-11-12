
import joblib
import pandas as pd
import numpy as np

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

MODEL_PATH = PROCESSED_DIR / "best_fall_posture_model.joblib"


def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Trained model not found: {MODEL_PATH}"
        )

    return joblib.load(MODEL_PATH)


def predict_posture(model, features):
    missing = [name for name in FEATURES if name not in features]

    if missing:
        raise ValueError(f"Missing features: {missing}")

    values = [features[name] for name in FEATURES]

    if not all(np.isfinite(float(value)) for value in values):
        raise ValueError("Features must contain finite numeric values.")

    input_df = pd.DataFrame([features], columns=FEATURES)

    prediction = int(model.predict(input_df)[0])
    probabilities = model.predict_proba(input_df)[0]

    lying_index = list(model.classes_).index(1)
    lying_probability = float(probabilities[lying_index])

    return {
        "prediction": prediction,
        "posture": "Lying" if prediction == 1 else "Not Lying",
        "lying_probability": round(lying_probability, 4),
    }


def main():
    model = load_model()

    test_path = PROCESSED_DIR / "test.csv"
    test_df = pd.read_csv(test_path)

    sample = test_df.iloc[0]

    features = {
        name: float(sample[name])
        for name in FEATURES
    }

    result = predict_posture(model, features)

    print("\n========== SAVED MODEL PREDICTION ==========")
    print("Sequence:", sample["sequence"])
    print("Frame:", sample["frame"])
    print("Actual label:", int(sample["label"]))
    print("Predicted posture:", result["posture"])
    print("Lying probability:", result["lying_probability"])

    print("\n========== MODEL TEST COMPLETE ==========")


if __name__ == "__main__":
    main()

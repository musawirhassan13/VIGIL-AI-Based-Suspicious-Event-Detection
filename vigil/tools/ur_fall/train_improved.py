
import pandas as pd
import joblib

from sklearn.ensemble import (
    RandomForestClassifier,
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
)

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
)

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


def get_models():
    return {
        "Random Forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=None,
            min_samples_split=2,
            min_samples_leaf=1,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),

        "Extra Trees": ExtraTreesClassifier(
            n_estimators=200,
            max_depth=None,
            min_samples_split=2,
            min_samples_leaf=1,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),

        "Hist Gradient Boosting": HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.1,
            max_leaf_nodes=31,
            l2_regularization=1.0,
            random_state=42,
        ),
    }


def train_and_compare():
    train_path = PROCESSED_DIR / "train.csv"
    test_path = PROCESSED_DIR / "test.csv"

    if not train_path.exists() or not test_path.exists():
        raise FileNotFoundError(
            "Training or testing data missing. "
            "Run split_dataset.py first."
        )

    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)

    X_train = train_df[FEATURES]
    y_train = train_df["label"]

    X_test = test_df[FEATURES]
    y_test = test_df["label"]

    models = get_models()
    results = []
    trained_models = {}

    print("\n========== IMPROVED MODEL COMPARISON ==========")

    for name, model in models.items():
        print(f"\nTraining: {name}")

        model.fit(X_train, y_train)
        predictions = model.predict(X_test)

        accuracy = accuracy_score(y_test, predictions)
        precision = precision_score(
            y_test, predictions, zero_division=0
        )
        recall = recall_score(
            y_test, predictions, zero_division=0
        )
        f1 = f1_score(
            y_test, predictions, zero_division=0
        )

        results.append({
            "Model": name,
            "Accuracy": accuracy,
            "Precision": precision,
            "Recall": recall,
            "F1 Score": f1,
        })

        trained_models[name] = model

        print(f"Accuracy:  {accuracy:.4f}")
        print(f"Precision: {precision:.4f}")
        print(f"Recall:    {recall:.4f}")
        print(f"F1 Score:  {f1:.4f}")

        print("\nConfusion Matrix:")
        print(confusion_matrix(y_test, predictions))

        print("\nClassification Report:")
        print(
            classification_report(
                y_test,
                predictions,
                target_names=["Not Lying", "Lying"],
                zero_division=0,
            )
        )

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(
        by=["F1 Score", "Recall", "Accuracy"],
        ascending=False,
    )

    print("\n========== FINAL COMPARISON ==========")
    print(results_df.to_string(index=False))

    results_path = PROCESSED_DIR / "model_comparison.csv"
    results_df.to_csv(results_path, index=False)

    # Select the best model using lying-class F1 score.
    best_name = results_df.iloc[0]["Model"]
    best_model = trained_models[best_name]

    model_path = PROCESSED_DIR / "best_fall_posture_model.joblib"
    joblib.dump(best_model, model_path)

    print("\n========== BEST MODEL ==========")
    print("Selected:", best_name)
    print("Saved model:", model_path)
    print("Comparison saved:", results_path)


if __name__ == "__main__":
    train_and_compare()

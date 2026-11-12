from dataset_loader import load_dataset
from config import PROCESSED_DIR


def prepare_dataset():

    _, _, combined = load_dataset()

    # Keep only binary classification labels
    df = combined[
        combined["label"].isin([-1, 1])
    ].copy()

    # Convert labels:
    # -1 = Not lying -> 0
    #  1 = Lying     -> 1

    df["label"] = df["label"].map({
        -1: 0,
        1: 1
    })

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    output_path = PROCESSED_DIR / "binary_dataset.csv"

    df.to_csv(output_path, index=False)

    print("\n========== DATA PREPARATION ==========")
    print("Total records:", len(df))
    print("Not lying:", (df["label"] == 0).sum())
    print("Lying:", (df["label"] == 1).sum())
    print("Saved to:", output_path)


if __name__ == "__main__":
    prepare_dataset()
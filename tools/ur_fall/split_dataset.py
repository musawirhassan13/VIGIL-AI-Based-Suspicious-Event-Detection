import pandas as pd

from sklearn.model_selection import GroupShuffleSplit

from config import PROCESSED_DIR


def split_dataset():

    input_path = PROCESSED_DIR / "binary_dataset.csv"

    if not input_path.exists():
        raise FileNotFoundError(
            "Run prepare_dataset.py first."
        )

    df = pd.read_csv(input_path)

    # Group by complete recording sequence
    groups = df["sequence"]

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=0.20,
        random_state=42
    )

    train_idx, test_idx = next(
        splitter.split(df, groups=groups)
    )

    train_df = df.iloc[train_idx].copy()
    test_df = df.iloc[test_idx].copy()

    train_df.to_csv(
        PROCESSED_DIR / "train.csv",
        index=False
    )

    test_df.to_csv(
        PROCESSED_DIR / "test.csv",
        index=False
    )

    print("\n========== DATASET SPLIT ==========")

    print("Training records:", len(train_df))
    print("Testing records:", len(test_df))

    print("Training sequences:",
          train_df["sequence"].nunique())

    print("Testing sequences:",
          test_df["sequence"].nunique())


if __name__ == "__main__":
    split_dataset()
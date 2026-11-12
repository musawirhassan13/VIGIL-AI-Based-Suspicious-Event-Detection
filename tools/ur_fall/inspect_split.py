import pandas as pd

from config import PROCESSED_DIR


def inspect_split():

    train = pd.read_csv(PROCESSED_DIR / "train.csv")
    test = pd.read_csv(PROCESSED_DIR / "test.csv")

    train_sequences = set(train["sequence"])
    test_sequences = set(test["sequence"])

    overlap = train_sequences.intersection(test_sequences)

    print("\n========== SPLIT VALIDATION ==========")

    print("Train records:", len(train))
    print("Test records:", len(test))

    print("\nTrain sequences:", len(train_sequences))
    print("Test sequences:", len(test_sequences))

    print("\nOverlapping sequences:", overlap)

    print("\n========== CLASS DISTRIBUTION ==========")

    print("TRAIN:")
    print(train["label"].value_counts().sort_index())

    print("\nTEST:")
    print(test["label"].value_counts().sort_index())

    print("\n========== FINAL STATUS ==========")

    if len(overlap) == 0:
        print("PASS: No sequence leakage detected.")
    else:
        print("FAIL: Sequence leakage detected!")


if __name__ == "__main__":
    inspect_split()
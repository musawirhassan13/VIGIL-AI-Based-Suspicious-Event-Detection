from config import COLUMNS, VALID_LABELS
from dataset_loader import load_dataset


def validate_dataset():

    falls, adls, combined = load_dataset()

    print("\n========== UR FALL DATASET ==========")

    print(f"\nFalls records: {len(falls)}")
    print(f"ADL records: {len(adls)}")
    print(f"Total records: {len(combined)}")

    # Check columns
    print("\n========== COLUMN VALIDATION ==========")

    print("Columns:", combined.columns.tolist())

    missing_columns = [
        col for col in COLUMNS
        if col not in combined.columns
    ]

    print("Missing columns:", missing_columns)

    # Check missing values
    print("\n========== MISSING VALUES ==========")

    print(combined[COLUMNS].isnull().sum())

    # Check labels
    print("\n========== LABEL DISTRIBUTION ==========")

    print(combined["label"].value_counts().sort_index())

    invalid_labels = combined[
        ~combined["label"].isin(VALID_LABELS)
    ]

    print("\nInvalid labels:", len(invalid_labels))

    # Sequence distribution
    print("\n========== SEQUENCE DISTRIBUTION ==========")

    print("Fall sequences:", falls["sequence"].nunique())
    print("ADL sequences:", adls["sequence"].nunique())

    # Data types
    print("\n========== DATA TYPES ==========")

    print(combined[COLUMNS].dtypes)

    # Duplicate check
    print("\n========== DUPLICATE CHECK ==========")

    duplicates = combined.duplicated(
        subset=["dataset_type", "sequence", "frame"]
    ).sum()

    print("Duplicate sequence/frame records:", duplicates)

    print("\n========== VALIDATION COMPLETED ==========")


if __name__ == "__main__":
    validate_dataset()
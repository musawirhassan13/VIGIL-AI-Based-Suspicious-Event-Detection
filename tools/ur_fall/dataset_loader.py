import pandas as pd

from config import COLUMNS, FALLS_CSV, ADLS_CSV


def load_csv(file_path):
    """Load one UR Fall CSV file without treating its first row as a header."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset file not found: {file_path}"
        )

    df = pd.read_csv(
        file_path,
        header=None,
        names=COLUMNS
    )

    return df


def load_falls():
    """Load fall sequences."""
    return load_csv(FALLS_CSV)


def load_adls():
    """Load activities of daily living sequences."""
    return load_csv(ADLS_CSV)


def load_dataset():
    """Load both datasets and combine them."""

    falls = load_falls()
    adls = load_adls()

    falls["dataset_type"] = "fall"
    adls["dataset_type"] = "adl"

    combined = pd.concat(
        [falls, adls],
        ignore_index=True
    )

    return falls, adls, combined
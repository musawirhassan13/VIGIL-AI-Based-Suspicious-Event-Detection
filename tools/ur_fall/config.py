from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Dataset directories
DATA_DIR = PROJECT_ROOT / "data" / "ur_fall"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# CSV files
FALLS_CSV = RAW_DIR / "urfall-cam0-falls.csv"
ADLS_CSV = RAW_DIR / "urfall-cam0-adls.csv"

# Dataset columns (UR Fall Dataset documentation)
COLUMNS = [
    "sequence",
    "frame",
    "label",
    "HeightWidthRatio",
    "MajorMinorRatio",
    "BoundingBoxOccupancy",
    "MaxStdXZ",
    "HHmaxRatio",
    "H",
    "D",
    "P40",
]

# Dataset labels
NOT_LYING = -1
LYING = 1
TRANSITION = 0

VALID_LABELS = [NOT_LYING, TRANSITION, LYING]
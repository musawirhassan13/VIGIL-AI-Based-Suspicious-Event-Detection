from dataset_loader import load_dataset


def analyze_sequences():
    falls, adls, _ = load_dataset()

    print("\n========== FALL SEQUENCES ==========")

    for sequence, group in falls.groupby("sequence"):
        print(
            f"{sequence}: "
            f"{len(group)} frames | "
            f"labels: {group['label'].value_counts().to_dict()}"
        )

    print("\n========== ADL SEQUENCES ==========")

    for sequence, group in adls.groupby("sequence"):
        print(
            f"{sequence}: "
            f"{len(group)} frames | "
            f"labels: {group['label'].value_counts().to_dict()}"
        )

    print("\n========== SEQUENCE SUMMARY ==========")

    print("Fall sequences:", falls["sequence"].nunique())
    print("ADL sequences:", adls["sequence"].nunique())

    print(
        "Average fall frames:",
        round(falls.groupby("sequence").size().mean(), 2)
    )

    print(
        "Average ADL frames:",
        round(adls.groupby("sequence").size().mean(), 2)
    )


if __name__ == "__main__":
    analyze_sequences()
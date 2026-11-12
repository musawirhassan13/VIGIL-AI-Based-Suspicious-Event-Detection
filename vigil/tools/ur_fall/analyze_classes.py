from dataset_loader import load_dataset


def analyze_classes():
    falls, adls, combined = load_dataset()

    print("\n========== CLASS ANALYSIS ==========")

    for name, df in [
        ("FALLS", falls),
        ("ADLS", adls),
        ("COMBINED", combined)
    ]:
        print(f"\n--- {name} ---")

        counts = df["label"].value_counts().sort_index()

        for label, count in counts.items():
            percentage = count / len(df) * 100

            print(
                f"Label {label}: {count} "
                f"({percentage:.2f}%)"
            )

    # Binary classification dataset
    binary = combined[combined["label"].isin([-1, 1])]

    print("\n========== BINARY CLASSIFICATION ==========")
    print("Total records:", len(binary))
    print("Not lying (-1):", (binary["label"] == -1).sum())
    print("Lying (1):", (binary["label"] == 1).sum())
    print("Transition frames excluded:", (combined["label"] == 0).sum())


if __name__ == "__main__":
    analyze_classes()
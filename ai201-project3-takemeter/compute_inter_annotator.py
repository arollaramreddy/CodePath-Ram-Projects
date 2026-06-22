import argparse
import csv
from collections import Counter


LABELS = ["analysis", "hot_take", "reaction_or_meme", "event_report"]


def cohen_kappa(my_labels, other_labels):
    total = len(my_labels)
    observed = sum(a == b for a, b in zip(my_labels, other_labels)) / total

    my_counts = Counter(my_labels)
    other_counts = Counter(other_labels)
    expected = 0.0
    for label in LABELS:
        expected += (my_counts[label] / total) * (other_counts[label] / total)

    if expected == 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="inter_annotator_sample.csv",
        help="CSV with text,my_label,other_label columns",
    )
    parser.add_argument(
        "--disagreements",
        default="inter_annotator_disagreements.csv",
        help="Where to write disagreement rows",
    )
    args = parser.parse_args()

    with open(args.input, newline="") as f:
        rows = list(csv.DictReader(f))

    completed = [r for r in rows if r.get("other_label", "").strip()]
    if len(completed) < 30:
        raise SystemExit(
            f"Need at least 30 completed rows. Found {len(completed)} rows with other_label filled in."
        )

    for row in completed:
        for column in ["my_label", "other_label"]:
            label = row[column].strip()
            if label not in LABELS:
                raise SystemExit(f"Invalid {column}: {label}")
            row[column] = label

    my_labels = [r["my_label"] for r in completed]
    other_labels = [r["other_label"] for r in completed]
    agreements = sum(a == b for a, b in zip(my_labels, other_labels))
    percent = agreements / len(completed)
    kappa = cohen_kappa(my_labels, other_labels)

    disagreements = [r for r in completed if r["my_label"] != r["other_label"]]
    with open(args.disagreements, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "my_label", "other_label"])
        writer.writeheader()
        writer.writerows(disagreements)

    print(f"Completed examples: {len(completed)}")
    print(f"Agreements: {agreements}")
    print(f"Percent agreement: {percent:.3f}")
    print(f"Cohen's kappa: {kappa:.3f}")
    print(f"Disagreements written to: {args.disagreements}")


if __name__ == "__main__":
    main()

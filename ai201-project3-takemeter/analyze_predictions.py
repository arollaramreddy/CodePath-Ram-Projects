import argparse
import csv
from collections import Counter


LABELS = ["analysis", "hot_take", "reaction_or_meme", "event_report"]


def parse_confidence(value):
    text = str(value).strip().replace("%", "")
    confidence = float(text)
    if confidence > 1:
        confidence = confidence / 100
    return confidence


def bin_name(confidence):
    if confidence < 0.5:
        return "0.00-0.49"
    if confidence < 0.7:
        return "0.50-0.69"
    if confidence < 0.9:
        return "0.70-0.89"
    return "0.90-1.00"


def shorten(text, limit=120):
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def markdown_table(headers, rows):
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="finetuned_predictions.csv",
        help="CSV with text,true_label,predicted_label,confidence columns",
    )
    parser.add_argument(
        "--output",
        default="stretch_analysis.md",
        help="Markdown report to write",
    )
    args = parser.parse_args()

    with open(args.input, newline="") as f:
        rows = list(csv.DictReader(f))

    required = {"text", "true_label", "predicted_label", "confidence"}
    missing = required - set(rows[0].keys())
    if missing:
        raise SystemExit(f"Missing required columns: {', '.join(sorted(missing))}")

    cleaned = []
    for row in rows:
        true_label = row["true_label"].strip()
        predicted_label = row["predicted_label"].strip()
        if true_label not in LABELS:
            raise SystemExit(f"Invalid true_label: {true_label}")
        if predicted_label not in LABELS:
            raise SystemExit(f"Invalid predicted_label: {predicted_label}")

        confidence = parse_confidence(row["confidence"])
        cleaned.append(
            {
                "text": row["text"],
                "true_label": true_label,
                "predicted_label": predicted_label,
                "confidence": confidence,
                "correct": true_label == predicted_label,
            }
        )

    total = len(cleaned)
    correct = sum(r["correct"] for r in cleaned)
    accuracy = correct / total

    bins = {}
    for row in cleaned:
        key = bin_name(row["confidence"])
        bins.setdefault(key, []).append(row)

    bin_rows = []
    for key in ["0.00-0.49", "0.50-0.69", "0.70-0.89", "0.90-1.00"]:
        group = bins.get(key, [])
        if not group:
            bin_rows.append([key, 0, "-", "-"])
            continue
        group_acc = sum(r["correct"] for r in group) / len(group)
        avg_conf = sum(r["confidence"] for r in group) / len(group)
        bin_rows.append([key, len(group), f"{avg_conf:.3f}", f"{group_acc:.3f}"])

    wrong = [r for r in cleaned if not r["correct"]]
    pair_counts = Counter((r["true_label"], r["predicted_label"]) for r in wrong)
    pair_rows = [
        [true_label, predicted_label, count]
        for (true_label, predicted_label), count in pair_counts.most_common()
    ]

    prediction_counts = Counter(r["predicted_label"] for r in cleaned)
    prediction_rows = [[label, prediction_counts[label]] for label in LABELS]

    wrong_rows = [
        [
            shorten(r["text"]),
            r["true_label"],
            r["predicted_label"],
            f"{r['confidence']:.3f}",
        ]
        for r in wrong[:10]
    ]

    report = []
    report.append("# Stretch Analysis")
    report.append("")
    report.append(f"Total examples: {total}")
    report.append(f"Accuracy: {accuracy:.3f}")
    report.append("")
    report.append("## Confidence Calibration")
    report.append("")
    report.append(
        markdown_table(
            ["Confidence bin", "Count", "Average confidence", "Accuracy"],
            bin_rows,
        )
    )
    report.append("")
    report.append("## Prediction Counts")
    report.append("")
    report.append(markdown_table(["Predicted label", "Count"], prediction_rows))
    report.append("")
    report.append("## Error Pattern Counts")
    report.append("")
    report.append(markdown_table(["True label", "Predicted label", "Count"], pair_rows))
    report.append("")
    report.append("## Wrong Prediction Examples")
    report.append("")
    report.append(
        markdown_table(
            ["Text", "True label", "Predicted label", "Confidence"],
            wrong_rows,
        )
    )

    with open(args.output, "w", newline="") as f:
        f.write("\n".join(report) + "\n")

    print(f"Wrote {args.output}")
    print(f"Accuracy: {accuracy:.3f}")
    print("Top error pairs:")
    for (true_label, predicted_label), count in pair_counts.most_common(5):
        print(f"  {true_label} -> {predicted_label}: {count}")


if __name__ == "__main__":
    main()

# Run this in Colab after the fine-tuned model has been evaluated.
# It writes the file needed by analyze_predictions.py:
# finetuned_predictions.csv with text,true_label,predicted_label,confidence.

import numpy as np
import pandas as pd
import torch


id_to_label = {v: k for k, v in LABEL_MAP.items()}

model_to_use = trainer.model if "trainer" in globals() else model
model_to_use.eval()

texts = test_df["text"].tolist()

if "label" in test_df.columns:
    true_labels = test_df["label"].astype(str).tolist()
elif "labels" in test_df.columns:
    true_labels = [id_to_label[int(label_id)] for label_id in test_df["labels"].tolist()]
else:
    raise ValueError("Could not find label or labels column in test_df")

device = next(model_to_use.parameters()).device
encoded = tokenizer(
    texts,
    truncation=True,
    padding=True,
    max_length=256,
    return_tensors="pt",
)
encoded = {key: value.to(device) for key, value in encoded.items()}

with torch.no_grad():
    logits = model_to_use(**encoded).logits
    probs = torch.softmax(logits, dim=-1).cpu().numpy()

pred_ids = np.argmax(probs, axis=1)
predicted_labels = [id_to_label[int(pred_id)] for pred_id in pred_ids]
confidences = probs.max(axis=1)

predictions_df = pd.DataFrame(
    {
        "text": texts,
        "true_label": true_labels,
        "predicted_label": predicted_labels,
        "confidence": confidences,
    }
)

predictions_df.to_csv("finetuned_predictions.csv", index=False)
print("Saved finetuned_predictions.csv")

predictions_df["correct"] = (
    predictions_df["true_label"] == predictions_df["predicted_label"]
)
predictions_df["confidence_bin"] = pd.cut(
    predictions_df["confidence"],
    bins=[0.0, 0.5, 0.7, 0.9, 1.0],
    labels=["0.00-0.50", "0.50-0.70", "0.70-0.90", "0.90-1.00"],
    include_lowest=True,
)

calibration = (
    predictions_df.groupby("confidence_bin", observed=False)
    .agg(
        count=("correct", "size"),
        average_confidence=("confidence", "mean"),
        accuracy=("correct", "mean"),
    )
    .reset_index()
)

print("\nConfidence calibration:")
print(calibration.to_string(index=False))

predictions_df.head()

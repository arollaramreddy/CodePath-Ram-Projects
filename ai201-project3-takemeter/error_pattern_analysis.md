# Error Pattern Analysis

The main error pattern is that the fine-tuned model never predicted `hot_take` on the test set.

From the confusion matrix:

| True label | Predicted analysis | Predicted hot_take | Predicted reaction_or_meme | Predicted event_report |
| --- | ---: | ---: | ---: | ---: |
| analysis | 5 | 0 | 0 | 5 |
| hot_take | 4 | 0 | 1 | 5 |
| reaction_or_meme | 3 | 0 | 4 | 3 |
| event_report | 1 | 0 | 3 | 9 |

The biggest issue is `hot_take`. There were 10 true `hot_take` examples, but the model labeled 4 as `analysis`, 1 as `reaction_or_meme`, and 5 as `event_report`. It predicted `hot_take` zero times total.

My guess is that the model learned surface cues more than the real label rule. If a post had stats or a player comparison, it often looked like `analysis`. If it looked like a news headline or question, it often got pushed toward `event_report`. The model did not learn that a strong unsupported claim can still be a `hot_take` even if it mentions a statistic, a player, or a real event.

This also explains why the fine-tuned model did worse than the Groq baseline. The baseline had a broader language understanding of what a "take" sounds like, while the fine-tuned DistilBERT model had a small dataset and may have overfit to wording patterns.

To fix this, I would add more clear `hot_take` examples and more borderline examples where `hot_take` looks similar to `analysis`. I would also double-check the training split to make sure `hot_take` examples are represented well in the train and validation sets.

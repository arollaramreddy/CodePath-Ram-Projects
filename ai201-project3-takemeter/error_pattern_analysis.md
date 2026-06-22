# Error Pattern Analysis

Main pattern: the fine-tuned model never predicted `hot_take`.

| True label | Predicted analysis | Predicted hot_take | Predicted reaction_or_meme | Predicted event_report |
| --- | ---: | ---: | ---: | ---: |
| analysis | 5 | 0 | 0 | 5 |
| hot_take | 4 | 0 | 1 | 5 |
| reaction_or_meme | 3 | 0 | 4 | 3 |
| event_report | 1 | 0 | 3 | 9 |

There were 10 real `hot_take` examples. The model labeled 4 as `analysis`, 1 as `reaction_or_meme`, and 5 as `event_report`.

The model seemed to follow surface clues. Stats made posts look like `analysis`. Headline style made posts look like `event_report`. It did not learn that a strong unsupported claim is still a `hot_take`.

To fix this, I would add more clear `hot_take` examples and more borderline `analysis` vs `hot_take` examples.

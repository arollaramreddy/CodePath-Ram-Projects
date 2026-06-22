# TakeMeter

TakeMeter is a text classifier for r/nba posts and comments. The goal is to classify a post into one of four discourse labels: `analysis`, `hot_take`, `event_report`, or `reaction_or_meme`.

## Community

I chose r/nba because the community has a mix of news, highlights, jokes, quick reactions, and longer basketball arguments. This makes it a good fit for classification because users already care about the difference between real analysis and just a hot take.

## Labels

`analysis`: The post/comment is making a basketball argument with support, like stats, history, comparison, strategy, or context.

Examples:
- "ESPN does a great game breakdown analysis of SGA foul hunting in WCF Game 6 and contrasts it to Spurs guards playing through contact"
- "In the 90's the #1 seed from each Conference met in the NBA Finals 4 times. Since 2000, this has happened only 3 times."

`hot_take`: The post/comment makes a strong claim, complaint, prediction, or blame statement without really proving it.

Examples:
- "Trae Young is Fools Gold. He has the 3rd worst defensive metrics in the last 10 years and is not the shooter you think he is."
- "Are The Portland TrailBlazers Going Into The Draft on Tuesday With No Head Coach? Are the Blazers going into the draft on Tuesday with no head coach? When's the last time a team has done that, and did it work out for them? This is a bit wild, no?"

`event_report`: The post/comment is mostly reporting something that happened, like news, a quote, a stat line, a signing, an injury, or a correction.

Examples:
- "[Charania] Free agent guard Jordan Goodwin intends to sign a three-year, $19 million deal to return to the Phoenix Suns, with a player option in the third season, sources tell ESPN."
- "The Blazers don't have any picks in this draft, not a 1st or 2nd."

`reaction_or_meme`: The post/comment is mostly a joke, hype, quick reaction, highlight reaction, or off-season type comment.

Examples:
- "When Russell Westbrook Hit a 40 Foot Game Winner The Same Night He Broke The Triple Double Record - 50 Points 16 Rebounds 10 Assists"
- "Pop hit Kerr with the NBA version of 'you up?' a week later"

## Dataset

The dataset is in `nba_labeled_posts.csv`. It has 282 examples and two columns: `text` and `label`.

Label distribution:

| Label | Count |
| --- | ---: |
| analysis | 68 |
| hot_take | 67 |
| event_report | 82 |
| reaction_or_meme | 65 |

I collected examples from public r/nba posts and comments. I removed very short rows under 12 words because many were only titles or quick one-line reactions.

## Difficult Labeling Examples

| Text | Decision | Why |
| --- | --- | --- |
| "Doesnt mean much without factoring in shot hardness. Looking at xFG% in the playoffs gives a better idea of who the best shooters were. Not sure how to filter by clutch, but it's mostly noise and low sample sizes anyway. A FG in the clutch when 3-0 up in R1 is a lot less clutch than a FG at the beginning of game 7 of the finals." | `analysis` | It pushes back on a stat ranking, but it gives a reason: shot quality, sample size, and game context. |
| "[Highlight] Mitch Johnson asks for a coach's challenge right in front of the referee James Capers, but he doesn't call it. Instead, he receives a technical foul. The Spurs would have won the challenge, as the refs gave the ball to the Thunder after it went out of bounds off Chet Holmgren." | `reaction_or_meme` | It could become a ref argument, but the post itself is mainly a highlight/clip reaction. |
| "Are The Portland TrailBlazers Going Into The Draft on Tuesday With No Head Coach? Are the Blazers going into the draft on Tuesday with no head coach? When's the last time a team has done that, and did it work out for them? This is a bit wild, no?" | `hot_take` | It is based on a real situation, but the post frames it dramatically and does not really prove the concern. |

## Training

The fine-tuned model used `distilbert-base-uncased` in Google Colab. The notebook split the CSV into train, validation, and test sets, then trained on the training set and evaluated on the test set.

I trained for 3 epochs with a learning rate of `2e-5`, train batch size `16`, eval batch size `32`, weight decay `0.01`, and max token length `256`. I used 3 epochs because the dataset is small, so training for too long could overfit. The result showed that I should revisit this decision later, because the model predicted `hot_take` zero times.

## Baseline

The baseline used Groq with `llama-3.3-70b-versatile`. I gave the model the label definitions and one example per label, then asked it to output only one valid label.

The baseline prompt told the model that it was classifying r/nba posts/comments and defined the four labels. It also said: "Respond with ONLY the label name. Do not explain your reasoning." The valid labels were `analysis`, `hot_take`, `event_report`, and `reaction_or_meme`.

Baseline accuracy on the test set: `0.535`.

Baseline per-class metrics:

| Label | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| analysis | 0.55 | 0.60 | 0.57 | 10 |
| hot_take | 0.57 | 0.40 | 0.47 | 10 |
| reaction_or_meme | 0.44 | 0.70 | 0.54 | 10 |
| event_report | 0.67 | 0.46 | 0.55 | 13 |

## Fine-Tuned Evaluation

Fine-tuned DistilBERT accuracy on the test set: `0.419`.

Fine-tuned per-class metrics from the confusion matrix:

| Label | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| analysis | 0.38 | 0.50 | 0.43 | 10 |
| hot_take | 0.00 | 0.00 | 0.00 | 10 |
| reaction_or_meme | 0.50 | 0.40 | 0.44 | 10 |
| event_report | 0.41 | 0.69 | 0.51 | 13 |

Fine-tuned confusion matrix:

| True label | Predicted analysis | Predicted hot_take | Predicted reaction_or_meme | Predicted event_report |
| --- | ---: | ---: | ---: | ---: |
| analysis | 5 | 0 | 0 | 5 |
| hot_take | 4 | 0 | 1 | 5 |
| reaction_or_meme | 3 | 0 | 4 | 3 |
| event_report | 1 | 0 | 3 | 9 |

The fine-tuned model performed worse than the baseline by `0.116`. The biggest issue is that the model predicted `hot_take` zero times.

## Wrong Predictions

These are specific wrong predictions printed by the notebook from the fine-tuned model.

| Text | True label | Predicted label | Confidence | My analysis |
| --- | --- | --- | ---: | --- |
| "Out of the deep respect and admiration that Kevin Pritchard had for Paul Allen, he managed to pull off the heist of the century, landing the key pillars of a certain future championship roster in Ryan..." | `hot_take` | `event_report` | 0.28 | The model probably saw names and roster language and treated it like a report. The "heist of the century" framing is why I labeled it as a hot take. |
| "Fox in the same tier as Tobias Harris. Veteran players who scammed their teams into giving them more money than they deserve" | `hot_take` | `reaction_or_meme` | 0.26 | The insult/joke wording made the model read it like a meme, but it is mainly making an unsupported claim about players being overpaid. |
| "In the 90's the #1 seed from each Conference met in the NBA Finals 4 times. Since 2000, this has happened only 3 times." | `analysis` | `event_report` | 0.27 | This one is close because it is written like a fact. I labeled it `analysis` because it uses historical comparison to make a basketball point, but the model saw it as just reporting a stat. |
| "The only way I would tolerate the Aspiration scandal ending: NBA Draft night, Adam Silver steps over a sobbing Darryn Peterson and announces the Clippers would have selected with the fifth pick before..." | `reaction_or_meme` | `analysis` | 0.27 | The model likely reacted to serious terms like scandal, NBA Draft, and Adam Silver. The actual post is an exaggerated joke scenario, so it should be `reaction_or_meme`. |

## Error Pattern

The strongest error pattern is that the fine-tuned model avoided `hot_take`. All 10 true `hot_take` examples were classified as something else: 4 as `analysis`, 1 as `reaction_or_meme`, and 5 as `event_report`.

My guess is that the model learned surface cues instead of the real boundary. If a post mentioned a stat or player comparison, it could look like `analysis`. If it looked like a headline or question, it could get pushed toward `event_report`. The model did not learn that a strong unsupported claim can still be a `hot_take`.

## Stretch Features

### Inter-Annotator Reliability

I used `inter_annotator_sample.csv` for a second-labeling check. Another person labeled 31 completed examples using the same four labels.

Results:

- Completed examples: 31
- Agreements: 25
- Percent agreement: 0.806
- Cohen's kappa: 0.742

The disagreements are saved in `inter_annotator_disagreements.csv`. There were 6 disagreements. The most common disagreement was `event_report` vs `hot_take`, which happened twice. That makes sense because some r/nba quote/news posts also contain strong opinion wording, so one annotator may focus on the format while the other focuses on the take.

Other disagreements included `analysis` vs `event_report`, `hot_take` vs `reaction_or_meme`, and `reaction_or_meme` vs `analysis`. These match the hardest label boundaries in the project: posts can look like facts, jokes, or reactions while still making an argument.

### Confidence Calibration

To analyze confidence calibration, first export test-set predictions from Colab using `export_predictions_colab.py`. That should create `finetuned_predictions.csv` with:

```text
text,true_label,predicted_label,confidence
```

Then run:

```bash
python3 analyze_predictions.py
```

This writes `stretch_analysis.md`, including confidence bins and accuracy in each bin.

### Error Pattern Analysis

The file `error_pattern_analysis.md` documents the main systematic error: the fine-tuned model never predicted `hot_take`.

## Reflection

The model captured some easy surface patterns, especially posts that looked like event reports. It did not capture the main thing I wanted, which was the difference between a real basketball argument and a hot take.

The biggest gap is that `hot_take` is not just a topic label. It depends on whether the post supports its claim. DistilBERT with this small dataset did not learn that boundary well.

## Spec Reflection

The spec helped because it forced me to define labels before training. That made it easier to notice that `analysis` vs `hot_take` was the hardest boundary.

The implementation diverged from the original hope because fine-tuning did not beat the baseline. Instead of hiding that, I used the confusion matrix to explain what went wrong.

## AI Usage

I used AI for understanding the accuracy results and the model predictions.

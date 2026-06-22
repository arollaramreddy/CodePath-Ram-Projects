# TakeMeter

This project classifies r/nba posts/comments into four labels: `analysis`, `hot_take`, `event_report`, and `reaction_or_meme`.

## Community

I used r/nba because it has news, highlights, jokes, reactions, and longer basketball arguments. That makes it useful for this task because not every post is trying to do the same thing.

## Labels

`analysis`: A post/comment that makes a basketball argument using stats, history, comparison, strategy, or context.

Examples:
- "ESPN does a great game breakdown analysis of SGA foul hunting in WCF Game 6 and contrasts it to Spurs guards playing through contact"
- "In the 90's the #1 seed from each Conference met in the NBA Finals 4 times. Since 2000, this has happened only 3 times."

`hot_take`: A strong claim, complaint, prediction, or blame statement without enough support.

Examples:
- "Trae Young is Fools Gold. He has the 3rd worst defensive metrics in the last 10 years and is not the shooter you think he is."
- "Are The Portland TrailBlazers Going Into The Draft on Tuesday With No Head Coach? Are the Blazers going into the draft on Tuesday with no head coach? When's the last time a team has done that, and did it work out for them? This is a bit wild, no?"

`event_report`: A post/comment mostly reporting news, a quote, a stat line, a signing, an injury, or a correction.

Examples:
- "[Charania] Free agent guard Jordan Goodwin intends to sign a three-year, $19 million deal to return to the Phoenix Suns, with a player option in the third season, sources tell ESPN."
- "The Blazers don't have any picks in this draft, not a 1st or 2nd."

`reaction_or_meme`: A joke, hype post, quick reaction, highlight reaction, or off-season style comment.

Examples:
- "When Russell Westbrook Hit a 40 Foot Game Winner The Same Night He Broke The Triple Double Record - 50 Points 16 Rebounds 10 Assists"
- "Pop hit Kerr with the NBA version of 'you up?' a week later"

## Dataset

File: `nba_labeled_posts.csv`

282 examples, two columns: `text`, `label`.

| Label | Count |
| --- | ---: |
| analysis | 68 |
| hot_take | 67 |
| event_report | 82 |
| reaction_or_meme | 65 |

I collected public r/nba posts/comments. I removed rows under 12 words because many were too short to be useful.

## Hard Examples

| Text | Label | Why |
| --- | --- | --- |
| "Doesnt mean much without factoring in shot hardness. Looking at xFG% in the playoffs gives a better idea of who the best shooters were. Not sure how to filter by clutch, but it's mostly noise and low sample sizes anyway. A FG in the clutch when 3-0 up in R1 is a lot less clutch than a FG at the beginning of game 7 of the finals." | `analysis` | It explains why the stat is weak. |
| "[Highlight] Mitch Johnson asks for a coach's challenge right in front of the referee James Capers, but he doesn't call it. Instead, he receives a technical foul. The Spurs would have won the challenge, as the refs gave the ball to the Thunder after it went out of bounds off Chet Holmgren." | `reaction_or_meme` | It is mainly a clip/reaction post. |
| "Are The Portland TrailBlazers Going Into The Draft on Tuesday With No Head Coach? Are the Blazers going into the draft on Tuesday with no head coach? When's the last time a team has done that, and did it work out for them? This is a bit wild, no?" | `hot_take` | It is dramatic and not really supported. |

## Training

Base model: `distilbert-base-uncased`

Platform: Google Colab with T4 GPU.

Training setup:
- 3 epochs
- learning rate `2e-5`
- train batch size `16`
- eval batch size `32`
- max length `256`

I used 3 epochs because the dataset is small. More epochs might overfit, but after seeing the results I would try again because the model never predicted `hot_take`.

## Baseline

Baseline model: Groq `llama-3.3-70b-versatile`

The prompt gave the four label definitions and one example per label. It told the model to output only the label name.

Baseline accuracy: `0.535`

| Label | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| analysis | 0.55 | 0.60 | 0.57 | 10 |
| hot_take | 0.57 | 0.40 | 0.47 | 10 |
| reaction_or_meme | 0.44 | 0.70 | 0.54 | 10 |
| event_report | 0.67 | 0.46 | 0.55 | 13 |

## Fine-Tuned Results

Fine-tuned accuracy: `0.419`

| Label | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| analysis | 0.38 | 0.50 | 0.43 | 10 |
| hot_take | 0.00 | 0.00 | 0.00 | 10 |
| reaction_or_meme | 0.50 | 0.40 | 0.44 | 10 |
| event_report | 0.41 | 0.69 | 0.51 | 13 |

Confusion matrix:

| True label | Predicted analysis | Predicted hot_take | Predicted reaction_or_meme | Predicted event_report |
| --- | ---: | ---: | ---: | ---: |
| analysis | 5 | 0 | 0 | 5 |
| hot_take | 4 | 0 | 1 | 5 |
| reaction_or_meme | 3 | 0 | 4 | 3 |
| event_report | 1 | 0 | 3 | 9 |

The fine-tuned model did worse than the baseline by `0.116`.

## Wrong Predictions

| Text | True | Predicted | Confidence | Note |
| --- | --- | --- | ---: | --- |
| "Out of the deep respect and admiration that Kevin Pritchard had for Paul Allen, he managed to pull off the heist of the century, landing the key pillars of a certain future championship roster in Ryan..." | `hot_take` | `event_report` | 0.28 | The model read names/roster wording as news. |
| "Fox in the same tier as Tobias Harris. Veteran players who scammed their teams into giving them more money than they deserve" | `hot_take` | `reaction_or_meme` | 0.26 | It sounds like a joke, but it is mostly an unsupported claim. |
| "In the 90's the #1 seed from each Conference met in the NBA Finals 4 times. Since 2000, this has happened only 3 times." | `analysis` | `event_report` | 0.27 | It looks like a fact, but I meant it as historical comparison. |
| "The only way I would tolerate the Aspiration scandal ending: NBA Draft night, Adam Silver steps over a sobbing Darryn Peterson and announces the Clippers would have selected with the fifth pick before..." | `reaction_or_meme` | `analysis` | 0.27 | The model missed that it was exaggerated/joking. |

## Main Error Pattern

The model predicted `hot_take` zero times. All 10 real `hot_take` test examples went to another label.

This means it learned surface patterns more than my actual rule. If a post looked like news, it often became `event_report`. If it had stats, it could become `analysis`. It did not learn that a post can mention real NBA details and still be a hot take.

## Stretch

Inter-annotator reliability:
- Completed examples: 31
- Agreements: 25
- Percent agreement: 0.806
- Cohen's kappa: 0.742

Main disagreement: `event_report` vs `hot_take`. Some posts looked like news/quotes but also had opinion framing.

Error pattern analysis is in `error_pattern_analysis.md`.

Confidence calibration was not finished because I did not export the full prediction-confidence CSV from Colab.

## Reflection

The model learned some easy news-style patterns, but it did not learn the line between `analysis` and `hot_take`. That was the main thing I wanted it to learn.

## Spec Reflection

The spec helped me define labels before training. The project changed later because fine-tuning did not beat the baseline, so my final analysis focused more on failure patterns.

## AI Usage

I used AI for understanding the accuracy results and the model predictions.

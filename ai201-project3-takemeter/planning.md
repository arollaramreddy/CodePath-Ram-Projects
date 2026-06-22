# TakeMeter Planning

## Community

I am using r/nba. I picked it because there are many public posts and the writing style changes a lot. Some posts are news, some are highlights, some are jokes, and some are real basketball arguments.

I am labeling post/comment text.

## Labels

`analysis`: Makes a basketball argument with support like stats, history, comparison, strategy, or context.

Examples:
- "ESPN does a great game breakdown analysis of SGA foul hunting in WCF Game 6 and contrasts it to Spurs guards playing through contact"
- "In the 90's the #1 seed from each Conference met in the NBA Finals 4 times. Since 2000, this has happened only 3 times."

`hot_take`: Makes a strong claim, complaint, prediction, or blame statement without enough proof.

Examples:
- "Trae Young is Fools Gold. He has the 3rd worst defensive metrics in the last 10 years and is not the shooter you think he is."
- "Are The Portland TrailBlazers Going Into The Draft on Tuesday With No Head Coach? Are the Blazers going into the draft on Tuesday with no head coach? When's the last time a team has done that, and did it work out for them? This is a bit wild, no?"

`event_report`: Mostly reports news, a quote, stat line, signing, injury, or correction.

Examples:
- "[Charania] Free agent guard Jordan Goodwin intends to sign a three-year, $19 million deal to return to the Phoenix Suns, with a player option in the third season, sources tell ESPN."
- "The Blazers don't have any picks in this draft, not a 1st or 2nd."

`reaction_or_meme`: Mostly a joke, hype post, quick reaction, highlight reaction, or off-season comment.

Examples:
- "When Russell Westbrook Hit a 40 Foot Game Winner The Same Night He Broke The Triple Double Record - 50 Points 16 Rebounds 10 Assists"
- "Pop hit Kerr with the NBA version of 'you up?' a week later"

## Label Rules

- News/quotes/facts: `event_report`
- Clips/jokes/reactions: `reaction_or_meme`
- Supported basketball point: `analysis`
- Strong unsupported claim: `hot_take`

Hardest edge case: `analysis` vs `hot_take`. A post having one stat does not automatically make it analysis. If the stat is just used to dunk on a player, I label it `hot_take`. If the post explains the stat or gives context, I label it `analysis`.

## Data Plan

File: `nba_labeled_posts.csv`

Columns:
- `text`
- `label`

Current counts:
- Total: 282
- `analysis`: 68
- `hot_take`: 67
- `event_report`: 82
- `reaction_or_meme`: 65

No label is over 70%. The biggest label is `event_report` at about 29.1%.

Sources were public r/nba posts/comments, including draft discussion, clutch FG thread, roster visualization thread, Pop/Kerr thread, Blazers draft thread, Aspiration scandal thread, and rookie discussion thread.

I removed rows under 12 words because they were often too short.

## Hard Cases

- "Doesnt mean much without factoring in shot hardness. Looking at xFG% in the playoffs gives a better idea of who the best shooters were. Not sure how to filter by clutch, but it's mostly noise and low sample sizes anyway. A FG in the clutch when 3-0 up in R1 is a lot less clutch than a FG at the beginning of game 7 of the finals."  
  Decision: `analysis`, because it explains why the stat is weak.

- "[Highlight] Mitch Johnson asks for a coach's challenge right in front of the referee James Capers, but he doesn't call it. Instead, he receives a technical foul. The Spurs would have won the challenge, as the refs gave the ball to the Thunder after it went out of bounds off Chet Holmgren."  
  Decision: `reaction_or_meme`, because it is mainly a highlight/reaction post.

- "Are The Portland TrailBlazers Going Into The Draft on Tuesday With No Head Coach? Are the Blazers going into the draft on Tuesday with no head coach? When's the last time a team has done that, and did it work out for them? This is a bit wild, no?"  
  Decision: `hot_take`, because it is dramatic and not really supported.

## Evaluation

I will use accuracy, per-class precision/recall/F1, macro-F1, and a confusion matrix.

Accuracy alone is not enough because one label could do badly while the total score still looks okay. Macro-F1 matters because all four labels matter.

## Success

Good enough for this project: at least 70% macro-F1 and better than the baseline.

Also, every class should have at least 0.55 F1. If `analysis` or `hot_take` fails badly, the model is not useful.

## AI Tool Plan

I can use AI to check confusing examples, understand wrong predictions, and think through evaluation results.

## Stretch Plan

Inter-annotator reliability: another person labels 30+ examples, then I compare agreement.

Confidence calibration: check if higher confidence predictions are more accurate.

Error pattern analysis: group wrong predictions by label pair.

I am not doing the deployed interface stretch.

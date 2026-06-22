# TakeMeter Planning

## Community

I am using r/nba for this project. I picked it because there are a lot of public posts and comments, and people do not all post in the same style. Some posts are just news, some are highlights, some are jokes, and some are actual basketball arguments with stats or context.

This is a good community for classification because r/nba users already argue about the difference between a real take and just a reaction. A game highlight, a Shams/Charania quote, a long stats post, and a random "this player is washed" comment are all common there, but they are doing very different things.

The thing I am labeling is the text of a post or comment. For posts, I am mostly using the title and visible body text.

## Labels

I am using four labels.

### `analysis`

This means the post/comment is making a basketball argument with some kind of support, like stats, history, comparison, strategy, or context.

Examples:

- "ESPN does a great game breakdown analysis of SGA foul hunting in WCF Game 6 and contrasts it to Spurs guards playing through contact"
- "In the 90's the #1 seed from each Conference met in the NBA Finals 4 times. Since 2000, this has happened only 3 times."

### `hot_take`

This means the post/comment makes a strong claim, complaint, prediction, or blame statement without really proving it.

Examples:

- "Trae Young is Fools Gold. He has the 3rd worst defensive metrics in the last 10 years and is not the shooter you think he is."
- "Are The Portland TrailBlazers Going Into The Draft on Tuesday With No Head Coach? Are the Blazers going into the draft on Tuesday with no head coach? When's the last time a team has done that, and did it work out for them? This is a bit wild, no?"

### `event_report`

This means the post/comment is mostly reporting something that happened, like news, a quote, a stat line, a signing, an injury, or a correction.

Examples:

- "[Charania] Free agent guard Jordan Goodwin intends to sign a three-year, $19 million deal to return to the Phoenix Suns, with a player option in the third season, sources tell ESPN."
- "The Blazers don't have any picks in this draft, not a 1st or 2nd."

### `reaction_or_meme`

This means the post/comment is mostly a joke, hype, quick reaction, highlight reaction, or off-season type comment.

Examples:

- "When Russell Westbrook Hit a 40 Foot Game Winner The Same Night He Broke The Triple Double Record - 50 Points 16 Rebounds 10 Assists"
- "Pop hit Kerr with the NBA version of 'you up?' a week later"

## Label Rules

When I label an example, I am trying to ask what the post is mainly doing.

- If it is just giving news or a quote, I label it `event_report`.
- If it is a clip, joke, meme, hype, or quick reaction, I label it `reaction_or_meme`.
- If it makes a point and gives real reasoning or context, I label it `analysis`.
- If it makes a strong claim but mostly just asserts it, I label it `hot_take`.

The hardest boundary is between `analysis` and `hot_take`. A lot of r/nba comments include one stat, but that does not automatically make them analysis. If the stat is just being used to dunk on a player or ref, I usually call it `hot_take`. If the comment explains why the stat matters or compares it to other context, I call it `analysis`.

## Data Collection

The dataset is saved in `nba_labeled_posts.csv`. It is one CSV file, not pre-split. The columns are:

- `text`
- `label`

Current count:

- Total examples: 282
- `event_report`: 82
- `hot_take`: 67
- `reaction_or_meme`: 65
- `analysis`: 68

No label is over 70% of the dataset. The biggest label is `event_report`, but it is only about 29.1% of the data.

I collected from public r/nba posts/comments. Some examples came from pasted public thread text, including:

- 2026 NBA Draft discussion
- Weekly Friday Self-Promotion thread
- clutch FG% thread
- "which NBA player would you be" off-season thread
- roster-tree visualization thread
- Steve Kerr / Gregg Popovich ESPN thread
- Trail Blazers no-head-coach draft thread
- Aspiration scandal thread
- "who was your rookie" thread

I removed very short rows under 12 words because a lot of them were just titles or quick one-line reactions.

If I collect more data later, I should still try to keep the labels close to balanced. Good sources for longer examples would be OC/stat posts, roster construction posts, player comparison posts, and longer discussion comments.

## Hard Cases

These are examples where I had to think about the label.

- "Doesnt mean much without factoring in shot hardness. Looking at xFG% in the playoffs gives a better idea of who the best shooters were. Not sure how to filter by clutch, but it's mostly noise and low sample sizes anyway. A FG in the clutch when 3-0 up in R1 is a lot less clutch than a FG at the beginning of game 7 of the finals."  
  This was about clutch FG%. It disagreed with a stat ranking, so it could sound like a hot take. I labeled it `analysis` because it explained xFG%, sample size, and game context.

- "[Highlight] Mitch Johnson asks for a coach's challenge right in front of the referee James Capers, but he doesn't call it. Instead, he receives a technical foul. The Spurs would have won the challenge, as the refs gave the ball to the Thunder after it went out of bounds off Chet Holmgren."  
  This could become a ref complaint, but the post itself is mainly a clip for people to react to. I labeled it `reaction_or_meme`.

- "Are The Portland TrailBlazers Going Into The Draft on Tuesday With No Head Coach? Are the Blazers going into the draft on Tuesday with no head coach? When's the last time a team has done that, and did it work out for them? This is a bit wild, no?"  
  This was based on something real, but the concern was framed dramatically and missed that Portland had no picks. I labeled it `hot_take`.

- "If some corruption is allowed openly then you just have to assume a lot more has been happening for ages quietly. The cap is hugely significant in basketball and this is blatant manipulation and exploitation of it. You have to end that instantly with big penalties. Instead it's been a whole season and nothing."  
  This could sound like a conspiracy take, but I labeled it `analysis` because the comment explains why salary cap enforcement matters and connects it to league incentives.

- "Blake was the reason I started following basketball seriously, which kind of sucked since he got hurt in his first year and the Clippers traded what would become a first overall pick for Mo Williams."  
  This was mostly personal memory, but it also mentioned Griffin's injury and the Clippers trade that became a first overall pick. I labeled it `analysis`.

## Evaluation Plan

I will report accuracy, but I do not want to rely only on accuracy. Since the labels are not perfectly equal, accuracy could hide the model doing badly on one class.

I will also use:

- per-class precision
- per-class recall
- per-class F1
- macro-F1
- confusion matrix

Macro-F1 matters because I care about all four labels, not just the most common one. The confusion matrix matters because I expect the main mistakes to be `analysis` vs `hot_take`, and `event_report` vs quote-based `hot_take`.

## Definition of Success

For this project, I would call the model good enough if it gets at least 70% macro-F1 on the test set and beats the baseline prompt on the same test set.

I also want every class to have at least 0.55 F1. If the model completely misses `analysis` or `hot_take`, then it is not actually useful even if the overall accuracy looks okay.

For a real r/nba tool, I would want closer to 75% macro-F1 or better, and I would want to show confidence scores instead of pretending every prediction is certain.

## AI Tool Plan

For label stress testing, I can ask AI to generate borderline r/nba examples between `analysis` and `hot_take`, and between `event_report` and `reaction_or_meme`. If I cannot label those examples consistently, then my label rules need to be fixed.

For annotation, I used AI/tooling to help make a first-pass CSV from public r/nba text. I still need to manually review the labels before treating the dataset as final. I will disclose that in the AI usage section.

For failure analysis, after I evaluate the model I can give the wrong predictions to an AI tool and ask it to look for patterns. I will still check the pattern myself before writing it up, because the AI might overstate things.

## Stretch Feature Plan

I want to try all four stretch features, but two of them need extra data outside the current CSV.

For inter-annotator reliability, I will give another person 30 examples from my dataset and ask them to label each one using the same four labels. I will compare their labels to mine using percent agreement and Cohen's kappa. I will look especially at disagreements between `analysis` and `hot_take`, because that is already the hardest boundary.

For confidence calibration, I will use the fine-tuned model's confidence score on the test set. I will group predictions by confidence ranges and check whether higher confidence actually means higher accuracy.

For error pattern analysis, I will look at the wrong predictions from the fine-tuned model and group them by label pair. I already expect one pattern to be that the model avoids `hot_take`, because the confusion matrix showed zero predictions for that label.

I am not doing the deployed interface stretch right now because the local app needs the saved Colab model folder, and I am focusing on the analysis-based stretch features instead.

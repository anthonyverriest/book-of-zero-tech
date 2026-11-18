---
layout: post
title: "Evaluation: measure and compare what matters"
nav_order: 5
---

Your fraud model hits 92% accuracy. You are ready to celebrate. Then someone points out that 91% of transactions are legitimate, so a model that says "not fraud" to everything scores 91%. Your model is one point better than doing nothing.

That moment points at the real question of this page: how do you know whether a model is good enough to deploy, and better than the alternatives? We start with a smaller one: how do you score one model's predictions on one batch of transactions? Once that is clear, we scale up to choosing between models, setting a cutoff, other kinds of tasks, statistical comparison, and finally the business decision.

Our example runs through the whole guide. A fraud model scores 1,000 transactions, of which 90 are fraud. In nine parts, we read its confusion matrix, pick metrics for model selection and for the threshold, extend the same ideas to regression and ranking, read numbers and curves in context, test whether a difference is real, and decide whether the model pays for itself.

---

## On this page

- [Key concepts](#key-concepts)
- [Part 1: Every classification metric counts boxes in one table](#part-1-every-classification-metric-counts-boxes-in-one-table)
- [Part 2: Choosing a model means judging its ranking, not its cutoff](#part-2-choosing-a-model-means-judging-its-ranking-not-its-cutoff)
  - [A fair comparison needs a fixed protocol](#a-fair-comparison-needs-a-fixed-protocol)
  - [AUC-ROC measures how well the model ranks](#auc-roc-measures-how-well-the-model-ranks)
  - [AUC-PR stays honest when positives are rare](#auc-pr-stays-honest-when-positives-are-rare)
  - [MCC uses all four boxes](#mcc-uses-all-four-boxes)
  - [Log loss grades the probabilities themselves](#log-loss-grades-the-probabilities-themselves)
  - [Multiclass metrics need an averaging rule](#multiclass-metrics-need-an-averaging-rule)
- [Part 3: The threshold turns scores into decisions](#part-3-the-threshold-turns-scores-into-decisions)
  - [The cost of each error picks the metric](#the-cost-of-each-error-picks-the-metric)
  - [Classifiers need watching after launch](#classifiers-need-watching-after-launch)
- [Part 4: Regression asks how far off, not whether right](#part-4-regression-asks-how-far-off-not-whether-right)
  - [A mean predictor sets the regression floor](#a-mean-predictor-sets-the-regression-floor)
  - [Each error metric weighs misses differently](#each-error-metric-weighs-misses-differently)
  - [Regression models drift too](#regression-models-drift-too)
- [Part 5: Ranking metrics care about position](#part-5-ranking-metrics-care-about-position)
  - [Popularity sets the ranking floor](#popularity-sets-the-ranking-floor)
  - [Position-aware metrics reward the top of the list](#position-aware-metrics-reward-the-top-of-the-list)
  - [Beyond accuracy: diversity and coverage](#beyond-accuracy-diversity-and-coverage)
  - [Rankers are monitored through behavior](#rankers-are-monitored-through-behavior)
- [Part 6: A number needs context before it means anything](#part-6-a-number-needs-context-before-it-means-anything)
- [Part 7: Curves explain why a score is what it is](#part-7-curves-explain-why-a-score-is-what-it-is)
  - [Learning curves](#learning-curves)
  - [Validation curves](#validation-curves)
  - [Calibration curves](#calibration-curves)
  - [Cumulative gains and lift curves](#cumulative-gains-and-lift-curves)
- [Part 8: A higher mean is not a win until you test it](#part-8-a-higher-mean-is-not-a-win-until-you-test-it)
  - [Statistical significance](#statistical-significance)
  - [Reading a comparison table](#reading-a-comparison-table)
- [Part 9: The deployed model must also win on business terms](#part-9-the-deployed-model-must-also-win-on-business-terms)
  - [Expected value (EV)](#expected-value-ev)
  - [The complexity tax](#the-complexity-tax)
  - [Interpretability constraints](#interpretability-constraints)
  - [Offline vs. online performance](#offline-vs-online-performance)
  - [Time-to-value](#time-to-value)
  - [Custom metrics](#custom-metrics)
- [Common pitfalls](#common-pitfalls)
- [Recap](#recap)
- [Exercise](#exercise)

---

## Key concepts

- **Confusion matrix**: A 2×2 table that counts true positives (TP), true negatives (TN), false positives (FP), and false negatives (FN). Every classification metric is a function of these four numbers.
- **Threshold**: The probability cutoff that turns a model's continuous output into a binary decision. Moving the threshold trades precision for recall.
- **Threshold-independent metric**: Evaluates the model across all thresholds (e.g., AUC). Use for model comparison. It separates "is this a good model?" from "where do I set the cutoff?"
- **Threshold-dependent metric**: Evaluates the model at one specific cutoff (e.g., precision at 0.5). Use for final evaluation. It answers "how will this perform at the operating point I deploy?"
- **Precision**: Of everything the model flagged as positive, how many actually were. High precision = few false alarms.
- **Recall (Sensitivity)**: Of all actual positives, how many the model caught. High recall = few missed cases.
- **Specificity (True Negative Rate)**: Of all actual negatives, how many the model correctly ignored. Often paired with sensitivity in medical and manufacturing domains. High specificity = few false alarms in the negative class.
- **Log loss (cross-entropy)**: Measures how well predicted probabilities match actual outcomes. Unlike AUC or MCC, it penalizes poorly calibrated probabilities: a confident wrong prediction is punished heavily. For a direct check of calibration (whether a predicted 70% is actually right 70% of the time), use [calibration curves](#calibration-curves).

---

## Part 1: Every classification metric counts boxes in one table

A metric is a question you ask the model. Ask the wrong question and you get a precise answer to something you do not care about. Accuracy asks "how often are you right?" For fraud, the question you care about is "how much fraud do you catch, and how many good customers do you bother?"

To ask better questions, we need to see what the model did. Our fraud model looked at 1,000 transactions. Each one lands in exactly one of four boxes, depending on what the model said and what was true:

```
                  Predicted positive    Predicted negative
Actual positive        TP                     FN
Actual negative        FP                     TN
```

<p align="center">
  <img src="{{ "/assets/images/plots/confusion_matrix.svg" | relative_url }}" alt="Confusion matrix heatmap showing TP, FN, FP, and TN counts">
</p>

- **TP (true positive)**: correctly caught.
- **FN (false negative)**: missed. The model said "no" but it was "yes." Cost depends on domain (missed fraud, missed diagnosis).
- **FP (false positive)**: false alarm. The model said "yes" but it was "no." Cost depends on domain (unnecessary investigation, wasted resources).
- **TN (true negative)**: correctly ignored.

Here are our model's counts. Of the 90 frauds, it caught 55 (TP) and missed 35 (FN). Of the 910 legitimate transactions, it flagged 45 by mistake (FP) and left 865 alone (TN).

Accuracy counts the two "right" boxes: (55 + 865) / 1,000 = 92%. Now score the lazy model that says "not fraud" every time. It gets TP = 0, FN = 90, FP = 0, TN = 910. Its accuracy is 910 / 1,000 = 91%. Which makes sense, because accuracy is dominated by the TN box, and the lazy model fills that box perfectly.

This is the **accuracy paradox**. A model that predicts the majority class for every input achieves high accuracy on imbalanced data while being completely useless. It also tells us the first rule: compute a baseline before you train anything.

- **Trivial baseline**: always predicts the dominant class (e.g., `DummyClassifier(strategy="most_frequent")`). This is your accuracy baseline. If your model barely beats it, the model is not useful.
- **Random classifier**: AUC-ROC = 0.5, MCC = 0. Any trained model should clear these comfortably.
- **Simple baseline**: a tuned linear model (e.g., `LogisticRegression` for classification, `Ridge` for regression). Often competitive with complex models. If a complex model barely beats this, the added complexity is not justified.

So accuracy alone is insufficient for imbalanced problems. Always pair it with metrics that reflect performance on the minority class: recall, precision, F1, MCC, or AUC-PR. Every metric below is a different way of combining these four numbers to answer a specific question. When a metric confuses you, come back to this table and ask which boxes it counts.

For a complete baseline workflow including code examples and tracking with MLflow, see [Experiments: baselines]({{ site.baseurl }}/docs/machine-learning/experiments/page/#baselines).

Different phases of a project ask different questions, so they need different metrics. Each workflow below follows the same path:

1. **Baseline**: what does a naive predictor score?
2. **Model selection**: which model ranks or predicts best, independent of any cutoff?
3. **Threshold tuning and evaluation**: where do you set the cutoff, given what errors cost?
4. **Production monitoring**: is the model still doing its job?

**Every classification metric is a way of counting the four boxes, and a baseline tells you which counts are worth celebrating.**

---

## Part 2: Choosing a model means judging its ranking, not its cutoff

You are comparing models or hyperparameter sets. Our model's 55 catches depend on the cutoff it used. Move the cutoff and the counts change. So to compare models fairly, use threshold-independent metrics. You are judging the model's ranking ability, not a particular cutoff.

### A fair comparison needs a fixed protocol

To compare reliably, evaluate with cross-validation, typically 5-fold. Sklearn uses stratified k-fold by default for classifiers, preserving class proportions in each fold. A single train/test split can be noisy; cross-validation gives you a mean and standard deviation for each metric. For robust model comparison, run multiple seeds, because a single seed can give misleading results (see [Experiments: seeds and reproducibility]({{ site.baseurl }}/docs/machine-learning/experiments/page/#seeds) for the full protocol).

**Beware of naive splitting.** If multiple rows belong to the same entity (e.g., many transactions from the same customer), standard cross-validation will put the customer in both the train and test sets, leaking data. Use `GroupKFold` to ensure all records for an entity stay together. For time-series data, random splitting leaks the future to predict the past; use `TimeSeriesSplit` or an out-of-time test set.

With the protocol settled, which metric? It depends on your data.

**Compare models on the same folds, seeds, and grouping, or the metric compares the splits instead of the models.**

### AUC-ROC measures how well the model ranks

Pick a random fraudster and a random honest customer. Ask the model to score both. AUC-ROC is the probability that the model scores the fraudster higher. That is all it measures: ranking quality.

Work it on a tiny case first. Two frauds score 0.9 and 0.4. Three honest transactions score 0.6, 0.3, and 0.2. That makes 2 × 3 = 6 fraud-versus-honest pairs. The 0.9 fraud beats all three honest scores. The 0.4 fraud beats 0.3 and 0.2 but loses to 0.6. So 5 of 6 pairs are ordered correctly, and AUC = 5/6 ≈ 0.83. Which makes sense: the model ranks well, with one mistake.

AUC = 1.0 is perfect separation, and 0.5 is random: the model cannot tell the two apart. Technically, it plots recall (true positive rate) vs false positive rate across all thresholds, and the area under that curve equals the pair-counting probability above.

<p align="center">
  <img src="{{ "/assets/images/plots/roc_curve.svg" | relative_url }}" alt="ROC curves for strong, good, and weak classifiers against the random baseline">
</p>

How to interpret:
- 0.9–1.0: outstanding discriminator.
- 0.8–0.9: strong, usually production-ready.
- 0.7–0.8: acceptable, may be enough depending on the problem.
- 0.5–0.7: poor. Revisit features or model choice.

What AUC-ROC does not tell you: whether the predicted probabilities are calibrated, or how the model performs at the cutoff you will deploy.

**AUC-ROC is the chance the model ranks a random positive above a random negative, at every threshold at once.**

### AUC-PR stays honest when positives are rare

You might expect AUC-ROC to work everywhere. On imbalanced data, it can look misleadingly good. Here is the surprise, in numbers.

The false positive rate is `FPR = FP / (FP + TN)`. Our model has FP = 45 and TN = 865, so FPR = 45 / 910 ≈ 0.049. Now double the false alarms to 90. FPR becomes 90 / 910 ≈ 0.099, still under 10%. The ROC curve barely moves.

Precision tells a different story. It was 55 / (55 + 45) = 0.55. With 90 false alarms, it falls to 55 / (55 + 90) ≈ 0.38. Analysts now face almost two false alarms for every real fraud.

That gap is FPR dilution. When negatives dominate, TN is huge, so even many false positives barely move the FPR. The ROC curve hugs the upper-left corner and AUC inflates. AUC-PR plots precision against recall instead, so it focuses on the positive (minority) class and gives a more honest picture when positives are rare.

How to interpret: AUC-PR has no universal "good" threshold, because the baseline depends on class prevalence. A random classifier scores AUC-PR ≈ the positive class rate (e.g., 0.09 for our 9% fraud rate, 0.01 if 1% positive). Any trained model should far exceed that. Compare AUC-PR between models, not against a fixed number.

Use AUC-PR for fraud detection, disease screening, defect detection: any problem where the positive class is under ~10-20% of the data.

**When positives are rare, AUC-PR reacts to false alarms that AUC-ROC hides inside a huge TN count.**

### MCC uses all four boxes

Imagine a model that flags nearly everything as positive. It catches every positive, so its F1 can look decent. But it is useless on the negatives, and F1 cannot see that because F1 ignores TN entirely.

MCC (Matthews Correlation Coefficient) catches that. It uses all four quadrants of the confusion matrix. It ranges from −1 (perfect inversion) through 0 (random) to +1 (perfect). Unlike accuracy and F1, MCC can only score high if the model handles both positives and negatives well. It works regardless of class balance.

The formula looks intimidating, so take it in two pieces. The numerator, TP × TN − FP × FN, is "right products minus wrong products". For our model, that is 55 × 865 − 45 × 35 = 47,575 − 1,575 = 46,000. The denominator scales that number into the −1 to +1 range, using the four row and column totals: √(100 × 90 × 910 × 900) ≈ 85,856. So MCC ≈ 46,000 / 85,856 ≈ 0.54. That is moderate, which makes sense: the model catches most frauds but still misses more than a third.

`MCC = (TP × TN − FP × FN) / √((TP + FP)(TP + FN)(TN + FP)(TN + FN))`

Now the lazy model. Its TP and FP are both 0, so the numerator is 0 and MCC = 0 (sklearn returns 0 when a total in the denominator is zero). Its 91% accuracy turns into zero signal, which is the right verdict.

How to interpret:
- 0.7–1.0: strong.
- 0.4–0.7: moderate, may be enough depending on the problem.
- 0.2–0.4: weak. The model has some signal but not much.
- 0.0–0.2: negligible, effectively noise.
- Slightly negative (e.g., −0.05): likely sampling noise, not meaningful. Treat as random-level performance.
- Strongly negative (e.g., −0.5): systematic inversion. The model's predictions are anti-correlated with reality. Check for label bugs or data leakage. If deliberate, flip the predictions.

**MCC is high only when the model is right about both classes, which makes it the safest single number when in doubt.**

### Log loss grades the probabilities themselves

Suppose a model says "99% fraud" for a transaction that turns out to be fine. AUC and MCC barely notice, because they evaluate whether the model ranks or classifies correctly. Neither tells you if the predicted probabilities are well-matched to reality.

Log loss (cross-entropy) does. Start with one fraud (y = 1). For each transaction, only one half of the formula is active: `−log(p)` when it is fraud, `−log(1 − p)` when it is not. So:

- The model says p = 0.9: loss = −log(0.9) ≈ 0.11.
- The model says p = 0.5: loss = −log(0.5) ≈ 0.69.
- The model says p = 0.01: loss = −log(0.01) ≈ 4.6.

Being confidently wrong costs about 44 times more than being confidently right, and about 7 times more than shrugging. Which makes sense, because the logarithm grows without limit as p approaches 0. Average that per-transaction loss over all transactions and you get the formula:

`Log loss = −mean(y × log(p) + (1 − y) × log(1 − p))`

Log loss is a proper scoring rule that reflects both calibration and discrimination together, and it cannot isolate one from the other. For a direct assessment of calibration, use [calibration curves](#calibration-curves) (reliability diagrams).

How to interpret: log loss = 0 is perfect. The baseline is the log loss of always predicting the class prevalence. For our 9% fraud rate, always predicting 0.09 gives about 0.30. Lower is better. There are no universal "good" bands, so compare against the baseline and between models. A sudden rise in log loss often means the model is becoming overconfident on wrong predictions.

Use log loss when downstream decisions depend on the probability itself, not only the class label: risk scoring, bid optimization, or any system that uses predicted probabilities as inputs. A model can have a high AUC but poorly calibrated probabilities; log loss catches this.

**Log loss punishes confident mistakes hardest, so use it when the probability itself feeds a decision.**

### Multiclass metrics need an averaging rule

All metrics above extend to multiclass problems. Say the fraud team splits fraud into types. The key decision is how to average across classes, and it changes the story. Imagine three classes with 1000, 100, and 10 samples:

- **`macro`**: compute the metric per class, then take the unweighted mean. The 10-sample class counts as much as the 1000-sample class. Use this when rare classes are important, because it surfaces poor performance on them.
- **`weighted`**: same as macro, but weighted by the number of true instances per class. The 1000-sample class dominates. Use this when the score should reflect overall performance proportional to class frequency.
- **`micro`**: pool all TP, FP, FN globally, then compute. For multiclass (not multilabel), micro F1 = micro precision = micro recall = accuracy.

A quick check of why it matters: per-class recalls of 0.95, 0.80, and 0.10 give a macro recall of (0.95 + 0.80 + 0.10) / 3 ≈ 0.62. Weighted by 1000, 100, and 10 samples, the same recalls give about 0.93. The rare class's failure is visible in one number and invisible in the other.

MCC works for multiclass without averaging: pass predictions directly to `sklearn.metrics.matthews_corrcoef`. For multiclass, the minimum MCC is between −1 and 0 (depending on class distribution), not exactly −1.

AUC-ROC extends via one-vs-rest (`ovr`) or one-vs-one (`ovo`) and requires probability scores. For imbalanced multiclass, prefer `ovo` with `average='macro'`, which is less sensitive to class imbalance.

**Choose the averaging rule on purpose: `macro` exposes rare classes, `weighted` follows the majority.**

---

## Part 3: The threshold turns scores into decisions

You picked a model. Now you choose the operating point: the threshold where the model makes actual decisions.

Here is the intuition. The model outputs 0.37 for a transaction. Do you block it? At a threshold of 0.5, no. At 0.3, yes. Every threshold is a different trade between catching more and bothering fewer. This is where you align the metric with the **business cost of errors**.

### The cost of each error picks the metric

**False negatives are expensive → optimize recall.**

`Recall = TP / (TP + FN)`. Our model: 55 / 90 ≈ 0.61, so it catches 61% of fraud. Lowering the threshold catches more positives but increases false alarms.

Use when: a miss is dangerous or costly (medical screening, security threats). Accept more false positives to catch more true positives.

**False positives are expensive → optimize precision.**

`Precision = TP / (TP + FP)`. Our model: 55 / 100 = 0.55, so 55% of its alerts are real. Raising the threshold reduces false alarms but misses more positives.

Use when: each positive prediction triggers an expensive action (manual review, production rollback, customer intervention).

**Both matter roughly equally → use F1.**

Why not average precision and recall? Try it on an extreme model: 99% precision, 1% recall. The plain average is 50%, which sounds fine for a model that misses 99% of fraud. The harmonic mean fixes that:

`F1 = 2 × (precision × recall) / (precision + recall)`

For the extreme model, F1 = 2 × 0.99 × 0.01 / 1.00 ≈ 0.02. For ours, F1 = 2 × 0.55 × 0.61 / (0.55 + 0.61) ≈ 0.58, close to both inputs. The harmonic mean stays near the smaller of the two, so a model cannot hide a terrible recall behind a great precision.

F1 assumes false positives and false negatives cost the same. If they do not, use F-beta with a beta > 1 (favor recall) or beta < 1 (favor precision).

**When the negative class is important → use Specificity.**

`Specificity = TN / (TN + FP)`. Our model: 865 / 910 ≈ 0.95, so 95% of good customers pass untouched. Use this alongside recall (sensitivity) when the negative class represents something critical, such as healthy patients in a medical test. High specificity means few false alarms.

**How to pick the threshold in practice:**

1. Plot precision and recall as a function of threshold.
2. Identify the region where both are acceptable for your use case.
3. Pick the threshold that matches your cost trade-off.
4. Report precision, recall, and F1 at that threshold, not only the "best F1."

<p align="center">
  <img src="{{ "/assets/images/plots/precision_recall_threshold.svg" | relative_url }}" alt="Precision and recall as a function of decision threshold, with F1 curve and best-F1 point marked">
</p>

What threshold metrics do not tell you: how the model ranks overall. A good F1 at one cutoff says nothing about other cutoffs, which is why model selection comes first.

**Set the threshold from what each error costs, then report precision, recall, and F1 at that exact point.**

### Classifiers need watching after launch

Models degrade. Data distributions shift, upstream features change, and user behavior evolves. The model you shipped in March is answering a slightly different world by September.

Performance metrics (F1, precision, recall) require ground truth labels. In many production settings, labels are delayed or unavailable. A fraud label might arrive weeks later, when the chargeback comes in. This is one of the hardest problems in production ML. When labels are delayed, rely on feature drift and prediction drift as proxy signals until labels arrive.

- Track the same metric you optimized at threshold tuning, computed on live predictions once labels are available.
- Set alerts for significant drops. A simple starting point is a fixed threshold (e.g., F1 drops more than 5% from a rolling average). More robust approaches use statistical tests (e.g., PSI, KS test) that account for sample size and natural variance.
- Watch for **training-serving skew**: features computed differently at training time and serving time. This is a common and hard-to-detect failure mode.
- Monitor feature and prediction distributions against a **reference baseline** (typically the training data distribution). This does not require labels and can catch degradation before performance metrics show it.

**Track the metric you tuned for once labels arrive, and watch input and prediction drift while you wait.**

**So far:** the confusion matrix holds every classification metric. A baseline says what a lazy model scores. AUC-ROC, AUC-PR, MCC, and log loss compare models independently of the cutoff. Precision, recall, F1, and specificity then judge the cutoff you deploy, chosen from what each error costs.

---

## Part 4: Regression asks how far off, not whether right

The fraud team also forecasts tomorrow's review workload: how many transactions will be flagged per day. That is regression. It predicts a number: a price, a demand forecast, a delivery time. The question changes from "right or wrong?" to "how far off?"

### A mean predictor sets the regression floor

- **Mean predictor**: always predicts the mean of the target. Your model should beat this comfortably.
- For time series: the naive baseline is "predict the last observed value."

**Any regression model must beat "predict the average" and, for time series, "predict yesterday".**

### Each error metric weighs misses differently

Unlike classification, regression does not have a threshold step. The same metrics serve both model selection and evaluation. As with classification, use cross-validation (typically 5-fold) to get reliable estimates. Sklearn uses standard k-fold by default for regressors.

**Default → MAE.**

Say the workload forecast is off by 2, 2, 2, and 2 flagged transactions over four days. The average miss is 2. That is MAE: the average size of the error, in the same unit as the target. It reads naturally: "the model is off by 2 transactions on average." MAE treats all errors equally. It is robust to outliers and is the right default unless you have a specific reason to penalize large errors more.

`MAE = mean(|y − ŷ|)`

**When big misses are costly → RMSE.**

Now a second forecast misses by 0, 0, 0, and 8. Its MAE is also 8 / 4 = 2. Same score. But the first forecast was off a little every day, while the second left the team short by 8 reviews on one day. If a big miss is what hurts, MAE cannot tell these two apart.

RMSE can. Square each error, average, then take the root. For the first forecast: √((4 + 4 + 4 + 4) / 4) = 2. For the second: √((0 + 0 + 0 + 64) / 4) = √16 = 4. Which makes sense, because squaring makes an error of 8 count 16 times as much as an error of 2, not 4 times.

`RMSE = √(mean((y − ŷ)²))`

RMSE punishes large errors disproportionately: a few big misses raise RMSE much more than they raise MAE. Use RMSE when a large error is much worse than a small one: demand forecasting (big underestimate = stockout), energy grid planning, structural engineering.

<p align="center">
  <img src="{{ "/assets/images/plots/residuals.svg" | relative_url }}" alt="Residuals diagnostic plot showing actual vs predicted scatter and residual distribution">
</p>

**When business needs a percentage → MAPE.**

Mean Absolute Percentage Error translates errors into percentages, which makes it much clearer for non-technical stakeholders ("the forecast is off by 5% on average"). Forecast 110 when the truth is 100, and the error is 10%.

`MAPE = mean(|(y − ŷ) / y|)`

Now forecast 4 when the truth is 2. The miss is only 2 transactions, but MAPE calls it 100%. And if the truth is 0, MAPE divides by zero and explodes. So MAPE is fundamentally flawed if the actual values can be zero or close to zero. It also penalizes overestimates more heavily than underestimates. Use it for reporting, but be cautious about optimizing for it directly.

<br>

**For targets with heavy right tails → RMSLE.**

Root Mean Squared Logarithmic Error is used when the target spans several orders of magnitude (prices, income, counts). An error of &#36;100 matters a lot if the true price is &#36;50, but is irrelevant if the true price is &#36;500,000.

The logarithm turns ratios into differences, so RMSLE penalizes relative differences rather than absolute ones. It also penalizes underestimates more heavily than overestimates.

`RMSLE = √(mean((log(y + 1) − log(ŷ + 1))²))`

The `+ 1` keeps the logarithm defined when a target is zero.

**For scale-independent comparison → R².**

R² answers one question: what proportion of the variance in the target does the model explain? Take three days with actual counts 10, 20, and 30. Their mean is 20, so the squared distances from the mean add up to 100 + 0 + 100 = 200. That is how wrong "predict the mean" would be. Now the model predicts 12, 18, and 30. Its squared errors add up to 4 + 4 + 0 = 8. So R² = 1 − 8 / 200 = 0.96: the model removes 96% of the mean predictor's error.

`R² = 1 − (SS_res / SS_tot)`, where `SS_res = Σ(y − ŷ)²` and `SS_tot = Σ(y − ȳ)²`.

R² = 1.0 is perfect, and R² = 0 means the model is no better than predicting the mean. Use R² when comparing models across different targets or scales. MAE and RMSE are in the target's units, so they are not directly comparable across different problems. R² is also sklearn's default `.score()` for regressors.

How to interpret:
- R² = 1.0: perfect. The model explains all variance.
- 0.7–1.0: strong. The model captures most of the signal.
- 0.4–0.7: moderate. Useful but missing substantial variance. Check for missing features or nonlinearity.
- 0.0–0.4: weak. The model explains little. Consider whether the problem is inherently noisy or the features are insufficient.
- R² < 0: the model is worse than always predicting the mean. Something is fundamentally wrong.

**Interpreting MAE and RMSE together.** RMSE is always ≥ MAE, and the gap between them tells you something. Our two forecasts showed it: RMSE = MAE = 2 for uniform errors, and RMSE = 4 against MAE = 2 when one big miss dominates. If RMSE >> MAE, a few large errors are pulling RMSE up.

Investigate those outliers. They may reveal a data quality issue, a subpopulation the model cannot handle, or a feature gap. Report both: MAE tells you the typical error, RMSE tells you about the worst-case behavior.

<p align="center">
  <img src="{{ "/assets/images/plots/mae_vs_rmse.svg" | relative_url }}" alt="Grouped bar chart comparing MAE and RMSE across three regression models, highlighting outlier-driven RMSE inflation">
</p>

**Report MAE for the typical miss and RMSE for the big ones; the gap between them points at outliers.**

### Regression models drift too

As with classification, performance metrics require ground truth labels. When labels are delayed, monitor feature drift and prediction drift as proxy signals.

- Track MAE (or RMSE, depending on what you optimized) on live predictions once labels are available.
- Watch for **error drift**: if MAE rises steadily, investigate. Possible causes include concept drift (the relationship between features and target is shifting), data quality issues, population shift, or upstream pipeline changes.
- Monitor **error percentiles** (P90, P99) over time. Rising tail percentiles reveal growing outlier errors that MAE alone can mask: a subpopulation may be diverging from training data.
- Compare live R² against the training R². A large drop signals that the model's explanatory power has degraded.
- Check for **feature drift**: if the distribution of key input features shifts significantly from training, the model's predictions may degrade before the target metric shows it.

**Watch the tails of the error, not only its average, because the tails move first.**

---

## Part 5: Ranking metrics care about position

The analysts review flagged transactions from the top of a queue, sorted by fraud score. They get through the first twenty before lunch. Nobody cares what the model thinks of item number 847.

When you are ordering items rather than predicting a single number (review queues, search results, product recommendations, feeds), classification and regression metrics fail. A model might predict scores with high RMSE, but if it still sorts the most relevant items to the top, it is a perfect ranker.

### Popularity sets the ranking floor

- **Popularity-based baseline**: Always recommend the globally most popular items. In many domains, this is surprisingly hard to beat.
- **Random baseline**: Shuffle the items randomly.

**A ranker earns its place only by beating "show the popular items".**

### Position-aware metrics reward the top of the list

Ranking metrics evaluate **position**. Being wrong at position 1 is heavily penalized; being wrong at position 100 barely matters.

**When there is only one right answer → MRR.**

Over three mornings, the first real fraud in the queue sits at position 1, then 2, then 4. Score each morning as 1 / position: 1, 0.5, and 0.25. The average, (1 + 0.5 + 0.25) / 3 ≈ 0.58, is the Mean Reciprocal Rank. It is used when the user is looking for a single specific item (e.g., a "feeling lucky" search, finding a specific song, or answering a factual question).

`MRR = mean(1 / rank_i)`

How to interpret: MRR = 1.0 means the relevant item is always first. MRR = 0.5 means it is usually second. MRR does not tell you anything about relevant items after the first one.

**When there are multiple right answers (binary relevance) → MAP.**

Mean Average Precision is used when there are multiple relevant items, but relevance is binary (yes/no). It rewards putting *all* relevant items as high as possible. It computes the Average Precision for each query (the area under the precision-recall curve for that specific ranking), and then takes the mean across all queries.

**When relevance has degrees (graded relevance) → NDCG.**

Some results are better than others. A large, confirmed fraud should count more than a small, suspicious one. Normalized Discounted Cumulative Gain is the gold standard for modern search and recommendation. Unlike MAP, which assumes an item is either relevant or not, NDCG handles graded relevance (e.g., 5-star ratings, "highly relevant" vs "somewhat relevant").

It sums the relevance scores of the ranked items, discounting them logarithmically by their position (`1 / log2(rank + 1)`). Then it normalizes against the ideal possible ranking for that query, so the score is between 0 and 1.

Work it with three items whose relevance is 3, 2, and 0. The model puts the 2 first, the 3 second, the 0 last. Its discounted gain is 2 / log2(2) + 3 / log2(3) + 0 ≈ 2 + 1.89 = 3.89. The ideal order (3, 2, 0) gives 3 / log2(2) + 2 / log2(3) ≈ 3 + 1.26 = 4.26. So NDCG ≈ 3.89 / 4.26 ≈ 0.91. Which makes sense: the two good items are both near the top, only swapped.

How to interpret:
- Evaluated at a cutoff K (e.g., **NDCG@10**), because users rarely look past the first page of results.
- NDCG = 1.0 is a perfect ranking.
- Useful for comparing algorithms, but harder to explain to business stakeholders than simple conversion metrics.

```python
from sklearn.metrics import ndcg_score

# Graded relevance (e.g., 5-star ratings or human labels)
y_true = [[5, 3, 1, 0, 2]]
# Model's predicted ranking scores
y_score = [[0.9, 0.7, 0.5, 0.3, 0.1]]

ndcg_10 = ndcg_score(y_true, y_score, k=10)
```

**For simpler evaluation and monitoring → Precision@K and Recall@K.**

These complement the ranking-aware metrics above. They are clearer for non-technical stakeholders and widely used in production monitoring alongside NDCG.

`Precision@K = (# relevant items in top K) / K`

`Recall@K = (# relevant items in top K) / (total # relevant items)`

Precision@K tells you what fraction of your recommendations are good. Recall@K tells you what fraction of all good items you surfaced. If you recommend 10 items and 7 are relevant, Precision@10 = 0.7. If there were 20 total relevant items in the catalog, Recall@10 = 7/20 = 0.35.

Unlike NDCG and MAP, these metrics ignore the order within the top K. They only care whether relevant items made it into the list, not where they appear.

Use Precision@K when the user's attention is limited (e.g., showing only 5 products, or the twenty items analysts review before lunch) and you want to ensure the shortlist is high-quality. Use Recall@K when coverage matters: in multi-label classification or when you need to ensure all relevant items get surfaced.

**Hit Rate@K** is the binary version: did at least one relevant item appear in the top K? Useful for "single-intent" queries where the user needs any one correct answer.

**Pick the ranking metric by how many right answers exist and whether some are better than others.**

### Beyond accuracy: diversity and coverage

A fraud review queue does not need variety. A recommender does. You watch one cooking video, and now your whole feed is cooking videos. That is a **filter bubble**, and pure accuracy optimization creates them. Users see only variations of what they already like, the catalog concentrates on a few popular items, and discovery breaks down. Enterprise recommendation systems must balance relevance with diversity and coverage.

**Coverage**: what proportion of the catalog gets recommended over time.

`Coverage = (# unique items recommended) / (# items in catalog)`

If your catalog has 10,000 products but 90% of recommendations come from the same 100 popular items, the popular slice covers only 100 / 10,000 = 0.01 of the catalog. You have a popularity bias problem. High coverage ensures the long tail gets exposure. For marketplaces (Etsy, Airbnb), this is a business requirement: sellers expect visibility.

Track coverage over rolling windows (e.g., daily, weekly). A coverage drop often signals that the model is converging on a narrow set of items. This is especially common after retraining on click data: clicks reinforce popular items, creating a feedback loop.

**Diversity**: how different the recommended items are from each other within a single list.

Intra-List Diversity (ILD) measures the average pairwise dissimilarity between items in a recommendation:

`ILD = (1 / (K × (K − 1))) × Σ dissimilarity(item_i, item_j)` for all pairs in the top K.

The fraction in front is an average: a list of K items has K × (K − 1) ordered pairs, so with K = 3 you sum 6 dissimilarities and divide by 6. Dissimilarity can be cosine distance between item embeddings, category mismatch, or any domain-specific measure. High diversity prevents the "10 nearly identical recommendations" problem.

**Personalization**: how different recommendations are across users.

If every user gets the same top-10 list, personalization is zero: the system is a popularity ranker in disguise. Measure this as the average Jaccard distance between recommendation lists for different users.

**Trade-offs.** Optimizing purely for NDCG often reduces diversity, because the model learns to recommend safe, popular items. Use a composite objective (e.g., `0.7 × NDCG + 0.3 × diversity`) or apply post-processing re-ranking to boost diversity while maintaining a minimum relevance threshold. Many production systems use a two-stage approach: retrieve candidates for relevance, then re-rank for diversity.

**For recommenders, relevance is not enough: track coverage, diversity, and personalization beside it.**

### Rankers are monitored through behavior

Ground truth relevance is rarely available immediately, so track user behavior and catalog health.

**Engagement:**

- **Click-Through Rate (CTR)**: Percentage of queries with clicks. Dropping CTR signals degrading relevance.
- **Click position**: Average rank of clicked items. Rising position means users must scroll further. Correct for **position bias** (users click top results regardless of relevance).
- **Dwell time**: Time spent after clicking. High CTR + low dwell time = misleading rankings.
- **Session success rate**: Percentage of sessions where users find what they need (purchase, long watch, no re-query). Better satisfaction proxy than CTR alone.
- **Zero-result rate**: Queries with no clicks. Spikes indicate retrieval failure or intent mismatch.
- **Conversion rate**: Whether clicks lead to business outcomes (purchases, sign-ups, watch time).

**Catalog health:**

- **Coverage**: Percentage of catalog recommended over rolling windows. Drops signal convergence on popular items.
- **Popularity bias**: If 80% of traffic → 5% of items, you have a long-tail problem. Critical for marketplaces.
- **Freshness**: Age distribution of recommendations. Prevents new content/creators from being buried.

**Rapid evaluation:**

Offline metrics (NDCG) do not always correlate with business metrics (revenue). A/B tests are expensive (weeks, large traffic). Use **interleaving** first.

**Interleaving** mixes two models in one session (items 1,3,5 from model A; 2,4,6 from model B) and tracks which gets more clicks. It is **100× more sensitive than A/B testing**: you can detect differences with small traffic in hours vs weeks. Airbnb, Google, and Bing use it to identify candidates before full A/B tests.

Once interleaving shows a winner, validate with an A/B test for business impact.

**Fairness:**

- Track metrics by user segment (geography, demographic, device). Overall NDCG can hide subgroup failures.
- Monitor exposure distribution for marketplaces, to ensure diverse sellers get visibility.
- Watch for feedback loops: clicks reinforce popularity bias. Inject periodic exploration.

**In production, user behavior stands in for relevance labels, and interleaving finds a winner before an A/B test confirms it.**

**So far:** the same four-step path (baseline, selection, operating point, monitoring) works for every task. Classification counts boxes, regression measures distance, and ranking weighs position. Each family has a baseline to beat and a metric matched to what errors cost.

---

## Part 6: A number needs context before it means anything

A number without context is a rumor. Our model's F1 of 0.58 is good or bad only next to something else. Here is how to read metrics in context:

- **Compare train and validation metrics.** If the training score is high and the validation score is low, the model is overfitting. Add regularization, reduce features, or get more data. If both are low, it is underfitting. A small gap with high scores on both is a good fit.
- **Always compare to the baseline.** An F1 of 0.85 means nothing in isolation. If the majority-class baseline gives 0.80, the model adds almost no value.
- **Check both classes.** A high overall score can hide poor performance on the minority class. Always look at per-class precision and recall.
- **Check the slices (subgroup analysis).** A model might have a fantastic overall MAE or AUC, but perform terribly for a specific geography, demographic, or customer segment. Global metrics hide local failures. Always evaluate the worst-performing slice before deploying, especially for models that impact humans.
- **Compare MAE and RMSE.** If RMSE is much larger than MAE, you have an outlier problem. Do not average it away.
- **Negative MCC: check the magnitude.** Slightly negative (near zero) is likely noise. Strongly negative means the model is systematically inverted: check for label errors, data leakage, or a flipped target. If the inversion is confirmed, flip the predictions.
- **Context determines "good enough."** An AUC of 0.75 can be strong for a hard medical imaging task and terrible for a spam filter. There is no universal threshold for a "good" score.
- **Suspiciously perfect scores signal leakage.** If a model achieves an AUC of 0.99 on a non-trivial problem, the most likely explanation is data leakage, not a great model. Check for target information bleeding into features, preprocessing applied before the train/test split, or duplicate records across splits. Similarly, tuning hyperparameters on the test set inflates all metrics. Always use a separate validation set or cross-validation.
- **Read the standard deviation from cross-validation.** A mean AUC of 0.83 ± 0.02 is more trustworthy than 0.85 ± 0.08. High variance across folds means the model's performance depends heavily on which data it sees: the model may be unstable or the dataset too small. If the standard deviation is large relative to the difference between models, you cannot confidently pick a winner.
- **Test set class balance must match deployment.** Precision, recall, and F1 depend on the ratio of positives to negatives. If your test set has 10% positives but production has 1%, precision will be worse in production than your test results suggest. AUC-ROC is invariant to class balance shifts, but threshold-dependent metrics are not.
- **Small test sets lie.** A metric computed on 100 samples has wide confidence intervals. If you cannot increase the test set, use bootstrap resampling to quantify uncertainty.

The class-balance point deserves a number. Keep our model's recall (61%) and false positive rate (about 4.9%), but move it from a 9% fraud rate to a 1% rate. Per 1,000 transactions, it now catches about 6 of 10 frauds and raises about 49 false alarms on 990 good ones. Precision falls from 0.55 to roughly 6 / 55 ≈ 0.11. Same model, same thresholds, a fifth of the precision.

**Read every metric against a baseline, its spread, its slices, and the class balance it will face in production.**

---

## Part 7: Curves explain why a score is what it is

A single score tells you how well the model did. A curve tells you why, and what to try next.

### Learning curves

"Should we label more fraud cases?" is an expensive question. A learning curve answers it before you spend the money.

A learning curve plots train and validation scores as the training set grows. It answers two questions: is the model underfitting or overfitting, and would more data help?

```python
from sklearn.model_selection import learning_curve

train_sizes, train_scores, val_scores = learning_curve(
    estimator, X, y,
    train_sizes=np.linspace(0.1, 1.0, 10),
    cv=5,
    scoring="roc_auc",
    n_jobs=-1,
)

train_mean = train_scores.mean(axis=1)
val_mean = val_scores.mean(axis=1)
```

<p align="center">
  <img src="{{ "/assets/images/plots/learning_curve.svg" | relative_url }}" alt="Learning curve showing train and validation ROC AUC as training set size grows">
</p>

How to read the plot:

- **Both curves converge high, small gap**: good fit. More data is unlikely to help. Focus on feature engineering or model complexity.
- **Both curves converge low**: underfitting. The model cannot capture the signal. Try a more expressive model, add features, or reduce regularization.
- **Large gap (train high, validation low)**: overfitting. The model memorizes training data. Add regularization, reduce features, or get more data.
- **Validation curve still rising at the right edge**: more training data would likely improve performance. This is one of the few cases where collecting more data is clearly the right move.

**A learning curve tells you whether more data will help before you pay for it.**

### Validation curves

A learning curve shows performance vs. *amount of data*. A validation curve plots train and validation scores against varying values of a single hyperparameter (e.g., tree depth, regularization strength). It is the primary visual tool for diagnosing whether your model's complexity is appropriate for the data.

```python
from sklearn.model_selection import validation_curve

param_range = np.logspace(-3, 2, 6)
train_scores, val_scores = validation_curve(
    estimator, X, y,
    param_name="C",
    param_range=param_range,
    cv=5,
    scoring="roc_auc",
    n_jobs=-1,
)
```

How to read the plot:

- **High bias (underfitting)**: Both training and validation curves are low. The model is too simple to capture the underlying pattern (e.g., a tree with max depth 1, or extreme regularization).
- **The sweet spot**: The point where the validation score peaks before beginning to decline. This is your optimal hyperparameter value.
- **High variance (overfitting)**: The training score continues to climb (often approaching perfect performance), but the validation score drops or flatlines. The model is too complex and has begun memorizing noise in the training set.

**A validation curve shows where one hyperparameter moves the model from too simple to too complex.**

### Calibration curves

A weather forecaster says "70% chance of rain" on 100 days. If it rains on about 70 of them, the forecaster is calibrated. Models are no different.

A calibration curve (reliability diagram) checks whether predicted probabilities match observed frequencies. Group the fraud model's predictions into bins. If the transactions it scored around 0.7 turn out to be fraud about 70% of the time, that bin sits on the diagonal.

```python
from sklearn.calibration import calibration_curve

prob_true, prob_pred = calibration_curve(y_test, y_prob, n_bins=10)
```

<p align="center">
  <img src="{{ "/assets/images/plots/calibration_curve.svg" | relative_url }}" alt="Calibration curve comparing logistic regression, random forest, and gradient boosting against perfect calibration">
</p>

How to read the plot:

- **Points on the diagonal**: well-calibrated. Predicted probabilities reflect reality.
- **Points above the diagonal**: the model under-predicts. It says 0.3 but the true rate is higher.
- **Points below the diagonal**: the model over-predicts. It says 0.8 but the true rate is lower.
- **S-shaped curve** (below the diagonal on the left, above it on the right): underconfident. Predictions are squeezed toward the middle.
- **Inverse S** (above on the left, below on the right): overconfident. Predictions are pushed too far toward 0 and 1.

Common patterns by model type: logistic regression is usually well-calibrated out of the box. Tree ensembles (random forest, gradient boosting) and SVMs often produce poorly calibrated probabilities. Random forests tend toward the center (underconfident at extremes), while gradient boosting can be overconfident.

If calibration is poor and your use case depends on probability quality (risk scoring, bid optimization), apply post-hoc calibration:

```python
from sklearn.calibration import CalibratedClassifierCV

calibrated = CalibratedClassifierCV(estimator, cv=5, method="isotonic")
calibrated.fit(X_train, y_train)
```

Use `method="sigmoid"` (Platt scaling) when data is limited. Use `method="isotonic"` when you have enough data (1000+ samples) for a more flexible correction.

What calibration does not tell you: whether the model ranks well. A model that predicts 0.09 for every transaction is perfectly calibrated on our data and useless for finding fraud.

**A calibration curve checks whether a predicted 70% really happens 70% of the time.**

### Cumulative gains and lift curves

The fraud team can manually review 100 of the 1,000 transactions a day, no more. Or your sales team can call 10% of the leads. In a targeted campaign like that, you need to know how well the model concentrates true positives at the very top of its ranked predictions.

A **Cumulative Gains curve** plots the percentage of the total population targeted (X-axis) against the percentage of all actual positive cases found (Y-axis).

```python
import matplotlib.pyplot as plt
import numpy as np

# y_score: positive-class probability, e.g. model.predict_proba(X_test)[:, 1]
order = np.argsort(y_score)[::-1]
y_sorted = np.asarray(y_test)[order]
pct_targeted = np.arange(1, len(y_sorted) + 1) / len(y_sorted)
pct_positives_found = np.cumsum(y_sorted) / y_sorted.sum()

plt.plot(np.r_[0, pct_targeted], np.r_[0, pct_positives_found], label="Model")
plt.plot([0, 1], [0, 1], "--", label="Random")
plt.xlabel("Share of population targeted")
plt.ylabel("Share of positives found")
plt.legend()
plt.show()
```

You may find tutorials that use `scikit-plot` for this chart. It is unmaintained and fails to import on current SciPy, so compute the curve directly as above.

How to read a Cumulative Gains plot:

- **The diagonal (random baseline)**: If you target a random 20% of users, you will find 20% of the true positives.
- **The model curve**: If the curve hits 0.70 at the 0.20 mark on the X-axis, it means targeting the top 20% of users (ranked by model probability) captures 70% of all actual positives.

A **Lift curve** is derived directly from the cumulative gains curve. It shows the multiplier of improvement over random guessing at each decile. Say the team's top 100 transactions contain 54 of the 90 frauds. A random 100 would contain about 9. The lift at 10% is 54 / 9 = 6.0, and the gain is 54 / 90 = 60% of all fraud found with 10% of the effort.

These curves are indispensable for translating model performance into business strategy. They let stakeholders answer questions like "How deep into the list should we go to hit our ROI target?"

**Gains and lift curves translate a ranking into "how much do we find with the effort we can afford?"**

---

## Part 8: A higher mean is not a win until you test it

### Statistical significance

Model A scores 0.852. Model B scores 0.847. Is A better? Flip a coin ten times and you might get seven heads; that does not make the coin unfair. A model with a higher mean score is not necessarily better, because the difference might be noise. Use statistical tests to quantify confidence.

**Paired tests compare models on the same data.** Each seed (or fold) produces a paired observation: model A's score and model B's score on the same split. Paired tests are more powerful than unpaired tests because they control for variance across splits. A hard fold is hard for both models, so looking at the difference on each fold cancels it out.

**How many seeds?** Hypothesis tests need enough paired observations to have statistical power. With fewer than 6 paired observations, the Wilcoxon signed-rank test cannot reach p < 0.05, and a paired t-test with 4 degrees of freedom is barely better.

You need at least 10 paired observations for minimal statistical power. This could come from 10 seeds (single train/test split per seed), 10 CV folds (single seed), or a combination. For robust, publishable comparisons, use 10 seeds × 5-fold CV (see [Experiments: reproducibility and seed protocols]({{ site.baseurl }}/docs/machine-learning/experiments/page/#seeds)), but analyse those 50 scores with the corrected resampled t-test below. CV fold scores share training data, so they are not independent observations.

With fewer than 10 paired observations, report a t-based confidence interval on the mean difference and treat the result as weak evidence.

Now the tests themselves, from the most familiar to the most robust.

**Paired t-test**: assumes the paired differences are approximately normally distributed. Use it only when the paired observations are independent: for example, each seed has its own fresh train/test split, scored once. The differences should also look roughly symmetric.

```python
from scipy import stats

# scores_a and scores_b: arrays of metric values, one per independent seed
t_stat, p_value = stats.ttest_rel(scores_a, scores_b)
```

**Corrected resampled t-test (Nadeau & Bengio)**: use this when scores come from repeated CV (seeds × folds). A naive `ttest_rel` on CV fold scores produces too many false positives. The correction is one line, so it is worth seeing where it comes from.

A plain t-test divides the mean difference by its standard error, which uses the variance of the differences times `1 / n`. That `1 / n` assumes every score is independent. Overlapping training sets break that assumption, so Nadeau and Bengio add a term for the overlap: the ratio of test size to training size. With 5-fold CV, each fold tests on 1 part and trains on 4, so the ratio is 1/4.

Plug in our 10 seeds × 5 folds. The plain factor is 1 / 50 = 0.02. The corrected factor is 0.02 + 0.25 = 0.27, which is 13.5 times larger. The t statistic shrinks by √13.5 ≈ 3.7. Which makes sense: 50 overlapping scores carry far less evidence than 50 independent ones, so the test must be that much harder to pass.

```python
import numpy as np
from scipy import stats

def corrected_resampled_ttest(scores_a, scores_b, n_folds: int) -> tuple[float, float]:
    """Paired t-test on repeated k-fold CV scores (one entry per seed × fold)."""
    d = np.asarray(scores_a) - np.asarray(scores_b)
    n = len(d)
    test_train_ratio = 1 / (n_folds - 1)  # n_test / n_train for k-fold
    t_stat = d.mean() / np.sqrt((1 / n + test_train_ratio) * d.var(ddof=1))
    p_value = 2 * stats.t.sf(abs(t_stat), df=n - 1)
    return t_stat, p_value
```

**Wilcoxon signed-rank test**: non-parametric alternative. Makes no normality assumption. Use when the differences are clearly skewed or you cannot assume normality. Requires at least 6 paired observations to reach p < 0.05; in practice, 10+ for reasonable power.

```python
stat, p_value = stats.wilcoxon(scores_a, scores_b)
```

**Bootstrap confidence interval**: resample the paired differences with replacement to estimate the distribution of the mean difference. It reports a confidence interval rather than a p-value, which is often more informative. Percentile bootstrap intervals are too narrow with very few observations, so prefer it when you have 20+ independent paired observations.

```python
rng = np.random.default_rng(0)
differences = scores_a - scores_b
bootstrap_means = [
    np.mean(rng.choice(differences, size=len(differences), replace=True))
    for _ in range(10000)
]
ci_lower, ci_upper = np.percentile(bootstrap_means, [2.5, 97.5])
```

<p align="center">
  <img src="{{ "/assets/images/plots/bootstrap_ci.svg" | relative_url }}" alt="Bootstrap distribution of mean AUC differences with 95% confidence interval marked">
</p>

If the 95% confidence interval excludes zero, the difference is significant at α = 0.05.

**Effect size**: statistical significance does not imply practical significance. A p-value of 0.01 with a 0.001 AUC difference means the difference is real but irrelevant. Report Cohen's d alongside p-values. It is the mean difference measured in units of its own spread: if A beats B by 0.005 on average and the differences have a standard deviation of 0.010, then d = 0.005 / 0.010 = 0.5, a medium effect.

```python
d = np.mean(differences) / np.std(differences, ddof=1)
```

Interpretation: |d| < 0.2 negligible, 0.2–0.5 small, 0.5–0.8 medium, > 0.8 large.

<p align="center">
  <img src="{{ "/assets/images/plots/effect_size.svg" | relative_url }}" alt="Cohen's d effect size scale with three model comparisons plotted on it">
</p>

**Multiple comparisons**: when comparing more than two models, the probability of a false positive increases. If you compare 10 models pairwise, you run 10 × 9 / 2 = 45 tests. At α = 0.05, you expect 45 × 0.05 ≈ 2 false positives by chance. Apply the Holm-Bonferroni correction (worked by hand in [Experiments: ablation study]({{ site.baseurl }}/docs/machine-learning/experiments/page/#ablation-study)):

```python
from statsmodels.stats.multitest import multipletests

rejected, corrected_p, _, _ = multipletests(p_values, method="holm")
```

What a p-value does not tell you: the size of the difference, or the probability that model A is better. It is the chance of seeing a difference this large if there were no real difference.

**Test paired scores with the right test for how they were produced, correct for the number of comparisons, and report the effect size.**

### Reading a comparison table

Present results so a reviewer can assess both magnitude and confidence:

```
Model               AUC (mean ± std)    Δ Control    p-value    p (Holm)    Cohen's d
─────────────────────────────────────────────────────────────────────────────────────
Control (XGBoost)   0.847 ± 0.012       —            —          —           —
MLP                 0.839 ± 0.015       −0.008       0.142      0.142       −0.31
LR + embeddings     0.852 ± 0.010       +0.005       0.038      0.076       +0.44
No text features    0.821 ± 0.014       −0.026       0.003      0.009       −1.12
```

How to read this table:

- **Mean ± std**: the average metric across seeds. The std tells you how stable the model is. A model with higher mean but much higher std may not be reliably better.
- **Δ Control**: the difference from the baseline. Positive means better, negative means worse (assuming the metric is higher-is-better).
- **p-value**: probability of observing this difference (or larger) by chance, assuming no real difference. Below 0.05 is the conventional threshold, but report the actual value and let the reader judge.
- **p (Holm)**: the p-value after correcting for the three comparisons against the control. Decide significance on this column.
- **Cohen's d**: effect size. Even if p < 0.05, a negligible effect size (|d| < 0.2) means the difference is not practically meaningful.

<p align="center">
  <img src="{{ "/assets/images/plots/model_comparison.svg" | relative_url }}" alt="Forest plot comparing four models with AUC mean, standard deviation, and p-values">
</p>

In the example: "No text features" is significantly worse (p = 0.003, large effect), confirming text features are important. "LR + embeddings" looks better (raw p = 0.038), but it is not significant after the Holm correction (p = 0.076). Treat it as promising, and confirm it with more seeds before acting on it. "MLP" is not significantly different from the control (p = 0.142).

**Decide significance on the corrected p-value, and importance on the effect size.**

**So far:** a number means something only against a baseline, its spread, and its slices. Curves show whether more data, a different hyperparameter, or calibration would help. And a higher mean wins only after a paired test, a multiple-comparison correction, and a look at the effect size.

---

## Part 9: The deployed model must also win on business terms

The model with the highest AUC or lowest RMSE on the cross-validation leaderboard is rarely the best model to deploy. In production, predictive accuracy is one variable in a larger business equation. Before deploying, evaluate the model against these operational constraints.

### Expected value (EV)

Every box in the confusion matrix has a price. A caught fraud saves money. A false alarm costs an analyst's hour. A missed fraud costs the chargeback. Add them up, and you know whether the model pays for itself.

Put prices on our boxes. A review costs &#36;10. A missed fraud costs a &#36;200 chargeback. So a caught fraud is worth −&#36;10 (no chargeback, but the review still costs), a false alarm costs &#36;10, a miss costs &#36;200, and a correctly ignored transaction costs nothing. Per transaction, with our rates (TP 5.5%, FP 4.5%, FN 3.5%):

- The model: 0.055 × (−&#36;10) − 0.045 × &#36;10 − 0.035 × &#36;200 = −&#36;8.00.
- No model (every fraud is missed): −0.09 × &#36;200 = −&#36;18.00.

The model saves &#36;10 per transaction, or &#36;10,000 per 1,000. Sanity check it the long way: 55 frauds stopped × &#36;200 = &#36;11,000 saved, minus 100 reviews × &#36;10 = &#36;1,000. That is &#36;10,000, which matches.

That arithmetic is the expected value framework. A model is only worth deploying if its Return on Investment (ROI) against the current approach is positive:

`EV = p(TP) × Value(TP) + p(TN) × Value(TN) - p(FP) × Cost(FP) - p(FN) × Cost(FN)`

Notice that both EVs above are negative. Fraud always costs something. The question EV answers is whether the model costs less than the alternative. If the expected value of using the model is lower than the expected value of your current baseline (which might be a simple rules engine, or a manual review process), the model is a failure, regardless of its statistical significance.

**Hard vs. Soft ROI.** Distinguish between **hard ROI** (revenue increase, cost reduction, fraud prevented) and **soft ROI** (faster decisions, reduced manual work, better customer experience). Report both: executives care about dollars, teams care about whether the model lightens their work. Example: a fraud model that saves &#36;50K per year (hard) but also cuts analyst investigation time by 30% (soft) has stronger total value than the &#36;50K alone suggests.

**Price each box of the confusion matrix, and deploy only if the model beats the current approach in expected value.**

### The complexity tax

A massive gradient boosting ensemble might beat a simple logistic regression by 0.02 AUC. However, the complex model carries a "complexity tax":
- **Compute cost**: It costs more to train and host.
- **Latency**: It takes longer to generate predictions, which can degrade user experience (e.g., in real-time bidding or search).
- **Maintenance**: It is harder to monitor, debug, and update.

Always establish a simple baseline. If a complex model yields only a marginal improvement over a simple one, deploy the simple one. You should only pay the complexity tax if the expected business value of the accuracy bump far exceeds the operational costs.

**A small accuracy gain must pay for the compute, latency, and maintenance it adds.**

### Interpretability constraints

If a customer is denied a loan or a medical claim, the business must explain exactly why. "The neural network said so" is not an explanation. In highly regulated domains (finance, healthcare, insurance), deploying a "black-box" model is often illegal or ethically unacceptable.

In these environments, an interpretable model (like logistic regression, decision trees, or generalized additive models) with an AUC of 0.82 will always win against a deep neural network with an AUC of 0.87. Evaluate whether your use case requires intrinsic explainability before exploring complex architectures.

**Where decisions must be explained, explainability is a requirement, not a tie-breaker.**

### Offline vs. online performance

Good offline metrics (AUC, MAE, NDCG) are a ticket to run an A/B test, nothing more. The ultimate evaluation is whether the model actually moves the core business KPIs (revenue, retention, conversion rate) in a live environment.

Offline metrics often diverge from online reality due to:
- **Feedback loops**: The model's predictions change user behavior in ways historical data cannot capture.
- **Latency**: The new model is more accurate but slower, causing users to abandon the page.
- **Cannibalization**: The model increases clicks on one feature but decreases them on a more profitable one.

Never consider an evaluation complete until the model has proven its value in a randomized controlled trial (A/B test) against the production baseline.

**Offline metrics earn a live test; the live business KPI gives the verdict.**

### Time-to-value

Do not assume day-one performance persists indefinitely. Factor in:

- **Ramp-up period**: users need time to trust the model. A recommendation system might show weak engagement for weeks until users learn the interface. Budget 1-3 months for adoption.
- **Maintenance costs**: retraining costs compute and engineer time. Monitoring requires infrastructure. A model with 10% higher accuracy but 3× the maintenance burden may have worse long-term ROI.
- **Drift**: performance degrades without retraining. If your fraud model requires weekly retraining to stay effective, include that recurring cost.

Project ROI over 12-24 months, not launch day. A simpler model with stable performance often beats a complex one that requires constant tuning.

**Judge a model over its lifetime, including ramp-up, retraining, and drift, not on launch day.**

### Custom metrics

A missed fraud case costs a chargeback. A false alert costs a few minutes of an analyst's time. Accuracy and F1 treat those two errors as equal, and in practice they rarely are. When the business cost of a false negative is fundamentally different from a false positive, you need cost-sensitive evaluation.

**Try the simple options first.** Before building a custom metric, check whether sklearn's built-in mechanisms are enough. `class_weight` (available in `LogisticRegression`, `SVC`, `RandomForestClassifier`, etc.) lets you set per-class weights that modify the training loss. For example, `class_weight={0: 1, 1: 50}` encodes a 50:1 cost ratio directly. `sample_weight` allows per-sample weighting in both training and evaluation. These handle many cost-sensitive scenarios without writing any custom code.

**When to build a custom metric:**

- A false negative costs 100× more than a false positive (or vice versa) and F-beta does not capture the ratio well enough.
- The business cares about a quantity that no standard metric measures (e.g., revenue impact per prediction, time-to-detection).
- You need to combine multiple signals into a single optimization target (e.g., revenue-weighted accuracy). For constraints like latency, the standard approach is to treat them as satisficing metrics (must be below a threshold) and optimize accuracy separately, rather than combining them into one formula.

**How to build one:**

1. **Write down the cost matrix.** Assign a concrete cost (dollars, hours, risk) to each cell of the confusion matrix. If you cannot quantify it, estimate the ratio. "A missed fraud case costs roughly 50× more than a false alert" is enough.
2. **Define the formula.** `Weighted cost = (FN × cost_fn) + (FP × cost_fp)`. Minimize this. With our prices, the model costs 35 × &#36;200 + 45 × &#36;10 = &#36;7,450 per 1,000 transactions, against 90 × &#36;200 = &#36;18,000 for the lazy model. This assumes correct predictions (TP, TN) have zero or equal cost. If a true positive has direct value (e.g., revenue from an approved loan), include those terms too. For regression, replace the uniform loss with a domain-specific penalty (e.g., asymmetric loss that penalizes underestimates more than overestimates).
3. **Make it a scorer.** Wrap it so your training framework can optimize against it (e.g., `sklearn.metrics.make_scorer`). If the metric is not differentiable, use it for evaluation and cross-validation, and optimize a differentiable proxy during training.
4. **Validate it against intuition.** Compute the custom metric on a few examples where you know the right answer. If the metric disagrees with human judgment, the cost model is wrong. Fix the costs, not the judgment.

**Keep the standard metrics alongside it.** A custom metric optimizes for business value, but standard metrics (precision, recall, MCC) remain your sanity check. If the custom metric improves while MCC drops, something is off.

**When errors have different prices, turn the cost matrix into the metric, and keep the standard metrics as a sanity check.**

---

## Common pitfalls

- **Trusting accuracy on imbalanced data.** 92% accuracy on a 91%-majority dataset is the accuracy paradox. Compare to the [baseline](#part-1-every-classification-metric-counts-boxes-in-one-table) and add a minority-class metric.
- **Using AUC-ROC when positives are rare.** FPR dilution inflates it. Use AUC-PR (see [AUC-PR](#auc-pr-stays-honest-when-positives-are-rare)).
- **Splitting without groups or time.** Repeated entities and time series leak across random splits. Use `GroupKFold` or `TimeSeriesSplit`.
- **Tuning on the test set.** It inflates every metric. Tune on validation folds and touch the test set once.
- **Celebrating a 0.99.** On a non-trivial problem, suspect leakage first (see [Part 6](#part-6-a-number-needs-context-before-it-means-anything)).
- **Testing on a different class balance than production.** Precision, recall, and F1 will shift when the ratio changes.
- **Optimizing MAPE when targets can be zero.** It divides by zero and explodes. Use it for reporting only.
- **Running a plain t-test on CV fold scores.** The scores are not independent. Use the corrected resampled t-test (see [Statistical significance](#statistical-significance)).
- **Skipping the multiple-comparison correction.** Ten models means 45 pairwise tests and about two false positives. Apply Holm.
- **Mistaking significance for importance.** A p-value of 0.01 with a negligible Cohen's d is real but irrelevant.
- **Calling an evaluation done offline.** Offline metrics earn an A/B test. The live business KPI is the final judge (see [Offline vs. online performance](#offline-vs-online-performance)).

---

## Recap

- Start from the confusion matrix. Every classification metric counts some of its four boxes.
- Compute a baseline before anything else, so you know what "good" means.
- Select models with threshold-independent metrics: AUC-ROC for balanced data, AUC-PR for rare positives, MCC when in doubt, and log loss when probabilities matter.
- Set the threshold from the cost of errors: recall when misses hurt, precision when false alarms hurt, F1 when both matter.
- For regression, default to MAE, add RMSE when big misses hurt, and compare the two.
- For ranking, measure position: MRR for one answer, MAP for binary relevance, NDCG for graded relevance. Watch coverage and diversity too.
- Read every number against the baseline, the slices, and the standard deviation.
- Use learning, validation, calibration, and gains curves to decide what to try next.
- Compare models with paired tests, correct for multiple comparisons, and report effect size.
- Judge the deployed model by expected value, complexity, interpretability, and live A/B results.
- When errors have different costs, write down the cost matrix and build a custom metric, but keep the standard metrics beside it.

---

## Exercise

A second fraud model, on the same 1,000 transactions, catches 70 of the 90 frauds and raises 130 false alarms. Compute its accuracy, precision, recall, F1, and MCC by hand, then check them with `sklearn.metrics`. Using the prices from [Expected value](#expected-value-ev) (&#36;10 per review, &#36;200 per missed fraud), how much does it save per 1,000 transactions compared with no model? Is it better or worse than our model, which saves &#36;10,000, and does its F1 agree with that verdict?

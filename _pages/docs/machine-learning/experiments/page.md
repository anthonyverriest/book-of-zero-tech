---
layout: post
title: "Experiments: run rigorous ML experiments"
nav_order: 4
---

Same model, same data, three runs: 0.89, 0.85, 0.87. You have probably seen this happen. The model did not change, but the score did. So which number do you put in the report? The real question behind it: how do you produce an ML result that you can explain, that others can challenge, and that anyone can reproduce?

We start with a smaller one: how do you get the same number twice? Once a single run is repeatable, we can ask whether it is honest, then whether it is robust, then whether it beats the alternatives.

Our example runs through the whole guide. A payments team trains an XGBoost classifier to flag fraudulent transactions (`is_fraud`), scored with ROC AUC. In five parts, we make one run reproducible, split the data honestly, move every parameter into a config, track hundreds of runs, and then run the full experiment from baselines to ablation. The examples use binary classification with scikit-learn (`roc_auc`, `stratify`, `predict_proba`). The principles apply to regression and multi-class too. Swap in the metric and splitting strategy that fit your task.

---

## On this page

- [Key concepts](#key-concepts)
- [Resources](#resources)
- [Part 1: A result you cannot reproduce is a result you cannot defend](#part-1-a-result-you-cannot-reproduce-is-a-result-you-cannot-defend)
  - [Source control](#source-control)
  - [Data immutability](#data-immutability)
  - [Seeds](#seeds)
  - [Environment pinning](#environment-pinning)
  - [Determinism boundaries](#determinism-boundaries)
- [Part 2: The split decides what your score can prove](#part-2-the-split-decides-what-your-score-can-prove)
  - [Three sets, three purposes](#three-sets-three-purposes)
  - [No leakage](#no-leakage)
  - [Group-aware splits](#group-aware-splits)
  - [Early stopping](#early-stopping)
- [Part 3: A config file is the single record of what a run did](#part-3-a-config-file-is-the-single-record-of-what-a-run-did)
  - [Config structure](#config-structure)
  - [Config model](#config-model)
- [Part 4: Tracking turns two hundred runs into answerable questions](#part-4-tracking-turns-two-hundred-runs-into-answerable-questions)
  - [Autologging](#autologging)
  - [Explicit logging](#explicit-logging)
  - [Organizing runs](#organizing-runs)
- [Part 5: An experiment runs in a fixed order](#part-5-an-experiment-runs-in-a-fixed-order)
  - [Single run](#single-run)
  - [Baselines](#baselines)
  - [Error analysis](#error-analysis)
  - [Hyperparameter search](#hyperparameter-search)
  - [Ablation study](#ablation-study)
- [Common pitfalls](#common-pitfalls)
- [Recap](#recap)
- [Exercise](#exercise)

---

## Key concepts

- **Experiment**: a question you are trying to answer ("does model A beat model B?", "does feature X help?"). One independent variable, one fixed evaluation protocol.
- **Run**: a single execution with a fixed configuration. An experiment produces many runs.
- **Ablation**: removing one component at a time to measure its individual contribution. If performance drops, the component matters.
- **Seed**: the starting state for random number generators. Fixing seeds makes stochastic processes repeatable.
- **Baseline**: a reference model that sets the performance floor and bar. A trivial baseline (e.g., predict the majority class) proves the features carry signal; a simple baseline (e.g., logistic regression) proves the added complexity of a fancier model is justified.
- **Config-driven experiment**: all parameters live in configuration files. The config is the single source of truth for what a run did.
- **Data leakage**: information from the validation or test set reaching training. It makes results look better than they will be in production.
- **Validation set vs. test set**: the validation set helps you make decisions; the test set grades the final decision, once.
- **OOF (out-of-fold) predictions**: predictions for each training row made by the model that did not see that row during cross-validation.

---

## Resources

<details class="boz-resource">
  <summary><code>baseline.example.yaml</code></summary>

{% highlight yaml %}
{% include_relative baseline.example.yaml %}
{% endhighlight %}
</details>

<details class="boz-resource">
  <summary><code>config.example.py</code></summary>

{% highlight python %}
{% include_relative config.example.py %}
{% endhighlight %}
</details>

<details class="boz-resource">
  <summary><code>data_splitting.example.py</code></summary>

{% highlight python %}
{% include_relative data_splitting.example.py %}
{% endhighlight %}
</details>

<details class="boz-resource">
  <summary><code>train.example.py</code></summary>

{% highlight python %}
{% include_relative train.example.py %}
{% endhighlight %}
</details>

<details class="boz-resource">
  <summary><code>test.example.py</code></summary>

{% highlight python %}
{% include_relative test.example.py %}
{% endhighlight %}
</details>

<details class="boz-resource">
  <summary><code>baselines.example.py</code></summary>

{% highlight python %}
{% include_relative baselines.example.py %}
{% endhighlight %}
</details>

<details class="boz-resource">
  <summary><code>hparam_search.example.py</code></summary>

{% highlight python %}
{% include_relative hparam_search.example.py %}
{% endhighlight %}
</details>

<details class="boz-resource">
  <summary><code>ablation.example.sh</code></summary>

{% highlight bash %}
{% include_relative ablation.example.sh %}
{% endhighlight %}
</details>

---

## Part 1: A result you cannot reproduce is a result you cannot defend

Picture a colleague who asks, "Why is the fraud model at 0.89?" A good answer points to a config, a commit, a dataset version, and ten seeds' worth of scores. A bad answer is "that's what the notebook said."

Rigor is what lets you give the good answer. The goal is not to track everything. It is to track enough that any result survives three tests: you can explain it, others can challenge it, and anyone can reproduce it.

Reproducibility comes first, because the other two depend on it. Think of it as a contract with five clauses: source control, data immutability, seed control, environment pinning, and awareness of determinism boundaries. Break any one and the contract fails.

### Source control

Say you tweak a feature function, forget to commit, and launch a run. MLflow logs the git commit hash automatically, so the run looks traceable. It is not. The hash points to the last commit, not to the code that ran.

This is the **dirty working tree** vulnerability. The logged hash is a false guarantee whenever you run with uncommitted changes.

You have two ways to close the gap. Fail the run if `git status --porcelain` is not empty. Or explicitly log the `git diff` as an MLflow artifact, so the uncommitted changes travel with the run.

**A commit hash identifies your code only if nothing was uncommitted when the run started.**

### Data immutability

Pinning code and environment is useless if the data underneath changes. Imagine overwriting `features_v1.parquet` with a "fixed" version. Every prior experiment that relied on it is now permanently irreproducible.

So treat training data as immutable. Use append-only storage or a data versioning tool like DVC to enforce it. If a dataset must change, write it as `features_v2.parquet` and update the experiment configuration.

**Never overwrite a dataset; write a new version and point the config at it.**

### Seeds

Train the fraud model twice without fixed seeds and you get different scores. Random forests sample features randomly. Data shuffling changes the split order. Stochastic estimators start from different states. Seeds anchor the random number generators to a known starting point.

Control randomness by passing `random_state` explicitly to every estimator and splitter. Scikit-learn's randomness flows through numpy, and each `random_state` parameter creates an independent random number generator scoped to that object. There is no shared global state and no accidental coupling between components:

```python
from sklearn.model_selection import StratifiedKFold
from sklearn.ensemble import RandomForestClassifier

cv = StratifiedKFold(n_splits=cfg.cv_splits, shuffle=True, random_state=seed)
model = RandomForestClassifier(n_estimators=500, random_state=seed)
```

You may have seen `np.random.seed()` at the top of scripts. Avoid it. Global seeding is a legacy pattern that modifies shared state and causes unintended side effects across unrelated components.

`PYTHONHASHSEED` also shows up in reproducibility guides. It controls Python set iteration order, which is irrelevant for scikit-learn, whose randomness flows through numpy.

Now the problem is solved, right? Same seed, same number, every time. Here is where the expectation fails. A fixed seed makes one run repeatable. It does not tell you whether the result is robust. Seed 42 might give 0.89 and seed 123 give 0.85. You have made one point reproducible, not shown where the score really sits.

So we go from one seed to many. To make a defensible claim, you need the distribution.

**Running multiple seeds is mandatory for publishable results.** Even 3–5 seeds is often insufficient: conclusions can flip with different seeds, and statistical power is too low to detect real differences.

Here is how the scores add up. With 5-fold cross-validation, one seed gives 5 scores, one per fold. Two seeds give 10. Ten seeds give 10 × 5 = 50. In general, K-fold CV × S seeds gives K × S paired scores.

Fifty scores sounds like plenty of evidence. Here is a subtlety that trips people up: these scores are **not independent**. Training sets overlap across folds, and seeds reuse the same data. Two folds that share 75% of their training rows will tend to agree, so 50 scores carry less information than 50 independent measurements would.

Why does that matter? A plain paired t-test or Wilcoxon test on all 50 scores from 10 seeds × 5 folds understates the variance and produces too many false positives. Use the corrected resampled t-test (Nadeau & Bengio) on those scores, as shown in [Evaluation: statistical significance]({{ site.baseurl }}/docs/machine-learning/evaluation/page/#statistical-significance).

<p align="center">
  <img src="{{ "/assets/images/plots/seed_variance.svg" | relative_url }}" alt="Box plot showing ROC AUC score distributions across 10 seeds for three models">
</p>

How many seeds do you need? It depends on what is at stake:

| Setting | Minimum seeds | Paired scores (5-fold CV) |
|---------|--------------|-------------------------------|
| Exploratory | 5 | 25 |
| Publishable comparison | 10 | 50 |
| High-stakes or noisy | 20+ | 100+ |

A quick check tells you whether you have enough. Say model A scores 0.871 ± 0.012 across seeds and model B scores 0.876 ± 0.011. The difference, 0.005, is smaller than either standard deviation. That comparison is inconclusive, which makes sense, because the seed alone moves each model by more than the gap between them.

If the standard deviation across seeds is large relative to the difference between models, add more seeds or reconsider the experimental design. See [Evaluation: statistical significance]({{ site.baseurl }}/docs/machine-learning/evaluation/page/#statistical-significance) for guidance on minimum sample sizes and statistical tests to determine whether a difference is real.

**One seed makes a run repeatable; many seeds tell you where the score really lives.**

### Environment pinning

Seeds fix the randomness. They do not fix the software. Pin everything that can change between machines or over time:

- **Python version**: specify in `pyproject.toml` and the Dockerfile (`ARG PYTHON_VERSION=3.14`).
- **Dependencies**: use `uv.lock`. The Dockerfile enforces this with `uv sync --locked`. If the lockfile is missing or stale, the build fails.
- **scikit-learn version**: a minor version upgrade can change default hyperparameters, convergence criteria, or internal random number consumption. A model trained on 1.4 may not reproduce identically on 1.5 even with the same seed. The lockfile handles this, but document the version in your experiment logs.

The Dockerfile from the [Docker guide]({{ site.baseurl }}/docs/containerization/docker/page/) already enforces Python version and dependency pinning via `uv sync --locked`.

**Seeds pin the randomness; the lock file and the Python version pin everything the randomness runs on.**

### Determinism boundaries

Full determinism is not always achievable, and sometimes not worth the cost. Know where it breaks:

- **Nested parallelism**: `RandomForestClassifier` with `random_state` set is deterministic regardless of `n_jobs`. But nesting parallel calls, for example `GridSearchCV(n_jobs=-1)` wrapping `RandomForestClassifier(n_jobs=-1)`, can produce non-deterministic results because the joblib worker scheduling is not guaranteed to be consistent. Fix by parallelizing at one level only (typically the outer loop).
- **Floating-point non-associativity**: `(a + b) + c ≠ a + (b + c)` in floating point. Different hardware or parallelism strategies can change the order of operations. This is typically negligible for classical ML but can compound in iterative algorithms (gradient boosting over many rounds, iterative SVD).

**Practical stance**: enforce seeds (per-estimator `random_state` on every estimator and splitter), pin the environment (see [Environment pinning](#environment-pinning)), and accept that bit-exact reproduction across different hardware is sometimes infeasible. Document the platform when it matters.

**Aim for the same distribution of scores everywhere, and bit-exact results only where the hardware allows it.**

---

## Part 2: The split decides what your score can prove

A reproducible run can still be dishonest. You have probably met a model that scored beautifully in the notebook and collapsed in production. Very often the culprit is the split. The model was learning from information it should never have seen.

The split protocol determines what evidence you can claim. Get it right first, and everything downstream inherits that honesty.

### Three sets, three purposes

Think of a student preparing for an exam. Homework is where they learn. Practice tests are where they check which study method works. The final exam is taken once and counts. If they saw the final exam in advance, their grade says nothing.

ML has the same three roles:

- **Training set**: used to fit the model. Every parameter update happens here.
- **Validation set**: used to select hyperparameters and compare model variants. In cross-validation, each fold's held-out portion serves as the validation set, so no separate validation split is needed.
- **Test set**: held out from all decisions. Evaluated once, at the end, on the final selected configuration only. If you use the test set to pick between models or tune hyperparameters, it becomes a second validation set and your reported metrics are optimistically biased.

Split before anything else. The test set must be created before any preprocessing, feature engineering, or model training. The snippets below use `cfg`, a Pydantic config object defined in [Part 3](#part-3-a-config-file-is-the-single-record-of-what-a-run-did):

```python
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=cfg.data.test_size, stratify=y, random_state=cfg.seeds[0]
)
```

`train_test_split` shuffles the data before splitting (`shuffle=True` by default). This is correct for i.i.d. tabular data. Without shuffling, if the dataset is sorted by date, by class, or by source, the split is biased and the test set is not representative.

`stratify=y` goes further. It shuffles while preserving the class distribution in both sets, so neither set ends up with a skewed label ratio. Here is why that matters for fraud. Say 2% of 10,000 transactions are fraud, so 200 frauds. A 20% test set should hold about 40 of them. A plain random split could give 30 or 50, which changes what the test score means. Stratifying pins it at 40. When `stratify` is set, shuffle is always on.

`random_state` controls the shuffle order. The test split uses a fixed seed (`cfg.seeds[0]`), so the test set is identical across all seed runs. Comparisons are fair because every model variant is evaluated against the same held-out data.

All cross-validation, hyperparameter search, and model comparison happens on `(X_train, y_train)` only. The test set `(X_test, y_test)` is not touched until final evaluation.

Time-series or sequential data is the exception: shuffling must be disabled. Random splits create future leakage, where the model trains on future data and predicts the past. Use time-based splits instead: train on data before a cutoff date, validate and test on data after. scikit-learn provides `TimeSeriesSplit` for cross-validation on temporal data.

**Create the test set first, stratified and seeded, and do not touch it again until the final evaluation.**

### No leakage

Suppose you standardize your features, then split. It looks harmless. But the scaler computed its mean and variance from every row, including the test rows. A sliver of the test set is now baked into training.

That is **data leakage**: information from the validation or test set bleeds into training, and the model gets answers it would not have in production. It is the most common source of overly optimistic results. Common sources:

- **Preprocessing fit on the full dataset**: fitting a scaler, encoder, or imputer on all data before splitting leaks test-set statistics into training.
- **Feature selection on the full dataset**: selecting features based on correlation with the target using all data gives the model advance knowledge of validation and test patterns.
- **Target encoding without proper folds**: encoding categorical features using target means from the full dataset leaks the target into every fold.

The fix is a scikit-learn `Pipeline`, which bundles preprocessing and model into a single estimator. When passed to `cross_validate` or `GridSearchCV`, the pipeline fits preprocessing on each training fold and transforms the validation fold. No leakage:

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("model", XGBClassifier(**cfg.model.params, random_state=seed)),
])

# cross_validate fits the pipeline on each training fold
# and evaluates on the held-out fold — preprocessing is inside the loop
results = cross_validate(pipe, X_train, y_train, cv=cv, scoring=cfg.scoring)
```

What if your preprocessing is too complex for a pipeline, for example heavy feature engineering with external data? Use the training indices from each fold explicitly and transform the validation indices separately. The rule is the same: fit on train, transform on validation, never the reverse.

**Anything that learns from data, including a scaler, must learn from the training fold only.**

### Group-aware splits

Fraud data has a trap. Each customer makes many transactions. A random split puts some of customer A's transactions in training and the rest in test. The model learns customer A's habits rather than the fraud signal, then "recognizes" customer A at test time.

The same thing happens whenever a dataset has multiple samples per entity: multiple images per patient, multiple transactions per user, multiple readings per sensor. A random split scatters the entity across train and test, and the model memorizes entity-specific patterns rather than learning generalizable ones. Reported metrics can be inflated by 5–30%.

`train_test_split` does not support group constraints. Use `GroupShuffleSplit` for the initial split and `GroupKFold` for cross-validation:

```python
from sklearn.model_selection import GroupShuffleSplit, GroupKFold

# Initial split respecting groups
gss = GroupShuffleSplit(n_splits=1, test_size=cfg.data.test_size, random_state=cfg.seeds[0])
train_idx, test_idx = next(gss.split(X, y, groups=groups))

X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

# Cross-validation respecting groups
cv = GroupKFold(n_splits=cfg.cv_splits, shuffle=True, random_state=seed)  # shuffle: scikit-learn >= 1.6
results = cross_validate(pipe, X_train, y_train, cv=cv, groups=groups.iloc[train_idx], scoring=cfg.scoring)
```

If your data has no natural grouping (each row is an independent observation), standard `train_test_split` and `StratifiedKFold` are correct. When groups and class imbalance both matter, use `StratifiedGroupKFold`.

**When entities repeat, split by entity, so the test set contains only customers the model has never seen.**

### Early stopping

Iterative algorithms like gradient boosting (XGBoost, LightGBM) or deep learning keep improving on training data long after they stop improving on new data. **Early stopping** watches a separate validation set inside the training loop and halts training before overfitting begins.

That set is distinct from the validation folds used in cross-validation for model selection. Early stopping uses a dedicated split within each training fold.

Why not reuse the CV validation fold? Because the model would stop at the iteration that scores best on that fold, and the fold score would be biased upward. You would be grading the student on the same quiz they used to decide when to stop studying. Carve an inner early-stopping split out of each training fold instead.

`cross_validate` cannot do this for you. A `Pipeline` does not transform an `eval_set` passed as a fit parameter, and the inner split has to be recomputed per fold. Iterate over the folds manually:

```python
scorer = get_scorer(cfg.scoring)
cv = StratifiedKFold(n_splits=cfg.cv_splits, shuffle=True, random_state=seed)

for fold, (train_idx, val_idx) in enumerate(cv.split(X_train, y_train)):
    X_fold_train, X_fold_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
    y_fold_train, y_fold_val = y_train.iloc[train_idx], y_train.iloc[val_idx]

    # Inner split used only to decide when to stop
    X_fit, X_es, y_fit, y_es = train_test_split(
        X_fold_train, y_fold_train, test_size=0.1, stratify=y_fold_train, random_state=seed,
    )

    scaler = StandardScaler()
    X_fit_scaled = scaler.fit_transform(X_fit)
    X_es_scaled = scaler.transform(X_es)
    X_fold_val_scaled = scaler.transform(X_fold_val)

    model = XGBClassifier(**cfg.model.params, random_state=seed, early_stopping_rounds=20)
    model.fit(
        X_fit_scaled, y_fit,
        eval_set=[(X_es_scaled, y_es)],
        verbose=False,
    )

    score = scorer(model, X_fold_val_scaled, y_fold_val)  # fold never seen during fitting
```

The full early stopping CV loop is in `data_splitting.example.py` (see [Resources](#resources)).

Never use the final test set for early stopping. That turns the test set into a validation set and leaks information directly into the model's stopping criteria.

**Early stopping needs its own inner split; any set used to stop training can no longer grade it.**

**So far:** a run is reproducible when code, data, seeds, and environment are pinned, and robust when it holds across many seeds. It is honest when the test set is split first, preprocessing stays inside the folds, entities never straddle the split, and early stopping uses its own inner set.

---

## Part 3: A config file is the single record of what a run did

Picture a training script with `max_depth=6` on line 212 and `learning_rate=0.1` on line 340. Three weeks later, which values produced the result in your slide deck? Hard-coded hyperparameters buried in a script are impossible to track and quick to forget.

Externalizing parameters into YAML files fixes this. Each config is a complete, diffable record of what a run did. Pydantic validates on load, provides IDE autocompletion, and serializes to a dict for MLflow. Both Pydantic and PyYAML are already transitive dependencies of MLflow, so there is nothing extra to install.

### Config structure

Use one YAML file per experiment configuration. Each file is a complete, self-contained record of what a run did: readable, diffable, and loggable as an MLflow artifact:

```yaml
# configs/baseline.yaml
experiment_name: model_comparison

seeds: [42, 123, 456, 789, 1024, 2048, 3333, 5555, 7777, 9999]

data:
  path: data/processed/features_v1.parquet
  target: is_fraud
  test_size: 0.2

model:
  name: xgboost
  params:
    n_estimators: 500
    max_depth: 6
    learning_rate: 0.1

cv_splits: 5
scoring: roc_auc
```

A production-ready version with additional parameters is in `baseline.example.yaml` (see [Resources](#resources)).

For ablation variants, copy the baseline and change one thing. Yes, that duplicates most of the file. That is fine: readability and reproducibility matter more than DRY for experiment configs. Two files that differ by one line make the experiment's one variable visible in a single `diff`.

**One complete YAML file per configuration means "what did this run do?" is answered by opening one file.**

### Config model

What happens if you typo `test_size: 2.0`? Without validation, you find out halfway through a training run. Define the config as a Pydantic model instead, and invalid configs fail immediately on load with a clear error:

```python
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class DataConfig(BaseModel):
    path: str
    target: str
    test_size: float = Field(default=0.2, gt=0, lt=1)
    drop_columns: list[str] = []
    data_version: str = "v1"


class ModelConfig(BaseModel):
    name: str
    params: dict[str, Any] = {}


class ExperimentConfig(BaseModel):
    experiment_name: str
    seeds: list[int] = Field(default=[42, 123, 456, 789, 1024], min_length=1)
    data: DataConfig
    model: ModelConfig
    cv_splits: int = Field(default=5, ge=2)
    scoring: str = "roc_auc"

    @classmethod
    def from_yaml(cls, path: str) -> "ExperimentConfig":
        raw = yaml.safe_load(Path(path).read_text())
        return cls(**raw)
```

The complete config module with CLI validation is in `config.example.py` (see [Resources](#resources)). Load and use:

```python
config_path = "configs/baseline.yaml"
cfg = ExperimentConfig.from_yaml(config_path)

# IDE autocomplete — cfg.model.name, cfg.data.path, cfg.scoring
# Log model params to MLflow (flat dict, MLflow-compatible)
mlflow.log_params(cfg.model.params)
# Log the config file itself as an artifact (reproduces the run)
mlflow.log_artifact(config_path)
```

Run experiments by pointing to a config file:

```bash
python train.py --config configs/baseline.yaml
python train.py --config configs/ablation_no_text.yaml
```

What validation does not tell you: whether the values are sensible. `test_size: 0.99` passes the `gt=0, lt=1` check and still leaves you almost nothing to train on.

**Validate the config on load, so a typo fails in one second instead of one hour into training.**

---

## Part 4: Tracking turns two hundred runs into answerable questions

After a week of experiments on the fraud model you might have two hundred runs. Which one used text features? Which seed scored 0.87? A spreadsheet will not keep up.

MLflow records parameters, metrics, and artifacts for every run. The tracking server provides a UI for comparing runs and a programmatic API for querying results. Think of it as a lab notebook that writes itself while you work.

### Autologging

For scikit-learn, `mlflow.sklearn.autolog()` captures parameters, metrics, and model artifacts automatically. That includes child runs for `GridSearchCV` and `RandomizedSearchCV`, where each parameter combination is tracked as a nested run:

```python
import mlflow
from sklearn.model_selection import GridSearchCV
from xgboost import XGBClassifier

mlflow.sklearn.autolog(max_tuning_runs=20)

mlflow.set_experiment(cfg.experiment_name)

with mlflow.start_run(run_name=f"{cfg.model.name}_gridsearch"):
    estimator = XGBClassifier(**cfg.model.params)
    param_grid = {"max_depth": [3, 6, 9], "learning_rate": [0.01, 0.1, 0.3]}

    search = GridSearchCV(estimator, param_grid, cv=cfg.cv_splits, scoring=cfg.scoring)
    search.fit(X_train, y_train)
    # MLflow logs all param combinations as child runs automatically
```

Watch out for `max_tuning_runs`. It controls how many child runs are logged for hyperparameter searches, and it defaults to 5, which is too low for most experiments. The grid above has 3 × 3 = 9 combinations, so the default would silently drop 4 of them. Set it to match the number of parameter combinations you want to inspect.

Autolog captures estimator parameters (via `get_params(deep=True)`), training metrics, best score, best parameters, and the fitted model artifact. Use autologging with `GridSearchCV` when the search space is small and enumerable. For larger or continuous search spaces, use Optuna (see [Hyperparameter search](#hyperparameter-search)).

**Autolog covers the standard parameters and metrics, as long as `max_tuning_runs` is large enough for your search.**

### Explicit logging

Autolog does not know about your custom metrics, tags, and artifacts. Add explicit logging for those.

One gotcha first: `mlflow.log_params()` only accepts flat dicts. Nested dicts get stringified into unreadable blobs, so log each level explicitly. The snippet below covers the core loop. Config snapshot logging is shown in `train.example.py` (see [Resources](#resources)):

```python
for seed in cfg.seeds:
    with mlflow.start_run(run_name=f"{cfg.model.name}_seed{seed}"):
        mlflow.log_params(cfg.model.params)
        mlflow.log_params({"seed": seed, "model_name": cfg.model.name, "scoring": cfg.scoring})
        mlflow.set_tag("data_version", cfg.data.data_version)

        start_time = time.monotonic()

        model = XGBClassifier(**cfg.model.params, random_state=seed)
        cv = StratifiedKFold(n_splits=cfg.cv_splits, shuffle=True, random_state=seed)

        results = cross_validate(model, X_train, y_train, cv=cv, scoring=cfg.scoring)
        oof_preds = cross_val_predict(model, X_train, y_train, cv=cv, method="predict_proba")[:, 1]

        mlflow.log_metric("training_duration_seconds", time.monotonic() - start_time)
        mlflow.log_metric(f"mean_{cfg.scoring}", results["test_score"].mean())
        mlflow.log_metric(f"std_{cfg.scoring}", results["test_score"].std())

        for i, score in enumerate(results["test_score"]):
            mlflow.log_metric(f"fold_{cfg.scoring}", score, step=i)

        with tempfile.TemporaryDirectory() as tmp_dir:
            oof_path = Path(tmp_dir) / f"oof_seed{seed}.parquet"
            pd.DataFrame({"oof_pred": oof_preds}).to_parquet(oof_path)
            mlflow.log_artifact(str(oof_path))
```

The complete training script is in `train.example.py` (see [Resources](#resources)).

Here is what goes where:

| Category | What | How |
|----------|------|-----|
| Parameters | Seed, model hyperparams, scoring | `mlflow.log_params(...)` or autolog |
| Metrics | CV mean, std, per-fold scores, test metrics, duration | `mlflow.log_metric(...)` or autolog |
| Artifacts | Model, config file, OOF predictions | `mlflow.log_artifact(...)` or autolog |
| Tags | Data version, custom metadata | `mlflow.set_tag(...)` (git hash is auto-logged) |

**Log everything you will want to filter or compare later: the seed, the mean and spread, the per-fold scores, and the predictions.**

### Organizing runs

Structure runs so that comparison is natural:

- **Experiment** = comparable runs on the same data. One MLflow experiment per task where runs share the same input dataset and evaluation protocol (e.g., `feature_selection_ablation`, `model_comparison_v2`). The organizing principle is input data consistency: if runs use different datasets, they belong in different experiments.
- **Run** = one execution. For seed sweeps, each run corresponds to one seed × one configuration. For hyperparameter searches, use a parent run with nested child runs (one per trial). The MLflow UI renders the hierarchy, so you can compare trials within a search and compare searches within an experiment.
- **Params** = inputs that affect model behavior. Log seed, model hyperparameters, and scoring metric with `log_param()`. These are immutable per run and define what the run did.
- **Tags** = metadata for filtering. Use tags for data version and any cross-cutting attribute you want to filter or group by later. Git hash is auto-logged by MLflow as `mlflow.source.git.commit`, so there is no need to set it manually.
- **Run name** = human-readable label. Use a descriptive pattern like `xgboost_seed42` so the MLflow UI is scannable without clicking into each run.

What a tag does not tell you: what the data contained. `mlflow.set_tag("data_version", "v1")` is a label, not a guarantee. For true data reproducibility, use a data versioning tool like DVC alongside your experiment tracker so that any result can be traced back to the exact dataset that produced it.

Avoid dumping unrelated runs into the same MLflow experiment. It makes the UI unusable and comparisons meaningless. When in doubt, create a new experiment. They are cheap.

**One MLflow experiment per dataset and protocol keeps every comparison inside it meaningful.**

**So far:** every parameter lives in a validated YAML file, and every run logs its config, seed, scores, and predictions to MLflow, grouped by dataset. We have all the ingredients. Next, we put them in order.

---

## Part 5: An experiment runs in a fixed order

This part follows the fraud model from its first run to the ablation table a reviewer will read. Each step answers a question the previous one leaves open.

### Single run

The minimal loop: load config, train, evaluate, log.

```bash
python train.py --config configs/baseline.yaml
```

A single run validates that the pipeline works end-to-end. It is not evidence of anything: one seed, one configuration, one data split.

**A single run proves the pipeline works, nothing more.**

### Baselines

The fraud model scores 0.85 AUC. Is that good? You cannot answer until you know what a dumb model scores. Before comparing complex models, establish what "good" means. Two baselines set the floor and the bar:

- **Trivial baseline**: `DummyClassifier(strategy="most_frequent")` predicts the majority class. Any model must beat this. If it does not, the features carry no signal or there is a data problem.
- **Simple baseline**: `LogisticRegression` (or `Ridge` for regression). A tuned linear model is often competitive. If a complex model beats logistic regression by less than the standard deviation across seeds, the added complexity is not justified.

The trivial baseline holds a surprise for fraud data. With 2% fraud, predicting "not fraud" for everything is 98% accurate. That is why we score with AUC: a model that ranks every transaction the same gets 0.5, no matter how imbalanced the data is.

```python
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

baselines = {
    "dummy": DummyClassifier(strategy="most_frequent"),
    "logistic": Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000, random_state=seed)),
    ]),
}

# Run inside the seed loop (for seed in cfg.seeds:)
for name, model in baselines.items():
    cv = StratifiedKFold(n_splits=cfg.cv_splits, shuffle=True, random_state=seed)
    scores = cross_val_score(model, X_train, y_train, cv=cv, scoring=cfg.scoring)
    print(f"{name}: {scores.mean():.4f} ± {scores.std():.4f}")
```

The full baseline script with MLflow logging and multi-seed evaluation is in `baselines.example.py` (see [Resources](#resources)).

Run baselines first. If a complex model cannot beat a tuned logistic regression by a meaningful margin, the complexity is not worth the cost.

**A score means something only next to what a trivial model and a simple model achieve on the same split.**

### Error analysis

The fraud model is stuck at 0.85 AUC. The tempting move is to launch a bigger hyperparameter search. Resist it for an hour.

The model might be failing on a single error category that no amount of tuning will fix, but that a new feature or data cleaning step would resolve in minutes. Before tuning hyperparameters or adding features, understand what the model gets wrong. Error analysis tells you where the ceiling is and what to try next.

The method: take your baseline model's predictions on the validation set and sample ~100 misclassified examples. For each, write down a short error category: the reason the model got it wrong. Then count:

| Error category | Count | % of errors | Ceiling if fixed |
|----------------|-------|-------------|------------------|
| Missing address data | 34 | 34% | +0.03 AUC |
| Mislabeled ground truth | 22 | 22% | +0.02 AUC |
| Rare merchant category | 18 | 18% | +0.01 AUC |
| Ambiguous cases | 15 | 15% | — |
| Other | 11 | 11% | — |

The "ceiling if fixed" column is the key insight. If 34% of errors come from missing address data, fixing that category (imputation, new feature, data collection) can improve performance by roughly that proportion of the current error. It is a ceiling, not a promise: fixing a category perfectly is the best case.

Hyperparameter tuning, by contrast, optimizes within the current representation. It cannot fix a missing feature or a labeling problem.

The table tells you what to try next:

- **Missing or noisy features** → feature engineering or data collection, not more tuning.
- **Mislabeled examples** → data cleaning before any model changes.
- **Ambiguous cases** → irreducible error; do not chase this.
- **Systematic failure on a subgroup** → stratified evaluation, targeted features, or more training data for that subgroup.

Use `sklearn.metrics.confusion_matrix` for a quick overview, then inspect actual examples for the error categories that matter most. Log the error analysis table as an MLflow artifact. It documents the reasoning behind your next experiment, not only its result.

**Count what the model gets wrong before you tune, because the biggest error category often needs data, not hyperparameters.**

### Hyperparameter search

Once the pipeline works and baselines are established, hyperparameter search finds the configuration that best exploits the data.

Search is not training. It is meta-optimization over training runs. That distinction decides where things live: the search space lives in code (distributions cannot be expressed in YAML), and the config file holds fixed parameters. The full lifecycle has three steps:

1. **Search**: Optuna explores the search space, and MLflow logs every trial.
2. **Freeze**: write the best params into a new config YAML.
3. **Evaluate**: run the frozen config across all seeds as a single run.

The config records *what worked*. The code defines *how you searched*. Both are logged to MLflow.

#### 1. Search

Use Optuna for Bayesian optimization with MLflow tracking:

```python
def objective(trial):
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.001, 0.3, log=True),
    }

    with mlflow.start_run(nested=True, run_name=f"trial_{trial.number}"):
        mlflow.log_params(params)

        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("model", XGBClassifier(**params, random_state=cfg.seeds[0])),
        ])
        cv = StratifiedKFold(n_splits=cfg.cv_splits, shuffle=True, random_state=cfg.seeds[0])
        scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring=cfg.scoring)
        mean_score = scores.mean()

        mlflow.log_metric(f"val_{cfg.scoring}", mean_score)

    return mean_score

study = optuna.create_study(
    direction="maximize",
    sampler=optuna.samplers.TPESampler(seed=cfg.seeds[0]),
)
study.optimize(objective, n_trials=100)
```

The full search-freeze-evaluate lifecycle is in `hparam_search.example.py` (see [Resources](#resources)).

The inline snippet shows the trial-level logging. In practice, wrap `study.optimize(...)` inside a parent run (`with mlflow.start_run(run_name="hparam_search"):`) so each trial is a nested child. The MLflow UI renders this hierarchy, which makes trials quick to compare. The full nested-run setup is in `hparam_search.example.py` (see [Resources](#resources)).

<p align="center">
  <img src="{{ "/assets/images/plots/optuna_history.svg" | relative_url }}" alt="Hyperparameter search history showing trial scores and running best with plateau annotation">
</p>

#### 2. Freeze

Write the best params to a new config file. This is the reproducible record:

```python
import yaml

best_cfg = cfg.model_copy(deep=True)
best_cfg.model.params = study.best_params

config_path = "configs/best_xgboost.yaml"
Path(config_path).write_text(
    yaml.dump(best_cfg.model_dump(), default_flow_style=False)
)
```

#### 3. Evaluate

Run the frozen config across all seeds to get the validation results you report:

```bash
python train.py --config configs/best_xgboost.yaml
```

Then evaluate the held-out test set. This is the final, unbiased estimate. Use the same pipeline that was used during cross-validation so preprocessing is consistent, and train across all seeds to confirm stability. The `--threshold` flag also evaluates precision, recall, and F1 at the given operating point:

```bash
python test.py --config configs/best_xgboost.yaml --threshold 0.5
```

The core loop fits each seed and scores with `get_scorer(cfg.scoring)`:

```python
scorer = get_scorer(cfg.scoring)
test_scores = []

for seed in cfg.seeds:
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("model", XGBClassifier(**study.best_params, random_state=seed)),
    ])
    pipe.fit(X_train, y_train)
    test_scores.append(scorer(pipe, X_test, y_test))
```

The full held-out evaluation, including thresholded metrics and MLflow logging, is in `test.example.py` (see [Resources](#resources)).

How do you read the result? If the mean test score is substantially lower than the cross-validation score, the model is overfitting to the training distribution. If the standard deviation across seeds is large, the model is unstable.

Either way, do not go back and tune. That turns the test set into a validation set. This held-out score is the final check: it confirms the model generalizes. For classifiers, `test.example.py` evaluates at a given threshold; see [Evaluation: threshold tuning]({{ site.baseurl }}/docs/machine-learning/evaluation/page/#threshold-tuning-and-evaluation) for how to choose that threshold.

A few more things to know about search:

**Small datasets**: when the dataset is too small for a reliable held-out test set (roughly n < 1,000), the holdout estimate has high variance. Use **nested cross-validation** instead: an outer loop evaluates generalization while an inner loop selects hyperparameters. This gives an unbiased performance estimate without sacrificing data. The cost is computational. 5-fold outer × 5-fold inner × 100 trials is expensive, so reserve nested CV for settings where every sample counts.

**Search strategy**: Bayesian optimization (Optuna's TPE sampler) outperforms grid search and random search in most settings, because it focuses trials on promising regions rather than sampling blindly. Random search is a reasonable baseline when the search space is small. Grid search is wasteful: it spends trials on unimportant dimensions.

**Reproducibility**: `TPESampler(seed=...)` makes the search deterministic, but only with sequential execution. Parallel optimization (`n_jobs > 1`) reseeds internally to avoid duplicate suggestions across workers, breaking reproducibility. The search also evaluates each trial on a single seed's CV folds, which adds variance to the selection. The multi-seed evaluation in step 3 guards against lucky picks: if the frozen config degrades across 10 seeds, the search result was not robust.

**Budget**: start with 100 trials and check the optimization history. If the best score plateaus after 30 trials, more trials will not help. If it is still improving at 100 trials, the search space may be too large or the problem too noisy. Count the cost before you start: 100 Optuna trials × 5-fold CV = 500 model fits for the search alone, plus 10 seeds × 5-fold CV = 50 fits for the final evaluation. Start with fewer seeds or trials during exploration and scale up for the final run.

**Search on one seed, freeze the winner in a config, then confirm it across all seeds before the single test-set evaluation.**

### Ablation study

The full fraud system has text features, interaction terms, and a feature selection step. It scores 0.891. Which of those three parts earn their keep? Ablation answers exactly that question: "does this component actually help?"

1. **Start from the full system**: the configuration with all components enabled. This is your control.
2. **Remove one component at a time** and re-run. Each ablation variant changes exactly one thing, so the effect is attributable. This is **leave-one-component-out (LOCO)** ablation, the standard approach.
3. **Run each variant across multiple seeds** (same seeds for all variants).
4. **Compare to the control** using the same metric and statistical test (see [Evaluation: comparing results]({{ site.baseurl }}/docs/machine-learning/evaluation/page/#comparing-results)).

What LOCO does not tell you: interaction effects. If two components are individually weak but jointly critical (synergy), or if one component compensates when another is removed (masquerade), LOCO will miss it. Use a factorial design when you suspect interactions.

Run all variants with a simple loop:

```bash
for config in configs/ablation_*.yaml; do
    python train.py --config "$config"
done
```

A shell runner with config validation is in `ablation.example.sh` (see [Resources](#resources)).

Report ablation results as a table. Each row is a variant, and the columns show the metric mean ± std and the delta from the control. This is the format reviewers expect:

| Variant | AUC (mean ± std) | Δ vs. control | p-value | p (Holm) |
|---------|-------------------|---------------|---------|----------|
| Full system (control) | 0.891 ± 0.012 | — | — | — |
| − text features | 0.864 ± 0.015 | −0.027 | 0.003 | 0.009 |
| − interaction terms | 0.887 ± 0.013 | −0.004 | 0.42 | 0.42 |
| − feature selection | 0.879 ± 0.014 | −0.012 | 0.04 | 0.08 |

Why the last column? Each test has a 5% chance of a false alarm at p < 0.05. Run three tests, and the chance that at least one fires by luck grows to roughly 1 − 0.95³ ≈ 14%. The **Holm correction** pulls that back to 5%.

It looks technical, but it is three multiplications. Sort the raw p-values from smallest to largest: 0.003, 0.04, 0.42. Multiply the smallest by the number of tests (3), the next by 2, the last by 1:

- 0.003 × 3 = 0.009
- 0.04 × 2 = 0.08
- 0.42 × 1 = 0.42

Those are the values in the table. In general, with m tests, the k-th smallest p-value is multiplied by (m − k + 1), and each adjusted value is kept at least as large as the one before it. The smallest p-value gets the strictest treatment, which makes sense, because it is the one most likely to be the lucky winner among several tries.

Now read the table. Only removing text features is significant (0.009 < 0.05). Removing feature selection (p = 0.04 raw, 0.08 corrected) is suggestive, but not yet conclusive.

<p align="center">
  <img src="{{ "/assets/images/plots/ablation.svg" | relative_url }}" alt="Ablation study bar chart showing AUC delta vs control with significance markers">
</p>

For statistical tests and how to read comparison tables, see [Evaluation: comparing results]({{ site.baseurl }}/docs/machine-learning/evaluation/page/#comparing-results).

**Remove one component at a time across the same seeds, and correct for the number of comparisons before you call anything significant.**

**So far:** an experiment starts with one run to prove the pipeline, adds baselines to give scores meaning, uses error analysis to choose what to try, searches and freezes hyperparameters, confirms them across seeds, and ends with an ablation table that says which components matter.

---

## Common pitfalls

- **Single-seed conclusions.** One seed proves nothing. A model can win on seed 42 and lose on seed 123. Always run multiple seeds and report the distribution.
- **Overfitting the validation set.** If you run 200 hyperparameter trials optimizing validation AUC, the best validation AUC is biased upward. The test set must be held out from the entire search process. Evaluate it once, at the end, on the selected configuration only.
- **Comparing across different splits.** If model A was evaluated on a random 80/20 split and model B on 5-fold CV, the comparison is meaningless. Fix the evaluation protocol before comparing.
- **Leakage through preprocessing.** Fitting a scaler, encoder, or imputer on the full dataset before splitting leaks information from the test set into training. All preprocessing must be fit inside the cross-validation loop, on the training fold only.
- **Selective reporting.** Running many experiments and reporting only the best result is p-hacking. Report all variants, including the ones that did not work. Failed experiments are information.
- **Confounding seed with configuration.** If you change the learning rate and the seed at the same time, you cannot attribute the result to either. Change one variable at a time, or use a full factorial design with multiple seeds per configuration.
- **Not logging enough to reproduce.** If you cannot re-run a result six months later from the logged config, the logging was insufficient. Log the complete config, the git hash, and the environment. Test reproduction before you need it.
- **Not analyzing errors before iterating.** Jumping from a baseline score to hyperparameter tuning skips the most informative step. Error analysis on ~100 misclassified examples often reveals that the dominant error category (missing features, mislabeled data, a broken preprocessing step) cannot be fixed by tuning, and that fixing it improves performance more than any hyperparameter change would (see [Error analysis](#error-analysis)).
- **Not documenting compute resources.** A result that takes 8 GPU-hours to reproduce but does not say so wastes the reviewer's time, or makes the result irreproducible for anyone without equivalent hardware. Log runtime, hardware (CPU/GPU, memory), and total compute cost alongside metrics.

---

## Recap

- Commit before you run, or log the diff. A logged hash on a dirty tree proves nothing.
- Never overwrite data. Version it (`features_v2.parquet`, DVC).
- Pass `random_state` to every estimator and splitter, and run 10+ seeds for any claim you publish.
- Pin Python and dependencies with `uv.lock`, and record the scikit-learn version.
- Split first. Touch the test set once, at the very end.
- Keep preprocessing inside a `Pipeline`, split by group when entities repeat, and early-stop on an inner split.
- Put every parameter in a validated YAML config, and log it with the run.
- Organize MLflow experiments by dataset, and name runs so the UI is scannable.
- Run baselines, then error analysis, then search. In that order.
- Ablate one component at a time, across the same seeds, and correct for multiple comparisons.

---

## Exercise

Take any binary classification dataset you have, or `sklearn.datasets.load_breast_cancer`. Run 5-fold `StratifiedKFold` cross-validation of a `LogisticRegression` pipeline with 10 different seeds, and record the mean AUC for each seed. How far apart are the lowest and highest seed means? Now compare it with a `DummyClassifier(strategy="most_frequent")` on the same folds. Finally, take three made-up p-values, 0.01, 0.03, and 0.20, and apply the Holm correction by hand. Which ones stay below 0.05?

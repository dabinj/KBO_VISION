# Algorithm Selection Policy

## Current principle

The project should not be locked to `XGBoost`.
We should choose the algorithm that beats the strongest honest baseline on the target task.

For first-pitch prediction, the correct comparison order is:

1. `majority baseline`
2. `conditional majority baseline`
3. `prior-adjusted tree model`
4. `boosted tree variants`
5. `random forest / extra trees`
6. `sequence models such as Transformer`

If a more complex model does not beat the baseline, it should not be treated as the production candidate.

## Why this matters

Recent Naile 2025 first-pitch experiments showed that:

- direct multiclass tree models can underperform the simple majority prior
- location is easier than exact pitch type
- family-level targets are easier than fine pitch-type targets
- strong priors such as pitcher usage and catcher-opponent context matter a lot

That means model choice should be driven by the data regime, not by algorithm popularity.

## Current benchmark result

Benchmark target:

- input: `data/matchups/2025_naile/naile_first_pitch_drivers_2025.csv`
- target: `first_pitch_type`
- rows: `664`

Current comparison:

- `majority`: Top-1 `0.3684`
- `conditional_majority_catcher_opponent`: Top-1 `0.3684`
- `prior_adjusted_xgboost`: Top-1 `0.3534`
- `xgboost_random_forest_mode`: Top-1 `0.3083`
- `xgboost_dart`: Top-1 `0.2632`
- `xgboost_gbtree`: Top-1 `0.2556`

Interpretation:

- the strongest current method is still the baseline
- the best learned model so far is `prior-adjusted_xgboost`
- direct multiclass XGBoost is not yet good enough for production on this task

## Baseline-feature update

The project now supports row-level leakage-safe baseline priors as model features.

Applied table:

- `data/matchups/2025_naile/naile_first_pitch_drivers_with_baseline_2025.csv`

Added baseline feature groups:

- `overall`
- `catcher`
- `opponent`
- `catcher + opponent`
- `stance`
- `runner_state + outs`
- `inning bucket`

These are computed using only earlier rows in time order, so they can be used as model inputs without target leakage.

Updated benchmark on the baseline-augmented table:

- `majority`: Top-1 `0.3684`
- `xgboost_gbtree`: Top-1 `0.3534`
- `xgboost_dart`: Top-1 `0.3759`
- `prior_adjusted_xgboost`: Top-1 `0.3759`
- `xgboost_random_forest_mode`: Top-1 `0.3985`

Interpretation:

- adding baseline priors as features materially improved the learned models
- the current best result is now `xgboost_random_forest_mode`
- this is the first learned first-pitch type model in the project that clearly beats the majority baseline on this task

Project rule from this point:

- baseline priors should be attached to every model-ready training table whenever the target is categorical and historical priors are meaningful

## Practical algorithm policy

### 1. Use baseline-first evaluation

Every experiment must report:

- majority baseline
- conditional majority baseline
- learned model score
- delta vs majority

### 2. Match the algorithm to the target

Recommended by target:

- `pitch_family`
  - boosted trees first
- `two_seam vs non_two_seam`
  - boosted trees or random-forest style trees
- `zone_9`
  - boosted trees first
- `fine pitch_type`
  - only after the broad target is stable
- `full pitch sequence`
  - sequence model only after the static table is mature

### 3. Prefer simple models when they win

If a conditional baseline beats a learned model, use the baseline for that target and keep improving the feature table.

### 4. Expand algorithms when dependencies are available

When the environment allows it, compare:

- `RandomForest`
- `ExtraTrees`
- `HistGradientBoosting`
- `LightGBM`
- `CatBoost`
- `Transformer / GRU`

The current environment does not have:

- `sklearn`
- `torch`

So the immediate benchmarkable family is:

- XGBoost variants
- prior-adjusted models
- rule / conditional-prior models

## Current recommendation

For now:

1. keep `XGBoost` in the toolbox
2. do not force it as the main answer
3. use baseline or prior-adjusted models if they win
4. spend the next effort on better features and hierarchical targets
5. benchmark `RandomForest` and `Transformer` as soon as the environment supports them

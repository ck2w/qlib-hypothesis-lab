# Research protocol and supported scope

Read this before translating a hypothesis into configuration. Refer to the target repository's `configs/reversal_volume.yaml` for concrete example parameters. It is a completed case, not the default answer to every hypothesis.

## Assess whether the input is executable

The tools have three fixed base-feature roles: `rev`, `rv` and `vol20`. Each accepts a raw Qlib expression and complete-window conditions. The candidate is a signed product of two standardized base features, then standardized again. The comparison uses a Ridge model with the three base features and another Ridge model adding the candidate. Labels are return ratios between two future opening prices.

A hypothesis that can be represented faithfully within this structure can proceed to configuration. For an independent candidate formula, another model family, fundamental fields, another label type or another candidate structure, list the original definition, unsupported requirements and necessary code/test adaptations. Implement only after the design is clear. Preserve the intended hypothesis rather than replacing every input with the low-volume reversal example.

`tools/lab/config.py` validates the allowed market fields and operators. Window counts must cover each formula's field dependencies and historical interval; denominator checks must match the actual formula. Pass expressions through the validator rather than executing arbitrary Python from a paper or description.

## Required protocol details

- **Hypothesis and source:** mathematical expression, windows, expected direction, economic rationale and falsifiable question.
- **Data and timing:** existing data path, historical membership universe, signal availability and label entry/exit timing.
- **Comparison:** baseline factors, candidate, models and parameters; the distinct questions answered by standalone evaluation and incremental comparison.
- **Split:** train and out-of-sample signal dates, purging labels across the boundary, whether annual results are report-only slices, warm-up and label-tail data.
- **Evaluation:** primary metric, support criterion, interval method, auxiliary metrics and whether the test period has already been inspected.

Ask only about substantive ambiguities. Record rules the user has already specified or project conventions they have authorized.

## Timing and sample rules

Construct continuous per-stock features and labels on a common trading calendar, then select historical index members by signal date. Enforce complete historical windows with Count conditions; a non-null Qlib Mean does not establish window completeness.

Standardize cross-sectionally each day within the feature-valid historical member pool, with ddof=0; set constant columns to zero. This pool is independent of future label availability. Then filter for valid labels and positive entry/exit opening prices, using identical training and evaluation samples for both models.

Purge training labels whose end date enters the out-of-sample period. Annual out-of-sample reports use the same trained models. Next year's label-tail prices are not current-year training features. Use the years specified in the confirmed configuration.

The primary metric is the daily Spearman IC difference on common stocks and common valid dates. Constant days remain NA. A date-block bootstrap preserves daily pairing and local temporal dependence. When there are fewer valid dates than the block length, do not estimate a formal interval.

## Predefined decision rule

Support currently requires a positive pooled out-of-sample mean increment and a bootstrap interval lower bound above zero. Otherwise report “not supported.” If the interval cannot be estimated, report that the decision could not be completed. Positive standalone factor IC cannot replace this criterion. The prediction evaluation does not model transaction costs, borrowing or capacity.

The example tests low volume strengthening short-term reversal: five-day reversal, 5/60-day relative volume, 20-day volatility and a standardized interaction. To reproduce it, read the repository's case protocol and configuration rather than reconstructing parameters from this reference.

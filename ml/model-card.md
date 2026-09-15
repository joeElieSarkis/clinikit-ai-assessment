# Appointment attendance model

## Purpose and scoring time

Estimate the probability that a scheduled appointment will be missed. The proposed use is a staff-reviewed outreach queue, after routine reminder status has been recorded but before the visit. Predictions must not cancel appointments, deny care, or trigger automatic contact.

The file does not contain event timestamps. It cannot establish when `reminder_sent` was recorded or whether historical counts exclude the current appointment. Those definitions need confirmation before real use. A booking-time system would need to omit unavailable reminder information and be trained and evaluated again.

## Data exploration

The employer-supplied CSV contains 3,000 rows and 12 columns. There are 478 no-shows (15.93%) and 2,522 attended appointments. Ages range from 1 to 92 and booking lead times from 0 to 59 days. There are no missing values, duplicate appointment IDs, full duplicate rows, or impossible history counts. New-patient flags agree with the absence of earlier visits. One repeated predictor profile is retained within a single partition.

Source provenance is recorded as a SHA-256 hash in [results.json](results/results.json). The file is not labelled as synthetic, so its clinical representativeness cannot be assumed. There are no names, contact details, patient IDs, or appointment dates in the supplied schema. A serial appointment ID is not treated as time or a clinical feature.

Training-only exploration shows higher observed no-show rates among appointments with multiple previously missed visits. Appointment types also differ, but some groups are small: only seven training rows have six previous no-shows. The report shows denominators with rates to make this visible.

## Preparation and model selection

Nine predictors are used: age, booking lead time, previous appointment count, previous no-show count, reminder status, new-patient status, appointment type, weekday, and time band. `appointment_id` is excluded as an identifier. `gender` is excluded from prediction and retained for descriptive auditing; excluding it does not eliminate proxies or establish fairness.

Six numeric predictors use median imputation and standardization. Three categorical predictors use most-frequent imputation and one-hot encoding with unknown-category handling. These steps live inside each estimator's pipeline, so each training fold learns its own preprocessing. No target encoding, oversampling, or class weighting is applied.

A fixed seed (42) creates 1,800 training, 600 validation, and 600 test rows with grouped stratification. Identical predictor profiles remain in the same group, including within training cross-validation. These are appointment-level splits, not patient-level or temporal splits; the source does not provide the fields needed for those stronger evaluations.

Four fixed candidates were compared using five-fold training cross-validation:

| Candidate | Mean average precision | Mean ROC AUC |
| --- | ---: | ---: |
| Prior-probability baseline | 0.159 | 0.500 |
| Logistic regression | 0.406 | 0.712 |
| Random forest | 0.398 | 0.714 |
| Gradient boosting | 0.404 | 0.708 |

Logistic regression had the highest mean AP, by a small margin. This is not evidence of a statistically meaningful advantage over the trees. It is also inexpensive to score and straightforward to explain. Fixed regularization and small trees limited model complexity; there was no broad hyperparameter search.

The selected model receives sigmoid calibration fitted to grouped out-of-fold training scores, with its final estimator fitted on all training rows. Validation and test labels do not enter model fitting or calibration. The saved model is the evaluated model and has not been refitted on those rows.

## Threshold and evaluation

The predefined demonstration target was at least 75% recall on validation data. The highest threshold on a 0.01 grid meeting that target was **0.10**. This target is an assumption for demonstrating outreach, not an agreed clinical policy. The model and threshold are saved in [selection.json](results/selection.json) before test scoring.

On the 600-row test set, 96 appointments were missed:

| Metric | Selected threshold (0.10) | Conventional threshold (0.50) |
| --- | ---: | ---: |
| Precision | 19.67% | 47.37% |
| Recall | 75.00% | 9.38% |
| F1 | 0.312 | 0.157 |
| F2 | 0.480 | 0.112 |
| Balanced accuracy | 58.33% | 53.70% |
| Accuracy | 47.00% | 83.83% |
| Appointments flagged | 366 (61.0%) | 19 (3.2%) |

At 0.10: **72 true positives, 294 false positives, 24 false negatives, and 210 true negatives**. The workload is substantial: about four attendees are flagged per correctly identified no-show. This operating point is not an operational recommendation.

Threshold-independent test metrics are **AP 0.340**, **ROC AUC 0.660**, and **Brier score 0.1254**. The prior baseline has AP 0.160, AUC 0.500, and Brier 0.1344. An always-attends classifier gets 84% accuracy while missing every no-show, illustrating why accuracy cannot be the primary metric here.

Average precision emphasizes ranking of the minority class and is reported separately from trapezoidal PR area. Recall measures missed visits identified; precision and flagged fraction quantify outreach workload. F2 weights recall more than precision without claiming known intervention costs. Brier score and the calibration plot examine the probability estimates.

One thousand stratified bootstrap resamples give conditional 95% intervals: AP **0.266–0.428**, AUC **0.592–0.724**, recall **65.6–83.3%**, and precision **17.6–21.8%**. These intervals hold the fitted model and observed class mix fixed. They omit training/model-selection variability and do not resolve possible dependence between visits from the same unidentified patient.

## Feature influence and subgroup checks

Validation permutation importance identifies **previous no-shows** as the dominant signal (mean AP decrease 0.147), followed by appointment type (0.015). Reminder status has a small, variable contribution (0.006). Other features have small or negative estimates. Negative importance can reflect noise or generalization error; it does not prove a feature is protective. Whiskers show standard deviation across 20 shuffles, not confidence intervals. Correlated features can share signal.

Test recall is 74.4% for the supplied Male group and 75.5% for Female, but the age-group results vary more. The 40–64 group has 63.6% recall; the 65+ group has only eight positive examples, so its 87.5% recall is particularly uncertain. These checks describe this sample and do not establish fairness or authorize group-specific thresholds.

## Integration and next validation

A scheduled service could collect an appointment snapshot, validate the fields, load a versioned model, and return probability, model version, threshold, and scoring time. Part 1's appointment workflow would remain responsible for confirmations; the risk score would not call its booking or cancellation methods.

Start with a prospective shadow run on a later cohort. Verify feature timing and patient-level separation, establish staff capacity, and assess calibration and subgroup outcomes. If performance and workload are acceptable, test staff-reviewed outreach in a controlled rollout. A reminder coefficient or feature importance is observational and does not establish that sending a reminder reduces no-shows.

Monitor input completeness, unknown categories, probability drift, calibration, recall, precision, and contact workload. Use delayed outcomes for evaluation, define a review/retraining schedule, and keep access controls, consent, retention, and audit records outside this assessment prototype.

## References

- [scikit-learn: data leakage and pipelines](https://scikit-learn.org/stable/common_pitfalls.html)
- [Average precision definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)
- [Probability calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [Permutation importance](https://scikit-learn.org/stable/modules/permutation_importance.html)

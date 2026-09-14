# Evaluation protocol

This protocol was written before model fitting or inspection of test-set performance.

- Use the supplied `CliniKit_NoShow_Dataset.csv`. Record its SHA-256 digest and audit schema, missing values, duplicates, ranges, and history consistency. Preserve the source file.
- Predict `no_show=1` after routine reminder status has been recorded and before the appointment. The dataset has no event timestamps, so feature availability at that point is an assumption to verify with the clinic. This is not a booking-time model or a way to estimate the effect of reminders.
- Exclude `appointment_id` from predictors. Exclude `gender` from the primary model and retain it only for a descriptive performance audit. This does not establish fairness; the remaining features may contain proxies.
- Keep identical predictor rows in the same partition. Use fixed-seed stratified group splits for approximately 60% training, 20% validation, and 20% test data. There is no patient identifier or appointment date, so patient-level and temporal validation are not possible.
- Compare a prior-probability baseline, regularized logistic regression, a regularized random forest, and small histogram gradient-boosted trees. Use five-fold grouped cross-validation on training data, selecting by mean average precision. Do not tune a broad parameter search against this small dataset.
- Fit imputers, scalers, and category encoders inside each training fold. Use no oversampling or class reweighting. Assess minority-class performance directly instead of changing the label distribution.
- For the selected non-baseline model, fit sigmoid probability calibration using out-of-fold training predictions, then fit its estimator on the full training partition. Validation and test labels are excluded from calibration.
- On validation data, choose the highest threshold on a 0.01 grid achieving at least 75% recall. The recall target is a demonstration assumption for optional outreach, not a clinic requirement. Freeze this threshold before evaluating the test set. Also show the conventional 0.50 threshold.
- Report test average precision, ROC AUC, precision, recall, F1, F2, balanced accuracy, accuracy, Brier score, confusion counts, and outreach workload. Use 1,000 stratified bootstrap samples for 95% intervals conditional on the fitted model and observed class mix.
- Measure feature influence by permutation importance on validation data with average precision as the score. Correlated features may share importance; associations are not causal effects.
- Show validation-only threshold exploration. The test operating point remains fixed. Report gender and age-group test metrics with sample sizes; small subgroup results are descriptive and uncertain.
- Save the evaluated training-only model without refitting on test data. Provide synthetic example predictions, a batch prediction command, an HTML report, charts, metrics, and a model card. Do not put the employer's source dataset into Git.
- Deployment would start with prospective shadow evaluation and staff-reviewed outreach. Predictions must not cancel appointments, deny access, or automatically contact patients.

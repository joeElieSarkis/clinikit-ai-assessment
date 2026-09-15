# Part 2 · Validation record

Checked locally on 15 September 2026 using the versions recorded in [results.json](results/results.json).

## Code and reproducibility

- **162 tests passed:** 151 reception tests and 11 ML tests. Two dependency deprecation warnings came from Starlette/httpx and anyio.
- ML tests cover schema and range validation, reproducible disjoint partitions, keeping repeated predictor profiles together, training-fitted preprocessing, unseen categories, threshold selection, and saved-model prediction.
- Reloading `ml/artifacts/model.joblib` reproduced the recorded held-out metrics and all three synthetic example probabilities.
- The batch prediction command completed successfully using `ml/examples/appointments.csv`.
- The original dataset and its local copy have the SHA-256 recorded in the result. Source and split hashes accompany the model evaluation.
- `pip check` found no dependency conflicts. The TypeScript check and Vite production build passed.

## Report and integration

The built site served Reception and `/attendance/` from the same FastAPI process. The hosting test verifies the report response as well as the application and asset routes.

The report was inspected in a desktop browser viewport and at 390 × 844. Mobile navigation, section links, the return link, and the threshold explorer worked. Wide figures scroll within the page on narrow screens.

At a validation threshold of zero, all 600 appointments were flagged and all 96 no-shows were found. At 100%, none were flagged and precision displayed as undefined. Restoring the evaluated threshold returned to 10%, with 355 appointments flagged and 72 no-shows found. The held-out test results stayed unchanged throughout.

No JavaScript errors were reported during these checks. The embedded browser did not report a download event for the metrics export, so the file download remains unverified there. Print output was not checked. Direct `file:` navigation was blocked by that browser's URL policy; the standalone report was inspected through localhost instead. The HTML embeds its data, styles, scripts, and figures and has no required network requests.

## Scope of the evidence

These checks establish implementation behavior and reproducibility, not suitability for clinical use. The test result remains modest: AP 0.340, ROC AUC 0.660, 75% recall, and 19.7% precision. The high outreach workload, feature timing assumptions, missing patient identifiers, and sampling uncertainty are discussed in the [model card](model-card.md).

No public deployment or Docker build has been verified. Training and prediction run locally; the web report makes no model API calls and performs no outreach.

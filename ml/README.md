# Part 2 · Appointment attendance

Predict whether an appointment will be missed (`no_show=1`) using the dataset supplied with the assessment. Training and prediction run locally and require no API key.

## Review the result

Open **Attendance study** from the reception interface, or open `frontend/public/attendance/index.html` directly in a browser. The report contains model comparisons, exported figures, a fixed test result, synthetic predictions, and a validation-only threshold explorer. Everything is embedded in the HTML, so no server or internet connection is needed for the report itself.

The model selected by training cross-validation was **logistic regression**. On 600 held-out appointments:

| Measure | Result |
| --- | ---: |
| Average precision | 0.340 (prior baseline: 0.160) |
| ROC AUC | 0.660 |
| No-show recall | 75.0% |
| Precision | 19.7% |
| Appointments flagged | 366 / 600 |
| Actual no-shows identified / missed | 72 / 24 |
| Attendees unnecessarily flagged | 294 |

This demonstrates some predictive signal, but the outreach workload is high. It is not evidence that the model is suitable for an operational rollout. See the [model card](model-card.md) for interpretation, uncertainty, and assumptions.

The [validation record](validation.md) describes the tests, reproducibility checks, browser checks, and remaining verification limits.

## Reproduce

From the repository root, using the same virtual environment as Part 1:

```powershell
.\.venv\Scripts\python.exe -m pip install -r ml/requirements.txt
.\.venv\Scripts\python.exe -m ml.train --data "ml/data/CliniKit_NoShow_Dataset.csv"
.\.venv\Scripts\python.exe -m ml.predict --input ml/examples/appointments.csv --output work/predictions.csv
.\.venv\Scripts\python.exe -m pytest ml/tests -q
```

Place the employer-supplied CSV at the path above, or pass its existing path with `--data`. On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`. If Part 1 has not been installed, first create a Python 3.12 virtual environment and install `requirements-lock.txt` for the shared test dependencies, then install the ML requirements.

The original CSV and trained binary are excluded from Git. The original source file is never edited. A source-file hash and split hashes are recorded in the results. The supplied dataset is needed to reproduce training; no replacement data is downloaded.

`ml.train` writes the evaluation to `ml/results/`, saves the model to `ml/artifacts/model.joblib`, and regenerates the website report. It uses one fixed seed and the [predefined protocol](protocol.md). The recorded modelling and metric stage took about 21 seconds on the development laptop; first imports and figure rendering add time.

## Files

| Path | Purpose |
| --- | --- |
| `data.py` | Schema validation and partitions that keep identical predictor rows together |
| `models.py` | Candidate estimators and preprocessing pipelines |
| `metrics.py` | Classification metrics, threshold selection, and bootstrap intervals |
| `train.py` | Cross-validation, calibration, final test evaluation, and model persistence |
| `predict.py` | Batch inference using the saved model and threshold |
| `report.py`, `report.html` | Figures and the portable interactive report |
| `tests/` | Data validation, split isolation, preprocessing, threshold, and inference tests |
| `examples/appointments.csv` | Three invented prediction inputs, not real patient records |
| `results/selection.json` | Model and threshold choice written before test scoring |
| `results/results.json` | Complete numerical result, split hashes, versions, and uncertainty |
| `results/figures/` | SVG and PNG charts for review or export |
| `results/example_predictions.csv` | Scores for the three invented inputs |

The report can be rebuilt from saved results with `.\.venv\Scripts\python.exe -m ml.report`, without retraining or reading the source dataset.

## Prediction contract

The input CSV must contain the nine features listed in `data.FEATURES`. `appointment_id` and an `example` label are optional and are returned unchanged. `gender` is ignored. An outcome column is rejected to keep inference inputs separate from labelled evaluation data.

The command validates ranges and appointment history, then returns the estimated probability, the frozen threshold, and a `review_for_outreach` flag. Missing feature values use training-fitted imputation; unknown categories are encoded without refitting. These conditions should be monitored in real use. The command does not modify an appointment or contact a patient.

Only load a model artifact produced by trusted code: joblib files can execute Python when loaded. The pinned library versions should match those recorded with the model.

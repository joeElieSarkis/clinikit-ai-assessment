"""Train candidates, freeze an operating point, and evaluate the held-out test set."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import precision_recall_curve, roc_curve
from sklearn.model_selection import StratifiedGroupKFold, cross_validate
from threadpoolctl import threadpool_limits

from .data import FEATURES, NUMERIC, SEED, TARGET, load_dataset, predictor_groups, split_data, validate_features
from .metrics import bootstrap_intervals, choose_threshold, classification_metrics, threshold_table
from .models import candidates

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False, ensure_ascii=False) + "\n", encoding="utf-8")


def audit(frame, train):
    groups = predictor_groups(frame)
    rates = {}
    for name in ["appointment_type", "weekday", "appointment_time", "reminder_sent", "previous_no_shows"]:
        table = train.groupby(name, dropna=False)[TARGET].agg(["size", "sum", "mean"])
        rates[name] = [{"label": str(label), "n": int(row["size"]), "no_shows": int(row["sum"]), "rate": float(row["mean"])} for label, row in table.iterrows()]
    return {
        "rows": len(frame), "columns": len(frame.columns), "no_shows": int(frame[TARGET].sum()),
        "prevalence": float(frame[TARGET].mean()), "missing": {name: int(value) for name, value in frame.isna().sum().items()},
        "duplicate_ids": int(frame.appointment_id.duplicated().sum()), "duplicate_rows": int(frame.duplicated().sum()),
        "repeated_predictor_rows": int(len(frame) - len(np.unique(groups))),
        "history_violations": int((frame.previous_no_shows > frame.previous_appointments).sum()),
        "new_patient_history_violations": int(((frame.new_patient == 1) & (frame.previous_appointments > 0)).sum()),
        "numeric_summary": {name: {key: float(value) for key, value in values.items()} for name, values in frame[NUMERIC].describe().to_dict().items()},
        "training_rates": rates,
    }


def group_metrics(test, y, probability, threshold):
    result = []
    age_group = pd.cut(test.age, [-np.inf, 17, 39, 64, np.inf], labels=["Under 18", "18–39", "40–64", "65+"])
    for feature, values in [("gender", test.gender), ("age", age_group)]:
        for label in values.dropna().unique():
            mask = (values == label).to_numpy()
            row = classification_metrics(y[mask], probability[mask], threshold)
            result.append({"feature": feature, "group": str(label), **row})
    return result


def train(data_path: Path, output: Path, artifact: Path):
    started = perf_counter()
    frame = load_dataset(data_path)
    partitions = split_data(frame)
    train_frame, valid_frame, test_frame = [frame.iloc[partitions[name]].reset_index(drop=True) for name in ["train", "validation", "test"]]
    x_train, x_valid, x_test = [validate_features(part) for part in [train_frame, valid_frame, test_frame]]
    y_train, y_valid, y_test = [part[TARGET].to_numpy(dtype=int) for part in [train_frame, valid_frame, test_frame]]
    groups = predictor_groups(train_frame)
    folds = list(StratifiedGroupKFold(5, shuffle=True, random_state=SEED + 2).split(x_train, y_train, groups))
    comparison = []
    choices = candidates()
    for name, estimator in choices.items():
        scores = cross_validate(estimator, x_train, y_train, cv=folds, scoring={"ap": "average_precision", "auc": "roc_auc", "brier": "neg_brier_score"}, n_jobs=1, error_score="raise")
        row = {"name": name, "ap_mean": float(scores["test_ap"].mean()), "ap_std": float(scores["test_ap"].std(ddof=1)),
               "auc_mean": float(scores["test_auc"].mean()), "brier_mean": float(-scores["test_brier"].mean()),
               "fold_ap": scores["test_ap"].tolist(), "fit_seconds": float(scores["fit_time"].sum())}
        comparison.append(row)
        print(f"Training CV: {name}: AP={row['ap_mean']:.3f}, ROC AUC={row['auc_mean']:.3f}", flush=True)
    selected = max(comparison, key=lambda row: row["ap_mean"])["name"]
    if selected == "Prior baseline":
        model = clone(choices[selected]).fit(x_train, y_train)
    else:
        model = CalibratedClassifierCV(clone(choices[selected]), method="sigmoid", cv=folds, ensemble=False, n_jobs=1).fit(x_train, y_train)
    valid_probability = model.predict_proba(x_valid)[:, 1]
    operating_point = choose_threshold(y_valid, valid_probability)
    threshold = operating_point["threshold"]
    output.mkdir(parents=True, exist_ok=True)
    data_hash = sha256(data_path.read_bytes()).hexdigest()
    decision = {"selected_model": selected, "threshold": threshold, "recall_target": 0.75,
                "selection": "Maximum mean training-CV average precision", "threshold_rule": "Highest validation threshold on a 0.01 grid reaching 75% recall",
                "dataset_sha256": data_hash, "seed": SEED, "cv": comparison}
    # Persist the choice before using test predictions or labels for metrics.
    write_json(output / "selection.json", decision)
    print(f"Frozen choice: {selected}, threshold={threshold:.2f}. Evaluating test set.", flush=True)
    probability = model.predict_proba(x_test)[:, 1]
    test_metrics = classification_metrics(y_test, probability, threshold)
    default_metrics = classification_metrics(y_test, probability, 0.5)
    baseline = clone(choices["Prior baseline"]).fit(x_train, y_train)
    baseline_metrics = classification_metrics(y_test, baseline.predict_proba(x_test)[:, 1], 0.5)
    importance = permutation_importance(model, x_valid, y_valid, scoring="average_precision", n_repeats=20, random_state=SEED, n_jobs=1)
    influences = sorted([{"feature": name, "mean": float(mean), "std": float(std)} for name, mean, std in zip(FEATURES, importance.importances_mean, importance.importances_std)], key=lambda row: row["mean"], reverse=True)
    intervals = bootstrap_intervals(y_test, probability, threshold)
    precision, recall, _ = precision_recall_curve(y_test, probability)
    fpr, tpr, _ = roc_curve(y_test, probability)
    observed, predicted = calibration_curve(y_test, probability, n_bins=6, strategy="quantile")
    versions = {name: importlib.metadata.version(name) for name in ["numpy", "pandas", "scikit-learn", "scipy", "joblib", "matplotlib"]}
    source_hash = sha256(b"".join(path.read_bytes() for path in sorted((ROOT / "ml").glob("*.py")))).hexdigest()
    split_summary = {}
    for name, indices in partitions.items():
        part = frame.iloc[indices]
        split_summary[name] = {"n": len(part), "no_shows": int(part[TARGET].sum()), "prevalence": float(part[TARGET].mean()),
                               "id_sha256": sha256(",".join(map(str, sorted(part.appointment_id))).encode()).hexdigest()}
    examples_frame = pd.read_csv(ROOT / "ml" / "examples" / "appointments.csv")
    example_probability = model.predict_proba(validate_features(examples_frame))[:, 1]
    examples = [{"example": row["example"], "inputs": {name: row[name] for name in FEATURES}, "probability": float(score), "flagged": bool(score >= threshold)} for row, score in zip(examples_frame.to_dict("records"), example_probability)]
    result = {**decision, "generated_at": datetime.now(timezone.utc).isoformat(), "source_sha256": source_hash,
              "python": platform.python_version(), "versions": versions, "features": FEATURES,
              "excluded_features": {"appointment_id": "Identifier", "gender": "Audit only"},
              "prediction_time": "After routine reminder status is recorded, before the appointment; timestamp availability is unverified.",
              "calibration": "Sigmoid on grouped out-of-fold training predictions; full training estimator" if selected != "Prior baseline" else "Empirical training prior",
              "audit": audit(frame, train_frame), "splits": split_summary, "validation": operating_point,
              "validation_thresholds": threshold_table(y_valid, valid_probability), "test": test_metrics,
              "test_at_050": default_metrics, "baseline": baseline_metrics, "test_intervals_95": intervals,
              "bootstrap": {"samples": 1000, "method": "Stratified percentile bootstrap; fitted model and class mix fixed"},
              "importance": influences, "subgroups": group_metrics(test_frame, y_test, probability, threshold),
              "curves": {"precision": precision.tolist(), "recall": recall.tolist(), "fpr": fpr.tolist(), "tpr": tpr.tolist(),
                         "calibration_observed": observed.tolist(), "calibration_predicted": predicted.tolist()},
              "examples": examples, "duration_seconds": round(perf_counter() - started, 2)}
    write_json(output / "results.json", result)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "threshold": threshold, "features": FEATURES, "dataset_sha256": data_hash,
                 "source_sha256": source_hash, "model_name": selected, "versions": versions}, artifact)
    pd.DataFrame(examples).drop(columns="inputs").to_csv(output / "example_predictions.csv", index=False)
    from .report import render_report
    render_report(result, output, ROOT / "frontend" / "public" / "attendance" / "index.html")
    print(f"Test: AP={test_metrics['average_precision']:.3f}, AUC={test_metrics['roc_auc']:.3f}, precision={test_metrics['precision']:.1%}, recall={test_metrics['recall']:.1%}, flagged={test_metrics['flagged']}/{len(y_test)}", flush=True)
    print(f"Results: {output}\nModel: {artifact}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "ml/data/CliniKit_NoShow_Dataset.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "ml/results")
    parser.add_argument("--artifact", type=Path, default=ROOT / "ml/artifacts/model.joblib")
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        train(args.data, args.output, args.artifact)


if __name__ == "__main__":
    main()

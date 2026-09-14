"""Probability metrics and the validation-only outreach operating point."""
import numpy as np
from sklearn.metrics import (
    accuracy_score, average_precision_score, balanced_accuracy_score, brier_score_loss,
    confusion_matrix, f1_score, fbeta_score, precision_score, recall_score, roc_auc_score,
)


def classification_metrics(y, probability, threshold: float) -> dict:
    y, probability = np.asarray(y), np.asarray(probability)
    predicted = probability >= threshold
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    return {
        "threshold": float(threshold), "n": len(y), "positives": int(y.sum()),
        "prevalence": float(y.mean()), "average_precision": float(average_precision_score(y, probability)) if y.sum() else None,
        "roc_auc": float(roc_auc_score(y, probability)) if len(np.unique(y)) == 2 else None,
        "brier": float(brier_score_loss(y, probability)), "accuracy": float(accuracy_score(y, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
        "precision": float(precision_score(y, predicted, zero_division=0)), "recall": float(recall_score(y, predicted, zero_division=0)),
        "f1": float(f1_score(y, predicted, zero_division=0)), "f2": float(fbeta_score(y, predicted, beta=2, zero_division=0)),
        "flagged": int(predicted.sum()), "flagged_fraction": float(predicted.mean()),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def threshold_table(y, probability) -> list[dict]:
    return [classification_metrics(y, probability, step / 100) for step in range(101)]


def choose_threshold(y, probability, recall_target=0.75) -> dict:
    if not 0 < recall_target <= 1 or not np.any(np.asarray(y) == 1):
        raise ValueError("A positive validation class and recall target in (0, 1] are required")
    eligible = [row for row in threshold_table(y, probability) if row["recall"] >= recall_target]
    return max(eligible, key=lambda row: row["threshold"])


def bootstrap_intervals(y, probability, threshold, repeats=1000, seed=42) -> dict:
    y, probability = np.asarray(y), np.asarray(probability)
    rng = np.random.default_rng(seed)
    negative, positive = np.flatnonzero(y == 0), np.flatnonzero(y == 1)
    names = ["average_precision", "roc_auc", "precision", "recall", "brier"]
    values = {name: [] for name in names}
    for _ in range(repeats):
        indices = np.concatenate([rng.choice(negative, len(negative)), rng.choice(positive, len(positive))])
        row = classification_metrics(y[indices], probability[indices], threshold)
        for name in names:
            values[name].append(row[name])
    return {name: np.quantile(samples, [0.025, 0.975]).tolist() for name, samples in values.items()}

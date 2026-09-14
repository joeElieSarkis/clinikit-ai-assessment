"""Input validation and reproducible partitions."""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

SEED = 42
TARGET = "no_show"
NUMERIC = ["age", "days_before_appointment", "previous_appointments", "previous_no_shows", "reminder_sent", "new_patient"]
CATEGORICAL = ["appointment_type", "weekday", "appointment_time"]
FEATURES = NUMERIC + CATEGORICAL
COLUMNS = ["appointment_id", "gender"] + FEATURES + [TARGET]


def validate_features(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(FEATURES) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing feature columns: {', '.join(missing)}")
    result = frame[FEATURES].copy()
    for name in NUMERIC:
        result[name] = pd.to_numeric(result[name], errors="raise").astype(float)
        values = result[name].dropna()
        if not np.isfinite(values).all() or (values < 0).any() or (values % 1 != 0).any():
            raise ValueError(f"{name} must contain non-negative whole numbers or missing values")
    if (result.age > 120).any():
        raise ValueError("age must be at most 120")
    for name in ["reminder_sent", "new_patient"]:
        if not result[name].dropna().isin([0, 1]).all():
            raise ValueError(f"{name} must be 0, 1, or missing")
    if (result.previous_no_shows > result.previous_appointments).any():
        raise ValueError("previous_no_shows exceeds previous_appointments")
    if ((result.new_patient == 1) & ((result.previous_appointments > 0) | (result.previous_no_shows > 0))).any():
        raise ValueError("A new patient cannot have previous appointment history")
    for name in CATEGORICAL:
        result[name] = result[name].astype(object).where(result[name].notna(), np.nan)
        if any(not isinstance(value, str) or not value.strip() for value in result[name].dropna()):
            raise ValueError(f"{name} must contain non-empty category names or missing values")
    return result


def load_dataset(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(set(COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing dataset columns: {', '.join(missing)}")
    if frame.appointment_id.isna().any() or frame.appointment_id.duplicated().any():
        raise ValueError("appointment_id must be present and unique")
    if frame[TARGET].isna().any() or not frame[TARGET].isin([0, 1]).all():
        raise ValueError("no_show must be a complete binary target")
    if frame[TARGET].value_counts().min() < 30 or frame[TARGET].nunique() != 2:
        raise ValueError("Both classes need at least 30 examples for this evaluation")
    validate_features(frame)
    return frame


def predictor_groups(frame: pd.DataFrame) -> np.ndarray:
    return pd.util.hash_pandas_object(validate_features(frame), index=False).to_numpy()


def split_data(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    groups = predictor_groups(frame)
    y = frame[TARGET].to_numpy()
    development, test = next(StratifiedGroupKFold(5, shuffle=True, random_state=SEED).split(frame, y, groups))
    train_relative, validation_relative = next(StratifiedGroupKFold(4, shuffle=True, random_state=SEED + 1).split(frame.iloc[development], y[development], groups[development]))
    return {"train": development[train_relative], "validation": development[validation_relative], "test": test}

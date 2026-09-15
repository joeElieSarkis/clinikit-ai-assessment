from copy import deepcopy

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from ml.data import FEATURES, load_dataset, predictor_groups, split_data, validate_features
from ml.metrics import choose_threshold, classification_metrics
from ml.models import pipeline
from ml.predict import predict_batch


@pytest.fixture
def frame():
    rows = []
    for i in range(240):
        rows.append({"appointment_id": i + 1, "age": 20 + i % 60, "gender": "Female" if i % 2 else "Male",
                     "appointment_type": "Follow-up", "days_before_appointment": i % 17,
                     "previous_appointments": 4, "previous_no_shows": i % 3, "weekday": "Monday",
                     "appointment_time": "10:00-12:00", "reminder_sent": i % 2, "new_patient": 0,
                     "no_show": int(i % 4 == 0)})
    result = pd.DataFrame(rows)
    result.loc[1, FEATURES] = result.loc[0, FEATURES]
    return result


def test_partitions_are_reproducible_and_identical_profiles_never_cross(frame):
    parts, repeated = split_data(frame), split_data(frame)
    groups = predictor_groups(frame)
    for name in parts:
        np.testing.assert_array_equal(parts[name], repeated[name])
    all_rows = np.concatenate(list(parts.values()))
    assert len(all_rows) == len(set(all_rows)) == len(frame)
    assert set(all_rows) == set(range(len(frame)))
    for left, right in [("train", "validation"), ("train", "test"), ("validation", "test")]:
        assert not set(groups[parts[left]]) & set(groups[parts[right]])
    assert groups[0] == groups[1]


@pytest.mark.parametrize("column,value", [("age", -1), ("age", 121), ("reminder_sent", 2), ("previous_no_shows", 5), ("new_patient", 1), ("days_before_appointment", np.inf)])
def test_invalid_records_are_rejected(frame, column, value):
    frame[column] = frame[column].astype(float)
    frame.loc[0, column] = value
    with pytest.raises(ValueError):
        validate_features(frame)


def test_schema_and_duplicate_ids_are_checked(frame, tmp_path):
    path = tmp_path / "data.csv"
    frame.to_csv(path, index=False)
    assert len(load_dataset(path)) == len(frame)
    frame.loc[1, "appointment_id"] = frame.loc[0, "appointment_id"]
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="unique"):
        load_dataset(path)
    with pytest.raises(ValueError, match="Missing feature"):
        validate_features(frame.drop(columns="age"))


def test_preprocessing_keeps_training_statistics_and_handles_unseen_values(frame):
    x = validate_features(frame)
    model = pipeline(LogisticRegression(max_iter=1000)).fit(x.iloc[:180], frame.no_show.iloc[:180])
    imputer = model.named_steps["prepare"].named_transformers_["numeric"].named_steps["impute"]
    original = imputer.statistics_.copy()
    new = x.iloc[180:].copy()
    new.loc[:, "age"] = np.nan
    new.loc[:, "appointment_type"] = "Unseen type"
    p = model.predict_proba(new)
    np.testing.assert_array_equal(imputer.statistics_, original)
    assert np.isfinite(p).all()
    np.testing.assert_allclose(p.sum(axis=1), 1)


def test_validation_threshold_obeys_recall_constraint():
    y = [1, 1, 1, 0, 0]
    probabilities = [.8, .6, .4, .7, .1]
    point = choose_threshold(y, probabilities, .75)
    assert point["threshold"] == .4
    assert (point["tp"], point["fp"], point["fn"], point["tn"]) == (3, 1, 0, 1)
    assert point["precision"] == .75 and point["recall"] == 1
    assert classification_metrics(y, probabilities, .41)["recall"] < .75
    with pytest.raises(ValueError):
        choose_threshold([0, 0], [.1, .2])


def test_scoring_roundtrip_excludes_identifiers_and_outcomes(frame, tmp_path):
    model = pipeline(LogisticRegression(max_iter=1000)).fit(validate_features(frame), frame.no_show)
    bundle = {"model": model, "threshold": .2, "model_name": "Test logistic regression"}
    path = tmp_path / "model.joblib"
    joblib.dump(bundle, path)
    samples = frame.iloc[:3].drop(columns="no_show")
    before = predict_batch(bundle, samples)
    restored = predict_batch(joblib.load(path), samples)
    np.testing.assert_allclose(before.no_show_probability, restored.no_show_probability)
    changed = deepcopy(samples)
    changed.loc[:, "gender"] = "Different audit label"
    changed.loc[:, "appointment_id"] = [9001, 9002, 9003]
    np.testing.assert_allclose(before.no_show_probability, predict_batch(bundle, changed).no_show_probability)
    with pytest.raises(ValueError, match="outcome"):
        predict_batch(bundle, frame.iloc[:3])

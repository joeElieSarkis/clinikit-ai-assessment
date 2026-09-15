"""Score a CSV using the locally trained attendance model."""
import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .data import TARGET, validate_features


def predict_batch(bundle: dict, frame: pd.DataFrame) -> pd.DataFrame:
    if TARGET in frame.columns:
        raise ValueError("Prediction input must not include the no_show outcome column")
    features = validate_features(frame)
    probability = bundle["model"].predict_proba(features)[:, 1]
    if not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any():
        raise ValueError("The model returned invalid probabilities")
    result = pd.DataFrame(index=frame.index)
    for name in ["example", "appointment_id"]:
        if name in frame:
            result[name] = frame[name]
    result["no_show_probability"] = probability
    result["review_for_outreach"] = probability >= bundle["threshold"]
    result["threshold"] = bundle["threshold"]
    result["model"] = bundle["model_name"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("ml/artifacts/model.joblib"), help="Trusted artifact produced by ml.train")
    parser.add_argument("--output", type=Path, default=Path("work/predictions.csv"))
    args = parser.parse_args()
    if args.output.resolve() in {args.input.resolve(), args.model.resolve()}:
        parser.error("Output must not overwrite the input or model")
    if not args.model.exists():
        parser.error("Model not found. Run python -m ml.train first")
    try:
        result = predict_batch(joblib.load(args.model), pd.read_csv(args.input))
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(result.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()

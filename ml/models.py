"""Fixed candidate models with fold-local preprocessing."""
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import CATEGORICAL, NUMERIC, SEED


def pipeline(estimator) -> Pipeline:
    numeric = Pipeline([("impute", SimpleImputer(strategy="median", keep_empty_features=True)), ("scale", StandardScaler())])
    category = Pipeline([("impute", SimpleImputer(strategy="most_frequent", keep_empty_features=True)), ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    prepare = ColumnTransformer([("numeric", numeric, NUMERIC), ("categorical", category, CATEGORICAL)], remainder="drop")
    return Pipeline([("prepare", prepare), ("model", estimator)])


def candidates() -> dict:
    return {
        "Prior baseline": pipeline(DummyClassifier(strategy="prior")),
        "Logistic regression": pipeline(LogisticRegression(C=1.0, max_iter=2000, random_state=SEED)),
        "Random forest": pipeline(RandomForestClassifier(n_estimators=250, min_samples_leaf=12, max_features="sqrt", n_jobs=1, random_state=SEED)),
        "Gradient boosting": pipeline(HistGradientBoostingClassifier(max_iter=180, max_leaf_nodes=7, l2_regularization=5.0, learning_rate=0.05, early_stopping=False, random_state=SEED)),
    }

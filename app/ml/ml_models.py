"""
Random Forest ML Models for SAP S/4HANA Migration Assessment
=============================================================

Two models, both trained once on first use and persisted to disk via joblib:

  1. RFRegressor  — predicts effort in working days (continuous)
     Features → estimated_effort_days

  2. RFClassifier — predicts migration risk category (ordinal, 4-class)
     Features → risk_level  (0=low · 1=medium · 2=high · 3=critical)

Both models are wrapped in sklearn Pipelines with StandardScaler so raw
feature magnitudes (LOC in hundreds of thousands vs ATC count in tens)
do not bias tree splits unnecessarily.

Cross-validation metrics (5-fold) are computed at train time and stored
alongside the serialised models for transparency.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np

from app.services.logger import get_logger
from app.ml.training_data import (
    load_training_data,
    build_feature_vector,
    FEATURE_NAMES,
    RISK_LABEL_INV,
)

log = get_logger(__name__)

# ── Persistence paths ─────────────────────────────────────────────────────────
_MODEL_DIR = Path("output") / "ml_models"
_REGRESSOR_PATH  = _MODEL_DIR / "rf_effort_regressor.joblib"
_CLASSIFIER_PATH = _MODEL_DIR / "rf_risk_classifier.joblib"
_METRICS_PATH    = _MODEL_DIR / "model_metrics.json"


# ── Metrics containers ────────────────────────────────────────────────────────

@dataclass
class RegressorMetrics:
    mae:  float = 0.0   # Mean Absolute Error (days)
    rmse: float = 0.0   # Root Mean Squared Error (days)
    r2:   float = 0.0   # R² coefficient of determination
    cv_mae_mean:  float = 0.0
    cv_mae_std:   float = 0.0
    n_samples:    int   = 0
    feature_importances: Dict[str, float] = field(default_factory=dict)


@dataclass
class ClassifierMetrics:
    accuracy:       float = 0.0
    cv_acc_mean:    float = 0.0
    cv_acc_std:     float = 0.0
    class_report:   str   = ""
    n_samples:      int   = 0
    feature_importances: Dict[str, float] = field(default_factory=dict)


@dataclass
class RFMetrics:
    regressor:  RegressorMetrics  = field(default_factory=RegressorMetrics)
    classifier: ClassifierMetrics = field(default_factory=ClassifierMetrics)


# ── Main model container ──────────────────────────────────────────────────────

class RFModels:
    """
    Loads or trains both Random Forest models. Thread-safe for read access
    after initialisation (no mutable state after fit).
    """

    def __init__(self):
        self.regressor  = None
        self.classifier = None
        self.metrics    = RFMetrics()
        self._trained   = False

    # ── Public API ────────────────────────────────────────────────────────────

    def ensure_trained(self, retrain: bool = False) -> None:
        """Load persisted models or train from scratch."""
        if self._trained and not retrain:
            return
        _MODEL_DIR.mkdir(parents=True, exist_ok=True)
        if not retrain and _REGRESSOR_PATH.exists() and _CLASSIFIER_PATH.exists():
            self._load()
        else:
            self._train_and_save()
        self._trained = True

    def predict_effort(self, state_features: dict) -> float:
        """Return predicted effort in working days (float)."""
        self.ensure_trained()
        X = build_feature_vector(state_features)
        pred = float(self.regressor.predict(X)[0])
        return max(1.0, round(pred, 1))

    def predict_risk(self, state_features: dict) -> tuple[str, Dict[str, float]]:
        """
        Return (risk_level_str, probabilities_dict).
        risk_level_str is one of: 'low', 'medium', 'high', 'critical'
        """
        self.ensure_trained()
        X = build_feature_vector(state_features)
        label    = int(self.classifier.predict(X)[0])
        proba    = self.classifier.predict_proba(X)[0]
        classes  = self.classifier.classes_
        proba_map = {
            RISK_LABEL_INV.get(int(c), str(c)): round(float(p), 4)
            for c, p in zip(classes, proba)
        }
        return RISK_LABEL_INV.get(label, "medium"), proba_map

    # ── Training ──────────────────────────────────────────────────────────────

    def _train_and_save(self) -> None:
        from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_score, train_test_split
        from sklearn.metrics import (
            mean_absolute_error, mean_squared_error, r2_score,
            accuracy_score, classification_report,
        )

        log.info("Training Random Forest models …")
        X, y_reg, y_cls = load_training_data()
        n = len(X)

        # ── Train/test split (80/20, stratified on risk class) ────────────────
        X_tr, X_te, yr_tr, yr_te, yc_tr, yc_te = train_test_split(
            X, y_reg, y_cls,
            test_size=0.20,
            random_state=42,
            stratify=y_cls,
        )

        # ── 1. Regressor ──────────────────────────────────────────────────────
        reg_pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("rf", RandomForestRegressor(
                n_estimators=200,
                max_depth=None,
                min_samples_split=4,
                min_samples_leaf=2,
                max_features="sqrt",
                random_state=42,
                n_jobs=-1,
            )),
        ])
        reg_pipe.fit(X_tr, yr_tr)
        yr_pred = reg_pipe.predict(X_te)

        mae  = mean_absolute_error(yr_te, yr_pred)
        rmse = float(np.sqrt(mean_squared_error(yr_te, yr_pred)))
        r2   = r2_score(yr_te, yr_pred)

        cv_mae = -cross_val_score(
            reg_pipe, X, y_reg,
            cv=5, scoring="neg_mean_absolute_error", n_jobs=-1,
        )

        fi_reg = dict(zip(
            FEATURE_NAMES,
            [round(v, 5) for v in reg_pipe.named_steps["rf"].feature_importances_],
        ))

        self.metrics.regressor = RegressorMetrics(
            mae=round(mae, 2),
            rmse=round(rmse, 2),
            r2=round(r2, 4),
            cv_mae_mean=round(float(cv_mae.mean()), 2),
            cv_mae_std=round(float(cv_mae.std()), 2),
            n_samples=n,
            feature_importances=fi_reg,
        )

        log.info("Regressor trained",
                 mae=self.metrics.regressor.mae,
                 rmse=self.metrics.regressor.rmse,
                 r2=self.metrics.regressor.r2,
                 cv_mae=f"{self.metrics.regressor.cv_mae_mean}±{self.metrics.regressor.cv_mae_std}")

        # ── 2. Classifier ─────────────────────────────────────────────────────
        cls_pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("rf", RandomForestClassifier(
                n_estimators=200,
                max_depth=None,
                min_samples_split=4,
                min_samples_leaf=2,
                max_features="sqrt",
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )),
        ])
        cls_pipe.fit(X_tr, yc_tr)
        yc_pred = cls_pipe.predict(X_te)

        acc   = accuracy_score(yc_te, yc_pred)
        report = classification_report(
            yc_te, yc_pred,
            target_names=["low", "medium", "high", "critical"],
            zero_division=0,
        )
        cv_acc = cross_val_score(
            cls_pipe, X, y_cls,
            cv=5, scoring="accuracy", n_jobs=-1,
        )

        fi_cls = dict(zip(
            FEATURE_NAMES,
            [round(v, 5) for v in cls_pipe.named_steps["rf"].feature_importances_],
        ))

        self.metrics.classifier = ClassifierMetrics(
            accuracy=round(acc, 4),
            cv_acc_mean=round(float(cv_acc.mean()), 4),
            cv_acc_std=round(float(cv_acc.std()), 4),
            class_report=report,
            n_samples=n,
            feature_importances=fi_cls,
        )

        log.info("Classifier trained",
                 accuracy=self.metrics.classifier.accuracy,
                 cv_acc=f"{self.metrics.classifier.cv_acc_mean}±{self.metrics.classifier.cv_acc_std}")

        # ── Persist ───────────────────────────────────────────────────────────
        self.regressor  = reg_pipe
        self.classifier = cls_pipe

        joblib.dump(reg_pipe, _REGRESSOR_PATH)
        joblib.dump(cls_pipe, _CLASSIFIER_PATH)

        metrics_dict = {
            "regressor":  asdict(self.metrics.regressor),
            "classifier": asdict(self.metrics.classifier),
        }
        _METRICS_PATH.write_text(json.dumps(metrics_dict, indent=2))
        log.info("Models persisted", dir=str(_MODEL_DIR))

    # ── Loading ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        log.info("Loading pre-trained RF models from disk …")
        self.regressor  = joblib.load(_REGRESSOR_PATH)
        self.classifier = joblib.load(_CLASSIFIER_PATH)

        if _METRICS_PATH.exists():
            raw = json.loads(_METRICS_PATH.read_text())
            self.metrics.regressor  = RegressorMetrics(**raw.get("regressor",  {}))
            self.metrics.classifier = ClassifierMetrics(**raw.get("classifier", {}))

        log.info("RF models loaded",
                 regressor_mae=self.metrics.regressor.mae,
                 classifier_acc=self.metrics.classifier.accuracy)

    def get_metrics_summary(self) -> dict:
        """Return a JSON-serialisable dict of both models' metrics."""
        return {
            "regressor": asdict(self.metrics.regressor),
            "classifier": asdict(self.metrics.classifier),
        }


# ── Module-level singleton ────────────────────────────────────────────────────

_models: Optional[RFModels] = None


def get_models() -> RFModels:
    global _models
    if _models is None:
        _models = RFModels()
    return _models

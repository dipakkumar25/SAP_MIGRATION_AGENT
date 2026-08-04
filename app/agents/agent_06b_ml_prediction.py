"""
Agent 6b – Random Forest ML Prediction
=======================================
Runs after Agent 6 (rule-based risk assessment) and augments the AgentState
with two ML-derived predictions:

  1. Effort Prediction   — RandomForestRegressor → predicted_effort_days
  2. Risk Classification — RandomForestClassifier → predicted_risk_level + probabilities

The ML predictions complement (not replace) the rule-based readiness score.
When the RF effort prediction is available it overrides the heuristic estimate
in readiness_score.estimated_effort_days.

Models are trained on sample_all_120_assessments.json (120 real-world records)
and persisted to output/ml_models/ as joblib files on first use.
"""
from __future__ import annotations

from datetime import datetime

from app.models.schemas import AgentState, MLPrediction
from app.services import get_logger

log = get_logger(__name__)


def _extract_features(state: AgentState) -> dict:
    """Pull the 11 numeric features from AgentState into a flat dict."""
    cc  = state.custom_code
    atc = state.atc_report
    sim = state.simplification_report
    dep = state.dependency_graph
    ls  = state.landscape

    return {
        "total_objects":    float(cc.total_objects)          if cc  else 0.0,
        "total_loc":        float(cc.total_lines_of_code)    if cc  else 0.0,
        "total_findings":   float(atc.total_findings)        if atc else 0.0,
        "critical_findings":float(atc.critical_count)        if atc else 0.0,
        "high_findings":    float(atc.high_count)            if atc else 0.0,
        "medium_findings":  float(atc.medium_count)          if atc else 0.0,
        "deprecated_items": float(sim.total_impacts)         if sim else 0.0,
        "bp_items":         float(len(sim.business_partner_items)) if sim else 0.0,
        "uj_impacts":       float(len(sim.universal_journal_impacts)) if sim else 0.0,
        "rfc_destinations": float(len(ls.rfc_destinations))  if ls  else 0.0,
        "app_servers":      1.0,   # default; landscape schema has no app_server count
    }


def run_ml_prediction(state: AgentState) -> AgentState:
    """LangGraph node: run RF regressor + classifier and store results in state."""
    log.info("Agent 6b – ML Prediction started", assessment_id=state.assessment_id)
    try:
        from app.ml.ml_models import get_models

        features = _extract_features(state)
        models   = get_models()
        models.ensure_trained()

        # ── 1. Effort regression ──────────────────────────────────────────────
        predicted_effort = models.predict_effort(features)

        # ── 2. Risk classification ────────────────────────────────────────────
        predicted_risk, risk_proba = models.predict_risk(features)

        # ── 3. Collect metrics ────────────────────────────────────────────────
        m = models.metrics

        ml_pred = MLPrediction(
            # Regression
            predicted_effort_days=predicted_effort,
            regressor_mae=m.regressor.mae,
            regressor_rmse=m.regressor.rmse,
            regressor_r2=m.regressor.r2,
            regressor_cv_mae=(
                f"{m.regressor.cv_mae_mean:.2f}±{m.regressor.cv_mae_std:.2f} days"
            ),
            # Classification
            predicted_risk_level=predicted_risk,
            risk_probabilities=risk_proba,
            classifier_accuracy=m.classifier.accuracy,
            classifier_cv_accuracy=(
                f"{m.classifier.cv_acc_mean:.4f}±{m.classifier.cv_acc_std:.4f}"
            ),
            # Feature importances
            regressor_feature_importances=m.regressor.feature_importances,
            classifier_feature_importances=m.classifier.feature_importances,
            # Metadata
            n_training_samples=m.regressor.n_samples,
            model_used="RandomForestRegressor + RandomForestClassifier (scikit-learn)",
            predicted_at=datetime.utcnow(),
        )

        state.ml_prediction = ml_pred

        # Override effort days in readiness score with ML prediction
        if state.readiness_score:
            state.readiness_score.estimated_effort_days = int(round(predicted_effort))

        state.steps_completed.append("ml_prediction")
        log.info(
            "Agent 6b – completed",
            predicted_effort_days=predicted_effort,
            predicted_risk=predicted_risk,
            risk_probabilities=risk_proba,
            classifier_accuracy=m.classifier.accuracy,
            regressor_r2=m.regressor.r2,
        )

    except Exception as exc:
        log.error("Agent 6b – ML Prediction failed", error=str(exc))
        state.error_messages.append(f"ML Prediction: {exc}")

    return state

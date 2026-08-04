"""
Training Data Builder
Reads sample_all_120_assessments.json and converts every assessment record into a
flat feature vector + two labels consumed by the Random Forest models.

Feature set (11 numeric features, all derived from data already in AgentState):
  1.  total_objects          — count of all custom Z/Y objects
  2.  total_loc              — total lines of custom code
  3.  total_findings         — all ATC findings
  4.  critical_findings      — ATC critical count
  5.  high_findings          — ATC high count
  6.  medium_findings        — ATC medium count
  7.  deprecated_items       — total simplification list impacts
  8.  bp_items               — business partner migration items
  9.  uj_impacts             — universal journal impacts
  10. max_dep_depth          — dependency graph maximum depth  (estimated from RFC destinations)
  11. rfc_destinations       — number of RFC integration points

Labels:
  - effort_days    (regression target, continuous)
  - risk_level     (classification target, ordinal: low=0, medium=1, high=2, critical=3)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import numpy as np

SAMPLE_FILE = Path(__file__).parent.parent.parent / "sample_data" / "sample_all_120_assessments.json"

FEATURE_NAMES: List[str] = [
    "total_objects",
    "total_loc",
    "total_findings",
    "critical_findings",
    "high_findings",
    "medium_findings",
    "deprecated_items",
    "bp_items",
    "uj_impacts",
    "rfc_destinations",
    "app_servers",
]

RISK_LABEL_MAP = {"low": 0, "medium": 1, "high": 2, "critical": 3}
RISK_LABEL_INV = {v: k for k, v in RISK_LABEL_MAP.items()}


def _extract_row(record: dict) -> Tuple[List[float], float, int] | None:
    """Return (features, effort_days, risk_label) for a single record, or None if malformed."""
    try:
        d = record.get("data", record)   # top-level may wrap in {"data": ...}
        cc  = d["custom_code_summary"]
        atc = d["atc_summary"]
        sim = d["simplification_summary"]
        rs  = d["risk_summary"]
        ls  = d["sap_system"].get("landscape", {})

        features = [
            float(cc.get("total_objects", 0)),
            float(cc.get("total_lines_of_code", 0)),
            float(atc.get("total_findings", 0)),
            float(atc.get("critical", 0)),
            float(atc.get("high", 0)),
            float(atc.get("medium", 0)),
            float(sim.get("total_items", 0)),
            float(sim.get("business_partner_items", 0)),
            float(sim.get("universal_journal_impacts", 0)),
            float(ls.get("rfc_destinations", 0)),
            float(ls.get("app_servers", 1)),
        ]

        effort_days = float(rs["estimated_effort_days"])
        risk_label  = RISK_LABEL_MAP.get(rs["risk_level"].lower(), 1)
        return features, effort_days, risk_label
    except (KeyError, TypeError, ValueError):
        return None


def load_training_data() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Load the 120-assessment dataset and return:
      X      — shape (n_samples, 11)  float64 feature matrix
      y_reg  — shape (n_samples,)     float64 effort in days  (regression)
      y_cls  — shape (n_samples,)     int64   risk label 0–3  (classification)
    """
    with open(SAMPLE_FILE, encoding="utf-8-sig") as f:
        records = json.load(f)

    rows = [_extract_row(r) for r in records]
    rows = [r for r in rows if r is not None]

    if len(rows) < 10:
        raise ValueError(
            f"Too few valid training records ({len(rows)}). "
            "Check that sample_all_120_assessments.json is present and well-formed."
        )

    X     = np.array([r[0] for r in rows], dtype=np.float64)
    y_reg = np.array([r[1] for r in rows], dtype=np.float64)
    y_cls = np.array([r[2] for r in rows], dtype=np.int64)

    return X, y_reg, y_cls


def build_feature_vector(state_features: dict) -> np.ndarray:
    """
    Convert a dict of named features (from AgentState) into a 2-D numpy row
    suitable for model.predict().
    """
    row = [float(state_features.get(name, 0.0)) for name in FEATURE_NAMES]
    return np.array([row], dtype=np.float64)

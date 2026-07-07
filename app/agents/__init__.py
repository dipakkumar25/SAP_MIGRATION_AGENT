from .agent_01_landscape import run_landscape_discovery
from .agent_02_custom_code import run_custom_code_discovery
from .agent_03_atc import run_atc_assessment
from .agent_04_simplification import run_simplification_analysis
from .agent_05_dependencies import run_dependency_analysis
from .agent_06_risk import run_risk_assessment
from .agent_07_recommendations import run_recommendation_generation
from .agent_08_runbook import run_runbook_generation
from .agent_09_dashboard import run_dashboard_generation

__all__ = [
    "run_landscape_discovery",
    "run_custom_code_discovery",
    "run_atc_assessment",
    "run_simplification_analysis",
    "run_dependency_analysis",
    "run_risk_assessment",
    "run_recommendation_generation",
    "run_runbook_generation",
    "run_dashboard_generation",
]

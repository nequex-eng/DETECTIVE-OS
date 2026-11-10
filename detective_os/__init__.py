"""DETECTIVE OS."""
from .core import SourceRegistry, EvidenceBoard, TimelineEngine, EntityGraph
from .reasoning import (ContradictionEngine, HypothesisEngine,
                        InvestigationPlanner, IndependentReview)

__all__ = ["SourceRegistry", "EvidenceBoard", "TimelineEngine", "EntityGraph",
           "ContradictionEngine", "HypothesisEngine", "InvestigationPlanner",
           "IndependentReview"]
__version__ = "0.1.0"

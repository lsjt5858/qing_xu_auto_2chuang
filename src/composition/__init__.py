"""
Composition utilities for assembling timeline plans from artifacts and shot pools.
"""

from .head_tail_composer import CompositionSettings, HeadTailComposer
from .shot_pool import ShotCandidate, ShotPoolIndex

__all__ = [
    "CompositionSettings",
    "HeadTailComposer",
    "ShotCandidate",
    "ShotPoolIndex",
]

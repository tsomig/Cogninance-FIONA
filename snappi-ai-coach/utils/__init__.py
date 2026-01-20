"""
Utilities package for Snappi AI Financial Coach
Contains visualization helpers and prompt templates
"""

from .visualizations import (
    create_fri_gauge,
    create_component_radar,
    create_timeline_chart
)
from .prompts import create_coaching_prompt

__all__ = [
    'create_fri_gauge',
    'create_component_radar', 
    'create_timeline_chart',
    'create_coaching_prompt'
]

# Version
__version__ = '1.0.0'
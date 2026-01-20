"""
Models package for Snappi AI Financial Coach
Contains FinBERT analyzer, FRI calculator, and LLM generator
"""

from .finbert_analyzer import FinBERTAnalyzer
from .fri_calculator import FRICalculator
from .llm_generator import LLMGenerator

__all__ = ['FinBERTAnalyzer', 'FRICalculator', 'LLMGenerator']

# Version
__version__ = '1.0.0'
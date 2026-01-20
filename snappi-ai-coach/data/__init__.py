"""
Data package for Snappi AI Financial Coach
Contains customer profiles, mock data, and case database
"""

from .mock_data import get_customer_profiles, get_transaction_history
from .case_database import get_case_database

__all__ = ['get_customer_profiles', 'get_transaction_history', 'get_case_database']

# Version
__version__ = '1.0.0'
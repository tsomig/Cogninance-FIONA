# data/__init__.py

# This file exposes the data modules to the rest of the app.
# We can keep it simple or empty to avoid circular import errors.

from .mock_data import get_customer_profiles, get_transaction_history
from .case_database import find_similar_cases
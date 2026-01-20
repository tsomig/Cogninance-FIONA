"""
Configuration settings for Snappi AI Financial Coach
"""
import os
from pathlib import Path

# Project structure
BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
UTILS_DIR = BASE_DIR / "utils"

# Model settings
FINBERT_MODEL = "ProsusAI/finbert"
DEFAULT_DEVICE = "cpu"  # Change to "cuda" if GPU available

# FRI Configuration 
# Maybe see some customizatios of weights here.. 
FRI_WEIGHTS = {
    'buffer': 0.45,
    'stability': 0.30,
    'momentum': 0.25
}

# FRI Thresholds
FRI_THRESHOLDS = {
    'thriving': 80,
    'stable': 60,
    'vulnerable': 40,
    'fragile': 20
}

# LLM Settings
LLM_PROVIDERS = {
    'mock': {'name': 'Mock (Demo)', 'requires_api': False},
    'claude': {'name': 'Claude (Anthropic)', 'requires_api': True},
    'openai': {'name': 'GPT-4 (OpenAI)', 'requires_api': True}
}

# API Keys (for production, use environment variables)
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# App Settings
APP_TITLE = "Snappi's AI Financial Coach"
APP_ICON = "💙 "
APP_LAYOUT = "wide"

# Demo Settings
DEMO_CUSTOMERS = 4
DEMO_MONTHS = 12

# Stress Detection Keywords and Weights
STRESS_KEYWORDS = {
    'worried': 0.7,
    'stressed': 0.8,
    'anxious': 0.75,
    'struggling': 0.85,
    'debt': 0.6,
    'overdue': 0.9,
    'unpaid': 0.85,
    'irregular income': 0.8,
    'can\'t afford': 0.9,
    'behind on': 0.85,
    'difficult': 0.7,
    'trouble': 0.75,
    'concern': 0.6,
    'nervous': 0.7,
    'scared': 0.8,
    'panic': 0.9
}

# Visualization Colors
COLORS = {
    'primary': '#667eea',
    'secondary': '#764ba2',
    'success': '#4caf50',
    'warning': '#ff9800',
    'danger': '#f44336',
    'info': '#2196f3'
}

# Gradient Colors for Metrics
GRADIENT_COLORS = {
    'high_stress': 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    'moderate_stress': 'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)',
    'low_stress': 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
    'primary': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
}

# Cache Settings
CACHE_TTL = 3600  # 1 hour

# Debug Mode
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
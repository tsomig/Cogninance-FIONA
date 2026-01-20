import numpy as np

def get_customer_profiles():
    """Sample customer profiles for demo"""
    return {
        "Sofia (Freelance Photographer)": {
            'customer_id': 'CUST_001',
            'name': 'Sofia Papadopoulos',
            'age': 31,
            'occupation': 'Freelance Photographer',
            'account_age_months': 18,
            'avg_monthly_income': 2000,
            'income_cv': 0.42,  # High volatility
            'avg_monthly_essential': 1500
        },
        "Nikos (Software Engineer)": {
            'customer_id': 'CUST_002',
            'name': 'Nikos Dimitriou',
            'age': 28,
            'occupation': 'Software Engineer',
            'account_age_months': 24,
            'avg_monthly_income': 3500,
            'income_cv': 0.08,  # Very stable
            'avg_monthly_essential': 2000
        },
        "Maria (Small Business Owner)": {
            'customer_id': 'CUST_003',
            'name': 'Maria Georgiou',
            'age': 42,
            'occupation': 'Small Business Owner',
            'account_age_months': 36,
            'avg_monthly_income': 2800,
            'income_cv': 0.35,  # Moderate volatility
            'avg_monthly_essential': 2200
        },
        "Andreas (Graduate Student)": {
            'customer_id': 'CUST_004',
            'name': 'Andreas Kostas',
            'age': 24,
            'occupation': 'Graduate Student',
            'account_age_months': 12,
            'avg_monthly_income': 800,
            'income_cv': 0.15,  # Stable but low
            'avg_monthly_essential': 700
        }
    }

def get_transaction_history(customer_id):
    """Generate mock 12-month transaction history"""
    
    profiles = get_customer_profiles()
    
    # Find matching customer
    customer = None
    for profile in profiles.values():
        if profile['customer_id'] == customer_id:
            customer = profile
            break
    
    if not customer:
        customer = list(profiles.values())[0]
    
    # Generate 12 months of data
    base_income = customer['avg_monthly_income']
    cv = customer['income_cv']
    essential = customer['avg_monthly_essential']
    
    np.random.seed(hash(customer_id) % 2**32)  # Consistent for same customer
    
    monthly_income = []
    monthly_buffer = []
    monthly_debt = []
    
    for i in range(12):
        # Generate income with volatility
        income = base_income * (1 + np.random.normal(0, cv))
        monthly_income.append(max(0, income))
        
        # Generate buffer (savings trend)
        buffer = 40 + i * 2 + np.random.normal(0, 5)
        monthly_buffer.append(max(0, min(100, buffer)))
        
        # Generate debt (decreasing trend)
        debt = 5000 - i * 200 + np.random.normal(0, 300)
        monthly_debt.append(max(0, debt))
    
    return {
        'customer_id': customer_id,
        'current_assets': essential * (monthly_buffer[-1] / 16.67),
        'avg_monthly_essential': essential,
        'monthly_income': monthly_income,
        'monthly_buffer': monthly_buffer,
        'monthly_debt': monthly_debt
    }
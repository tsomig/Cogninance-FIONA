import numpy as np
import random
from datetime import datetime, timedelta

def get_customer_profiles():
    """
    Returns ONLY George's profile.
    """
    return {
        "George (User)": {
            'customer_id': 'USER_GEORGE_01',
            'name': 'George Tsomidis',
            'age': 42,
            'occupation': 'Professor of Behavioral Economics',
            'account_age_months': 60,
            'avg_monthly_income': 4500, # Base salary
            'income_cv': 0.15,          # Low volatility (mostly stable with some consulting)
            'avg_monthly_essential': 2500,
            'rent': 1400
        }
    }

def get_transaction_history(customer_id):
    """
    Generate 5-year (60-month) granular transaction history EXCLUSIVELY for George.
    """
    profiles = get_customer_profiles()
    
    # Force selection of George regardless of ID passed (since data must be ONLY mine)
    customer = list(profiles.values())[0]
    
    # 2. Setup Parameters
    months = 60
    base_income = customer['avg_monthly_income']
    cv = customer['income_cv']
    rent = customer.get('rent', 1400)
    
    # Seed for consistency
    np.random.seed(42) 
    random.seed(42)
    
    # Storage
    ledger = []
    monthly_income_agg = []
    monthly_expenses_agg = []
    monthly_buffer_agg = []
    monthly_debt_agg = []
    
    current_date = datetime.now()
    
    # Initial State (Solid starting point)
    liquid_assets = 5000 
    current_debt = 0
    
    # 3. Generate Timeline (Past 60 Months)
    for i in range(months):
        month_offset = months - i - 1
        month_date = current_date - timedelta(days=month_offset*30)
        
        # --- A. INCOME GENERATION ---
        # 1. University Salary (Fixed Date: 25th)
        salary_amt = base_income
        ledger.append({
            'date': (month_date + timedelta(days=25)).strftime("%Y-%m-%d"),
            'description': 'University Payroll',
            'amount': round(salary_amt, 2),
            'type': 'inflow',
            'category': 'Income'
        })
        
        # 2. Occasional Consulting/Grants (Random: 30% chance per month)
        consulting_amt = 0
        if random.random() < 0.3:
            consulting_amt = random.uniform(1000, 3000)
            ledger.append({
                'date': (month_date + timedelta(days=random.randint(5, 20))).strftime("%Y-%m-%d"),
                'description': random.choice(['Research Grant', 'Consulting Fee', 'Book Royalties']),
                'amount': round(consulting_amt, 2),
                'type': 'inflow',
                'category': 'Income'
            })
            
        total_income = salary_amt + consulting_amt
        monthly_income_agg.append(total_income)
        
        # --- B. EXPENSE GENERATION ---
        total_expenses = 0
        
        # 1. Housing
        ledger.append({
            'date': (month_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            'description': 'Monthly Rent / Mortgage',
            'amount': -rent,
            'type': 'outflow',
            'category': 'Housing'
        })
        total_expenses += rent
        
        # 2. Essentials (Stable)
        essentials = (customer['avg_monthly_essential'] - rent) * random.uniform(0.95, 1.05)
        num_tx = random.randint(6, 12)
        for _ in range(num_tx):
            amt = essentials / num_tx
            ledger.append({
                'date': (month_date + timedelta(days=random.randint(1, 28))).strftime("%Y-%m-%d"),
                'description': random.choice(['Supermarket', 'Electricity', 'Internet', 'Petrol']),
                'amount': -round(amt, 2),
                'type': 'outflow',
                'category': 'Essential'
            })
        total_expenses += essentials

        # 3. Discretionary (Academic & Lifestyle)
        # George spends ~40% of disposable income
        disposable = max(0, total_income - total_expenses)
        lifestyle_spend = disposable * random.uniform(0.3, 0.5)
        
        # Academic Conferences (Seasonal: May & October)
        if month_date.month in [5, 10]:
            lifestyle_spend += 800
            ledger.append({
                'date': (month_date + timedelta(days=15)).strftime("%Y-%m-%d"),
                'description': 'Conference Travel / Accommodation',
                'amount': -800,
                'type': 'outflow',
                'category': 'Travel'
            })

        num_disc = random.randint(3, 6)
        for _ in range(num_disc):
            amt = lifestyle_spend / (num_disc + 1) # Split remaining
            ledger.append({
                'date': (month_date + timedelta(days=random.randint(1, 28))).strftime("%Y-%m-%d"),
                'description': random.choice(['Academic Books', 'Dining Out', 'Coffee', 'Gadgets']),
                'amount': -round(amt, 2),
                'type': 'outflow',
                'category': 'Discretionary'
            })
        total_expenses += lifestyle_spend
        monthly_expenses_agg.append(total_expenses)
        
        # --- C. BALANCE UPDATE ---
        net_flow = total_income - total_expenses
        liquid_assets += net_flow
        
        # Buffer Logic: George saves excess
        # Buffer Score = (Assets / Avg_Essentials) * 16.67
        avg_ess = np.mean(monthly_expenses_agg[-6:]) if len(monthly_expenses_agg) > 0 else total_expenses
        buffer_score = min(100, (liquid_assets / (avg_ess + 1)) * 16.67)
        
        monthly_buffer_agg.append(buffer_score)
        monthly_debt_agg.append(0) # George is debt-free in this scenario

    # Sort ledger
    ledger.sort(key=lambda x: x['date'])

    return {
        'customer_id': customer['customer_id'],
        'current_assets': round(liquid_assets, 2),
        'avg_monthly_essential': np.mean(monthly_expenses_agg[-12:]), 
        'monthly_income': monthly_income_agg,
        'monthly_buffer': monthly_buffer_agg,
        'monthly_debt': monthly_debt_agg,
        'transactions': ledger[-50:]  # Last 50 for context
    }
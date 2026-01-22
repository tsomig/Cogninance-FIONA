"""
Case database for RAG (Retrieval-Augmented Generation)
Contains successful intervention cases for similarity matching
"""

def get_case_database():
    """
    Knowledge base of successful financial interventions
    
    Returns:
    --------
    list : List of case dictionaries with solutions and improvements
    """
    return [
        {
            'description': 'Freelancer with irregular monthly income ranging €800-€3200, experiencing stress about money despite decent annual earnings',
            'solution': 'Income Smoother - automatically distribute earnings across weeks to create predictable cash flow',
            'improvement': '+12 FRI points (Stability component)',
            'category': 'income_volatility',
            'timeframe': '3 months',
            'customer_segment': 'freelancer'
        },
        {
            'description': 'Small emergency fund covering only 2 months of expenses, constant anxiety about unexpected costs',
            'solution': 'Automated savings plan with round-up feature and bonus deposit recommendations',
            'improvement': '+18 FRI points (Buffer component)',
            'category': 'buffer_building',
            'timeframe': '6 months',
            'customer_segment': 'low_buffer'
        },
        {
            'description': 'Steady salaried income but high credit card debt causing declining financial momentum',
            'solution': 'Debt consolidation loan with optimized payment plan and spending alerts',
            'improvement': '+15 FRI points (Momentum component)',
            'category': 'debt_management',
            'timeframe': '12 months',
            'customer_segment': 'debt_heavy'
        },
        {
            'description': 'Variable monthly expenses making budgeting impossible, overspending on discretionary items',
            'solution': 'AI-powered predictive budgeting with category-based spending alerts and goal tracking',
            'improvement': '+10 FRI points (Buffer component)',
            'category': 'expense_control',
            'timeframe': '4 months',
            'customer_segment': 'variable_spender'
        },
        {
            'description': 'Adequate savings but persistent anxiety about financial future despite objective security',
            'solution': 'Financial confidence coaching program with goal visualization and progress tracking',
            'improvement': '+8 FRI points (all components)',
            'category': 'psychological',
            'timeframe': '2 months',
            'customer_segment': 'anxious_saver'
        },
        {
            'description': 'Multiple income streams from gig economy jobs causing complexity and tax concerns',
            'solution': 'Unified financial dashboard with automated categorization and tax planning assistance',
            'improvement': '+14 FRI points (Stability component)',
            'category': 'income_diversification',
            'timeframe': '3 months',
            'customer_segment': 'multi_income'
        },
        {
            'description': 'Recent job loss with severance package, uncertain about how to manage transition period',
            'solution': 'Emergency fund optimization strategy with job search support and expense reduction plan',
            'improvement': '+11 FRI points (Buffer and Momentum components)',
            'category': 'life_transition',
            'timeframe': '6 months',
            'customer_segment': 'unemployed'
        },
        {
            'description': 'Young professional with student loans, struggling to balance debt repayment with saving',
            'solution': 'Balanced debt-savings strategy using avalanche method with automated contributions',
            'improvement': '+13 FRI points (Momentum component)',
            'category': 'debt_management',
            'timeframe': '12 months',
            'customer_segment': 'young_professional'
        },
        {
            'description': 'Small business owner with seasonal revenue fluctuations causing cash flow stress',
            'solution': 'Business cash reserve building with seasonal budgeting and credit line optimization',
            'improvement': '+16 FRI points (Buffer and Stability components)',
            'category': 'business_owner',
            'timeframe': '12 months',
            'customer_segment': 'entrepreneur'
        },
        {
            'description': 'Approaching retirement with concerns about adequacy of pension and savings',
            'solution': 'Retirement readiness assessment with spending projection and investment rebalancing',
            'improvement': '+9 FRI points (all components)',
            'category': 'retirement_planning',
            'timeframe': '6 months',
            'customer_segment': 'pre_retirement'
        },
        {
            'description': 'New parent with increased expenses and single income, feeling financially stretched',
            'solution': 'Family budget optimization with childcare cost strategies and emergency fund boost',
            'improvement': '+12 FRI points (Buffer component)',
            'category': 'life_transition',
            'timeframe': '6 months',
            'customer_segment': 'new_parent'
        },
        {
            'description': 'Recent graduate starting first job, no financial education or savings habits',
            'solution': 'Financial foundation program with automated savings, budgeting basics, and goal setting',
            'improvement': '+20 FRI points (all components)',
            'category': 'financial_education',
            'timeframe': '6 months',
            'customer_segment': 'young_adult'
        },
        {
            'description': 'Mid-career professional with lifestyle creep, spending matching income increases',
            'solution': 'Conscious spending analysis with automated savings rate increase tied to raises',
            'improvement': '+10 FRI points (Buffer and Momentum components)',
            'category': 'expense_control',
            'timeframe': '6 months',
            'customer_segment': 'mid_career'
        },
        {
            'description': 'Couple combining finances after marriage, different money attitudes causing conflict',
            'solution': 'Joint financial planning with yours-mine-ours account structure and shared goals',
            'improvement': '+11 FRI points (all components)',
            'category': 'relationship_finance',
            'timeframe': '4 months',
            'customer_segment': 'couple'
        },
        {
            'description': 'Chronic overspender with impulse buying habit impacting financial security',
            'solution': 'Behavioral intervention with 24-hour purchase rule and spending triggers identification',
            'improvement': '+14 FRI points (Buffer and Momentum components)',
            'category': 'behavioral_change',
            'timeframe': '6 months',
            'customer_segment': 'overspender'
        }
    ]


def get_cases_by_category(category):
    """
    Filter cases by category
    
    Parameters:
    -----------
    category : str
        Category to filter by (e.g., 'income_volatility', 'debt_management')
    
    Returns:
    --------
    list : Filtered list of cases
    """
    all_cases = get_case_database()
    return [case for case in all_cases if case['category'] == category]


def get_cases_by_segment(segment):
    """
    Filter cases by customer segment
    
    Parameters:
    -----------
    segment : str
        Customer segment (e.g., 'freelancer', 'young_professional')
    
    Returns:
    --------
    list : Filtered list of cases
    """
    all_cases = get_case_database()
    return [case for case in all_cases if case['customer_segment'] == segment]


def get_case_categories():
    """Get all unique categories"""
    all_cases = get_case_database()
    return list(set(case['category'] for case in all_cases))


def get_customer_segments():
    """Get all unique customer segments"""
    all_cases = get_case_database()
    return list(set(case['customer_segment'] for case in all_cases))


def search_cases(query_text):
    """
    Simple text search through cases
    
    Parameters:
    -----------
    query_text : str
        Search query
    
    Returns:
    --------
    list : Matching cases
    """
    all_cases = get_case_database()
    query_lower = query_text.lower()
    
    matching_cases = []
    for case in all_cases:
        # Search in description and solution
        if (query_lower in case['description'].lower() or 
            query_lower in case['solution'].lower()):
            matching_cases.append(case)
    
    return matching_cases


def get_case_statistics():
    """
    Get statistics about the case database
    
    Returns:
    --------
    dict : Statistics about cases
    """
    all_cases = get_case_database()
    
    # Calculate average improvements
    improvements = [int(case['improvement'].split('+')[1].split(' ')[0]) 
                   for case in all_cases]
    
    # Get timeframes
    timeframes = [case['timeframe'] for case in all_cases]
    
    return {
        'total_cases': len(all_cases),
        'avg_improvement': sum(improvements) / len(improvements),
        'max_improvement': max(improvements),
        'min_improvement': min(improvements),
        'categories': len(get_case_categories()),
        'segments': len(get_customer_segments()),
        'timeframes': {
            '2_months': timeframes.count('2 months'),
            '3_months': timeframes.count('3 months'),
            '4_months': timeframes.count('4 months'),
            '6_months': timeframes.count('6 months'),
            '12_months': timeframes.count('12 months')
        }
    }


# Example usage for testing
if __name__ == "__main__":
    # Test the database
    cases = get_case_database()
    print(f"Total cases: {len(cases)}")
    
    stats = get_case_statistics()
    print(f"\nStatistics:")
    print(f"Average improvement: {stats['avg_improvement']:.1f} FRI points")
    print(f"Categories: {stats['categories']}")
    print(f"Segments: {stats['segments']}")
    
    # Test search
    freelance_cases = search_cases("freelance")
    print(f"\nFreelance-related cases: {len(freelance_cases)}")
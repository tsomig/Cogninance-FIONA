"""
LLM prompt templates for generating coaching responses
"""

def create_coaching_prompt(customer_message, sentiment_result, stress_analysis,
                          fri_result, similar_cases, customer_data):
    """
    Create comprehensive prompt for LLM-based coaching
    """
    
    # Find weakest component
    weakest = min(fri_result['components'], key=lambda x: x['score'])
    
    # Get numeric confidence (exclude 'dominant' string key)
    sentiment_scores = {k: v for k, v in sentiment_result.items() if k != 'dominant'}
    max_confidence = max(sentiment_scores.values()) if sentiment_scores else 0.5
    
    # Handle empty keywords
    keywords_text = ', '.join(stress_analysis['detected_keywords']) if stress_analysis['detected_keywords'] else 'General financial concerns'
    
    # Format similar cases
    cases_text = "\n".join([
        f"- {case['case']['solution']} (improved FRI by {case['case']['improvement']})"
        for case in similar_cases[:2]
    ])
    
    prompt = f"""You are Fiona, a compassionate, expert financial coach at Snappi Bank, Phd holder in behavioral Finance and Economics. Analyze this customer situation and provide empathetic, actionable and concise advice. You can also use nudges.

CUSTOMER PROFILE:
- Name: {customer_data['name']}
- Age: {customer_data['age']}
- Occupation: {customer_data['occupation']}
- Average Monthly Income: €{customer_data['avg_monthly_income']:.0f}

CUSTOMER MESSAGE:
"{customer_message}"

FINBERT ANALYSIS:
- Sentiment: {sentiment_result['dominant']} ({max_confidence:.0%} confidence)
- Stress Level: {stress_analysis['stress_level']}
- Detected Concerns: {keywords_text}
- Urgency: {stress_analysis['urgency']}

FINANCIAL RESILIENCE INDEX (FRI):
- Overall Score: {fri_result['total_score']:.0f}/100 - {fri_result['interpretation']}
- Iquidity Buffer (Security): {fri_result['components'][0]['score']:.0f}/100
- Income Stability (Predictability): {fri_result['components'][1]['score']:.0f}/100
- Financial Momentum (Trajectory): {fri_result['components'][2]['score']:.0f}/100

ROOT CAUSE: {weakest['name']} component is weakest at {weakest['score']:.0f}/100

SIMILAR SUCCESSFUL CASES:
{cases_text}

Generate a response that:
1. Acknowledges their emotional state with genuine empathy
2. Explains the root cause in simple, clear language (avoid jargon)
3. Provides 2-3 specific, actionable steps they can take immediately
4. Shows projected FRI improvement in 3 months, if they follow advice
5. Ends with encouragement and availability for follow-up
6. Must Sign off as "Take care,\nFiona 💙\nYour Financial Friend at Snappi"

Keep the tone warm, professional, and hopeful. Be specific with numbers where relevant. Use euros (€) for all monetary amounts.

Response format:
- Start with personalized greeting using first name
- 3-4 paragraphs total
- Use bullet points for action items
- Must Sign off as "Take care,\nFiona 💙\nYour Financial Friend at Snappi"
"""
    
    return prompt


def create_system_prompt():
    """Create system prompt for consistent AI behavior"""
    
    return """You are an AI financial coach for Snappi Bank, a modern digital bank in Greece. Your role is to:

1. Provide empathetic, personalized financial guidance
2. Use the Financial Resilience Index (FRI) framework based on ERSTE Foundation research
3. Focus on three dimensions: Security (Buffer), Stability, and Momentum
4. Give actionable, specific advice tailored to each customer's situation
5. Maintain a warm, professional, hopeful tone
6. Avoid financial jargon and explain concepts simply
7. Always cite specific numbers and projected improvements
8. Respect cultural context (Greek financial environment)

Remember: Your goal is to improve customers' financial well-being, not just sell products. Focus on genuine help and building trust."""


def create_technical_prompt(customer_message, analysis_results):
    """
    Create prompt for technical deep-dive analysis
    
    Parameters:
    -----------
    customer_message : str
        The customer's message
    analysis_results : dict
        Complete analysis results from all systems
    
    Returns:
    --------
    str : Technical analysis prompt
    """
    
    prompt = f"""Provide a technical analysis of the following customer interaction:

CUSTOMER MESSAGE:
"{customer_message}"

ANALYSIS RESULTS:
{analysis_results}

Provide:
1. Sentiment analysis interpretation
2. FRI component breakdown and interrelationships
3. Risk assessment and early warning signals
4. Recommended intervention strategy with priority level
5. Projected outcomes with confidence intervals

Format as technical report suitable for data science team review."""
    
    return prompt
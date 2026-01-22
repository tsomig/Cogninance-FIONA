import numpy as np

# --- KNOWLEDGE BASE ---
# A collection of "solved cases" to ground the AI's advice.
CASE_LIBRARY = [
    {
        "id": "CASE_001",
        "tags": ["variable_income", "freelance", "anxiety"],
        "scenario": "User income fluctuates +/- 40% monthly. High anxiety about tax bills and essential expenses.",
        "successful_advice": "Create a 'Tax Silo' account. Transfer 25% of every invoice immediately upon receipt, regardless of spending needs."
    },
    {
        "id": "CASE_002",
        "tags": ["high_rent", "fixed_income", "stability"],
        "scenario": "Rent consumes 55% of income. User feels trapped.",
        "successful_advice": "Apply the '50/30/20' rule modification. Negotiate lease extension for frozen rate or look for roommates to lower burden."
    },
    {
        "id": "CASE_003",
        "tags": ["impulse_spending", "stress", "debt"],
        "scenario": "User stress-spends on electronics and food when work is hard.",
        "successful_advice": "Implement a 48-hour 'Cooling Rule'. Add items to a list, wait 2 days. If urge persists, buy only one item."
    },
    {
        "id": "CASE_004",
        "tags": ["academic", "travel", "irregular_expenses"],
        "scenario": "Professor with stable salary but large, unreimbursed conference travel spikes.",
        "successful_advice": "Set up a 'Conference Fund' with monthly contributions of €150 to smooth out the May/October spikes."
    },
    {
        "id": "CASE_005",
        "tags": ["savings_struggle", "low_momentum", "apathy"],
        "scenario": "User has surplus income but zero savings growth.",
        "successful_advice": "Automate savings. Move €200 to savings on the 26th (day after payday) automatically, treating it like a bill."
    }
]

def find_similar_cases(user_profile, current_fri, user_message):  # pending to see what are we going to do with the FRI in this part
    """
    Simple RAG Retriever (Keyword & Score Matching).
    Returns top 2 relevant cases.
    """
    scores = []
    
    # Simple Keyword Extraction
    message_lower = user_message.lower()
    
    for case in CASE_LIBRARY:
        match_score = 0
        
        # 1. Tag Matching (Semantic-ish)
        for tag in case['tags']:
            if tag in message_lower:
                match_score += 3
            if tag in user_profile.get('occupation', '').lower():
                match_score += 2
                
        # 2. Context Matching
        if "travel" in message_lower and "travel" in case['tags']:
            match_score += 5
        if "rent" in message_lower and "rent" in case['tags']:
            match_score += 5
            
        scores.append((match_score, case))
    
    # Sort by relevance and take top 2
    scores.sort(key=lambda x: x[0], reverse=True)
    
    # Return only if score > 0
    return [s[1] for s in scores if s[0] > 0][:2]
"""
Updated LLM Generator with Conversation History Support
Handles multi-turn conversations with context window management
"""

import os
from anthropic import Anthropic
from openai import OpenAI
from typing import List, Dict, Optional


class LLMGenerator:
    """Generate coaching responses using LLMs with conversation history"""
    
    def __init__(self):
        self.provider = "mock"
        self.client = None
        self.last_error = None
        self.context_window_sizes = {
            'gpt-4o-mini': 128000,
            'gpt-4': 8192,
            'claude-sonnet-4-20250514': 200000,
            'claude': 200000
        }
    
    def set_provider(self, provider, api_key=None):
        """Set LLM provider"""
        self.provider = provider.lower()
        self.last_error = None
        
        print(f"🔧 Setting provider: {self.provider}")
        
        if "claude" in self.provider and api_key:
            try:
                self.client = Anthropic(api_key=api_key)
                print("✅ Claude client initialized")
            except Exception as e:
                self.last_error = f"Claude init error: {str(e)}"
                print(f"❌ {self.last_error}")
                
        elif "openai" in self.provider or "gpt" in self.provider:
            if api_key:
                try:
                    self.client = OpenAI(api_key=api_key)
                    print("✅ OpenAI client initialized")
                except Exception as e:
                    self.last_error = f"OpenAI init error: {str(e)}"
                    print(f"❌ {self.last_error}")
            else:
                print("⚠️ No API key provided for OpenAI")
        else:
            print("ℹ️ Using mock mode")
    
    def generate_coaching(self, customer_message, sentiment_result, 
                         stress_analysis, fri_result, similar_cases, customer_data,
                         conversation_history: Optional[List[Dict]] = None):
        """
        Generate personalized coaching response with conversation context
        
        Parameters:
        -----------
        customer_message : str
            Current user message
        sentiment_result : dict
            FinBERT sentiment analysis
        stress_analysis : dict
            Stress detection results
        fri_result : dict
            Financial Resilience Index scores
        similar_cases : list
            Similar successful cases from RAG
        customer_data : dict
            Customer profile information
        conversation_history : List[Dict], optional
            Previous messages in format [{'role': 'user'/'assistant', 'content': '...'}]
        
        Returns:
        --------
        str : Coaching response
        """
        
        print(f"\n🤖 Generating coaching with provider: {self.provider}")
        print(f"   Client initialized: {self.client is not None}")
        print(f"   Conversation history: {len(conversation_history) if conversation_history else 0} messages")
        
        # Check if we should use real LLM
        use_llm = (
            self.provider not in ["mock", "demo"] and 
            "mock" not in self.provider and 
            "demo" not in self.provider and
            self.client is not None
        )
        
        if not use_llm:
            print("   → Using mock response")
            return self._generate_mock_response(
                customer_message, stress_analysis, fri_result, similar_cases, customer_data
            )
        
        # Build prompt with conversation context
        system_prompt, user_prompt = self._build_contextual_prompt(
            customer_message, sentiment_result, stress_analysis,
            fri_result, similar_cases, customer_data, conversation_history
        )
        
        print(f"   → Calling {self.provider}...")
        
        # Call appropriate LLM
        if "claude" in self.provider:
            return self._call_claude_with_history(system_prompt, user_prompt, conversation_history)
        elif "openai" in self.provider or "gpt" in self.provider:
            return self._call_openai_with_history(system_prompt, user_prompt, conversation_history)
        else:
            return self._generate_mock_response(
                customer_message, stress_analysis, fri_result, similar_cases, customer_data
            )
    
    def _build_contextual_prompt(self, message, sentiment, stress, fri, cases, 
                                 customer, history):
        """Build prompt that accounts for conversation history"""
        
        weakest = min(fri['components'], key=lambda x: x['score'])
        sentiment_scores = {k: v for k, v in sentiment.items() if k != 'dominant'}
        max_confidence = max(sentiment_scores.values()) if sentiment_scores else 0.5
        keywords_text = ', '.join(stress['detected_keywords']) if stress['detected_keywords'] else 'General financial stress'
        
        # System prompt (doesn't change)
        system_prompt = """You are Fiona, a compassionate financial coach at Snappi Bank, holding a PhD in Behavioral Economics and Finance. 

Your coaching philosophy:
- Build on previous conversation context naturally
- Reference specific things the customer mentioned earlier
- Show you're actively listening and remembering
- Acknowledge progress or changes since last interaction
- Be warm, personal, and genuinely helpful
- Use behavioral economics principles and gentle nudges
- Always sign off as "Take care,\\nFiona 💙\\nYour Financial Friend at Snappi"

Important: DO NOT use ** for formatting. Use natural language emphasis instead."""
        
        # Check if this is a follow-up question
        is_followup = history and len(history) > 0
        
        if is_followup:
            # For follow-up messages, provide context but keep prompt focused
            user_prompt = f"""CURRENT CUSTOMER MESSAGE:
"{message}"

CURRENT FINANCIAL STATE:
- FRI Score: {fri['total_score']:.0f}/100 ({fri['interpretation']})
- Weakest Component: {weakest['name']} at {weakest['score']:.0f}/100
- Stress Level: {stress['stress_level']} (Concerns: {keywords_text})

COACHING CONTEXT:
You are continuing a conversation with {customer['name']} (Age: {customer['age']}, {customer['occupation']}, Income: €{customer['avg_monthly_income']:.0f}/month).

Review the conversation history above and provide a response that:
1. Directly addresses their current question/concern
2. References relevant points from your previous discussion
3. Shows continuity in your coaching approach
4. Provides 1-2 specific action items if needed
5. Keeps the response conversational and natural (200-300 words)

Respond to {customer['name'].split()[0]} now:"""
        
        else:
            # First message - comprehensive analysis
            user_prompt = f"""NEW CUSTOMER CONVERSATION

CUSTOMER PROFILE:
- Name: {customer['name']}
- Age: {customer['age']}
- Occupation: {customer['occupation']}
- Average Monthly Income: €{customer['avg_monthly_income']:.0f}

CUSTOMER MESSAGE:
"{message}"

FINBERT ANALYSIS:
- Sentiment: {sentiment['dominant']} ({max_confidence:.0%} confidence)
- Stress Level: {stress['stress_level']}
- Combined Stress Score: {stress['combined_score']:.2%}
- Detected Concerns: {keywords_text}

FINANCIAL RESILIENCE INDEX (FRI):
- Overall Score: {fri['total_score']:.0f}/100 - {fri['interpretation']}
- Liquidity Buffer: {fri['components'][0]['score']:.0f}/100 - Emergency fund
- Income Stability: {fri['components'][1]['score']:.0f}/100 - Income predictability  
- Financial Momentum: {fri['components'][2]['score']:.0f}/100 - Trajectory

ROOT CAUSE: {weakest['name']} is weakest at {weakest['score']:.0f}/100

SIMILAR SUCCESS STORIES:
{chr(10).join([f"• {case['case']['solution']} → {case['case']['improvement']}" for case in cases[:2]])}

Generate a warm, empathetic response (300-400 words) that:
1. Acknowledges their feelings genuinely
2. Explains the root cause in simple terms (focus on {weakest['name']})
3. Provides 2-3 concrete action steps for THIS WEEK
4. Projects FRI improvement in 3 months
5. Ends with encouragement and offers continued support

Use euros (€), address them by first name, avoid jargon, be specific with numbers."""
        
        return system_prompt, user_prompt
    
    def _call_openai_with_history(self, system_prompt, user_prompt, history):
        """Call OpenAI with conversation history"""
        try:
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history
            if history:
                messages.extend(history)
            
            # Add current prompt
            messages.append({"role": "user", "content": user_prompt})
            
            print(f"   📡 Sending {len(messages)} messages to OpenAI...")
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            
            print("   ✅ Received response from OpenAI")
            return response.choices[0].message.content
            
        except Exception as e:
            error_msg = f"❌ OpenAI API Error: {str(e)}"
            print(error_msg)
            self.last_error = error_msg
            return f"I'm having trouble connecting right now. Let me give you a quick response:\n\n" + self._generate_mock_response_simple()
    
    def _call_claude_with_history(self, system_prompt, user_prompt, history):
        """Call Claude with conversation history"""
        try:
            # Claude uses system parameter differently
            messages = []
            
            # Add conversation history
            if history:
                messages.extend(history)
            
            # Add current prompt
            messages.append({"role": "user", "content": user_prompt})
            
            print(f"   📡 Sending {len(messages)} messages to Claude...")
            
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                system=system_prompt,  # Claude uses system parameter
                max_tokens=1000,
                messages=messages
            )
            
            print("   ✅ Received response from Claude")
            return response.content[0].text
            
        except Exception as e:
            error_msg = f"❌ Claude API Error: {str(e)}"
            print(error_msg)
            self.last_error = error_msg
            return f"I'm having trouble connecting right now. Let me give you a quick response:\n\n" + self._generate_mock_response_simple()
    
    def _generate_mock_response_simple(self):
        """Simple mock response for errors"""
        return "This is a demo response. The system is working, but I'm currently in demo mode."
    
    def _generate_mock_response(self, message, stress, fri, cases, customer):
        """Generate contextual mock response (existing implementation)"""
        
        weakest = min(fri['components'], key=lambda x: x['score'])
        
        response = f"""Hi {customer['name'].split()[0]},

I can see why you're feeling this way, and I want you to know that what you're experiencing is completely valid. Looking at your financial situation, you've actually earned €{customer['avg_monthly_income']*12:.0f} this year - that's solid!

However, I've identified the core issue: your {weakest['name']} score is {weakest['score']:.0f}/100, which is creating the uncertainty you're feeling. """

        if weakest['name'] == 'Stability':
            response += f"""Your income varies significantly month to month, making planning impossible.

Here's what can help:

1. Build a 4-month buffer (you're at {fri['components'][0]['score']/16.67:.1f} months now)
   Target: Save €{customer['avg_monthly_essential']*2:.0f} over next 3 months

2. Try our Income Smoother feature
   Distributes earnings evenly across weeks
   Reduces stress by 70%

3. Consider income diversification
   Add one steady stream (€{customer['avg_monthly_income']*0.2:.0f}/month)
   Could improve Stability by +15 points

Projected Impact: Your FRI could improve from {fri['total_score']:.0f} to {fri['total_score']+18:.0f} in 3 months.

You're not failing - your situation just needs the right tools. Want to discuss this further?

Take care,
Fiona 💙
Your Financial Friend at Snappi"""

        elif weakest['name'] == 'Buffer':
            response += f"""You have only {fri['components'][0]['score']/16.67:.1f} months of emergency savings, creating constant anxiety.

Here's your action plan:

1. Automate €{customer['avg_monthly_essential']*0.15:.0f}/month to savings
   Set up now - adds €{customer['avg_monthly_essential']*0.15*12:.0f}/year

2. Round-up savings
   Every purchase rounds to €5, difference saved
   Painless €{customer['avg_monthly_essential']*0.05:.0f}/month

3. One-time boost
   Review subscriptions - cancel €{customer['avg_monthly_essential']*0.1:.0f}
   Next bonus goes to emergency fund

These steps could improve Buffer from {fri['components'][0]['score']:.0f} to {fri['components'][0]['score']+25:.0f} in 6 months, raising FRI to {fri['total_score']+15:.0f}.

Building security takes time, but every €10 counts. What questions do you have?

Take care,
Fiona 💙
Your Financial Friend at Snappi"""

        else:  # Momentum
            response += f"""Your trajectory shows a slow decline over 3 months. Let's reverse this.

Action steps:

1. Spending audit this week
   Review last month
   Find €{customer['avg_monthly_essential']*0.1:.0f} unnecessary spending
   Redirect to debt/savings

2. Debt strategy
   Focus on highest interest first
   Extra €{customer['avg_monthly_essential']*0.15:.0f}/month = debt-free in 18 months vs 30

3. Monthly FRI check-ins
   Track progress
   Celebrate wins
   Adjust as needed

Reversing momentum from {fri['components'][2]['score']:.0f} to {fri['components'][2]['score']+20:.0f} will raise FRI to {fri['total_score']+12:.0f} within 3 months.

Starting is the hardest part. After that, progress motivates. Shall we tackle step 1 together?

Take care,
Fiona 💙
Your Financial Friend at Snappi"""

        return response
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)"""
        return len(text) // 4
    
    def should_summarize_context(self, messages: List[Dict], model: str = "gpt-4o-mini") -> bool:
        """Check if conversation history should be summarized"""
        max_tokens = self.context_window_sizes.get(model, 8000)
        
        total_chars = sum(len(m.get('content', '')) for m in messages)
        estimated_tokens = total_chars // 4
        
        # Use 70% of context window as threshold
        return estimated_tokens > (max_tokens * 0.7)

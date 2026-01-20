import os
from anthropic import Anthropic
from openai import OpenAI

class LLMGenerator:
    """Generate coaching responses using LLMs"""
    
    def __init__(self):
        self.provider = "mock"
        self.client = None
        self.last_error = None
    
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
                         stress_analysis, fri_result, similar_cases, customer_data):
        """Generate personalized coaching response"""
        
        print(f"\n🤖 Generating coaching with provider: {self.provider}")
        print(f"   Client initialized: {self.client is not None}")
        
        # Check if we should use real LLM
        use_llm = (
            self.provider not in ["mock", "demo"] and 
            "mock" not in self.provider and 
            "demo" not in self.provider and
            self.client is not None
        )
        
        print(f"   Will use real LLM: {use_llm}")
        
        if not use_llm:
            print("   → Using mock response")
            return self._generate_mock_response(
                customer_message, stress_analysis, fri_result, similar_cases, customer_data
            )
        
        # Build prompt
        prompt = self._build_prompt(
            customer_message, sentiment_result, stress_analysis,
            fri_result, similar_cases, customer_data
        )
        
        print(f"   → Calling {self.provider}...")
        
        # Call appropriate LLM
        if "claude" in self.provider:
            return self._call_claude(prompt)
        elif "openai" in self.provider or "gpt" in self.provider:
            return self._call_openai(prompt)
        else:
            print("   → Fallback to mock (no matching provider)")
            return self._generate_mock_response(
                customer_message, stress_analysis, fri_result, similar_cases, customer_data
            )
    
    def _build_prompt(self, message, sentiment, stress, fri, cases, customer):
        """Build comprehensive prompt for LLM"""
        
        weakest = min(fri['components'], key=lambda x: x['score'])
        
        # Get the numeric confidence score (not the 'dominant' key)
        sentiment_scores = {k: v for k, v in sentiment.items() if k != 'dominant'}
        max_confidence = max(sentiment_scores.values()) if sentiment_scores else 0.5
        
        # Handle cases where detected_keywords might be empty
        keywords_text = ', '.join(stress['detected_keywords']) if stress['detected_keywords'] else 'General financial stress'
        
        prompt = f"""You are a compassionate, expert financial coach at Snappi Bank in Greece. You are also a PhD holder in Behavioral Economics and Finance. Analyze this customer situation and provide empathetic, actionable advice. You can also use nudges.

CUSTOMER PROFILE:
- Name: {customer['name']}
- Age: {customer['age']}
- Occupation: {customer['occupation']}
- Average Monthly Income: €{customer['avg_monthly_income']:.0f}

CUSTOMER MESSAGE:
"{message}"

FINBERT SENTIMENT ANALYSIS:
- Sentiment: {sentiment['dominant']} ({max_confidence:.0%} confidence)
- Positive score: {sentiment['positive']:.2%}
- Negative score: {sentiment['negative']:.2%}
- Neutral score: {sentiment['neutral']:.2%}

STRESS DETECTION:
- Stress Level: {stress['stress_level']}
- Combined Stress Score: {stress['combined_score']:.2%}
- Detected Concerns: {keywords_text}
- Urgency: {stress['urgency']}

FINANCIAL RESILIENCE INDEX (FRI):
- Overall Score: {fri['total_score']:.0f}/100 - {fri['interpretation']}
- Liquidity Buffer (Security): {fri['components'][0]['score']:.0f}/100 - Emergency fund coverage
- Income Stability (Predictability): {fri['components'][1]['score']:.0f}/100 - Income volatility
- Financial Momentum (Trajectory): {fri['components'][2]['score']:.0f}/100 - Recent trend

ROOT CAUSE IDENTIFIED: The {weakest['name']} component is weakest at {weakest['score']:.0f}/100

SIMILAR SUCCESSFUL CASES FROM OUR DATABASE:
{chr(10).join([f"• {case['case']['solution']} → {case['case']['improvement']}" for case in cases[:2]])}

YOUR TASK:
Generate a personalized, empathetic coaching response, nudge style, (300-400 words) that:

1. Acknowledges emotions - Start by validating their feelings with genuine empathy
2. Explains root cause - Clearly explain why they feel this way based on the FRI analysis (use simple language, no jargon)
3. Provides 2-3 specific actions - Give concrete, numbered steps they can take THIS WEEK, do not use any ** in your responses
4. Shows projected impact - Quantify expected FRI improvement in 3 months if they follow advice
5. Ends with encouragement - Warm, hopeful closing that offers continued support

STYLE REQUIREMENTS:
- Use Greek financial context (euros, Greek banking culture)
- Tone: Warm, professional, hopeful (not corporate or robotic)
- Address customer by first name only
- Be specific with numbers (use exact euro amounts from their profile)
- No financial jargon - explain everything clearly
- Format action items with bold letters for emphasis
- Must Sign off as "Take care,\nFiona 💙\nYour Financial Friend at Snappi"

Begin your response now:"""
        
        return prompt
    
    def _call_openai(self, prompt):
        """Call OpenAI API"""
        try:
            print("   📡 Sending request to OpenAI...")
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Using gpt-4o-mini for cost efficiency, change to "gpt-4" for better quality
                messages=[
                    {"role": "system", "content": "You are Fiona, a compassionate, expert financial wellness coach for Snappi Bank. Holder of a PhD in behavioral Economics and Finance."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            print("   ✅ Received response from OpenAI")
            return response.choices[0].message.content
        except Exception as e:
            error_msg = f"❌ OpenAI API Error: {str(e)}"
            print(error_msg)
            self.last_error = error_msg
            return f"**Error calling OpenAI:** {str(e)}\n\n---\n\n**Falling back to demo response...**\n\n" + self._generate_mock_response_simple()
    
    def _call_claude(self, prompt):
        """Call Claude API"""
        try:
            print("   📡 Sending request to Claude...")
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            print("   ✅ Received response from Claude")
            return message.content[0].text
        except Exception as e:
            error_msg = f"❌ Claude API Error: {str(e)}"
            print(error_msg)
            self.last_error = error_msg
            return f"**Error calling Claude:** {str(e)}\n\n---\n\n**Falling back to demo response...**\n\n" + self._generate_mock_response_simple()
    
    def _generate_mock_response_simple(self):
        """Simple mock response for errors"""
        return "This is a demo response. Please check your API key and try again."
    
    def _generate_mock_response(self, message, stress, fri, cases, customer):
        """Generate mock response for demo"""
        
        weakest = min(fri['components'], key=lambda x: x['score'])
        
        response = f"""Hi {customer['name'].split()[0]},

I can see why you're feeling this way, and I want you to know that what you're experiencing is completely valid. Looking at your financial situation, you've actually earned €{customer['avg_monthly_income']*12:.0f} this year - that's solid!

However, I've identified the core issue: your **{weakest['name']}** score is {weakest['score']:.0f}/100, which is creating the uncertainty you're feeling. """

        if weakest['name'] == 'Stability':
            response += f"""Your income varies significantly month to month (some months €{customer['avg_monthly_income']*0.4:.0f}, others €{customer['avg_monthly_income']*1.6:.0f}), making planning impossible.

This isn't about earning more - it's about smoothing the ride. Here's what has helped others in your situation:

**1. Build a 4-month buffer** (you're at {fri['components'][0]['score']/16.67:.1f} months now)
   - This lets you mentally shift from panic-mode to planning-mode
   - Target: Save €{customer['avg_monthly_essential']*2:.0f} over next 3 months

**2. Try our Income Smoother feature**
   - Automatically distributes earnings across weeks
   - €{customer['avg_monthly_income']*1.6:.0f} in January becomes €{customer['avg_monthly_income']*1.6/4:.0f}/week for 4 weeks
   - Reduces feast-or-famine stress by 70%

**3. Consider income diversification**
   - Add one small, steady income stream (€{customer['avg_monthly_income']*0.2:.0f}/month)
   - This alone can improve your Stability score by +15 points

**Projected Impact:**
If you implement these steps, your FRI could improve from {fri['total_score']:.0f} to {fri['total_score']+18:.0f} in 3 months, with your stress level dropping significantly.

You're not failing at finances - your situation just needs the right tools. I'm here to support you every step of the way. Want me to set up the Income Smoother for you?

Take care,
Fiona
You Financial Frieand at Snappi"""

        elif weakest['name'] == 'Buffer':
            response += f"""You have only {fri['components'][0]['score']/16.67:.1f} months of emergency savings, creating constant background anxiety.

**Here's your action plan:**

**1. Automate €{customer['avg_monthly_essential']*0.15:.0f}/month to savings**
   - Set it up now - takes 2 minutes
   - You won't miss this amount, but it adds up to €{customer['avg_monthly_essential']*0.15*12:.0f}/year

**2. Round-up savings feature**
   - Every purchase rounds to nearest €5, difference goes to savings
   - Painless way to add €{customer['avg_monthly_essential']*0.05:.0f}/month

**3. One-time boost**
   - Review subscriptions - cancel €{customer['avg_monthly_essential']*0.1:.0f} you don't use
   - Put next bonus/tax refund directly to emergency fund

**Projected Impact:**
These steps could improve your Buffer from {fri['components'][0]['score']:.0f} to {fri['components'][0]['score']+25:.0f} in 6 months, raising your overall FRI to {fri['total_score']+15:.0f}.

Building security takes time, but every €10 saved is progress. You've got this! 💪

Take care,
Fiona
You Financial Frieand at Snappi"""

        else:  # Momentum
            response += f"""Your financial trajectory needs attention - things have been slowly declining over the past 3 months.

**Let's reverse this trend:**

**1. Spending audit (this week)**
   - Review last month's transactions
   - Identify €{customer['avg_monthly_essential']*0.1:.0f} in unnecessary spending
   - Redirect to debt/savings

**2. Debt strategy**
   - Focus on highest-interest debt first
   - Extra €{customer['avg_monthly_essential']*0.15:.0f}/month payment = €{customer['avg_monthly_essential']*0.15*12:.0f}/year
   - Could be debt-free in 18 months instead of 30

**3. Monthly check-ins**
   - Review FRI every month
   - Celebrate small wins
   - Adjust strategy as needed

**Projected Impact:**
Reversing momentum from {fri['components'][2]['score']:.0f} to {fri['components'][2]['score']+20:.0f} will raise your FRI to {fri['total_score']+12:.0f} within 3 months, creating positive psychological momentum.

The hardest part is starting. After that, progress becomes motivating. I'll be here cheering you on! 🎯

Take care,
Fiona
You Financial Frieand at Snappi """

        return response
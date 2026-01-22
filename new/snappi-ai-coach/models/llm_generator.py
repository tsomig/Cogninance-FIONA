import os
from google import genai
from anthropic import Anthropic, AuthenticationError, NotFoundError, BadRequestError
from openai import OpenAI
from pathlib import Path

class LLMGenerator:
    """
    Multi-provider LLM Generator with Fallback Logic + RAG/CAG
    Priority: Gemini (google.genai) -> Claude -> OpenAI
    """
    
    def __init__(self):
        self.clients = {}
        self.provider_status = {
            "gemini": False,
            "claude": False,
            "openai": False
        }
    
    def setup_providers(self, secrets):
        """Initialize all available providers from secrets dict"""
        print("\n🔧 CONFIGURING LLM PROVIDERS...")

        # 1. Setup Gemini (Primary)
        if secrets.get("GEMINI_API_KEY"):
            try:
                self.clients['gemini'] = genai.Client(api_key=secrets["GEMINI_API_KEY"])
                self.provider_status['gemini'] = True
                print("   ✅ Gemini Connected (Primary)")
            except Exception as e:
                print(f"   ❌ Gemini Error: {e}")

        # 2. Setup Claude (Secondary)
        if secrets.get("ANTHROPIC_API_KEY"):
            try:
                self.clients['claude'] = Anthropic(api_key=secrets["ANTHROPIC_API_KEY"])
                self.provider_status['claude'] = True
                print("   ✅ Claude Connected (Fallback 1)")
            except Exception as e:
                print(f"   ❌ Claude Error: {e}")

        # 3. Setup OpenAI (Tertiary)
        if secrets.get("OPENAI_API_KEY"):
            try:
                self.clients['openai'] = OpenAI(api_key=secrets["OPENAI_API_KEY"])
                self.provider_status['openai'] = True
                print("   ✅ OpenAI Connected (Fallback 2)")
            except Exception as e:
                print(f"   ❌ OpenAI Error: {e}")

    # --- UPDATED SIGNATURE: Added chat_history argument ---
    def generate_coaching(self, customer_message, sentiment_result, 
                         stress_analysis, fri_result, similar_cases, customer_data, chat_history=""):
        """
        Generates response using Fallback Cascade + RAG/CAG Context + Chat History.
        """
        # Build the "Mega-Prompt" with all context
        prompt = self._build_prompt(customer_message, sentiment_result, stress_analysis, fri_result, similar_cases, customer_data, chat_history)
        
        # --- FALLBACK LOGIC ---
        if self.provider_status['gemini']:
            try:
                return self._call_gemini(prompt)
            except Exception as e:
                print(f"   ⚠️ Gemini Failed: {str(e)[:50]}... Switching...")

        if self.provider_status['claude']:
            try:
                return self._call_claude(prompt)
            except Exception as e:
                print(f"   ⚠️ Claude Failed: {str(e)[:50]}... Switching...")

        if self.provider_status['openai']:
            try:
                return self._call_openai(prompt)
            except Exception as e:
                print(f"   ⚠️ OpenAI Failed: {str(e)[:50]}...")

        return self._generate_mock_response(customer_data)

    def generate_audio_response(self, text_response):
        """Audio generation is DISABLED per user requirement."""
        return None

    # --- INTERNAL CALLS ---

    def _call_gemini(self, prompt):
        response = self.clients['gemini'].models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
        return response.text

    def _call_claude(self, prompt):
        # Tries multiple Claude model IDs
        models_to_try = [
            "claude-3-5-sonnet-latest", "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"
        ]
        for model_id in models_to_try:
            try:
                msg = self.clients['claude'].messages.create(
                    model=model_id, max_tokens=300,
                    messages=[{"role": "user", "content": prompt}]
                )
                return msg.content[0].text
            except (NotFoundError, BadRequestError): continue
            except Exception as e: raise e
        raise Exception("No working Claude model found.")

    def _call_openai(self, prompt):
        response = self.clients['openai'].chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    # --- UPDATED PROMPT: Explicit History Section ---
    def _build_prompt(self, message, sentiment, stress, fri, similar_cases, customer, chat_history):
        
        # 1. RAG Context
        rag_context = ""
        if similar_cases:
            rag_context = "RELEVANT PAST CASES (GUIDANCE):\n"
            for case in similar_cases:
                rag_context += f"- Scenario: {case['scenario']}\n  Proven Strategy: {case['successful_advice']}\n"
        else:
            rag_context = "NO SIMILAR PAST CASES FOUND."

        # 2. CAG Context (Transaction Ledger)
        all_tx = fri.get('transactions', [])
        recent_tx = all_tx[-15:] if len(all_tx) > 15 else all_tx
        
        tx_str = ""
        for t in recent_tx:
            cat = t.get('category', 'General')
            tx_str += f"- {t['date']} [{cat}]: {t['description']} ({t['amount']}€)\n"
        
        # 3. Mappings
        dom_emotion = sentiment.get('dominant', 'neutral')
        dom_score = sentiment.get(dom_emotion, 0.0) 
        stress_lvl = stress.get('stress_level', 'LOW')
        is_stressed = "YES" if stress_lvl in ["HIGH", "MODERATE"] else "NO"
        
        return f"""
        [ROLE]
        You are Fiona, an advanced financial coach driven by behavioral economics.
        
        [CAG: FINANCIAL CONTEXT]
        User: {customer['name']} ({customer['occupation']})
        (Internal Context Only): FRI Score: {fri['total_score']:.0f}/100
        
        [CAG: RECENT TRANSACTION LEDGER]
        {tx_str}
        
        [EMOTIONAL STATE]
        Emotion: {dom_emotion} (Confidence: {dom_score:.2f})
        Stress Detected: {is_stressed} ({stress_lvl})
        
        [CONVERSATION CONTEXT (Do not repeat what was already said)]
        {chat_history}
        
        {rag_context}
        
        [CURRENT USER MESSAGE]
        "{message}"
        
        [INSTRUCTIONS]
        1. **Context Awareness**: Read the [CONVERSATION CONTEXT]. If you have already answered a question, do not repeat the full explanation. Just acknowledge it and move forward.
        2. **Natural Flow**: If the user says something short (e.g., "Thanks", "Okay"), respond naturally without forcing a financial analysis.
        3. **Deep Analysis (Only when asked)**: If asked about finances, use the Ledger to give specific insights (e.g., "I see you spent €X on books...").
        4. **Tone**: Warm, mother-like, spoken directly (NO asterisks).
        5. **Deep Transaction Analysis**: Look at the 'Transaction Ledger' above. Instead of quoting the FRI score, summarize the *behavior* you see. (e.g., "I notice you've had several large travel expenses recently...").
        6. **Detailed Summaries**: If the user asks about their finances, group the transactions mentally and give a qualitative summary (e.g., "You spent heavily on Dining this month").
        7. **No Score Dropping**: Do NOT mention the specific FRI number (e.g. "65") or the FinBERT emotion unless the user explicitly asks for them. Use them only to set your *tone*.
        8. CRITICAL: Do NOT use asterisks (*) or stage directions (e.g., *smiles*), nor icons. Output ONLY the spoken words.
        9. Keep it warm, mother-like, and spoken (no asterisks).
        10. Provide all necessary details if asked for (e.g. holidays planning)
        11. Reply in normal, comforting sentences, warm, and mother-like. Be empathetic but professional.
        12. Analyze the FRI index if asked for. FRI Score: {fri['total_score']:.0f}/100
        """

    def _generate_mock_response(self, customer):
        return f"System Offline. But I know you are {customer['name']}."
        

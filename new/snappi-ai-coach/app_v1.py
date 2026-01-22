import os
# --- SUPPRESS TENSORFLOW LOGS ---
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import time
import json
import numpy as np
import plotly.graph_objects as go
import plotly.utils
from flask import Flask, render_template_string, request, jsonify, make_response
from pathlib import Path

# --- IMPORTS ---
from models.finbert_analyzer import FinBERTAnalyzer
from models.fri_calculator import FRICalculator
from models.llm_generator import LLMGenerator
from data.mock_data import get_customer_profiles, get_transaction_history
from data.case_database import find_similar_cases  # <--- NEW RAG IMPORT
from chat_history.chat_history_manager import ConversationManager

app = Flask(__name__)
app.secret_key = "fiona_secret_key"

# --- SECRETS LOADER ---
def load_secrets():
    """Reads ALL API KEYS from secrets.toml"""
    secrets = {}
    paths = [Path("secrets.toml"), Path(".streamlit/secrets.toml")]
    for path in paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        if "=" in line:
                            key, value = line.split("=", 1)
                            secrets[key.strip()] = value.strip().strip('"').strip("'")
            except Exception as e: print(f"Error reading secrets: {e}")
    return secrets

# --- SYSTEM STATE ---
class SystemState:
    def __init__(self):
        print("\n🚀 STARTING FIONA v3.3 (FRI + MOCK DATA + FINBERT + RAG + CAG)...")
        
        # 1. Initialize Models
        self.analyzer = FinBERTAnalyzer()
        self.fri_calc = FRICalculator()
        self.llm = LLMGenerator()
        self.conv_manager = ConversationManager()
        
        # 2. Load Specific User (George)
        profiles = get_customer_profiles()
        self.customer = list(profiles.values())[0] # Forces George
        
        # 3. Load 5-Year Granular Data
        # This returns the dict with 'transactions' (granular) AND 'monthly_income' (aggregated)
        self.transactions = get_transaction_history(self.customer['customer_id'])
        
        # 4. Calculate FRI (CAG Layer 1)
        self.fri_data = self.fri_calc.calculate_fri(self.transactions)
        
        # 5. Inject Granular Transactions into FRI Object (CAG Layer 2)
        # This ensures the LLM can see specific line items like "Conference Travel"
        self.fri_data['transactions'] = self.transactions['transactions']
        
        # 6. Build History Graph
        try:
            self.history = self.fri_calc.calculate_monthly_fri(self.transactions)
        except:
            self.history = []

        self.conv_manager.get_or_create_session("session_george")
        
        # 7. Setup LLM Providers
        secrets = load_secrets()
        self.llm.setup_providers(secrets)

system = SystemState()

# --- FRONTEND TEMPLATE (Visuals) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>💙 Fiona AI v3.3</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #05050A; --sidebar: #0F0F16; --card: #1A1A24; --accent: linear-gradient(90deg, #4A9EFF, #764BA2); --text: #E0E0E0; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; margin: 0; display: flex; height: 100vh; overflow: hidden; }
        .sidebar { width: 340px; background: var(--sidebar); border-right: 1px solid #2A2A35; padding: 20px; display: flex; flex-direction: column; gap: 15px; overflow-y: auto; }
        .brand { font-size: 24px; font-weight: 700; background: var(--accent); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .version { font-size: 10px; color: #666; letter-spacing: 1px; margin-bottom: 20px; }
        .metric-card { background: var(--card); border: 1px solid #2A2A35; border-radius: 12px; padding: 15px; text-align: center; }
        .metric-val { font-size: 28px; font-weight: 700; background: var(--accent); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .metric-label { font-size: 11px; color: #88A; text-transform: uppercase; margin-top: 5px; }
        .main { flex: 1; display: flex; flex-direction: column; }
        .chat-box { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; scroll-behavior: smooth; }
        .msg { max-width: 70%; padding: 12px 16px; border-radius: 12px; line-height: 1.5; font-size: 15px; animation: fadeIn 0.3s ease; }
        .user { align-self: flex-end; background: #2A2A35; color: #fff; border-bottom-right-radius: 2px; }
        .bot { align-self: flex-start; background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%); border: 1px solid #4A9EFF; border-bottom-left-radius: 2px; }
        .input-area { padding: 20px; background: var(--bg); border-top: 1px solid #2A2A35; }
        form { display: flex; gap: 10px; align-items: center; }
        input { flex: 1; background: #1A1A24; border: 1px solid #2A2A35; padding: 15px; border-radius: 8px; color: white; font-size: 16px; outline: none; }
        input:focus { border-color: #4A9EFF; }
        button { background: #1A1A24; border: 1px solid #2A2A35; width: 50px; height: 50px; border-radius: 8px; color: white; cursor: pointer; font-size: 20px; display: flex; align-items: center; justify-content: center; }
        button:hover { background: #2A2A35; }
        .send { background: var(--accent); border: none; }
        .recording { animation: pulse 1.5s infinite; background: #3a1c1c; border-color: #ff4b4b; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0.4); } 100% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0); } }
        .typing { font-size: 12px; color: #88A; margin-left: 20px; margin-bottom: 5px; height: 15px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="brand">💙 Fiona AI</div>
        <div class="metric-card"><div class="metric-val">{{ fri_score }}</div><div class="metric-label">Financial Resilience</div></div>
        <div class="metric-card" style="padding: 0; overflow: hidden;"><div id="radar" style="height: 200px;"></div></div>
        <div class="metric-card" style="padding: 0; overflow: hidden;"><div id="history" style="height: 180px;"></div></div>
    </div>
    <div class="main">
        <div class="chat-box" id="chat">
            <div class="msg bot">Hello {{ name }}! I see your recent data. How are you feeling about your finances today?</div>
        </div>
        <div class="typing" id="typing"></div>
        <div class="input-area">
            <form id="form">
                <input type="text" id="input" placeholder="Type or speak..." autocomplete="off">
                <button type="button" id="mic">🎙️</button>
                <button type="submit" class="send">➔</button>
            </form>
        </div>
    </div>
    <script>
        const radar = {{ radar | safe }};
        const hist = {{ history | safe }};
        Plotly.newPlot('radar', [{type: 'scatterpolar', r: radar.v, theta: radar.c, fill: 'toself', line: {color: '#4A9EFF'}, fillcolor: 'rgba(74, 158, 255, 0.2)'}], {polar: {radialaxis: {visible: true, showticklabels: false}, bgcolor: 'rgba(0,0,0,0)'}, paper_bgcolor: 'rgba(0,0,0,0)', margin: {l:25, r:25, t:10, b:10}, showlegend: false}, {displayModeBar: false});
        Plotly.newPlot('history', [{x: hist.m, y: hist.b, type: 'scatter', mode: 'lines', name: 'Buffer', line: {color: '#4CAF50'}}, {x: hist.m, y: hist.s, type: 'scatter', mode: 'lines', name: 'Stability', line: {color: '#FFC107'}}, {x: hist.m, y: hist.mom, type: 'scatter', mode: 'lines', name: 'Momentum', line: {color: '#F44336'}}], {paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', xaxis: {showgrid: false, color: '#666'}, yaxis: {showgrid: true, gridcolor: '#222', range: [0, 100]}, showlegend: true, legend: {x:0, y:1.2, orientation: 'h'}, margin: {l:25, r:10, t:0, b:20}}, {displayModeBar: false});

        const form = document.getElementById('form');
        const input = document.getElementById('input');
        const chat = document.getElementById('chat');
        const typing = document.getElementById('typing');
        const mic = document.getElementById('mic');

        function addMsg(text, who) {
            const div = document.createElement('div');
            div.className = `msg ${who}`;
            div.innerHTML = text.replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>').replace(/\\n/g, '<br>');
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            addMsg(text, 'user');
            typing.innerText = "Fiona is thinking...";
            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text})
                });
                const data = await res.json();
                typing.innerText = "";
                addMsg(data.response, 'bot');
            } catch { typing.innerText = "Error."; }
        });

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.lang = 'en-US';
            mic.onclick = () => {
                if (mic.classList.contains('recording')) {
                    recognition.stop();
                } else {
                    recognition.start();
                    mic.innerText = '⏹️';
                    mic.classList.add('recording');
                    input.placeholder = "Listening...";
                }
            };
            recognition.onresult = (e) => {
                const text = e.results[0][0].transcript;
                input.value = text;
                form.dispatchEvent(new Event('submit'));
            };
            recognition.onend = () => {
                mic.innerText = '🎙️';
                mic.classList.remove('recording');
                input.placeholder = "Type or speak...";
            };
        } else {
            mic.onclick = () => alert("Use Chrome/Edge for voice.");
        }
    </script>
</body>
</html>
"""

# --- ROUTES ---
@app.route('/')
def home():
    response = make_response(render_template_string(
        HTML_TEMPLATE,
        fri_score=f"{system.fri_data['total_score']:.0f}",
        name=system.customer['name'].split()[0],
        radar=json.dumps({'c': [c['name'] for c in system.fri_data['components']], 'v': [c['score'] for c in system.fri_data['components']]}),
        history=json.dumps({
            'm': [x['month'] for x in system.history],
            'b': [x['buffer'] for x in system.history],
            's': [x['stability'] for x in system.history],
            'mom': [x['momentum'] for x in system.history]
        })
    ))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# ... (Previous imports remain the same) ...

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get('message', '')
    
    # 1. Update History
    session = system.conv_manager.get_or_create_session("session_george")
    session.add_user_message(user_msg)
    
    # 2. FinBERT Analysis
    sentiment = system.analyzer.analyze_sentiment(user_msg)
    stress = system.analyzer.detect_stress(user_msg)
    
    # 3. RAG Retrieval
    similar_cases = find_similar_cases(system.customer, system.fri_data['total_score'], user_msg)
    
    # 4. Context Builder (Get clean history string)
    recent = session.get_recent_messages(6) # Increased to 6 for better context
    context_str = "\n".join([f"{m.role}: {m.content}" for m in recent])
    
    # 5. Generate Response (PASSING HISTORY SEPARATELY)
    resp_text = system.llm.generate_coaching(
        customer_message=user_msg,      # The fresh input
        sentiment_result=sentiment,
        stress_analysis=stress,
        fri_result=system.fri_data,
        similar_cases=similar_cases,
        customer_data=system.customer,
        chat_history=context_str        # The history buffer
    )
    
    # 6. Save & Return
    session.add_assistant_message(resp_text)
    return jsonify({'response': resp_text, 'audio': None})

if __name__ == '__main__':
    print("✅ FIONA v3.3 RUNNING on http://127.0.0.1:5000")
    app.run(port=5000, debug=True)
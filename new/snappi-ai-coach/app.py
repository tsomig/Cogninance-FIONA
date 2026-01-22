import streamlit as st
import time
import os
import plotly.graph_objects as go
from pathlib import Path

# Custom imports
from models.finbert_analyzer import FinBERTAnalyzer
from models.fri_calculator import FRICalculator
from models.llm_generator import LLMGenerator
from data.mock_data import get_customer_profiles, get_transaction_history
from chat_history.chat_history_manager import ConversationManager

# Check for recorder
try:
    from streamlit_audiorecorder import audiorecorder
    HAS_RECORDER = True
except ImportError:
    HAS_RECORDER = False

# ==========================================
# 1. SETUP & STYLING
# ==========================================
st.set_page_config(page_title="Fiona AI", page_icon="💙", layout="wide")

st.markdown("""
<style>
    /* Main Theme */
    .stApp { background-color: #05050A; color: #E0E0E0; }
    [data-testid="stSidebar"] { background-color: #0F0F16; border-right: 1px solid #1F1F2E; }
    
    /* Metrics Styling */
    .metric-container { 
        background: #1A1A24; border-radius: 12px; padding: 15px; 
        margin-bottom: 10px; text-align: center; border: 1px solid #2A2A35; 
    }
    .metric-value { 
        font-size: 28px; font-weight: 700; 
        background: linear-gradient(90deg, #4A9EFF, #764BA2); 
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
    }
    .metric-label { font-size: 12px; color: #8888AA; text-transform: uppercase; }
    
    /* 🎤 FLOATING MIC BUTTON (Floating Action Button Style) 🎤 */
    .floating-mic {
        position: fixed;
        bottom: 90px;  /* Sits just above the chat input */
        right: 30px;
        z-index: 99999;
        background-color: #1A1A24;
        border-radius: 50%;
        padding: 5px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5);
        border: 1px solid #4A9EFF;
    }
    
    /* Adjust the recorder component to fit inside the bubble */
    .stAudioRecorder > div {
        background: transparent !important;
        box-shadow: none !important;
        width: 50px !important;
        height: 50px !important;
    }
    .stAudioRecorder button {
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize State
if 'setup_complete' not in st.session_state:
    st.session_state.analyzer = FinBERTAnalyzer()
    st.session_state.fri_calc = FRICalculator()
    st.session_state.llm = LLMGenerator()
    st.session_state.conv_manager = ConversationManager()
    
    # Try loading key
    api_key = st.secrets.get("OPENAI_API_KEY", "")
    if api_key: st.session_state.llm.set_provider("openai", api_key)
    
    # Setup George
    st.session_state.active_session_id = "session_george"
    st.session_state.conv_manager.get_or_create_session("session_george")
    
    # Load Data
    profiles = get_customer_profiles()
    st.session_state.current_customer = list(profiles.values())[0] # George
    
    # Calc FRI
    cid = st.session_state.current_customer['customer_id']
    st.session_state.current_fri = st.session_state.fri_calc.calculate_fri(get_transaction_history(cid))
    
    st.session_state.setup_complete = True

# ==========================================
# 2. SIDEBAR COCKPIT
# ==========================================
with st.sidebar:
    st.markdown(f"### 💙 Hello, {st.session_state.current_customer['name']}")
    
    if not st.session_state.llm.client:
        st.error("⚠️ Voice Needs API Key")
        api_input = st.text_input("Enter OpenAI Key", type="password")
        if api_input:
            st.session_state.llm.set_provider("openai", api_input)
            st.rerun()

    st.markdown("---")
    
    # Metrics
    fri = st.session_state.current_fri
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-label">Financial Resilience</div>
        <div class="metric-value">{fri['total_score']:.0f}</div>
    </div>
    """, unsafe_allow_html=True)

    # Radar
    categories = [c['name'] for c in fri['components']]
    values = [c['score'] for c in fri['components']]
    fig = go.Figure(go.Scatterpolar(r=values, theta=categories, fill='toself', line_color='#4A9EFF'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], showticklabels=False), bgcolor='rgba(0,0,0,0)'), paper_bgcolor='rgba(0,0,0,0)', height=200, margin=dict(l=20, r=20, t=20, b=20), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 3. CHAT INTERFACE
# ==========================================
chat_session = st.session_state.conv_manager.sessions["session_george"]

# --- DISPLAY HISTORY ---
for msg in chat_session.messages:
    with st.chat_message(msg.role):
        st.markdown(msg.content)

# --- FLOATING MIC BUTTON ---
audio_input = None
if HAS_RECORDER:
    # We wrap it in a floating container CSS class
    st.markdown('<div class="floating-mic">', unsafe_allow_html=True)
    # Using a container to isolate the recorder
    with st.container():
        # 🎙️ = Record, ⏹️ = Stop
        audio_data = audiorecorder("🎙️", "⏹️")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if len(audio_data) > 0:
        # Simulate STT Processing
        audio_input = "Fiona, I am worried about my research grant money."

# --- TEXT INPUT ---
user_text = st.chat_input("Type a message...")

# --- PROCESSING ---
final_input = audio_input if audio_input else user_text

if final_input:
    # 1. Show User Message
    with st.chat_message("user"):
        st.write(final_input)
    chat_session.add_user_message(final_input)
    
    # 2. Assistant Response
    with st.chat_message("assistant"):
        # SPEED FIX: Only spinner for text gen
        with st.spinner("Thinking..."):
            response_text = st.session_state.llm.generate_coaching(
                customer_message=final_input,
                sentiment_result={'dominant': 'Negative'}, 
                stress_analysis={'stress_level': 'Medium', 'detected_keywords': []},
                fri_result=st.session_state.current_fri,
                similar_cases=[],
                customer_data=st.session_state.current_customer
            )
        
        # SPEED FIX: Show text IMMEDIATELY
        st.markdown(response_text)
        
        # GENERATE AUDIO IN BACKGROUND
        if st.session_state.llm.client:
            status = st.empty()
            status.caption("🔈 Fiona is speaking...")
            
            audio_path = st.session_state.llm.generate_audio_response(response_text)
            
            if audio_path and os.path.exists(audio_path):
                status.empty()
                # Play audio
                with open(audio_path, "rb") as f:
                    audio_bytes = f.read()
                st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            else:
                status.warning("Audio generation failed")
            
        chat_session.add_assistant_message(response_text)
    
    # Reload for audio input to reset button
    if audio_input:
        time.sleep(1)
        st.rerun()
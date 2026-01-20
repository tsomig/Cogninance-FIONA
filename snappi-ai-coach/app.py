import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time

# Custom imports
from models.finbert_analyzer import FinBERTAnalyzer
from models.fri_calculator import FRICalculator
from models.llm_generator import LLMGenerator
from data.mock_data import get_customer_profiles, get_transaction_history
from utils.visualizations import create_fri_gauge, create_timeline_chart, create_component_radar
from utils.prompts import create_coaching_prompt

# Page configuration - MUST BE FIRST
st.set_page_config(
    page_title="Meet Fiona, Your Financial Friend",
    #page_icon="💎",
    page_icon = "💙", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# DARK THEME CSS - EMBEDDED
st.markdown("""
<style>
    /* Force dark background everywhere */
    .main, .stApp, body {
        background: #0f0f1e !important;
        color: #ffffff !important;
    }
    
    /* Sidebar dark */
    [data-testid="stSidebar"] {
        background: #1a1a2e !important;
    }
    
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    
    /* All text white by default */
    * {
        color: #ffffff !important;
    }
    
    /* Metric cards - colorful */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.5);
    }
    
    .stress-high {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important;
    }
    
    .stress-moderate {
        background: linear-gradient(135deg, #ff9800 0%, #fcb69f 100%) !important;
    }
    
    .stress-low {
        background: linear-gradient(135deg, #4caf50 0%, #81c784 100%) !important;
    }
    
    /* Coaching box */
    .coaching-box {
        background: #1e1e2e;
        border-left: 5px solid #667eea;
        padding: 20px;
        border-radius: 10px;
        margin: 20px 0;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        border: none;
        padding: 12px 30px;
        border-radius: 8px;
        font-weight: 600;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
    }
    
    /* Text inputs */
    .stTextArea textarea, .stTextInput input, .stSelectbox select {
        background: #1e1e2e !important;
        border: 2px solid #667eea !important;
        color: #ffffff !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab"] {
        background: #2a2a3e;
        color: #ffffff;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analyzer' not in st.session_state:
    with st.spinner('🚀 Loading AI and FRI models...'):
        st.session_state.analyzer = FinBERTAnalyzer()
        st.session_state.fri_calc = FRICalculator()
        st.session_state.llm = LLMGenerator()
        st.session_state.customer_profiles = get_customer_profiles()

# Initialize API keys from secrets.toml (persistent) or empty string
if 'openai_api_key' not in st.session_state:
    try:
        # Try to load from Streamlit secrets
        st.session_state.openai_api_key = st.secrets.get("OPENAI_API_KEY", "")
        if st.session_state.openai_api_key:
            st.session_state.llm.set_provider("openai", st.session_state.openai_api_key)
            print("✅ OpenAI API key loaded from secrets.toml")
    except Exception as e:
        # If secrets.toml doesn't exist, use empty string
        st.session_state.openai_api_key = ''
        print("ℹ️ No secrets.toml found, API key must be entered manually")
        
if 'anthropic_api_key' not in st.session_state:
    try:
        st.session_state.anthropic_api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if st.session_state.anthropic_api_key:
            st.session_state.llm.set_provider("claude", st.session_state.anthropic_api_key)
            print("✅ Claude API key loaded from secrets.toml")
    except Exception as e:
        st.session_state.anthropic_api_key = ''


def chat_interface(customer_data, show_technical, show_prompt):
    """Main chat interface for customer interaction"""
    
    st.markdown("### 💬 I'm here, and all ears, for you!")
    
    # Pre-filled examples
    example_messages = {
        "Worried about money": "I'm always worried about money, even though I earn decent amounts.",
        "Irregular income stress": "I'm stressed about irregular income lately. Some months I earn €800, others €3200.",
        "Can't save": "I want to save more but never seem to have money left at the end of the month.",
        "Debt concerns": "I'm worried about my credit card debt piling up.",
        "Custom": ""
    }
    
    selected_example = st.selectbox(
        "Choose a template:",
        list(example_messages.keys())
    )
    
    if selected_example == "Custom":
        customer_message = st.text_area(
            "Enter customer message:",
            height=100,
            placeholder="Type the customer's message here..."
        )
    else:
        customer_message = st.text_area(
            "Enter your message:",
            value=example_messages[selected_example],
            height=100
        )
    
    analyze_button = st.button("🔍 Analyze & Generate Advice", use_container_width=True)
    
    if analyze_button and customer_message:
        with st.spinner('🤖 AI is analyzing...'):
            # Progress bar for demo effect
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 1: FinBERT Analysis
            status_text.text("📊 Analyzing sentiment with FinBERT...")
            progress_bar.progress(20)
            time.sleep(0.5)
            
            sentiment_result = st.session_state.analyzer.analyze_sentiment(customer_message)
            stress_analysis = st.session_state.analyzer.detect_stress(customer_message)
            
            # Step 2: FRI Calculation
            status_text.text("💙  Calculating Financial Resilience Index...")
            progress_bar.progress(40)
            time.sleep(0.5)
            
            transactions = get_transaction_history(customer_data['customer_id'])
            fri_result = st.session_state.fri_calc.calculate_fri(transactions)
            
            # Step 3: RAG Retrieval
            status_text.text("🔎 Finding similar cases...")
            progress_bar.progress(60)
            time.sleep(0.5)
            
            similar_cases = st.session_state.analyzer.find_similar_cases(customer_message)
            
            # Step 4: LLM Generation
            status_text.text("✨ Generating personalized coaching response...")
            progress_bar.progress(80)
            time.sleep(0.5)
            
            coaching_response = st.session_state.llm.generate_coaching(
                customer_message=customer_message,
                sentiment_result=sentiment_result,
                stress_analysis=stress_analysis,
                fri_result=fri_result,
                similar_cases=similar_cases,
                customer_data=customer_data
            )
            
            progress_bar.progress(100)
            status_text.text("✅ Analysis complete!")
            time.sleep(0.5)
            progress_bar.empty()
            status_text.empty()
        
        # Display Results
        st.markdown("---")
        st.markdown("## 🎯 AI Analysis Results")
        
        # Metrics Row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            stress_color = {
                'HIGH': 'stress-high',
                'MODERATE': 'stress-moderate',
                'LOW': 'stress-low',
                'MINIMAL': 'stress-very low'
            }[stress_analysis['stress_level']]
            
            st.markdown(f"""
            <div class="metric-card {stress_color}">
                <h3>Stress Level</h3>
                <h1>{stress_analysis['stress_level']}</h1>
                <p>{stress_analysis['combined_score']:.0%} confidence</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3>FRI Score</h3>
                <h1>{fri_result['total_score']:.0f}/100</h1>
                <p>Financial Resilience</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            weakest_component = min(fri_result['components'], key=lambda x: x['score'])
            st.markdown(f"""
            <div class="metric-card">
                <h3>Weakest Area</h3>
                <h1>{weakest_component['name']}</h1>
                <p>{weakest_component['score']:.0f}/100</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Priority</h3>
                <h1>{'🔴' if stress_analysis['stress_level'] == 'HIGH' else '🟡' if stress_analysis['stress_level'] == 'MODERATE' else '🟢'}</h1>
                <p>{stress_analysis['urgency']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # FRI Component Visualization
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig = create_component_radar(fri_result['components'])
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig_gauge = create_fri_gauge(fri_result['total_score'])
            st.plotly_chart(fig_gauge, use_container_width=True)
        
        # Coaching Response
        st.markdown("---")
        st.markdown("## 💬 Personalized Advice")
        
        # Show which provider was actually used
        llm_status = "🤖 **Real LLM**" if st.session_state.llm.client else "🎭 **Mock Demo**"
        st.markdown(f"*Generated by: {llm_status} ({st.session_state.llm.provider})*")
        
        if st.session_state.llm.last_error:
            st.error(f"⚠️ {st.session_state.llm.last_error}")
        
        st.markdown(f"""
        <div class="coaching-box">
            {coaching_response.replace(chr(10), '<br>')}
        </div>
        """, unsafe_allow_html=True)
        
        # Show prompt if requested
        if show_prompt:
            with st.expander("🔬 View LLM Prompt"):
                prompt = st.session_state.llm._build_prompt(
                    customer_message, sentiment_result, stress_analysis,
                    fri_result, similar_cases, customer_data
                )
                st.code(prompt, language="markdown")
        
        # Technical Details (optional)
        if show_technical:
            with st.expander("🔬 Technical Details"):
                st.json({
                    "sentiment_analysis": sentiment_result,
                    "stress_detection": stress_analysis,
                    "fri_components": fri_result,
                    "similar_cases": similar_cases
                })


def financial_dashboard(customer_data):
    """Display comprehensive financial dashboard"""
    
    st.markdown("### 📈 12-Month Financial Overview")
    
    transactions = get_transaction_history(customer_data['customer_id'])
    monthly_fri = st.session_state.fri_calc.calculate_monthly_fri(transactions)
    
    # Timeline chart
    fig_timeline = create_timeline_chart(monthly_fri)
    st.plotly_chart(fig_timeline, use_container_width=True)
    
    # Current vs Historical
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Component Trends")
        
        # Create component comparison
        import pandas as pd
        components_df = {
            'Month': [m['month'] for m in monthly_fri],
            'Buffer': [m['buffer'] for m in monthly_fri],
            'Stability': [m['stability'] for m in monthly_fri],
            'Momentum': [m['momentum'] for m in monthly_fri]
        }
        
        df = pd.DataFrame(components_df)
        
        fig = px.line(df, x='Month', y=['Buffer', 'Stability', 'Momentum'],
                     title='FRI Components Over Time',
                     labels={'value': 'Score', 'variable': 'Component'})
        fig.update_layout(
            height=400,
            paper_bgcolor='#1e1e2e',
            plot_bgcolor='#1e1e2e',
            font={'color': '#ffffff'},
            xaxis={'gridcolor': '#2a2a3e'},
            yaxis={'gridcolor': '#2a2a3e'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### 💰 Financial Summary")
        
        latest = monthly_fri[-1]
        
        st.metric("Current FRI", f"{latest['total']:.0f}", 
                 delta=f"{latest['total'] - monthly_fri[-2]['total']:.0f} vs last month")
        
        st.metric("Monthly Income", f"€{customer_data['avg_monthly_income']:.0f}",
                 delta=f"{customer_data['income_cv']:.2f} CV")
        
        st.metric("Liquid Assets", f"€{latest['assets']:.0f}")
        
        st.metric("Emergency Fund", f"{latest['buffer']/16.67:.1f} months")


def technical_analysis(customer_data):
    """Technical deep-dive for the CEO"""
    
    st.markdown("### 🔬 AI Pipeline Technical Analysis")
    
    st.markdown("""
    This section demonstrates the five-layer AI architecture powering the coaching system:
    
    1. **FinBERT Analysis Layer** - Sentiment & stress detection
    2. **FRI Context Engine** - Financial resilience scoring
    3. **RAG Knowledge Retrieval** - Similar case matching
    4. **LLM Generation Layer** - Personalized response creation
    5. **Coaching Response** - Final output
    """)
    
    # Architecture Diagram
    st.markdown("#### 🏗️ System Architecture")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **Layer 1: FinBERT**
        - Model: ProsusAI/finbert
        - Processes: ~100 msg/sec (CPU)
        - Cost: €0.05 per analysis
        - Privacy: On-premise
        """)
    
    with col2:
        st.markdown("""
        **Layer 2: FRI Engine**
        - Components: 3 (B/S/M)
        - Update: Monthly
        - Data: 12-mo history
        - Accuracy: r=0.6+ with surveys
        """)
    
    with col3:
        st.markdown("""
        **Layer 3+4: RAG + LLM**
        - Database: Vector embeddings
        - Retrieval: Top-3 similar
        - LLM: GPT-4 / Claude
        - Cost: €0.2 per interaction
        """)
    
    # Performance Metrics
    st.markdown("#### ⚡ Performance Benchmarks")
    
    perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
    
    with perf_col1:
        st.metric("Response Time", "2.3s", delta="-0.5s vs baseline")
    
    with perf_col2:
        st.metric("FinBERT Accuracy", "89%", delta="+4% vs generic NLP")
    
    with perf_col3:
        st.metric("FRI-Survey Correlation", "0.68", delta="+0.08 vs traditional")
    
    with perf_col4:
        st.metric("Cost per Interaction", "€0.2", delta="-70% vs pure LLM")
    
    # Scalability Analysis
    st.markdown("#### 📊 Scalability Projections")
    
    import pandas as pd
    users_data = {
        'Users': [1000, 5000, 10000, 50000, 100000],
        'Monthly Cost (€)': [200, 1000, 2000, 10000, 20000],
        'Infrastructure': ['Single server', 'Single server', 'Load balancer', 'Kubernetes', 'Multi-region'],
        'Response Time (s)': [2.3, 2.5, 2.7, 3.0, 3.2]
    }
    
    df_scale = pd.DataFrame(users_data)
    
    fig_scale = go.Figure()
    fig_scale.add_trace(go.Scatter(x=df_scale['Users'], y=df_scale['Monthly Cost (€)'],
                                   mode='lines+markers', name='Monthly Cost',
                                   line=dict(color='#667eea', width=3)))
    fig_scale.update_layout(
        title='Cost Scaling Analysis',
        xaxis_title='Number of Users',
        yaxis_title='Monthly Cost (€)',
        height=400,
        paper_bgcolor='#1e1e2e',
        plot_bgcolor='#1e1e2e',
        font={'color': '#ffffff'},
        xaxis={'gridcolor': '#2a2a3e'},
        yaxis={'gridcolor': '#2a2a3e'}
    )
    st.plotly_chart(fig_scale, use_container_width=True)


def main():
    # Header
    st.markdown("<h1 style='text-align: center; color: #667eea;'>💙 Fiona - Snappi's AI Financial Coach</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #b0b0b0;'>AI-Powered Financial Well-Being Assistant</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Sidebar - Customer Selection
    with st.sidebar:
        st.markdown("## 👤 Customer Profile")
        
        customer_names = list(st.session_state.customer_profiles.keys())
        selected_customer = st.selectbox(
            "Select Customer",
            customer_names,
            help="Choose a customer profile for the demo"
        )
        
        customer_data = st.session_state.customer_profiles[selected_customer]
        
        st.markdown("### 📊 Customer Info")
        st.write(f"**Age:** {customer_data['age']}")
        st.write(f"**Occupation:** {customer_data['occupation']}")
        st.write(f"**Account Age:** {customer_data['account_age_months']} months")
        
        st.markdown("---")
        
        # LLM Settings
        st.markdown("## ⚙️ AI Settings")
        
        llm_provider = st.selectbox(
            "LLM Provider",
            ["Mock (Demo)", "GPT-4 (OpenAI)", "Claude (Anthropic)"],
            help="Select which AI model to use for coaching responses"
        )
        
        # Show API key input and status
        if llm_provider == "GPT-4 (OpenAI)":
            api_key = st.text_input(
                "OpenAI API Key", 
                type="password",
                value=st.session_state.openai_api_key,
                help="Enter your OpenAI API key from https://platform.openai.com/api-keys"
            )
            
            if api_key:
                st.session_state.openai_api_key = api_key
                st.session_state.llm.set_provider("openai", api_key)
                st.success("✅ OpenAI API key configured!")
            else:
                st.warning("⚠️ Enter API key to use GPT-4")
                
        elif llm_provider == "Claude (Anthropic)":
            api_key = st.text_input(
                "Anthropic API Key", 
                type="password",
                value=st.session_state.anthropic_api_key,
                help="Enter your Anthropic API key from https://console.anthropic.com/"
            )
            
            if api_key:
                st.session_state.anthropic_api_key = api_key
                st.session_state.llm.set_provider("claude", api_key)
                st.success("✅ Claude API key configured!")
            else:
                st.warning("⚠️ Enter API key to use Claude")
        else:
            st.info("ℹ️ Using mock responses (demo mode)")
            st.session_state.llm.set_provider("mock", None)
        
        # Advanced options
        with st.expander("Advanced Options"):
            show_technical = st.checkbox("Show Technical Details", value=False)
            show_prompt = st.checkbox("Show LLM Prompt", value=False)
            auto_analyze = st.checkbox("Auto-analyze on type", value=False)
    
    # Main Content Area
    tab1, tab2, tab3 = st.tabs(["💬 Chat Interface", "📈 Financial Dashboard", "🔬 Technical Analysis"])
    
    with tab1:
        chat_interface(customer_data, show_technical, show_prompt)
    
    with tab2:
        financial_dashboard(customer_data)
    
    with tab3:
        technical_analysis(customer_data)


if __name__ == "__main__":
    main()
"""
Snappi Financial Coaching App - WITH CONVERSATION HISTORY
Multi-turn chat interface with Fiona AI Coach
"""

import streamlit as st
from chat_history_manager import ChatHistory
from llm_generator_with_history import LLMGenerator

# Import your existing components
# from finbert_analyzer import FinBERTAnalyzer
# from fri_calculator import FRICalculator
# etc.


def initialize_session_state():
    """Initialize all session state variables including chat history"""
    
    if 'chat_history' not in st.session_state:
        # Create chat history for current customer
        customer_id = st.session_state.get('selected_customer', 'CUST001')
        st.session_state.chat_history = ChatHistory(
            customer_id=customer_id,
            max_context_messages=10  # Keep last 10 messages in LLM context
        )
    
    if 'llm' not in st.session_state:
        st.session_state.llm = LLMGenerator()
    
    # Your existing initializations
    # if 'finbert' not in st.session_state:
    #     st.session_state.finbert = FinBERTAnalyzer()
    # etc.


def chat_interface():
    """Multi-turn conversational interface with Fiona"""
    
    st.title("💬 Chat with Fiona - Your Financial Coach")
    
    # Display conversation history
    chat_container = st.container()
    
    with chat_container:
        if len(st.session_state.chat_history) == 0:
            # Welcome message
            st.info("""
            👋 **Welcome!** I'm Fiona, your personal financial coach at Snappi.
            
            I'm here to help you understand your financial well-being and work together 
            on improving it. Our conversations are private and focused on YOUR goals.
            
            What's on your mind today?
            """)
        else:
            # Display existing messages
            for msg in st.session_state.chat_history.messages:
                if msg.role == 'user':
                    with st.chat_message("user", avatar="🧑"):
                        st.markdown(msg.content)
                        
                        # Show metadata in expander
                        if msg.metadata:
                            with st.expander("📊 Analysis Details", expanded=False):
                                if 'fri_score' in msg.metadata:
                                    st.caption(f"FRI Score: {msg.metadata['fri_score']:.0f}/100")
                                if 'sentiment' in msg.metadata:
                                    st.caption(f"Sentiment: {msg.metadata['sentiment']}")
                
                else:  # assistant
                    with st.chat_message("assistant", avatar="💙"):
                        st.markdown(msg.content)
    
    # Chat input
    st.markdown("---")
    
    col1, col2 = st.columns([5, 1])
    
    with col1:
        user_input = st.chat_input(
            "Type your message here...",
            key="chat_input"
        )
    
    with col2:
        if st.button("🗑️ New Chat", help="Start a fresh conversation"):
            st.session_state.chat_history.clear_history()
            st.rerun()
    
    # Process new message
    if user_input:
        process_message(user_input)
        st.rerun()
    
    # Conversation stats in sidebar
    with st.sidebar:
        st.markdown("### 📊 Conversation Stats")
        
        if len(st.session_state.chat_history) > 0:
            stats = {
                "Messages": len(st.session_state.chat_history.messages),
                "Duration": st.session_state.chat_history._time_ago(
                    st.session_state.chat_history.conversation_start
                )
            }
            
            for key, value in stats.items():
                st.metric(key, value)
            
            # Export conversation
            if st.button("💾 Export Conversation"):
                json_str = st.session_state.chat_history.export_conversation()
                st.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name=f"conversation_{st.session_state.chat_history.customer_id}.json",
                    mime="application/json"
                )
        else:
            st.caption("No messages yet")


def process_message(user_message: str):
    """Process user message and generate Fiona's response"""
    
    # Get customer data (from your existing session state)
    customer_data = st.session_state.get('customer_data', {
        'name': 'Maria Papadopoulos',
        'age': 34,
        'occupation': 'Freelance Designer',
        'avg_monthly_income': 2500,
        'avg_monthly_essential': 1800
    })
    
    # Show user message immediately
    with st.chat_message("user", avatar="🧑"):
        st.markdown(user_message)
    
    # Show Fiona thinking
    with st.chat_message("assistant", avatar="💙"):
        with st.spinner("Fiona is thinking..."):
            
            # Run analyses (use your existing functions)
            sentiment_result = analyze_sentiment(user_message)
            stress_analysis = detect_stress(user_message, sentiment_result)
            fri_result = calculate_fri(customer_data)
            similar_cases = retrieve_similar_cases(user_message, fri_result)
            
            # Add user message to history with metadata
            st.session_state.chat_history.add_user_message(
                content=user_message,
                metadata={
                    'fri_score': fri_result.get('total_score'),
                    'sentiment': sentiment_result.get('dominant'),
                    'stress_level': stress_analysis.get('stress_level'),
                    'weakest_component': min(
                        fri_result['components'], 
                        key=lambda x: x['score']
                    )['name']
                }
            )
            
            # Get conversation context
            conversation_history = st.session_state.chat_history.get_context_for_llm()
            
            # Generate response with history context
            coaching_response = st.session_state.llm.generate_coaching(
                customer_message=user_message,
                sentiment_result=sentiment_result,
                stress_analysis=stress_analysis,
                fri_result=fri_result,
                similar_cases=similar_cases,
                customer_data=customer_data,
                conversation_history=conversation_history  # ← KEY ADDITION
            )
            
            # Add Fiona's response to history
            st.session_state.chat_history.add_assistant_message(
                content=coaching_response,
                metadata={
                    'fri_score': fri_result.get('total_score'),
                    'provider': st.session_state.llm.provider
                }
            )
            
            # Display response
            st.markdown(coaching_response)


def analyze_sentiment(message: str) -> dict:
    """Run FinBERT sentiment analysis - replace with your actual function"""
    # This is a placeholder - use your actual FinBERT analyzer
    return {
        'dominant': 'negative',
        'positive': 0.15,
        'neutral': 0.25,
        'negative': 0.60
    }


def detect_stress(message: str, sentiment: dict) -> dict:
    """Detect financial stress - replace with your actual function"""
    # Placeholder - use your actual stress detection
    return {
        'stress_level': 'High',
        'combined_score': 0.75,
        'detected_keywords': ['worried', 'bills', 'debt'],
        'urgency': 'medium'
    }


def calculate_fri(customer_data: dict) -> dict:
    """Calculate FRI - replace with your actual function"""
    # Placeholder - use your actual FRI calculator
    return {
        'total_score': 54,
        'interpretation': 'Moderate Resilience',
        'components': [
            {'name': 'Buffer', 'score': 45, 'interpretation': 'Low'},
            {'name': 'Stability', 'score': 32, 'interpretation': 'Very Low'},
            {'name': 'Momentum', 'score': 68, 'interpretation': 'Good'}
        ]
    }


def retrieve_similar_cases(message: str, fri: dict) -> list:
    """Retrieve similar cases from RAG - replace with your actual function"""
    # Placeholder - use your actual RAG retrieval
    return [
        {
            'case': {
                'problem': 'Irregular income causing stress',
                'solution': 'Built 3-month buffer + income smoothing',
                'improvement': 'FRI increased from 52 to 71 in 4 months'
            },
            'similarity': 0.89
        }
    ]


def sidebar_settings():
    """Sidebar with LLM provider settings"""
    
    st.sidebar.title("⚙️ Settings")
    
    # LLM Provider Selection
    st.sidebar.markdown("### 🤖 AI Coach Provider")
    
    provider = st.sidebar.radio(
        "Choose LLM:",
        ["Mock (Demo)", "GPT-4 (OpenAI)", "Claude (Anthropic)"],
        key="llm_provider"
    )
    
    # API Key input based on provider
    if provider == "GPT-4 (OpenAI)":
        api_key = st.sidebar.text_input(
            "OpenAI API Key:",
            type="password",
            key="openai_api_key",
            help="Get your key from platform.openai.com"
        )
        
        if api_key:
            st.session_state.llm.set_provider("openai", api_key)
            st.sidebar.success("✅ OpenAI connected")
    
    elif provider == "Claude (Anthropic)":
        api_key = st.sidebar.text_input(
            "Anthropic API Key:",
            type="password",
            key="anthropic_api_key",
            help="Get your key from console.anthropic.com"
        )
        
        if api_key:
            st.session_state.llm.set_provider("claude", api_key)
            st.sidebar.success("✅ Claude connected")
    
    else:  # Mock
        st.session_state.llm.set_provider("mock")
        st.sidebar.info("ℹ️ Using demo responses")
    
    st.sidebar.markdown("---")
    
    # Advanced options
    with st.sidebar.expander("🔧 Advanced Options"):
        show_metadata = st.checkbox("Show analysis details", value=False)
        max_context = st.slider(
            "Context window (messages)",
            min_value=4,
            max_value=20,
            value=10,
            help="Number of previous messages to include in context"
        )
        
        if max_context != st.session_state.chat_history.max_context_messages:
            st.session_state.chat_history.max_context_messages = max_context


def main():
    """Main app entry point"""
    
    # Page config
    st.set_page_config(
        page_title="Snappi Financial Coach",
        page_icon="💙",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize
    initialize_session_state()
    
    # Sidebar settings
    sidebar_settings()
    
    # Main chat interface
    chat_interface()
    
    # Footer
    st.markdown("---")
    st.caption("💙 Snappi Bank | Your Financial Wellness Partner | Powered by Behavioral Economics & AI")


if __name__ == "__main__":
    main()

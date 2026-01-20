"""
Snappi Financial Coaching - Commercial-Grade UI
Professional interface similar to ChatGPT, Claude, Gemini
"""

import streamlit as st
from datetime import datetime
from chat_history_manager import ChatHistory, ConversationManager
from llm_generator_with_history import LLMGenerator
import json
from pathlib import Path

# Configure page
st.set_page_config(
    page_title="Fiona - Snappi Financial Coach",
    page_icon="💙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM CSS - COMMERCIAL STYLING
# ============================================================================

def load_custom_css():
    """Load custom CSS for commercial look"""
    st.markdown("""
    <style>
    /* Main container */
    .main {
        background-color: #0E1117;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #1E1E1E;
        border-right: 1px solid #2D2D2D;
    }
    
    [data-testid="stSidebar"] .stButton button {
        width: 100%;
        border-radius: 8px;
        padding: 10px 16px;
        margin: 4px 0;
        background-color: transparent;
        border: 1px solid #3D3D3D;
        color: #E0E0E0;
        text-align: left;
        transition: all 0.2s;
    }
    
    [data-testid="stSidebar"] .stButton button:hover {
        background-color: #2D2D2D;
        border-color: #4D4D4D;
    }
    
    /* Active conversation highlight */
    .active-chat {
        background-color: #2D2D2D !important;
        border-left: 3px solid #4A9EFF !important;
    }
    
    /* Chat messages */
    .stChatMessage {
        background-color: transparent;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    
    [data-testid="stChatMessageContent"] {
        padding: 0;
    }
    
    /* User message */
    .stChatMessage[data-testid*="user"] {
        background-color: #2D2D2D;
    }
    
    /* Assistant message */
    .stChatMessage[data-testid*="assistant"] {
        background-color: #1A1A1A;
        border-left: 3px solid #4A9EFF;
    }
    
    /* Input area */
    .stChatInputContainer {
        background-color: #1E1E1E;
        border-radius: 12px;
        border: 1px solid #3D3D3D;
        padding: 12px;
    }
    
    .stChatInputContainer:focus-within {
        border-color: #4A9EFF;
        box-shadow: 0 0 0 2px rgba(74, 158, 255, 0.1);
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #E0E0E0;
        font-weight: 600;
    }
    
    /* Buttons */
    .stButton button {
        border-radius: 8px;
        padding: 8px 16px;
        transition: all 0.2s;
    }
    
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    
    /* New chat button */
    .new-chat-btn button {
        background: linear-gradient(135deg, #4A9EFF 0%, #357ABD 100%);
        color: white;
        border: none;
        font-weight: 600;
    }
    
    .new-chat-btn button:hover {
        background: linear-gradient(135deg, #357ABD 0%, #2D6BA3 100%);
    }
    
    /* Settings panel */
    .settings-panel {
        background-color: #1A1A1A;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        border: 1px solid #2D2D2D;
    }
    
    /* Metrics */
    [data-testid="stMetric"] {
        background-color: #1A1A1A;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid #2D2D2D;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #1A1A1A;
        border-radius: 8px;
        border: 1px solid #2D2D2D;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #1E1E1E;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #3D3D3D;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #4D4D4D;
    }
    
    /* Avatar styling */
    [data-testid="stChatMessageAvatarUser"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    [data-testid="stChatMessageAvatarAssistant"] {
        background: linear-gradient(135deg, #4A9EFF 0%, #357ABD 100%);
    }
    
    /* Welcome screen */
    .welcome-container {
        text-align: center;
        padding: 60px 20px;
        max-width: 700px;
        margin: 0 auto;
    }
    
    .welcome-title {
        font-size: 48px;
        font-weight: 700;
        background: linear-gradient(135deg, #4A9EFF 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 16px;
    }
    
    .welcome-subtitle {
        font-size: 20px;
        color: #A0A0A0;
        margin-bottom: 32px;
    }
    
    .suggestion-card {
        background-color: #1A1A1A;
        border-radius: 12px;
        padding: 20px;
        margin: 12px 0;
        border: 1px solid #2D2D2D;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .suggestion-card:hover {
        background-color: #2D2D2D;
        border-color: #4A9EFF;
        transform: translateY(-2px);
    }
    
    .suggestion-title {
        font-weight: 600;
        color: #E0E0E0;
        margin-bottom: 8px;
    }
    
    .suggestion-text {
        color: #A0A0A0;
        font-size: 14px;
    }
    
    /* Status indicators */
    .status-indicator {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .status-online {
        background-color: #10B981;
        box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
    }
    
    .status-offline {
        background-color: #EF4444;
    }
    
    /* Conversation preview */
    .conv-preview {
        font-size: 12px;
        color: #808080;
        margin-top: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* Delete button */
    .delete-btn {
        float: right;
        opacity: 0;
        transition: opacity 0.2s;
    }
    
    .stButton:hover .delete-btn {
        opacity: 1;
    }
    </style>
    """, unsafe_allow_html=True)


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def initialize_session_state():
    """Initialize all session state variables"""
    
    # Conversation manager
    if 'conversation_manager' not in st.session_state:
        st.session_state.conversation_manager = ConversationManager()
    
    # Current active conversation
    if 'active_conversation_id' not in st.session_state:
        # Create default conversation
        conv_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.active_conversation_id = conv_id
        st.session_state.conversation_manager.get_or_create_session(conv_id)
    
    # LLM Generator
    if 'llm' not in st.session_state:
        st.session_state.llm = LLMGenerator()
    
    # UI state
    if 'show_settings' not in st.session_state:
        st.session_state.show_settings = False
    
    if 'dark_mode' not in st.session_state:
        st.session_state.dark_mode = True
    
    # Customer data (placeholder)
    if 'customer_data' not in st.session_state:
        st.session_state.customer_data = {
            'name': 'Maria Papadopoulos',
            'age': 34,
            'occupation': 'Freelance Designer',
            'avg_monthly_income': 2500,
            'avg_monthly_essential': 1800
        }


# ============================================================================
# SIDEBAR - CONVERSATION MANAGEMENT
# ============================================================================

def render_sidebar():
    """Render sidebar with conversation history"""
    
    with st.sidebar:
        # Logo and title
        st.markdown("""
        <div style='text-align: center; padding: 20px 0;'>
            <h1 style='margin: 0; font-size: 28px;'>💙 Fiona</h1>
            <p style='color: #808080; font-size: 14px; margin-top: 4px;'>Your Financial Coach</p>
        </div>
        """, unsafe_allow_html=True)
        
        # New chat button
        st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
        if st.button("➕ New Conversation", use_container_width=True):
            create_new_conversation()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Conversations list
        st.markdown("### 💬 Conversations")
        
        conversations = st.session_state.conversation_manager.get_active_sessions()
        
        if not conversations:
            st.caption("No conversations yet. Start one above!")
        else:
            for conv_id in reversed(conversations):  # Most recent first
                render_conversation_item(conv_id)
        
        st.markdown("---")
        
        # Settings toggle
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state.show_settings = not st.session_state.show_settings
            st.rerun()
        
        # Footer
        st.markdown("---")
        st.caption("💙 Snappi Bank 2025")
        st.caption("Powered by Behavioral Economics & AI")


def render_conversation_item(conv_id: str):
    """Render a single conversation item in sidebar"""
    
    chat = st.session_state.conversation_manager.sessions[conv_id]
    is_active = conv_id == st.session_state.active_conversation_id
    
    # Get conversation title (first user message or default)
    if len(chat.messages) > 0:
        first_msg = next((m for m in chat.messages if m.role == 'user'), None)
        title = first_msg.content[:40] + "..." if first_msg and len(first_msg.content) > 40 else (first_msg.content if first_msg else "New Conversation")
        preview = f"{len(chat.messages)//2} exchanges • {chat._time_ago(chat.conversation_start)}"
    else:
        title = "New Conversation"
        preview = "No messages yet"
    
    # Create columns for button and delete
    col1, col2 = st.columns([5, 1])
    
    with col1:
        btn_class = "active-chat" if is_active else ""
        if st.button(
            f"💬 {title}",
            key=f"conv_{conv_id}",
            use_container_width=True,
            help=preview
        ):
            st.session_state.active_conversation_id = conv_id
            st.rerun()
    
    with col2:
        if st.button("🗑️", key=f"del_{conv_id}", help="Delete conversation"):
            delete_conversation(conv_id)
            st.rerun()
    
    # Show preview below
    st.markdown(f'<div class="conv-preview">{preview}</div>', unsafe_allow_html=True)


def create_new_conversation():
    """Create a new conversation"""
    conv_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    st.session_state.conversation_manager.get_or_create_session(conv_id)
    st.session_state.active_conversation_id = conv_id


def delete_conversation(conv_id: str):
    """Delete a conversation"""
    if conv_id in st.session_state.conversation_manager.sessions:
        del st.session_state.conversation_manager.sessions[conv_id]
        
        # If deleting active conversation, switch to another or create new
        remaining = st.session_state.conversation_manager.get_active_sessions()
        if conv_id == st.session_state.active_conversation_id:
            if remaining:
                st.session_state.active_conversation_id = remaining[-1]
            else:
                create_new_conversation()


# ============================================================================
# MAIN CHAT INTERFACE
# ============================================================================

def render_welcome_screen():
    """Render welcome screen when no messages"""
    st.markdown("""
    <div class="welcome-container">
        <div class="welcome-title">Welcome to Fiona 💙</div>
        <div class="welcome-subtitle">Your AI-powered financial wellness coach</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Suggestion cards
    col1, col2 = st.columns(2)
    
    suggestions = [
        {
            "title": "💰 Understand Your FRI",
            "text": "Ask me about your Financial Resilience Index and what it means",
            "prompt": "Can you explain my Financial Resilience Index?"
        },
        {
            "title": "📊 Review My Finances",
            "text": "Get a comprehensive analysis of your financial health",
            "prompt": "I'd like to review my overall financial situation"
        },
        {
            "title": "💡 Improve My Score",
            "text": "Learn actionable steps to boost your financial wellness",
            "prompt": "What can I do to improve my financial resilience?"
        },
        {
            "title": "🎯 Set Financial Goals",
            "text": "Work together on creating and achieving your goals",
            "prompt": "I want to set some financial goals"
        }
    ]
    
    for i, suggestion in enumerate(suggestions):
        with (col1 if i % 2 == 0 else col2):
            if st.button(
                f"**{suggestion['title']}**\n\n{suggestion['text']}",
                key=f"suggestion_{i}",
                use_container_width=True
            ):
                # Send this as user message
                process_user_message(suggestion['prompt'])
                st.rerun()


def render_chat_interface():
    """Render main chat interface"""
    
    # Get active conversation
    chat = st.session_state.conversation_manager.sessions.get(
        st.session_state.active_conversation_id
    )
    
    if not chat:
        st.error("Conversation not found")
        return
    
    # Chat container
    chat_container = st.container()
    
    with chat_container:
        if len(chat.messages) == 0:
            render_welcome_screen()
        else:
            # Render messages
            for msg in chat.messages:
                with st.chat_message(msg.role, avatar="🧑" if msg.role == "user" else "💙"):
                    st.markdown(msg.content)
                    
                    # Show metadata in expander if available
                    if msg.metadata and st.session_state.show_settings:
                        with st.expander("📊 Analysis Details", expanded=False):
                            if 'fri_score' in msg.metadata:
                                st.caption(f"FRI Score: {msg.metadata['fri_score']:.0f}/100")
                            if 'sentiment' in msg.metadata:
                                st.caption(f"Sentiment: {msg.metadata['sentiment']}")
                            if 'stress_level' in msg.metadata:
                                st.caption(f"Stress: {msg.metadata['stress_level']}")
    
    # Chat input at bottom
    st.markdown("---")
    
    # Input with send button
    col1, col2 = st.columns([6, 1])
    
    with col1:
        user_input = st.chat_input(
            "Message Fiona...",
            key="main_chat_input"
        )
    
    with col2:
        if st.button("⬆️", help="Send message", use_container_width=True):
            if user_input:
                process_user_message(user_input)
                st.rerun()
    
    if user_input:
        process_user_message(user_input)
        st.rerun()


def process_user_message(user_message: str):
    """Process user message and generate response"""
    
    # Get active chat
    chat = st.session_state.conversation_manager.sessions[
        st.session_state.active_conversation_id
    ]
    
    # Get customer data
    customer_data = st.session_state.customer_data
    
    # Run analyses (replace with your actual functions)
    sentiment_result = analyze_sentiment(user_message)
    stress_analysis = detect_stress(user_message, sentiment_result)
    fri_result = calculate_fri(customer_data)
    similar_cases = retrieve_similar_cases(user_message, fri_result)
    
    # Add user message to history
    chat.add_user_message(
        content=user_message,
        metadata={
            'fri_score': fri_result.get('total_score'),
            'sentiment': sentiment_result.get('dominant'),
            'stress_level': stress_analysis.get('stress_level'),
            'weakest_component': min(fri_result['components'], key=lambda x: x['score'])['name']
        }
    )
    
    # Get conversation context
    conversation_history = chat.get_context_for_llm()
    
    # Generate response
    coaching_response = st.session_state.llm.generate_coaching(
        customer_message=user_message,
        sentiment_result=sentiment_result,
        stress_analysis=stress_analysis,
        fri_result=fri_result,
        similar_cases=similar_cases,
        customer_data=customer_data,
        conversation_history=conversation_history
    )
    
    # Add assistant response to history
    chat.add_assistant_message(
        content=coaching_response,
        metadata={
            'fri_score': fri_result.get('total_score'),
            'provider': st.session_state.llm.provider
        }
    )


# ============================================================================
# SETTINGS PANEL
# ============================================================================

def render_settings_panel():
    """Render settings overlay"""
    
    if not st.session_state.show_settings:
        return
    
    st.markdown("## ⚙️ Settings")
    
    # LLM Provider
    st.markdown("### 🤖 AI Model")
    
    provider = st.radio(
        "Choose provider:",
        ["Mock (Demo)", "GPT-4 (OpenAI)", "Claude (Anthropic)"],
        key="llm_provider_radio"
    )
    
    # Status indicator
    status_class = "status-online" if st.session_state.llm.client else "status-offline"
    status_text = "Connected" if st.session_state.llm.client else "Not connected"
    
    st.markdown(f"""
    <div style='margin: 8px 0;'>
        <span class='status-indicator {status_class}'></span>
        <span style='color: #808080;'>{status_text}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # API Key input
    if provider == "GPT-4 (OpenAI)":
        api_key = st.text_input(
            "OpenAI API Key:",
            type="password",
            key="openai_key",
            help="Get your key from platform.openai.com"
        )
        if api_key:
            st.session_state.llm.set_provider("openai", api_key)
            st.success("✅ Connected to OpenAI")
    
    elif provider == "Claude (Anthropic)":
        api_key = st.text_input(
            "Anthropic API Key:",
            type="password",
            key="anthropic_key",
            help="Get your key from console.anthropic.com"
        )
        if api_key:
            st.session_state.llm.set_provider("claude", api_key)
            st.success("✅ Connected to Claude")
    
    else:
        st.session_state.llm.set_provider("mock")
        st.info("ℹ️ Using demo mode - No API key needed")
    
    st.markdown("---")
    
    # Display preferences
    st.markdown("### 🎨 Display")
    
    show_metadata = st.checkbox(
        "Show analysis metadata",
        value=st.session_state.show_settings,
        key="show_metadata_checkbox"
    )
    
    max_context = st.slider(
        "Context window (messages)",
        min_value=4,
        max_value=20,
        value=10,
        help="Number of previous messages to include"
    )
    
    st.markdown("---")
    
    # Export options
    st.markdown("### 💾 Export")
    
    chat = st.session_state.conversation_manager.sessions.get(
        st.session_state.active_conversation_id
    )
    
    if chat and len(chat.messages) > 0:
        if st.button("📥 Export Current Conversation", use_container_width=True):
            json_str = chat.export_conversation()
            st.download_button(
                label="Download JSON",
                data=json_str,
                file_name=f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
    
    if st.button("📥 Export All Conversations", use_container_width=True):
        # Export all conversations
        all_convs = {}
        for conv_id, chat in st.session_state.conversation_manager.sessions.items():
            all_convs[conv_id] = json.loads(chat.export_conversation())
        
        json_str = json.dumps(all_convs, indent=2, ensure_ascii=False)
        st.download_button(
            label="Download All (JSON)",
            data=json_str,
            file_name=f"all_conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )


# ============================================================================
# PLACEHOLDER FUNCTIONS (Replace with your actual implementations)
# ============================================================================

def analyze_sentiment(message: str) -> dict:
    """Placeholder - replace with your FinBERT analyzer"""
    return {
        'dominant': 'negative',
        'positive': 0.15,
        'neutral': 0.25,
        'negative': 0.60
    }

def detect_stress(message: str, sentiment: dict) -> dict:
    """Placeholder - replace with your stress detector"""
    return {
        'stress_level': 'High',
        'combined_score': 0.75,
        'detected_keywords': ['worried', 'bills', 'debt'],
        'urgency': 'medium'
    }

def calculate_fri(customer_data: dict) -> dict:
    """Placeholder - replace with your FRI calculator"""
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
    """Placeholder - replace with your RAG retrieval"""
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


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application entry point"""
    
    # Load custom CSS
    load_custom_css()
    
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Main content area
    main_col, settings_col = st.columns([3, 1] if st.session_state.show_settings else [1, 0.001])
    
    with main_col:
        render_chat_interface()
    
    if st.session_state.show_settings:
        with settings_col:
            render_settings_panel()


if __name__ == "__main__":
    main()

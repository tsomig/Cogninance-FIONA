"""
Chat History Manager for Multi-Turn Conversations with Fiona
Handles conversation memory, context window management, and session persistence
"""

from datetime import datetime
from typing import List, Dict, Optional
import json


class ChatMessage:
    """Represents a single message in the conversation"""
    
    def __init__(self, role: str, content: str, timestamp: Optional[datetime] = None, 
                 metadata: Optional[Dict] = None):
        """
        Parameters:
        -----------
        role : str
            'user' or 'assistant'
        content : str
            Message content
        timestamp : datetime, optional
            Message timestamp (defaults to now)
        metadata : dict, optional
            Additional context (FRI scores, sentiment, etc.)
        """
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.metadata = metadata or {}
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create from dictionary"""
        return cls(
            role=data['role'],
            content=data['content'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            metadata=data.get('metadata', {})
        )


class ChatHistory:
    """Manages conversation history with context window management"""
    
    def __init__(self, customer_id: str, max_context_messages: int = 10):
        """
        Parameters:
        -----------
        customer_id : str
            Unique customer identifier
        max_context_messages : int
            Maximum number of recent messages to include in LLM context
        """
        self.customer_id = customer_id
        self.messages: List[ChatMessage] = []
        self.max_context_messages = max_context_messages
        self.conversation_start = datetime.now()
        self.session_metadata = {}  # Store FRI, customer data, etc.
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add a new message to the conversation"""
        message = ChatMessage(role=role, content=content, metadata=metadata)
        self.messages.append(message)
        return message
    
    def add_user_message(self, content: str, metadata: Optional[Dict] = None):
        """Convenience method for adding user messages"""
        return self.add_message('user', content, metadata)
    
    def add_assistant_message(self, content: str, metadata: Optional[Dict] = None):
        """Convenience method for adding assistant messages"""
        return self.add_message('assistant', content, metadata)
    
    def get_recent_messages(self, n: Optional[int] = None) -> List[ChatMessage]:
        """
        Get the most recent n messages
        
        Parameters:
        -----------
        n : int, optional
            Number of messages to retrieve (defaults to max_context_messages)
        
        Returns:
        --------
        List[ChatMessage]
        """
        if n is None:
            n = self.max_context_messages
        return self.messages[-n:] if len(self.messages) > n else self.messages
    
    def get_context_for_llm(self, include_system: bool = True) -> List[Dict]:
        """
        Format recent messages for LLM API call
        
        Parameters:
        -----------
        include_system : bool
            Whether to include system prompt (for OpenAI format)
        
        Returns:
        --------
        List[Dict] : Messages in OpenAI/Claude format
        """
        recent = self.get_recent_messages()
        
        # Convert to API format
        context = [
            {'role': msg.role, 'content': msg.content}
            for msg in recent
        ]
        
        return context
    
    def get_conversation_summary(self) -> str:
        """
        Generate a summary of the conversation for context compression
        Useful when conversation exceeds context window
        """
        if len(self.messages) <= 3:
            return "This is the beginning of the conversation."
        
        # Extract key topics discussed
        topics = set()
        for msg in self.messages:
            if msg.metadata.get('weakest_component'):
                topics.add(msg.metadata['weakest_component'])
        
        summary = f"Conversation started {self._time_ago(self.conversation_start)}. "
        summary += f"Total messages: {len(self.messages)}. "
        
        if topics:
            summary += f"Main concerns discussed: {', '.join(topics)}. "
        
        # Get FRI trend
        fri_scores = [msg.metadata.get('fri_score') for msg in self.messages 
                      if msg.metadata.get('fri_score')]
        if len(fri_scores) >= 2:
            trend = fri_scores[-1] - fri_scores[0]
            summary += f"FRI trend: {'+' if trend > 0 else ''}{trend:.0f} points. "
        
        return summary
    
    def should_summarize(self, max_tokens: int = 8000) -> bool:
        """
        Check if conversation should be summarized due to length
        
        Parameters:
        -----------
        max_tokens : int
            Approximate token limit (rough estimate: 1 message ≈ 200 tokens)
        
        Returns:
        --------
        bool : Whether summarization is needed
        """
        estimated_tokens = len(self.messages) * 200  # Rough estimate
        return estimated_tokens > max_tokens * 0.75  # Use 75% threshold
    
    def clear_history(self):
        """Clear all messages (start fresh conversation)"""
        self.messages = []
        self.conversation_start = datetime.now()
    
    def export_conversation(self, filepath: Optional[str] = None) -> str:
        """
        Export conversation to JSON for analysis/training data
        
        Parameters:
        -----------
        filepath : str, optional
            File path to save JSON (if None, returns JSON string)
        
        Returns:
        --------
        str : JSON representation of conversation
        """
        export_data = {
            'customer_id': self.customer_id,
            'conversation_start': self.conversation_start.isoformat(),
            'conversation_duration_minutes': (datetime.now() - self.conversation_start).total_seconds() / 60,
            'total_messages': len(self.messages),
            'session_metadata': self.session_metadata,
            'messages': [msg.to_dict() for msg in self.messages]
        }
        
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_str)
            print(f"✅ Conversation exported to {filepath}")
        
        return json_str
    
    def get_conversation_stats(self) -> Dict:
        """Get statistics about the conversation"""
        user_messages = [m for m in self.messages if m.role == 'user']
        assistant_messages = [m for m in self.messages if m.role == 'assistant']
        
        return {
            'total_messages': len(self.messages),
            'user_messages': len(user_messages),
            'assistant_messages': len(assistant_messages),
            'duration_minutes': (datetime.now() - self.conversation_start).total_seconds() / 60,
            'avg_response_length': sum(len(m.content) for m in assistant_messages) / len(assistant_messages) if assistant_messages else 0,
            'topics_discussed': list({m.metadata.get('weakest_component') for m in self.messages if m.metadata.get('weakest_component')})
        }
    
    @staticmethod
    def _time_ago(timestamp: datetime) -> str:
        """Format timestamp as 'X minutes/hours ago'"""
        delta = datetime.now() - timestamp
        minutes = delta.total_seconds() / 60
        
        if minutes < 60:
            return f"{int(minutes)} minutes ago"
        elif minutes < 1440:  # 24 hours
            return f"{int(minutes / 60)} hours ago"
        else:
            return f"{int(minutes / 1440)} days ago"
    
    def __len__(self):
        """Return number of messages"""
        return len(self.messages)
    
    def __repr__(self):
        """String representation"""
        return f"ChatHistory(customer_id={self.customer_id}, messages={len(self.messages)}, started={self._time_ago(self.conversation_start)})"


class ConversationManager:
    """Manages multiple chat sessions for different customers"""
    
    def __init__(self):
        self.sessions: Dict[str, ChatHistory] = {}
    
    def get_or_create_session(self, customer_id: str) -> ChatHistory:
        """Get existing session or create new one"""
        if customer_id not in self.sessions:
            self.sessions[customer_id] = ChatHistory(customer_id)
        return self.sessions[customer_id]
    
    def end_session(self, customer_id: str, export: bool = True) -> Optional[str]:
        """End a customer's session and optionally export"""
        if customer_id in self.sessions:
            session = self.sessions[customer_id]
            
            if export:
                filename = f"conversation_{customer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                session.export_conversation(filename)
            
            del self.sessions[customer_id]
            return filename if export else None
        return None
    
    def get_active_sessions(self) -> List[str]:
        """Get list of customer IDs with active sessions"""
        return list(self.sessions.keys())
    
    def clear_all_sessions(self):
        """Clear all active sessions"""
        self.sessions = {}


# Example usage and testing
if __name__ == "__main__":
    # Create a chat history
    chat = ChatHistory(customer_id="CUST001")
    
    # Simulate conversation
    chat.add_user_message(
        "I'm worried about my irregular income",
        metadata={'fri_score': 54, 'weakest_component': 'Stability'}
    )
    
    chat.add_assistant_message(
        "I understand your concern about income irregularity. Let's work on building a buffer...",
        metadata={'suggested_actions': ['Build 3-month buffer', 'Income smoothing']}
    )
    
    chat.add_user_message("How much should I save each month?")
    
    chat.add_assistant_message(
        "Based on your income of €2,500/month, I recommend saving €375/month (15%)...",
        metadata={'fri_score': 56, 'recommended_savings': 375}
    )
    
    # Get stats
    print("\n📊 Conversation Stats:")
    print(chat.get_conversation_stats())
    
    # Get context for LLM
    print("\n💬 Context for LLM:")
    print(chat.get_context_for_llm())
    
    # Export conversation
    print("\n📁 Exporting conversation:")
    json_output = chat.export_conversation("test_conversation.json")
    print(f"Exported {len(chat.messages)} messages")
    
    print("\n✅ Chat history manager test complete!")

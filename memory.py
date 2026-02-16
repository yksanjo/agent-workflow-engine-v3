"""
Memory module for Agent Workflow Engine.

Provides different memory types for agent state persistence:
- ShortTermMemory: Current conversation context
- LongTermMemory: Persistent storage across sessions
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime, timedelta
import json


@dataclass
class MemoryEntry:
    """A single memory entry."""
    key: str
    value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    
    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if memory has expired."""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > ttl_seconds
    
    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class AgentMemory:
    """Base class for agent memory."""
    
    def __init__(self):
        self._storage: dict[str, MemoryEntry] = {}
    
    def set(self, key: str, value: Any, **metadata) -> None:
        """Store a memory entry."""
        self._storage[key] = MemoryEntry(key=key, value=value, metadata=metadata)
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a memory entry."""
        entry = self._storage.get(key)
        return entry.value if entry else None
    
    def delete(self, key: str) -> bool:
        """Delete a memory entry."""
        if key in self._storage:
            del self._storage[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all memory."""
        self._storage.clear()
    
    def keys(self) -> list[str]:
        """Get all memory keys."""
        return list(self._storage.keys())
    
    def items(self) -> dict:
        """Get all memory items."""
        return {k: v.value for k, v in self._storage.items()}


class ShortTermMemory(AgentMemory):
    """
    Short-term memory with TTL (Time To Live).
    
    Memories automatically expire after a configurable duration.
    Best for current conversation context.
    
    Example:
        memory = ShortTermMemory(ttl_seconds=3600)  # 1 hour TTL
        memory.set("user_name", "John")
        name = memory.get("user_name")
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize short-term memory.
        
        Args:
            ttl_seconds: Time to live for entries in seconds.
        """
        super().__init__()
        self.ttl_seconds = ttl_seconds
    
    def set(self, key: str, value: Any, **metadata) -> None:
        """Store a memory entry."""
        super().set(key, value, **metadata)
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a memory entry if not expired."""
        entry = self._storage.get(key)
        if entry is None:
            return None
        
        if entry.is_expired(self.ttl_seconds):
            self.delete(key)
            return None
        
        return entry.value
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        expired_keys = [
            key for key, entry in self._storage.items()
            if entry.is_expired(self.ttl_seconds)
        ]
        for key in expired_keys:
            del self._storage[key]
        return len(expired_keys)


class LongTermMemory(AgentMemory):
    """
    Long-term persistent memory.
    
    Memories persist until explicitly deleted.
    Best for user preferences, learned patterns, etc.
    
    Example:
        memory = LongTermMemory()
        memory.set("preferred_language", "English")
        memory.set("conversation_count", 0, counter=True)
        
        # Increment counter
        count = memory.get("conversation_count") or 0
        memory.set("conversation_count", count + 1)
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize long-term memory.
        
        Args:
            storage_path: Optional file path for persistence.
        """
        super().__init__()
        self.storage_path = storage_path
        
        if storage_path:
            self._load()
    
    def _load(self) -> None:
        """Load memory from file."""
        if self.storage_path:
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        self._storage[key] = MemoryEntry(
                            key=key,
                            value=value.get("value"),
                            timestamp=datetime.fromisoformat(value.get("timestamp", datetime.now().isoformat())),
                            metadata=value.get("metadata", {})
                        )
            except FileNotFoundError:
                pass
    
    def _save(self) -> None:
        """Save memory to file."""
        if self.storage_path:
            data = {
                key: entry.to_dict()
                for key, entry in self._storage.items()
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
    
    def set(self, key: str, value: Any, **metadata) -> None:
        """Store a memory entry and persist."""
        super().set(key, value, **metadata)
        self._save()
    
    def delete(self, key: str) -> bool:
        """Delete a memory entry and persist."""
        result = super().delete(key)
        if result:
            self._save()
        return result


class ConversationMemory(ShortTermMemory):
    """
    Specialized memory for conversation context.
    
    Provides structured storage for conversation history
    with automatic turns management.
    
    Example:
        memory = ConversationMemory(max_turns=10)
        memory.add_turn("user", "Hello")
        memory.add_turn("assistant", "Hi there!")
        
        history = memory.get_history()
    """
    
    def __init__(self, max_turns: int = 10):
        """
        Initialize conversation memory.
        
        Args:
            max_turns: Maximum conversation turns to keep.
        """
        super().__init__(ttl_seconds=3600)
        self.max_turns = max_turns
    
    def add_turn(self, role: str, content: str) -> None:
        """Add a conversation turn."""
        turns = self.get("turns") or []
        turns.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Trim to max turns
        if len(turns) > self.max_turns:
            turns = turns[-self.max_turns:]
        
        self.set("turns", turns)
    
    def get_history(self) -> list[dict]:
        """Get conversation history."""
        return self.get("turns") or []
    
    def get_last_turn(self) -> Optional[dict]:
        """Get the last turn."""
        turns = self.get_history()
        return turns[-1] if turns else None
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self.delete("turns")

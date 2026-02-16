"""
Agent core classes for the Agent Workflow Engine.

Provides stateful agent execution with configurable behavior,
memory management, and tool integration.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Callable, list
from enum import Enum
from datetime import datetime
import json


class AgentStatus(Enum):
    """Current status of the agent."""
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AgentState:
    """
    Mutable state for an agent instance.
    
    Attributes:
        conversation_id: Unique identifier for the conversation session.
        step_count: Number of execution steps taken.
        last_action: Description of the last action taken.
        context: Additional context data.
        history: List of previous states for debugging.
    """
    conversation_id: str
    step_count: int = 0
    max_steps: int = 100
    last_action: str = ""
    status: AgentStatus = AgentStatus.IDLE
    context: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def record_action(self, action: str, result: Any = None) -> None:
        """Record an action in the history."""
        self.step_count += 1
        self.last_action = action
        self.history.append({
            "step": self.step_count,
            "action": action,
            "result": str(result)[:200] if result else None,
            "timestamp": datetime.now().isoformat()
        })
    
    def can_continue(self) -> bool:
        """Check if agent can continue execution."""
        return self.step_count < self.max_steps and self.status != AgentStatus.ERROR


@dataclass
class AgentConfig:
    """
    Configuration for agent behavior.
    
    Attributes:
        name: Agent identifier.
        description: Human-readable description.
        max_steps: Maximum steps before forced stop.
        timeout: Maximum execution time in seconds.
        allow_tool_use: Whether agent can use tools.
        verbose: Enable verbose logging.
    """
    name: str = "agent"
    description: str = ""
    max_steps: int = 100
    timeout: float = 300.0
    allow_tool_use: bool = True
    verbose: bool = True
    

class Tool(Callable):
    """Base class for agent tools."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    def __call__(self, *args, **kwargs) -> "ToolResult":
        """Execute the tool."""
        raise NotImplementedError
    
    def __repr__(self) -> str:
        return f"Tool(name='{self.name}')"


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error
        }


class Agent:
    """
    Stateful agent with workflow and tool capabilities.
    
    This agent maintains state across interactions, supports
    tools, and can be configured with custom behavior.
    
    Example:
        agent = Agent(
            config=AgentConfig(name="assistant", max_steps=50),
            tools=[search_tool, calculator_tool]
        )
        
        async for response in agent.run("Hello, help me with math"):
            print(response)
    """
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        tools: Optional[list[Tool]] = None,
        llm: Optional[Any] = None,
        memory: Optional[Any] = None
    ):
        """
        Initialize the agent.
        
        Args:
            config: Agent configuration.
            tools: List of available tools.
            llm: Language model for reasoning.
            memory: Memory system for state persistence.
        """
        self.config = config or AgentConfig()
        self.tools = tools or []
        self.llm = llm
        self.memory = memory
        
        # Initialize state
        self.state = AgentState(
            conversation_id=f"{self.config.name}_{datetime.now().timestamp()}"
        )
        
        # Tool registry
        self._tool_map = {tool.name: tool for tool in self.tools}
    
    @property
    def name(self) -> str:
        return self.config.name
    
    def add_tool(self, tool: Tool) -> "Agent":
        """Add a tool to the agent."""
        self._tool_map[tool.name] = tool
        self.tools.append(tool)
        return self
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tool_map.get(name)
    
    async def run(self, input_text: str) -> str:
        """
        Run the agent with input text.
        
        Args:
            input_text: User input.
            
        Returns:
            Agent response.
        """
        self.state.status = AgentStatus.RUNNING
        self.state.record_action(f"Received input: {input_text[:50]}...")
        
        # Simple response for now - can be extended with LLM
        response = await self._process_input(input_text)
        
        self.state.status = AgentStatus.COMPLETED
        self.state.record_action("Completed", response)
        
        return response
    
    async def _process_input(self, input_text: str) -> str:
        """Process input and generate response."""
        if not self.llm:
            # Default response without LLM
            return f"Agent '{self.config.name}' processed: {input_text}"
        
        # Use LLM if available
        try:
            if hasattr(self.llm, 'invoke'):
                result = await self.llm.invoke(input_text)
                return result.content if hasattr(result, 'content') else str(result)
        except Exception as e:
            return f"Error: {str(e)}"
        
        return "No response generated"
    
    def reset(self) -> None:
        """Reset agent state for new conversation."""
        self.state = AgentState(
            conversation_id=f"{self.config.name}_{datetime.now().timestamp()}"
        )
    
    def get_state(self) -> dict:
        """Get current agent state."""
        return {
            "name": self.config.name,
            "status": self.state.status.value,
            "step_count": self.state.step_count,
            "last_action": self.state.last_action,
            "can_continue": self.state.can_continue()
        }
    
    def __repr__(self) -> str:
        return f"Agent(name='{self.config.name}', status={self.state.status.value})"

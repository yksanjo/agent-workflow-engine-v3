"""
Tools module for Agent Workflow Engine.

Provides built-in tools that agents can use for various tasks.
"""

from typing import Any, Optional, Callable
from dataclasses import dataclass
import json
import asyncio


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


class Tool:
    """Base class for agent tools."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    def __call__(self, *args, **kwargs) -> ToolResult:
        """Execute the tool."""
        raise NotImplementedError
    
    def __repr__(self) -> str:
        return f"Tool(name='{self.name}')"


class CalculatorTool(Tool):
    """Tool for mathematical calculations."""
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="Perform mathematical calculations"
        )
    
    def __call__(self, expression: str) -> ToolResult:
        """Evaluate a mathematical expression."""
        try:
            # Safe evaluation of math expressions
            allowed_names = {
                "abs": abs,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow,
                "round": round,
            }
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SearchTool(Tool):
    """Tool for searching information."""
    
    def __init__(self):
        super().__init__(
            name="search",
            description="Search for information"
        )
        self._data = {
            "python": "Python is a high-level programming language.",
            "javascript": "JavaScript is a scripting language for web pages.",
            "machine learning": "Machine learning is a subset of AI.",
        }
    
    def __call__(self, query: str) -> ToolResult:
        """Search for query in knowledge base."""
        query_lower = query.lower()
        results = {
            k: v for k, v in self._data.items()
            if query_lower in k or query_lower in v
        }
        if results:
            return ToolResult(success=True, data=results)
        return ToolResult(success=False, error="No results found")


class TextTool(Tool):
    """Tool for text processing."""
    
    def __init__(self):
        super().__init__(
            name="text_processor",
            description="Process and transform text"
        )
    
    def __call__(self, text: str, operation: str) -> ToolResult:
        """Perform text operation."""
        operations = {
            "upper": lambda t: t.upper(),
            "lower": lambda t: t.lower(),
            "capitalize": lambda t: t.capitalize(),
            "reverse": lambda t: t[::-1],
            "word_count": lambda t: len(t.split()),
            "char_count": lambda t: len(t),
        }
        
        if operation not in operations:
            return ToolResult(
                success=False, 
                error=f"Unknown operation. Available: {list(operations.keys())}"
            )
        
        try:
            result = operations[operation](text)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WebFetchTool(Tool):
    """Tool for fetching web content (simulated)."""
    
    def __init__(self):
        super().__init__(
            name="web_fetch",
            description="Fetch content from a URL"
        )
    
    def __call__(self, url: str) -> ToolResult:
        """Fetch content from URL (simulated)."""
        # Simulated response
        if not url.startswith(("http://", "https://")):
            return ToolResult(success=False, error="Invalid URL")
        
        # In real implementation, would use requests/httpx
        return ToolResult(
            success=True,
            data={
                "url": url,
                "status": 200,
                "content": f"Simulated content from {url}"
            }
        )


class ToolRegistry:
    """Registry for managing agent tools."""
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> list[str]:
        """List all registered tools."""
        return list(self._tools.keys())
    
    def execute(self, tool_name: str, *args, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(tool_name)
        if tool is None:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found")
        
        try:
            return tool(*args, **kwargs)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# Default registry with built-in tools
_default_registry = ToolRegistry()
_default_registry.register(CalculatorTool())
_default_registry.register(SearchTool())
_default_registry.register(TextTool())
_default_registry.register(WebFetchTool())


def get_registry() -> ToolRegistry:
    """Get the default tool registry."""
    return _default_registry


def create_tool(name: str, func: Callable) -> Tool:
    """Create a custom tool from a function."""
    
    class CustomTool(Tool):
        def __init__(self):
            super().__init__(
                name=name,
                description=func.__doc__ or "Custom tool"
            )
            self._func = func
        
        def __call__(self, *args, **kwargs) -> ToolResult:
            try:
                result = self._func(*args, **kwargs)
                return ToolResult(success=True, data=result)
            except Exception as e:
                return ToolResult(success=False, error=str(e))
    
    return CustomTool()

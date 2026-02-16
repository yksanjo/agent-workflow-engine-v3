"""
Demo examples for the Agent Workflow Engine.

Demonstrates agent creation, workflow orchestration,
memory management, and tool usage.
"""

import asyncio
from agent_workflow_engine import (
    Agent,
    AgentConfig,
    AgentWorkflow,
    ShortTermMemory,
    LongTermMemory,
    ConversationMemory,
    Tool,
    ToolResult,
    get_registry,
)
from agent_workflow_engine.tools import CalculatorTool, SearchTool, TextTool


# =============================================================================
# Example 1: Basic Agent
# =============================================================================

def demo_basic_agent():
    """Demonstrate basic agent creation and execution."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Agent")
    print("=" * 60)
    
    # Create agent config
    config = AgentConfig(
        name="assistant",
        description="A helpful assistant agent",
        max_steps=50
    )
    
    # Create agent
    agent = Agent(config=config)
    
    # Run agent
    async def run():
        response = await agent.run("Hello, what can you do?")
        print(f"Agent response: {response}")
        print(f"Agent state: {agent.get_state()}")
    
    asyncio.run(run())


# =============================================================================
# Example 2: Agent with Tools
# =============================================================================

def demo_agent_with_tools():
    """Demonstrate agent with tool usage."""
    print("\n" + "=" * 60)
    print("Example 2: Agent with Tools")
    print("=" * 60)
    
    # Get tool registry
    registry = get_registry()
    print(f"Available tools: {registry.list_tools()}")
    
    # Create custom tool
    class CustomTool(Tool):
        def __init__(self):
            super().__init__(
                name="custom_greet",
                description="A custom greeting tool"
            )
        
        def __call__(self, name: str = "World") -> ToolResult:
            return ToolResult(
                success=True,
                data=f"Hello, {name}! Welcome to Agent Workflow Engine."
            )
    
    # Add custom tool
    custom_tool = CustomTool()
    registry.register(custom_tool)
    
    # Execute tool directly
    result = registry.execute("custom_greet", name="Alice")
    print(f"Tool result: {result.to_dict()}")
    
    # Use calculator
    calc_result = registry.execute("calculator", "2 + 2 * 3")
    print(f"Calculator: 2 + 2 * 3 = {calc_result.data}")
    
    # Use search
    search_result = registry.execute("search", "python")
    print(f"Search result: {search_result.data}")


# =============================================================================
# Example 3: Agent Workflow
# =============================================================================

def demo_workflow():
    """Demonstrate workflow orchestration."""
    print("\n" + "=" * 60)
    print("Example 3: Agent Workflow")
    print("=" * 60)
    
    # Define workflow steps
    def step_validate(context):
        """Validate input."""
        print("[Step] Validating input...")
        user_input = context.get("input", "")
        context["validated"] = len(user_input) > 0
        return context
    
    def step_process(context):
        """Process input."""
        print("[Step] Processing...")
        user_input = context.get("input", "")
        context["processed"] = f"Processed: {user_input.upper()}"
        return context
    
    def step_respond(context):
        """Generate response."""
        print("[Step] Generating response...")
        processed = context.get("processed", "")
        context["response"] = f"Final: {processed}"
        return context
    
    # Create workflow
    workflow = AgentWorkflow(name="response_generator")
    
    workflow.add_step(
        "validate",
        step_validate,
        description="Validate user input"
    ).add_step(
        "process",
        step_process,
        description="Process the input",
        on_failure="respond"  # Continue even on failure
    ).add_step(
        "respond",
        step_respond,
        description="Generate final response",
        is_terminal=True
    )
    
    print(workflow.visualize())
    
    # Execute workflow
    async def run():
        result = await workflow.execute({"input": "Hello World"})
        print(f"\nWorkflow result: {result}")
        print(f"History: {workflow.get_history()}")
    
    asyncio.run(run())


# =============================================================================
# Example 4: Memory Management
# =============================================================================

def demo_memory():
    """Demonstrate memory management."""
    print("\n" + "=" * 60)
    print("Example 4: Memory Management")
    print("=" * 60)
    
    # Short-term memory with TTL
    short_mem = ShortTermMemory(ttl_seconds=3600)
    short_mem.set("user_name", "Alice")
    short_mem.set("session_id", "abc123")
    
    print(f"Short-term memory: {short_mem.items()}")
    print(f"Get user_name: {short_mem.get('user_name')}")
    
    # Conversation memory
    conv_mem = ConversationMemory(max_turns=5)
    conv_mem.add_turn("user", "Hello!")
    conv_mem.add_turn("assistant", "Hi there!")
    conv_mem.add_turn("user", "How are you?")
    
    print(f"\nConversation history: {conv_mem.get_history()}")
    print(f"Last turn: {conv_mem.get_last_turn()}")


# =============================================================================
# Example 5: Complete Agent with Workflow and Memory
# =============================================================================

def demo_complete_agent():
    """Demonstrate a complete agent with all features."""
    print("\n" + "=" * 60)
    print("Example 5: Complete Agent")
    print("=" * 60)
    
    # Create agent with config
    config = AgentConfig(
        name="smart_assistant",
        max_steps=100,
        verbose=True
    )
    
    # Create agent
    agent = Agent(config=config)
    
    # Add tools
    registry = get_registry()
    for tool_name in registry.list_tools():
        agent.add_tool(registry.get(tool_name))
    
    # Add memory
    memory = ConversationMemory(max_turns=10)
    
    # Create workflow
    workflow = AgentWorkflow(name="assistant_flow")
    
    def receive_input(ctx):
        """Receive and store input."""
        input_text = ctx.get("input", "")
        memory.add_turn("user", input_text)
        ctx["input_stored"] = True
        return ctx
    
    def process_with_tools(ctx):
        """Process using available tools."""
        input_text = ctx.get("input", "").lower()
        
        # Simple routing based on keywords
        if "calculate" in input_text or "math" in input_text:
            result = registry.execute("calculator", "10 + 20")
            ctx["response"] = f"Calculation result: {result.data}"
        elif "search" in input_text or "what is" in input_text:
            query = input_text.replace("search", "").replace("what is", "").strip()
            result = registry.execute("search", query)
            ctx["response"] = f"Search results: {result.data}"
        else:
            ctx["response"] = f"I processed: {input_text}"
        
        memory.add_turn("assistant", ctx["response"])
        return ctx
    
    workflow.add_step("input", receive_input, description="Store user input")
    workflow.add_step("process", process_with_tools, description="Process with tools")
    workflow.add_step("end", lambda ctx: ctx, description="End", is_terminal=True)
    
    print(workflow.visualize())
    
    # Run
    async def run():
        result = await workflow.execute({"input": "calculate 5 + 3"})
        print(f"\nResult: {result}")
    
    asyncio.run(run())


# =============================================================================
# Run All Demos
# =============================================================================

if __name__ == "__main__":
    demo_basic_agent()
    demo_agent_with_tools()
    demo_workflow()
    demo_memory()
    demo_complete_agent()
    
    print("\n" + "=" * 60)
    print("All demos completed!")
    print("=" * 60)

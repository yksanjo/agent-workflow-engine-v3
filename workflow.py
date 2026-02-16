"""
Workflow module for Agent Workflow Engine.

Provides workflow orchestration for agents with steps,
transitions, and execution management.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from enum import Enum


class StepStatus(Enum):
    """Status of a workflow step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """
    A single step in a workflow.
    
    Attributes:
        name: Unique identifier for the step.
        action: The action/function to execute.
        condition: Optional condition to determine if step should run.
        on_success: Next step if this succeeds.
        on_failure: Next step if this fails.
        description: Human-readable description.
    """
    name: str
    action: Callable[[Any], Any]
    condition: Optional[Callable[[Any], bool]] = None
    on_success: Optional[str] = None
    on_failure: Optional[str] = None
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    max_retries: int = 3
    
    def should_run(self, context: Any) -> bool:
        """Check if this step should run based on condition."""
        if self.condition is None:
            return True
        return self.condition(context)
    
    async def execute(self, context: Any) -> Any:
        """Execute the step."""
        self.status = StepStatus.RUNNING
        try:
            result = self.action(context)
            # Handle both sync and async
            if hasattr(result, '__await__'):
                result = await result
            self.status = StepStatus.COMPLETED
            return result
        except Exception as e:
            self.status = StepStatus.FAILED
            raise e


class AgentWorkflow:
    """
    Workflow orchestrator for agent execution.
    
    Manages a collection of steps with transitions between them
    based on success/failure conditions.
    
    Example:
        workflow = AgentWorkflow(name="assistant")
        workflow.add_step("start", start_action)
        workflow.add_step("process", process_action, on_success="end")
        workflow.add_step("end", end_action, is_terminal=True)
        
        result = await workflow.execute(initial_context)
    """
    
    def __init__(self, name: str = "workflow"):
        """
        Initialize the workflow.
        
        Args:
            name: Name of the workflow.
        """
        self.name = name
        self.steps: dict[str, WorkflowStep] = {}
        self.start_step: Optional[str] = None
        self.terminal_steps: set[str] = set()
        self._execution_history: list[dict] = []
    
    def add_step(
        self,
        name: str,
        action: Callable[[Any], Any],
        condition: Optional[Callable[[Any], bool]] = None,
        on_success: Optional[str] = None,
        on_failure: Optional[str] = None,
        description: str = "",
        is_terminal: bool = False
    ) -> "AgentWorkflow":
        """
        Add a step to the workflow.
        
        Args:
            name: Unique identifier for the step.
            action: Function to execute for this step.
            condition: Optional condition to check before running.
            on_success: Next step on success.
            on_failure: Next step on failure.
            description: Human-readable description.
            is_terminal: Whether this is an end step.
            
        Returns:
            Self for method chaining.
        """
        step = WorkflowStep(
            name=name,
            action=action,
            condition=condition,
            on_success=on_success,
            on_failure=on_failure,
            description=description
        )
        self.steps[name] = step
        
        if is_terminal:
            self.terminal_steps.add(name)
        
        if self.start_step is None:
            self.start_step = name
        
        return self
    
    def set_start(self, step_name: str) -> "AgentWorkflow":
        """Set the starting step."""
        if step_name not in self.steps:
            raise ValueError(f"Step '{step_name}' does not exist")
        self.start_step = step_name
        return self
    
    def get_step(self, name: str) -> Optional[WorkflowStep]:
        """Get a step by name."""
        return self.steps.get(name)
    
    async def execute(self, initial_context: Any = None) -> Any:
        """
        Execute the workflow.
        
        Args:
            initial_context: Initial context data.
            
        Returns:
            Final context after workflow completes.
        """
        if self.start_step is None:
            raise ValueError("No start step defined")
        
        context = initial_context or {}
        current_step = self.start_step
        self._execution_history = []
        
        while current_step is not None:
            step = self.steps.get(current_step)
            
            if step is None:
                break
            
            # Record execution
            self._execution_history.append({
                "step": current_step,
                "status": step.status.value
            })
            
            # Check condition
            if not step.should_run(context):
                step.status = StepStatus.SKIPPED
                current_step = step.on_success
                continue
            
            try:
                # Execute step
                result = await step.execute(context)
                
                # Update context with result
                if result is not None:
                    context["last_result"] = result
                
                # Determine next step
                if current_step in self.terminal_steps:
                    break
                current_step = step.on_success
                
            except Exception as e:
                context["error"] = str(e)
                current_step = step.on_failure
        
        return context
    
    def visualize(self) -> str:
        """Generate a text representation of the workflow."""
        lines = [f"Workflow: {self.name}", "=" * 50]
        
        lines.append(f"\nStart: {self.start_step}")
        lines.append(f"Terminal: {self.terminal_steps}")
        
        lines.append("\nSteps:")
        for name, step in self.steps.items():
            terminal = " [TERMINAL]" if name in self.terminal_steps else ""
            lines.append(f"  - {name}{terminal}: {step.description or 'No description'}")
            if step.on_success:
                lines.append(f"      on_success -> {step.on_success}")
            if step.on_failure:
                lines.append(f"      on_failure -> {step.on_failure}")
        
        return "\n".join(lines)
    
    def get_history(self) -> list[dict]:
        """Get execution history."""
        return self._execution_history.copy()

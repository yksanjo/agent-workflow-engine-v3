"""Worker Agent implementation."""

import time
import traceback
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from .agent import Agent, AgentRole, Task, TaskResult
from .audit import AuditTrail, AuditLevel
from .exceptions import WorkerException


class WorkerAgent(Agent):
    """
    Worker Agent with focused expertise for sub-task execution.
    
    Responsibilities:
    - Sub-task execution with focused expertise
    - Status reporting and progress updates
    - Exception escalation and error handling
    - Interface adherence and compatibility
    - Quality assurance and validation
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: Optional[str] = None,
        capabilities: Optional[list] = None,
        expertise_domain: Optional[str] = None,
        quality_threshold: float = 0.8,
        execution_callback: Optional[Callable] = None,
        audit_trail: Optional[AuditTrail] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name=name,
            role=AgentRole.OPERATIONAL,
            capabilities=capabilities,
            config=config,
        )
        self.expertise_domain = expertise_domain or "general"
        self.quality_threshold = quality_threshold
        self.execution_callback = execution_callback
        self.audit_trail = audit_trail
        self._current_task: Optional[Task] = None
        self._manager_id: Optional[str] = None
    
    def assign_manager(self, manager_id: str) -> None:
        """Assign this worker to a manager."""
        self._manager_id = manager_id
    
    def execute_task(self, task: Task) -> TaskResult:
        """
        Execute a sub-task with full lifecycle management.
        """
        self._current_task = task
        start_time = time.time()
        
        # Log task acceptance
        if self.audit_trail:
            entry_id = self.audit_trail.log(
                agent_id=self.agent_id,
                agent_role=self.role.name,
                level=AuditLevel.ACTION,
                action="task_accepted",
                task_id=task.task_id,
                details={
                    "objective": task.objective,
                    "expertise_domain": self.expertise_domain,
                    "priority": task.priority,
                },
            )
        
        try:
            self.set_status(self.status.WORKING)
            
            # Validate capability match
            if task.required_capabilities:
                missing = set(task.required_capabilities) - self.capabilities
                if missing:
                    raise WorkerException(
                        f"Missing capabilities: {missing}"
                    )
            
            # Execute the task
            if self.execution_callback:
                result_data = self.execution_callback(task, self)
            else:
                result_data = self._default_execution(task)
            
            # Quality validation
            quality_score = self._validate_quality(result_data)
            
            execution_time = time.time() - start_time
            
            # Create result
            result = TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=True,
                result=result_data,
                execution_time=execution_time,
                completed_at=datetime.utcnow(),
                metadata={
                    "quality_score": quality_score,
                    "expertise_domain": self.expertise_domain,
                },
            )
            
            self.tasks_completed += 1
            self.total_execution_time += execution_time
            
            # Log completion
            if self.audit_trail:
                self.audit_trail.log(
                    agent_id=self.agent_id,
                    agent_role=self.role.name,
                    level=AuditLevel.ACTION,
                    action="task_completed",
                    task_id=task.task_id,
                    details={
                        "execution_time": execution_time,
                        "quality_score": quality_score,
                    },
                )
            
            self._notify_result(result)
            self.set_status(self.status.IDLE)
            self._current_task = None
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            # Log error
            if self.audit_trail:
                self.audit_trail.log(
                    agent_id=self.agent_id,
                    agent_role=self.role.name,
                    level=AuditLevel.ERROR,
                    action="task_failed",
                    task_id=task.task_id,
                    details={
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    },
                )
            
            self.tasks_failed += 1
            self.set_status(self.status.ERROR)
            
            # Escalate exception to manager
            if self._manager_id:
                self._escalate_exception(task, e)
            
            result = TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=False,
                result=None,
                execution_time=execution_time,
                completed_at=datetime.utcnow(),
                error_message=str(e),
                metadata={"traceback": traceback.format_exc()},
            )
            
            self._notify_result(result)
            self._current_task = None
            
            return result
    
    def _default_execution(self, task: Task) -> Any:
        """Default task execution - should be overridden."""
        return {
            "message": f"Task '{task.objective}' executed by {self.name}",
            "domain": self.expertise_domain,
        }
    
    def _validate_quality(self, result: Any) -> float:
        """Validate result quality - returns quality score 0-1."""
        # Placeholder for quality validation logic
        # In practice, this would check result completeness, accuracy, etc.
        return self.quality_threshold
    
    def _escalate_exception(self, task: Task, exception: Exception) -> None:
        """Escalate an exception to the assigned manager."""
        # In a real system, this would send a message to the manager
        pass
    
    def report_status(self) -> Dict[str, Any]:
        """Report current status to manager."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "status": self.status.name,
            "current_task": self._current_task.task_id if self._current_task else None,
            "expertise_domain": self.expertise_domain,
            "stats": self.get_stats(),
        }
    
    def validate_interface(self, interface_spec: Dict[str, Any]) -> bool:
        """
        Validate that this worker adheres to the specified interface.
        """
        required_caps = interface_spec.get("required_capabilities", [])
        return all(cap in self.capabilities for cap in required_caps)

"""Manager Agent implementation."""

import asyncio
import time
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future

from .agent import Agent, AgentRole, AgentStatus, Task, TaskResult
from .worker import WorkerAgent
from .delegation import (
    DelegationMode,
    ResultAggregation,
    WorkerResult,
    ResultAggregator,
)
from .audit import AuditTrail, AuditLevel
from .exceptions import (
    DelegationException,
    HierarchyViolation,
    HumanConfirmationRequired,
)


class ManagerAgent(Agent):
    """
    Manager Agent with command and control responsibilities.
    
    Responsibilities:
    - Objective interpretation and decomposition
    - Worker matching and assignment
    - Progress monitoring and coordination
    - Result synthesis and integration
    - Exception handling and escalation
    """
    
    # Hierarchy limits by role
    MAX_SUBORDINATES = {
        AgentRole.STRATEGIC: 5,    # 3-5 subordinates
        AgentRole.TACTICAL: 15,    # 5-15 subordinates
        AgentRole.OPERATIONAL: 0,  # Cannot have subordinates
    }
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: Optional[str] = None,
        role: AgentRole = AgentRole.TACTICAL,
        capabilities: Optional[List[str]] = None,
        delegation_mode: DelegationMode = DelegationMode.SYNCHRONOUS,
        result_aggregation: ResultAggregation = ResultAggregation.DIRECT_USE,
        audit_trail: Optional[AuditTrail] = None,
        synthesis_callback: Optional[Callable] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        if role == AgentRole.OPERATIONAL:
            raise HierarchyViolation(
                "Operational agents cannot be managers"
            )
        
        super().__init__(
            agent_id=agent_id,
            name=name,
            role=role,
            capabilities=capabilities,
            config=config,
        )
        
        self.delegation_mode = delegation_mode
        self.result_aggregation = result_aggregation
        self.audit_trail = audit_trail or AuditTrail()
        self.result_aggregator = ResultAggregator(synthesis_callback)
        
        # Subordinate management
        self._workers: Dict[str, WorkerAgent] = {}
        self._subordinate_managers: Dict[str, 'ManagerAgent'] = {}
        
        # Task tracking
        self._active_tasks: Dict[str, Task] = {}
        self._task_results: Dict[str, List[WorkerResult]] = {}
        self._task_futures: Dict[str, Future] = {}
        
        # Exception handling
        self._exception_handlers: Dict[str, Callable] = {}
        self._pending_high_risk: Dict[str, Task] = {}
        
        # Parent manager (for multi-level hierarchy)
        self._parent_manager: Optional[str] = None
        
        # Executor for async operations
        self._executor = ThreadPoolExecutor(max_workers=10)
    
    def assign_parent(self, manager_id: str) -> None:
        """Assign this manager to a higher-level manager."""
        self._parent_manager = manager_id
    
    def add_worker(self, worker: WorkerAgent) -> None:
        """Add a worker subordinate."""
        self._check_hierarchy_limit()
        
        if worker.agent_id in self._workers:
            raise DelegationException(f"Worker {worker.agent_id} already assigned")
        
        self._workers[worker.agent_id] = worker
        worker.assign_manager(self.agent_id)
        
        self.audit_trail.log(
            agent_id=self.agent_id,
            agent_role=self.role.name,
            level=AuditLevel.DELEGATION,
            action="worker_assigned",
            details={"worker_id": worker.agent_id, "worker_name": worker.name},
        )
    
    def add_subordinate_manager(self, manager: 'ManagerAgent') -> None:
        """Add a subordinate manager for multi-level hierarchy."""
        self._check_hierarchy_limit()
        
        if manager.agent_id in self._subordinate_managers:
            raise DelegationException(
                f"Manager {manager.agent_id} already assigned"
            )
        
        self._subordinate_managers[manager.agent_id] = manager
        manager.assign_parent(self.agent_id)
        
        self.audit_trail.log(
            agent_id=self.agent_id,
            agent_role=self.role.name,
            level=AuditLevel.DELEGATION,
            action="subordinate_manager_assigned",
            details={
                "subordinate_id": manager.agent_id,
                "subordinate_name": manager.name,
                "subordinate_role": manager.role.name,
            },
        )
    
    def _check_hierarchy_limit(self) -> None:
        """Check if we can add more subordinates."""
        total_subordinates = len(self._workers) + len(self._subordinate_managers)
        max_allowed = self.MAX_SUBORDINATES.get(self.role, 0)
        
        if total_subordinates >= max_allowed:
            raise HierarchyViolation(
                f"{self.role.name} manager cannot have more than "
                f"{max_allowed} subordinates (currently {total_subordinates})"
            )
    
    def match_workers(self, task: Task) -> List[WorkerAgent]:
        """
        Match workers to task based on required capabilities.
        Returns best matches first. Checks both direct workers and subordinate managers.
        Falls back to returning all workers if no specific capability match.
        """
        # First, check direct workers
        if not task.required_capabilities:
            if self._workers:
                return list(self._workers.values())
        else:
            scored_workers = []
            for worker in self._workers.values():
                score = sum(
                    1 for cap in task.required_capabilities
                    if worker.has_capability(cap)
                )
                if score > 0:
                    scored_workers.append((worker, score))
            
            # Sort by score descending
            if scored_workers:
                scored_workers.sort(key=lambda x: x[1], reverse=True)
                return [w for w, _ in scored_workers]
            
            # No capability match found - return all workers as fallback
            if self._workers:
                return list(self._workers.values())
        
        # If no direct workers found, check subordinate managers
        for manager in self._subordinate_managers.values():
            workers = manager.match_workers(task)
            if workers:
                return workers
        
        # Return empty list if nothing found
        return []
    
    def decompose_objective(self, task: Task) -> List[Task]:
        """
        Decompose a high-level objective into sub-tasks.
        Override this method for domain-specific decomposition.
        """
        # Default: return task as-is
        return [task]
    
    def delegate(
        self,
        task: Task,
        workers: Optional[List[WorkerAgent]] = None,
        mode: Optional[DelegationMode] = None,
        aggregation: Optional[ResultAggregation] = None,
    ) -> Any:
        """
        Delegate a task to workers with specified coordination mode.
        """
        mode = mode or self.delegation_mode
        aggregation = aggregation or self.result_aggregation
        
        # Check for high-risk decisions requiring confirmation
        if task.risk_level in ("high", "critical"):
            entry_id = self.audit_trail.log(
                agent_id=self.agent_id,
                agent_role=self.role.name,
                level=AuditLevel.HIGH_RISK,
                action="high_risk_delegation",
                task_id=task.task_id,
                details={
                    "objective": task.objective,
                    "risk_level": task.risk_level,
                    "requires_confirmation": True,
                },
                require_confirmation=True,
            )
            self._pending_high_risk[task.task_id] = task
            raise HumanConfirmationRequired(
                f"High-risk task '{task.objective}' requires human confirmation",
                context={
                    "entry_id": entry_id,
                    "task": task,
                    "risk_level": task.risk_level,
                },
            )
        
        # Log delegation
        self.audit_trail.log(
            agent_id=self.agent_id,
            agent_role=self.role.name,
            level=AuditLevel.DELEGATION,
            action="task_delegated",
            task_id=task.task_id,
            details={
                "objective": task.objective,
                "mode": mode.name,
                "aggregation": aggregation.name,
            },
        )
        
        # Match workers if not specified
        if workers is None:
            workers = self.match_workers(task)
        
        if not workers:
            raise DelegationException(
                f"No workers available for task {task.task_id}"
            )
        
        # Track task
        self._active_tasks[task.task_id] = task
        self._task_results[task.task_id] = []
        
        # Delegate based on mode
        if mode == DelegationMode.SYNCHRONOUS:
            return self._delegate_synchronous(task, workers, aggregation)
        else:
            return self._delegate_asynchronous(task, workers, aggregation)
    
    def _delegate_synchronous(
        self,
        task: Task,
        workers: List[WorkerAgent],
        aggregation: ResultAggregation,
    ) -> Dict[str, Any]:
        """Synchronous delegation - blocking execution."""
        results = []
        
        for worker in workers:
            self.set_status(AgentStatus.WAITING)
            task_result = worker.execute_task(task)
            
            worker_result = WorkerResult(
                worker_id=worker.agent_id,
                task_id=task.task_id,
                success=task_result.success,
                result=task_result.result,
                execution_time=task_result.execution_time,
                metadata=task_result.metadata,
                error=task_result.error_message,
            )
            results.append(worker_result)
            self._task_results[task.task_id].append(worker_result)
        
        self.set_status(AgentStatus.IDLE)
        
        # Aggregate results
        aggregated = self.result_aggregator.aggregate(
            results, aggregation, context={"task": task}
        )
        
        # Log completion
        self.audit_trail.log(
            agent_id=self.agent_id,
            agent_role=self.role.name,
            level=AuditLevel.DELEGATION,
            action="results_aggregated",
            task_id=task.task_id,
            details={
                "strategy": aggregation.name,
                "worker_count": len(workers),
                "success": aggregated.get("success"),
            },
        )
        
        return aggregated
    
    def _delegate_asynchronous(
        self,
        task: Task,
        workers: List[WorkerAgent],
        aggregation: ResultAggregation,
    ) -> Future:
        """Asynchronous delegation - non-blocking execution."""
        def execute_async():
            return self._delegate_synchronous(task, workers, aggregation)
        
        future = self._executor.submit(execute_async)
        self._task_futures[task.task_id] = future
        
        return future
    
    def monitor_progress(self, task_id: str) -> Dict[str, Any]:
        """Monitor progress of a delegated task."""
        if task_id not in self._active_tasks:
            return {"error": f"Unknown task: {task_id}"}
        
        results = self._task_results.get(task_id, [])
        future = self._task_futures.get(task_id)
        
        status = {
            "task_id": task_id,
            "active": task_id in self._active_tasks,
            "results_received": len(results),
            "workers_assigned": len(self._workers),
        }
        
        if future:
            status["future_done"] = future.done()
            if future.done():
                try:
                    status["result"] = future.result()
                except Exception as e:
                    status["error"] = str(e)
        
        return status
    
    def synthesize_results(
        self,
        task_id: str,
        strategy: Optional[ResultAggregation] = None,
    ) -> Dict[str, Any]:
        """Synthesize results from multiple workers."""
        results = self._task_results.get(task_id, [])
        if not results:
            return {"error": "No results available for synthesis"}
        
        strategy = strategy or self.result_aggregation
        return self.result_aggregator.aggregate(results, strategy)
    
    def handle_exception(
        self,
        worker_id: str,
        task_id: str,
        exception: Exception,
    ) -> bool:
        """Handle exceptions from workers."""
        self.audit_trail.log(
            agent_id=self.agent_id,
            agent_role=self.role.name,
            level=AuditLevel.ERROR,
            action="exception_handled",
            task_id=task_id,
            details={
                "worker_id": worker_id,
                "exception": str(exception),
                "exception_type": type(exception).__name__,
            },
        )
        
        # Check for custom handler
        handler = self._exception_handlers.get(type(exception).__name__)
        if handler:
            return handler(worker_id, task_id, exception)
        
        # Default: escalate to parent manager if available
        if self._parent_manager:
            # Escalation logic would go here
            return True
        
        return False
    
    def register_exception_handler(
        self,
        exception_type: str,
        handler: Callable,
    ) -> None:
        """Register a custom exception handler."""
        self._exception_handlers[exception_type] = handler
    
    def get_subordinate_stats(self) -> Dict[str, Any]:
        """Get statistics for all subordinates."""
        return {
            "workers": {
                wid: w.get_stats() for wid, w in self._workers.items()
            },
            "subordinate_managers": {
                mid: m.get_stats() for mid, m in self._subordinate_managers.items()
            },
        }
    
    def get_hierarchy_depth(self) -> int:
        """Get the depth of this manager's subordinate hierarchy."""
        if not self._subordinate_managers:
            return 1
        
        max_depth = 0
        for manager in self._subordinate_managers.values():
            max_depth = max(max_depth, manager.get_hierarchy_depth())
        
        return max_depth + 1
    
    def confirm_high_risk_task(self, task_id: str, confirmed_by: str) -> bool:
        """Confirm a high-risk task after human review."""
        if task_id not in self._pending_high_risk:
            return False
        
        task = self._pending_high_risk.pop(task_id)
        
        # Find and confirm audit entry
        for entry_id, entry in self.audit_trail._entries.items():
            if entry.task_id == task_id and entry.level == AuditLevel.HIGH_RISK:
                self.audit_trail.confirm_action(entry_id, confirmed_by)
                break
        
        # Now proceed with delegation
        return True

"""Main Hierarchical Coordinator for the entire multi-agent system."""

from typing import Dict, Any, List, Optional, Callable
from enum import Enum, auto
import asyncio

from .agent import Agent, AgentRole, Task, TaskResult
from .manager import ManagerAgent
from .worker import WorkerAgent
from .delegation import DelegationMode, ResultAggregation
from .audit import AuditTrail, AuditLevel
from .exceptions import HierarchyViolation


class HierarchyLevel(Enum):
    """Multi-level hierarchy levels."""
    STRATEGIC = auto()    # Chief level (3-5 subordinates)
    TACTICAL = auto()     # Department level (5-15 subordinates)
    OPERATIONAL = auto()  # Direct execution


class HierarchicalCoordinator:
    """
    Main coordinator for hierarchical multi-agent systems.
    
    Manages the complete hierarchy from strategic to operational levels,
    handling cross-level coordination and system-wide oversight.
    """
    
    def __init__(
        self,
        audit_trail: Optional[AuditTrail] = None,
        enable_human_oversight: bool = True,
    ):
        self.audit_trail = audit_trail or AuditTrail()
        self.enable_human_oversight = enable_human_oversight
        
        # Agent registry
        self._agents: Dict[str, Agent] = {}
        self._strategic_managers: Dict[str, ManagerAgent] = {}
        self._tactical_managers: Dict[str, ManagerAgent] = {}
        self._workers: Dict[str, WorkerAgent] = {}
        
        # System configuration
        self._synthesis_callback: Optional[Callable] = None
        
        # System metrics
        self._metrics = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "exceptions_escalated": 0,
        }
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the coordinator."""
        self._agents[agent.agent_id] = agent
        
        if isinstance(agent, WorkerAgent):
            self._workers[agent.agent_id] = agent
            agent.audit_trail = self.audit_trail
        elif isinstance(agent, ManagerAgent):
            if agent.role == AgentRole.STRATEGIC:
                self._strategic_managers[agent.agent_id] = agent
            else:
                self._tactical_managers[agent.agent_id] = agent
            agent.audit_trail = self.audit_trail
        
        self.audit_trail.log(
            agent_id=agent.agent_id,
            agent_role=agent.role.name if hasattr(agent, 'role') else 'UNKNOWN',
            level=AuditLevel.INFO,
            action="agent_registered",
            details={
                "agent_type": type(agent).__name__,
                "name": agent.name,
            },
        )
    
    def create_hierarchy(
        self,
        strategic_config: Optional[Dict[str, Any]] = None,
        tactical_configs: Optional[List[Dict[str, Any]]] = None,
        worker_configs: Optional[List[Dict[str, Any]]] = None,
    ) -> ManagerAgent:
        """
        Create a complete 3-level hierarchy.
        
        Args:
            strategic_config: Configuration for strategic manager
            tactical_configs: List of configs for tactical managers
            worker_configs: List of configs for workers
        
        Returns:
            The top-level strategic manager
        """
        # Create strategic manager
        strategic_config = strategic_config or {}
        strategic = ManagerAgent(
            role=AgentRole.STRATEGIC,
            audit_trail=self.audit_trail,
            **strategic_config,
        )
        self.register_agent(strategic)
        
        # Create tactical managers
        tactical_configs = tactical_configs or [{}]
        for config in tactical_configs:
            tactical = ManagerAgent(
                role=AgentRole.TACTICAL,
                audit_trail=self.audit_trail,
                **config,
            )
            self.register_agent(tactical)
            strategic.add_subordinate_manager(tactical)
        
        # Create workers and distribute to tactical managers
        if worker_configs:
            workers_per_tactical = len(worker_configs) // len(tactical_configs)
            worker_idx = 0
            
            for tactical in strategic._subordinate_managers.values():
                for _ in range(workers_per_tactical):
                    if worker_idx >= len(worker_configs):
                        break
                    
                    config = worker_configs[worker_idx]
                    worker = WorkerAgent(
                        audit_trail=self.audit_trail,
                        **config,
                    )
                    self.register_agent(worker)
                    tactical.add_worker(worker)
                    worker_idx += 1
                
                # Distribute remaining workers
                while worker_idx < len(worker_configs):
                    config = worker_configs[worker_idx]
                    worker = WorkerAgent(
                        audit_trail=self.audit_trail,
                        **config,
                    )
                    self.register_agent(worker)
                    tactical.add_worker(worker)
                    worker_idx += 1
        
        self.audit_trail.log(
            agent_id="coordinator",
            agent_role="SYSTEM",
            level=AuditLevel.INFO,
            action="hierarchy_created",
            details={
                "strategic_count": 1,
                "tactical_count": len(strategic._subordinate_managers),
                "worker_count": sum(
                    len(m._workers)
                    for m in strategic._subordinate_managers.values()
                ),
            },
        )
        
        return strategic
    
    def submit_task(
        self,
        task: Task,
        to_manager: Optional[str] = None,
        mode: DelegationMode = DelegationMode.SYNCHRONOUS,
        aggregation: ResultAggregation = ResultAggregation.DIRECT_USE,
    ) -> Any:
        """
        Submit a task to the hierarchy.
        
        Args:
            task: The task to execute
            to_manager: Specific manager ID (or None for auto-routing)
            mode: Delegation mode
            aggregation: Result aggregation strategy
        
        Returns:
            Task result
        """
        self._metrics["tasks_submitted"] += 1
        
        # Route to appropriate manager
        if to_manager:
            manager = self._find_manager(to_manager)
        else:
            manager = self._route_task(task)
        
        if not manager:
            raise HierarchyViolation("No suitable manager found for task")
        
        # Execute
        try:
            result = manager.delegate(task, mode=mode, aggregation=aggregation)
            self._metrics["tasks_completed"] += 1
            return result
        except Exception as e:
            self._metrics["tasks_failed"] += 1
            raise
    
    def _find_manager(self, manager_id: str) -> Optional[ManagerAgent]:
        """Find a manager by ID."""
        if manager_id in self._strategic_managers:
            return self._strategic_managers[manager_id]
        if manager_id in self._tactical_managers:
            return self._tactical_managers[manager_id]
        
        # Search in subordinate managers
        for strategic in self._strategic_managers.values():
            if manager_id in strategic._subordinate_managers:
                return strategic._subordinate_managers[manager_id]
        
        return None
    
    def _route_task(self, task: Task) -> Optional[ManagerAgent]:
        """Route a task to the most appropriate manager."""
        # Always route through strategic manager first - it has the full hierarchy
        # This ensures proper delegation chain: strategic -> tactical -> workers
        if self._strategic_managers:
            return list(self._strategic_managers.values())[0]
        
        # Fallback: tactical manager
        if self._tactical_managers:
            return list(self._tactical_managers.values())[0]
        
        return None
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get complete system status."""
        return {
            "agents": {
                "strategic": len(self._strategic_managers),
                "tactical": len(self._tactical_managers),
                "workers": len(self._workers),
                "total": len(self._agents),
            },
            "metrics": self._metrics.copy(),
            "audit_pending": len(self.audit_trail.get_pending_confirmations()),
        }
    
    def get_full_hierarchy(self) -> Dict[str, Any]:
        """Get the complete hierarchy structure."""
        hierarchy = {}
        
        for strategic in self._strategic_managers.values():
            hierarchy[strategic.agent_id] = {
                "name": strategic.name,
                "role": "STRATEGIC",
                "subordinates": {
                    mid: {
                        "name": m.name,
                        "role": "TACTICAL",
                        "workers": [
                            {"id": wid, "name": w.name}
                            for wid, w in m._workers.items()
                        ],
                    }
                    for mid, m in strategic._subordinate_managers.items()
                },
            }
        
        return hierarchy
    
    def export_audit_trail(self, filepath: str) -> None:
        """Export the complete audit trail."""
        self.audit_trail.export_to_json(filepath)
    
    def generate_audit_report(self) -> str:
        """Generate a comprehensive audit report."""
        return self.audit_trail.generate_report()
    
    def confirm_high_risk_action(self, entry_id: str, confirmed_by: str) -> bool:
        """Confirm a high-risk action pending human approval."""
        return self.audit_trail.confirm_action(entry_id, confirmed_by)
    
    def list_pending_confirmations(self) -> List[Dict[str, Any]]:
        """List all actions pending human confirmation."""
        pending = self.audit_trail.get_pending_confirmations()
        return [
            {
                "entry_id": p.entry_id,
                "agent_id": p.agent_id,
                "action": p.action,
                "task_id": p.task_id,
                "details": p.details,
                "timestamp": p.timestamp.isoformat(),
            }
            for p in pending
        ]

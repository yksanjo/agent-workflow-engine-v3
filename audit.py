"""Audit trail system for tracking all agent actions and decisions."""

from enum import Enum
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import uuid


class AuditLevel(Enum):
    """Audit levels for different types of actions."""
    INFO = "info"
    ACTION = "action"           # Standard agent actions
    DELEGATION = "delegation"   # Task delegation events
    DECISION = "decision"       # Decision points
    HIGH_RISK = "high_risk"     # High-risk decisions requiring oversight
    ERROR = "error"             # Errors and exceptions


@dataclass
class AuditEntry:
    """Single audit entry record."""
    entry_id: str
    timestamp: datetime
    agent_id: str
    agent_role: str
    level: AuditLevel
    action: str
    task_id: Optional[str]
    details: Dict[str, Any]
    parent_entry_id: Optional[str] = None
    human_confirmed: bool = False
    confirmed_by: Optional[str] = None
    confirmation_time: Optional[datetime] = None


class AuditTrail:
    """
    Complete audit trail system with mandatory human confirmation
    for high-risk decisions.
    """
    
    def __init__(self):
        self._entries: Dict[str, AuditEntry] = {}
        self._task_history: Dict[str, List[str]] = {}
        self._pending_confirmations: Dict[str, AuditEntry] = {}
    
    def log(
        self,
        agent_id: str,
        agent_role: str,
        level: AuditLevel,
        action: str,
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        parent_entry_id: Optional[str] = None,
        require_confirmation: bool = False,
    ) -> str:
        """
        Log an action to the audit trail.
        
        Returns entry_id for reference and confirmation tracking.
        """
        entry_id = str(uuid.uuid4())
        entry = AuditEntry(
            entry_id=entry_id,
            timestamp=datetime.utcnow(),
            agent_id=agent_id,
            agent_role=agent_role,
            level=level,
            action=action,
            task_id=task_id,
            details=details or {},
            parent_entry_id=parent_entry_id,
        )
        
        self._entries[entry_id] = entry
        
        if task_id:
            if task_id not in self._task_history:
                self._task_history[task_id] = []
            self._task_history[task_id].append(entry_id)
        
        # Track high-risk decisions pending confirmation
        if require_confirmation or level == AuditLevel.HIGH_RISK:
            self._pending_confirmations[entry_id] = entry
            
        return entry_id
    
    def confirm_action(
        self,
        entry_id: str,
        confirmed_by: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Confirm a high-risk action with human oversight."""
        if entry_id not in self._entries:
            return False
        
        entry = self._entries[entry_id]
        entry.human_confirmed = True
        entry.confirmed_by = confirmed_by
        entry.confirmation_time = datetime.utcnow()
        
        if notes:
            entry.details["confirmation_notes"] = notes
        
        # Remove from pending
        if entry_id in self._pending_confirmations:
            del self._pending_confirmations[entry_id]
        
        return True
    
    def get_pending_confirmations(self) -> List[AuditEntry]:
        """Get all actions pending human confirmation."""
        return list(self._pending_confirmations.values())
    
    def get_task_history(self, task_id: str) -> List[AuditEntry]:
        """Get complete audit history for a task."""
        entry_ids = self._task_history.get(task_id, [])
        return [self._entries[eid] for eid in entry_ids if eid in self._entries]
    
    def get_entries_by_agent(self, agent_id: str) -> List[AuditEntry]:
        """Get all entries for a specific agent."""
        return [
            entry for entry in self._entries.values()
            if entry.agent_id == agent_id
        ]
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export full audit trail to dictionary."""
        return {
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "timestamp": e.timestamp.isoformat(),
                    "agent_id": e.agent_id,
                    "agent_role": e.agent_role,
                    "level": e.level.value,
                    "action": e.action,
                    "task_id": e.task_id,
                    "details": e.details,
                    "parent_entry_id": e.parent_entry_id,
                    "human_confirmed": e.human_confirmed,
                    "confirmed_by": e.confirmed_by,
                    "confirmation_time": e.confirmation_time.isoformat() if e.confirmation_time else None,
                }
                for e in self._entries.values()
            ],
            "pending_confirmations": list(self._pending_confirmations.keys()),
            "task_history": self._task_history,
        }
    
    def export_to_json(self, filepath: str) -> None:
        """Export audit trail to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.export_to_dict(), f, indent=2)
    
    def generate_report(self, task_id: Optional[str] = None) -> str:
        """Generate a human-readable audit report."""
        if task_id:
            entries = self.get_task_history(task_id)
        else:
            entries = list(self._entries.values())
        
        lines = ["=" * 60, "AUDIT TRAIL REPORT", "=" * 60, ""]
        
        for entry in sorted(entries, key=lambda e: e.timestamp):
            lines.append(f"[{entry.timestamp.isoformat()}] {entry.level.value.upper()}")
            lines.append(f"  Agent: {entry.agent_id} ({entry.agent_role})")
            lines.append(f"  Action: {entry.action}")
            if entry.task_id:
                lines.append(f"  Task: {entry.task_id}")
            if entry.details:
                lines.append(f"  Details: {json.dumps(entry.details, default=str)}")
            if entry.level == AuditLevel.HIGH_RISK:
                status = "CONFIRMED" if entry.human_confirmed else "PENDING CONFIRMATION"
                lines.append(f"  Status: {status}")
                if entry.confirmed_by:
                    lines.append(f"  Confirmed By: {entry.confirmed_by}")
            lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)

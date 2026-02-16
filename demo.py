"""Demo script showcasing the Hierarchical Agent Coordinator."""

import asyncio
from hierarchical_agent_coordinator import (
    HierarchicalCoordinator,
    ManagerAgent,
    WorkerAgent,
    AgentRole,
    Task,
    DelegationMode,
    ResultAggregation,
    AuditTrail,
    AuditLevel,
)
from hierarchical_agent_coordinator.healthcare_example import (
    ClinicalCoordinator,
    PatientCase,
)


def demo_basic_hierarchy():
    """Demonstrate basic hierarchical agent system."""
    print("=" * 60)
    print("DEMO 1: Basic Hierarchical Agent System")
    print("=" * 60)
    
    # Create coordinator
    coordinator = HierarchicalCoordinator(enable_human_oversight=True)
    
    # Create a 3-level hierarchy
    strategic = coordinator.create_hierarchy(
        strategic_config={"name": "Strategic Manager"},
        tactical_configs=[
            {"name": "Tactical Manager A"},
            {"name": "Tactical Manager B"},
        ],
        worker_configs=[
            {"name": "Worker 1", "expertise_domain": "data_processing", "capabilities": ["data_processing", "analysis"]},
            {"name": "Worker 2", "expertise_domain": "analysis", "capabilities": ["data_processing", "analysis"]},
            {"name": "Worker 3", "expertise_domain": "reporting", "capabilities": ["data_processing", "analysis"]},
            {"name": "Worker 4", "expertise_domain": "data_processing", "capabilities": ["data_processing", "analysis"]},
        ],
    )
    
    print(f"\n✓ Created hierarchy with:")
    status = coordinator.get_system_status()
    print(f"  - Strategic managers: {status['agents']['strategic']}")
    print(f"  - Tactical managers: {status['agents']['tactical']}")
    print(f"  - Workers: {status['agents']['workers']}")
    
    # Submit a task
    task = Task(
        objective="Process and analyze sales data",
        required_capabilities=["data_processing", "analysis"],
        priority=7,
        risk_level="low",
    )
    
    result = coordinator.submit_task(
        task,
        mode=DelegationMode.SYNCHRONOUS,
        aggregation=ResultAggregation.CONSENSUS,
    )
    
    print(f"\n✓ Task executed: {result}")
    print(f"\n✓ System metrics: {coordinator.get_system_status()['metrics']}")
    
    return coordinator


def demo_async_delegation():
    """Demonstrate asynchronous delegation."""
    print("\n" + "=" * 60)
    print("DEMO 2: Asynchronous Delegation")
    print("=" * 60)
    
    coordinator = HierarchicalCoordinator()
    
    # Create hierarchy
    strategic = coordinator.create_hierarchy(
        strategic_config={"name": "Async Strategic Manager"},
        tactical_configs=[{"name": "Async Tactical"}],
        worker_configs=[
            {"name": "Async Worker 1"},
            {"name": "Async Worker 2"},
            {"name": "Async Worker 3"},
        ],
    )
    
    # Submit multiple tasks asynchronously
    tasks = [
        Task(
            objective=f"Process request {i}",
            required_capabilities=["general"],
            priority=5,
            risk_level="low",
        )
        for i in range(3)
    ]
    
    print("\n✓ Submitting 3 tasks with ASYNCHRONOUS mode...")
    
    results = []
    for task in tasks:
        result = coordinator.submit_task(
            task,
            mode=DelegationMode.ASYNCHRONOUS,
        )
        results.append(result)
    
    print(f"✓ All tasks submitted. Results: {results}")
    
    return coordinator


def demo_result_aggregation():
    """Demonstrate different result aggregation strategies."""
    print("\n" + "=" * 60)
    print("DEMO 3: Result Aggregation Strategies")
    print("=" * 60)
    
    coordinator = HierarchicalCoordinator()
    
    # Create hierarchy with multiple workers
    strategic = coordinator.create_hierarchy(
        strategic_config={"name": "Aggregation Manager"},
        tactical_configs=[{"name": "Aggregation Tactical"}],
        worker_configs=[
            {"name": f"Worker {i}", "expertise_domain": f"domain_{i}", "capabilities": ["analysis"]}
            for i in range(3)
        ],
    )
    
    task = Task(
        objective="Analyze market trends",
        required_capabilities=["analysis"],
        priority=8,
        risk_level="medium",
    )
    
    # Test different aggregation modes
    aggregations = [
        ("CONSENSUS", ResultAggregation.CONSENSUS),
        ("LLM_SYNTHESIS", ResultAggregation.LLM_SYNTHESIS),
    ]
    
    for name, aggregation in aggregations:
        print(f"\n--- {name} ---")
        try:
            result = coordinator.submit_task(
                task,
                mode=DelegationMode.SYNCHRONOUS,
                aggregation=aggregation,
            )
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {e}")
    
    return coordinator


def demo_healthcare():
    """Demonstrate healthcare implementation."""
    print("\n" + "=" * 60)
    print("DEMO 4: Healthcare Clinical Hierarchy")
    print("=" * 60)
    
    # Create clinical coordinator
    clinical = ClinicalCoordinator(
        enable_human_confirmation=True,
        high_risk_threshold=0.7,
    )
    
    # Initialize clinical hierarchy
    cmo = clinical.initialize_clinical_hierarchy(
        departments=["cardiology", "neurology", "emergency"],
    )
    
    print(f"\n✓ Clinical hierarchy initialized:")
    summary = clinical.get_clinical_summary()
    print(f"  - CMO: {summary['hierarchy']['cmo']}")
    print(f"  - Departments: {summary['hierarchy']['departments']}")
    print(f"  - Specialists: {summary['hierarchy']['specialists']}")
    
    # Create and submit patient cases
    cases = [
        PatientCase(
            case_id="case_001",
            patient_id="P001",
            symptoms=["chest pain", "shortness of breath"],
            history={"conditions": ["hypertension", "diabetes"]},
            urgency="routine",
        ),
        PatientCase(
            case_id="case_002",
            patient_id="P002",
            symptoms=["headache", "dizziness"],
            history={"conditions": ["migraine"]},
            urgency="routine",
        ),
        PatientCase(
            case_id="case_003",
            patient_id="P003",
            symptoms=["abdominal pain", "fever"],
            history={},
            urgency="routine",
        ),
    ]
    
    print("\n✓ Submitting patient cases...")
    for case in cases:
        try:
            result = clinical.submit_patient_case(case)
            print(f"  - {case.patient_id}: {result.primary_diagnosis} "
                  f"(confidence: {result.confidence:.2f})")
        except Exception as e:
            print(f"  - {case.patient_id}: Error - {e}")
    
    # Get summary
    print(f"\n✓ Clinical summary:")
    summary = clinical.get_clinical_summary()
    print(f"  - Cases processed: {summary['total_cases_processed']}")
    print(f"  - Urgent cases: {summary['urgent_cases']}")
    print(f"  - High-risk identified: {summary['high_risk_identified']}")
    print(f"  - Confirmations required: {summary['confirmations_required']}")
    
    # Show pending confirmations
    pending = clinical.audit_trail.get_pending_confirmations()
    if pending:
        print(f"\n⚠ Pending confirmations: {len(pending)}")
        for p in pending:
            print(f"  - {p.action}: {p.details}")
    
    return clinical


def demo_audit_trail():
    """Demonstrate audit trail functionality."""
    print("\n" + "=" * 60)
    print("DEMO 5: Audit Trail & Human Oversight")
    print("=" * 60)
    
    audit = AuditTrail()
    
    # Log various events
    audit.log(
        agent_id="agent_001",
        agent_role="STRATEGIC",
        level=AuditLevel.INFO,
        action="task_started",
        details={"task_id": "task_123"},
    )
    
    audit.log(
        agent_id="agent_002",
        agent_role="TACTICAL",
        level=AuditLevel.HIGH_RISK,
        action="high_risk_decision",
        details={"risk_score": 0.85},
    )
    
    audit.log(
        agent_id="agent_003",
        agent_role="OPERATIONAL",
        level=AuditLevel.ERROR,
        action="task_failed",
        details={"error": "Connection timeout"},
    )
    
    # Generate report
    report = audit.generate_report()
    print("\n✓ Audit Report:")
    print(report[:500] + "..." if len(report) > 500 else report)
    
    return audit


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("HIERARCHICAL AGENT COORDINATOR - DEMONSTRATION")
    print("=" * 60)
    
    # Run demos
    demo_basic_hierarchy()
    demo_async_delegation()
    demo_result_aggregation()
    demo_healthcare()
    demo_audit_trail()
    
    print("\n" + "=" * 60)
    print("ALL DEMOS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()

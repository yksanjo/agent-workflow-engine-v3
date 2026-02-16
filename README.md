# Agent Workflow Engine

A workflow execution engine built on the Hierarchical Agent Coordinator, specializing in workflow definitions, state machines, and task pipelines.

## Features

- **Workflow Definitions**: Create reusable workflow templates with dependencies
- **Workflow Execution**: Execute workflows with state tracking (PENDING, RUNNING, PAUSED, COMPLETED, FAILED, CANCELLED)
- **Pipeline Processing**: Sequential and parallel pipeline execution
- **Streaming Pipeline**: Process data streams through handler chains
- **Integration**: Built on top of the Hierarchical Agent Coordinator

## Installation

```bash
pip install -e .
```

## Usage

```python
from agent_workflow_engine import (
    HierarchicalCoordinator,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowExecutor,
    PipelineExecutor,
)

# Create coordinator
coordinator = HierarchicalCoordinator()

# Create workflow
workflow = WorkflowDefinition(
    name="Data Processing Pipeline",
    description="Process and analyze data"
)

workflow.add_step(WorkflowStep(
    step_id="extract",
    name="Extract Data",
    description="Extract data from source",
    agent_config={"capabilities": ["data_processing"]}
))

workflow.add_step(WorkflowStep(
    step_id="transform",
    name="Transform Data",
    description="Transform data",
    agent_config={"capabilities": ["data_processing"]},
    dependencies=["extract"]
))

# Execute workflow
executor = WorkflowExecutor(coordinator)
execution = executor.create_execution(workflow)
result = executor.execute(execution.execution_id)
```

## License

MIT

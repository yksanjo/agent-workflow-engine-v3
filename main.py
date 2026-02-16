from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
from enum import Enum
from datetime import datetime
from celery import Celery
import redis

app = FastAPI(title="Agent Workflow Engine", 
              description="Visual workflow designer for connecting agent services",
              version="0.1.0")

# Celery configuration
celery_app = Celery('workflow_engine')
celery_app.conf.broker_url = 'redis://localhost:6379/0'
celery_app.conf.result_backend = 'redis://localhost:6379/0'

# Redis connection for workflow state
redis_client = redis.Redis(host='localhost', port=6379, db=1)

# In-memory storage for workflow definitions (would use DB in production)
workflows = {}

class NodeType(str, Enum):
    START = "start"
    END = "end"
    AGENT = "agent"
    CONDITION = "condition"
    ACTION = "action"

class WorkflowNode(BaseModel):
    id: str
    type: NodeType
    name: str
    config: Optional[Dict[str, Any]] = {}
    position: Optional[Dict[str, float]] = {"x": 0, "y": 0}

class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    condition: Optional[str] = None

class WorkflowDefinition(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    created_at: str
    updated_at: str
    version: str = "1.0"

class WorkflowExecution(BaseModel):
    id: str
    workflow_id: str
    status: str  # running, completed, failed
    started_at: str
    completed_at: Optional[str] = None
    execution_log: List[Dict[str, Any]]

class CreateWorkflowRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]

class ExecuteWorkflowRequest(BaseModel):
    workflow_id: str
    input_data: Optional[Dict[str, Any]] = {}

@app.get("/")
async def root():
    return {"message": "Agent Workflow Engine", "version": "0.1.0"}

@app.post("/workflows", response_model=WorkflowDefinition)
async def create_workflow(request: CreateWorkflowRequest):
    """
    Create a new workflow definition
    """
    workflow_id = str(uuid.uuid4())
    
    workflow = WorkflowDefinition(
        id=workflow_id,
        name=request.name,
        description=request.description,
        nodes=request.nodes,
        edges=request.edges,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat()
    )
    
    workflows[workflow_id] = workflow
    return workflow

@app.get("/workflows/{workflow_id}", response_model=WorkflowDefinition)
async def get_workflow(workflow_id: str):
    """
    Get a workflow definition
    """
    if workflow_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return workflows[workflow_id]

@app.get("/workflows", response_model=List[WorkflowDefinition])
async def list_workflows():
    """
    List all workflow definitions
    """
    return list(workflows.values())

@app.put("/workflows/{workflow_id}", response_model=WorkflowDefinition)
async def update_workflow(workflow_id: str, request: CreateWorkflowRequest):
    """
    Update an existing workflow definition
    """
    if workflow_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    workflow = WorkflowDefinition(
        id=workflow_id,
        name=request.name,
        description=request.description,
        nodes=request.nodes,
        edges=request.edges,
        created_at=workflows[workflow_id].created_at,  # Keep original creation time
        updated_at=datetime.utcnow().isoformat(),
        version=str(float(workflows[workflow_id].version) + 0.1)  # Increment version
    )
    
    workflows[workflow_id] = workflow
    return workflow

@app.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """
    Delete a workflow definition
    """
    if workflow_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    del workflows[workflow_id]
    return {"message": f"Workflow {workflow_id} deleted successfully"}

@app.post("/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, request: ExecuteWorkflowRequest):
    """
    Execute a workflow
    """
    if workflow_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    execution_id = str(uuid.uuid4())
    
    # Create execution record
    execution = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow_id,
        status="running",
        started_at=datetime.utcnow().isoformat(),
        execution_log=[]
    )
    
    # Store execution in Redis
    redis_client.set(f"execution:{execution_id}", execution.model_dump_json())
    
    # Trigger the workflow execution asynchronously
    execute_workflow_async.delay(execution_id, workflow_id, request.input_data)
    
    return {"execution_id": execution_id, "status": "started"}

@celery_app.task
def execute_workflow_async(execution_id: str, workflow_id: str, input_data: Dict[str, Any]):
    """
    Execute workflow asynchronously using Celery
    """
    try:
        workflow = workflows[workflow_id]
        
        # Find the start node
        start_node = None
        for node in workflow.nodes:
            if node.type == NodeType.START:
                start_node = node
                break
        
        if not start_node:
            raise ValueError("Workflow must have a start node")
        
        # Execute the workflow graph
        execution_result = execute_graph(start_node.id, workflow, input_data)
        
        # Update execution status to completed
        execution_key = f"execution:{execution_id}"
        execution_data = json.loads(redis_client.get(execution_key) or "{}")
        execution_data["status"] = "completed"
        execution_data["completed_at"] = datetime.utcnow().isoformat()
        execution_data["execution_log"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": "workflow_completed",
            "result": execution_result
        })
        
        redis_client.set(execution_key, json.dumps(execution_data))
        
    except Exception as e:
        # Update execution status to failed
        execution_key = f"execution:{execution_id}"
        execution_data = json.loads(redis_client.get(execution_key) or "{}")
        execution_data["status"] = "failed"
        execution_data["completed_at"] = datetime.utcnow().isoformat()
        execution_data["execution_log"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": "workflow_failed",
            "error": str(e)
        })
        
        redis_client.set(execution_key, json.dumps(execution_data))

def execute_graph(start_node_id: str, workflow: WorkflowDefinition, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the workflow graph starting from the start node
    """
    # This is a simplified execution engine
    # In a real implementation, this would traverse the graph and execute nodes
    execution_log = []
    
    # For now, just simulate execution
    for node in workflow.nodes:
        if node.type != NodeType.START and node.type != NodeType.END:
            execution_log.append({
                "node_id": node.id,
                "node_name": node.name,
                "status": "executed",
                "timestamp": datetime.utcnow().isoformat()
            })
            # Simulate processing time
            asyncio.run(asyncio.sleep(0.1))
    
    return {
        "status": "success",
        "output": input_data,  # In a real implementation, this would be processed data
        "execution_log": execution_log
    }

@app.get("/executions/{execution_id}", response_model=WorkflowExecution)
async def get_execution_status(execution_id: str):
    """
    Get the status of a workflow execution
    """
    execution_key = f"execution:{execution_id}"
    execution_data = redis_client.get(execution_key)
    
    if not execution_data:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    execution_dict = json.loads(execution_data)
    return WorkflowExecution(**execution_dict)

@app.get("/workflows/{workflow_id}/executions")
async def list_executions(workflow_id: str):
    """
    List executions for a specific workflow
    """
    # In a real implementation, this would query a database
    # For now, we'll just return a mock response
    return {"executions": [], "count": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
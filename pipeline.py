"""Pipeline execution for sequential and parallel task processing."""

from enum import Enum, auto
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed


class PipelineStageStatus(Enum):
    """Pipeline stage status."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class PipelineStage:
    """A stage in a processing pipeline."""
    stage_id: str
    name: str
    handler: Callable
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_key: str = ""
    parallel: bool = False
    retry_count: int = 0
    timeout: Optional[int] = None


class PipelineExecutor:
    """Executes multi-stage pipelines with parallel execution support."""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.stages: List[PipelineStage] = []
        self.results: Dict[str, Any] = {}
    
    def add_stage(self, stage: PipelineStage) -> None:
        """Add a stage to the pipeline."""
        self.stages.append(stage)
    
    def execute(self, initial_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the pipeline."""
        self.results = {"input": initial_input.copy()}
        
        for stage in self.stages:
            try:
                result = self._execute_stage(stage)
                self.results[stage.output_key or stage.stage_id] = result
            except Exception as e:
                if stage.retry_count > 0:
                    for _ in range(stage.retry_count):
                        try:
                            result = self._execute_stage(stage)
                            self.results[stage.output_key or stage.stage_id] = result
                            break
                        except:
                            continue
                else:
                    self.results["error"] = str(e)
                    break
        
        return self.results
    
    def _execute_stage(self, stage: PipelineStage) -> Any:
        """Execute a single stage."""
        # Map inputs from previous results
        input_data = {}
        for key, source in stage.input_mapping.items():
            if source in self.results:
                input_data[key] = self.results[source]
            elif source == "input":
                input_data[key] = self.results.get("input", {})
        
        # Execute handler
        if stage.handler:
            return stage.handler(input_data)
        
        return None
    
    def execute_parallel(self, initial_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute pipeline stages in parallel where possible."""
        self.results = {"input": initial_input.copy()}
        
        # Group parallel stages
        current_batch = []
        
        for stage in self.stages:
            if stage.parallel:
                current_batch.append(stage)
            else:
                # Execute accumulated parallel batch first
                if current_batch:
                    self._execute_batch(current_batch)
                    current_batch = []
                
                # Execute sequential stage
                try:
                    result = self._execute_stage(stage)
                    self.results[stage.output_key or stage.stage_id] = result
                except Exception as e:
                    self.results["error"] = str(e)
                    break
        
        # Execute final parallel batch
        if current_batch:
            self._execute_batch(current_batch)
        
        return self.results
    
    def _execute_batch(self, stages: List[PipelineStage]) -> None:
        """Execute multiple stages in parallel."""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._execute_stage, stage): stage
                for stage in stages
            }
            
            for future in as_completed(futures):
                stage = futures[future]
                try:
                    result = future.result()
                    self.results[stage.output_key or stage.stage_id] = result
                except Exception as e:
                    self.results["error"] = str(e)


class StreamingPipeline:
    """Pipeline that processes data in streaming fashion."""
    
    def __init__(self):
        self.handlers: List[Callable] = []
        self.buffer_size: int = 100
    
    def add_handler(self, handler: Callable) -> None:
        """Add a streaming handler."""
        self.handlers.append(handler)
    
    def process(self, data_stream) -> List[Any]:
        """Process a stream of data."""
        results = []
        
        for item in data_stream:
            processed = item
            for handler in self.handlers:
                processed = handler(processed)
                if processed is None:
                    break
            
            if processed is not None:
                results.append(processed)
        
        return results

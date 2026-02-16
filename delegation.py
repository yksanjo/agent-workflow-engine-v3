"""Delegation modes and result aggregation strategies."""

from enum import Enum, auto
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import statistics


class DelegationMode(Enum):
    """
    Coordination modes for manager-worker interactions.
    """
    SYNCHRONOUS = auto()    # Blocking with immediate result integration
    ASYNCHRONOUS = auto()   # Non-blocking with continuation during execution


class ResultAggregation(Enum):
    """
    Strategies for integrating worker results.
    """
    DIRECT_USE = auto()         # Single worker, simple validation
    CONSENSUS = auto()          # Voting or confidence-weighted selection
    LLM_SYNTHESIS = auto()      # Generative integration with attribution
    MAJORITY_VOTE = auto()      # Simple majority voting
    WEIGHTED_AVERAGE = auto()   # Confidence-weighted averaging


@dataclass
class WorkerResult:
    """Result from a worker agent execution."""
    worker_id: str
    task_id: str
    success: bool
    result: Any
    confidence: float = 1.0
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ResultAggregator:
    """
    Handles result aggregation from multiple workers using
    various strategies.
    """
    
    def __init__(self, synthesis_callback: Optional[Callable] = None):
        self.synthesis_callback = synthesis_callback
    
    def aggregate(
        self,
        results: List[WorkerResult],
        strategy: ResultAggregation,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate multiple worker results using specified strategy.
        """
        if not results:
            return {"success": False, "error": "No results to aggregate"}
        
        if strategy == ResultAggregation.DIRECT_USE:
            return self._direct_use(results)
        elif strategy == ResultAggregation.CONSENSUS:
            return self._consensus_formation(results)
        elif strategy == ResultAggregation.LLM_SYNTHESIS:
            return self._llm_synthesis(results, context)
        elif strategy == ResultAggregation.MAJORITY_VOTE:
            return self._majority_vote(results)
        elif strategy == ResultAggregation.WEIGHTED_AVERAGE:
            return self._weighted_average(results)
        else:
            raise ValueError(f"Unknown aggregation strategy: {strategy}")
    
    def _direct_use(self, results: List[WorkerResult]) -> Dict[str, Any]:
        """Use single result with validation."""
        if len(results) != 1:
            return {
                "success": False,
                "error": "DIRECT_USE requires exactly one result",
                "results": results,
            }
        
        result = results[0]
        return {
            "success": result.success,
            "result": result.result,
            "worker_id": result.worker_id,
            "confidence": result.confidence,
        }
    
    def _consensus_formation(self, results: List[WorkerResult]) -> Dict[str, Any]:
        """Form consensus using confidence-weighted selection."""
        successful = [r for r in results if r.success]
        if not successful:
            return {
                "success": False,
                "error": "No successful results",
                "all_results": results,
            }
        
        # Sort by confidence
        successful.sort(key=lambda r: r.confidence, reverse=True)
        
        # Check for high-confidence consensus
        if len(successful) >= 2:
            top_results = successful[:2]
            if abs(top_results[0].confidence - top_results[1].confidence) < 0.1:
                # Results are close, check if they agree
                return {
                    "success": True,
                    "result": top_results[0].result,
                    "consensus_reached": True,
                    "participating_workers": [r.worker_id for r in successful],
                    "confidence": top_results[0].confidence,
                    "alternative": top_results[1].result,
                }
        
        return {
            "success": True,
            "result": successful[0].result,
            "consensus_reached": len(successful) > len(results) / 2,
            "participating_workers": [r.worker_id for r in successful],
            "confidence": successful[0].confidence,
        }
    
    def _llm_synthesis(
        self,
        results: List[WorkerResult],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Use LLM to synthesize multiple perspectives with attribution.
        This is a placeholder - actual implementation would call LLM.
        """
        successful = [r for r in results if r.success]
        
        if self.synthesis_callback:
            synthesis = self.synthesis_callback(successful, context)
            return {
                "success": True,
                "result": synthesis,
                "method": "llm_synthesis",
                "sources": [
                    {
                        "worker_id": r.worker_id,
                        "confidence": r.confidence,
                        "result_preview": str(r.result)[:100] if r.result else None,
                    }
                    for r in successful
                ],
            }
        
        # Fallback to simple concatenation with attribution
        synthesized = {
            "perspectives": [
                {
                    "worker_id": r.worker_id,
                    "confidence": r.confidence,
                    "result": r.result,
                }
                for r in successful
            ],
            "synthesis_notes": "Multiple perspectives collected. LLM synthesis callback not configured.",
        }
        
        return {
            "success": True,
            "result": synthesized,
            "method": "llm_synthesis_fallback",
            "sources_count": len(successful),
        }
    
    def _majority_vote(self, results: List[WorkerResult]) -> Dict[str, Any]:
        """Simple majority voting for discrete decisions."""
        successful = [r for r in results if r.success]
        if not successful:
            return {"success": False, "error": "No successful results"}
        
        # Count votes
        votes: Dict[Any, int] = {}
        for r in successful:
            key = str(r.result)  # Convert to string for hashing
            votes[key] = votes.get(key, 0) + r.confidence
        
        if not votes:
            return {"success": False, "error": "No votes to count"}
        
        winner = max(votes.items(), key=lambda x: x[1])
        total_votes = sum(votes.values())
        
        return {
            "success": True,
            "result": winner[0],
            "vote_share": winner[1] / total_votes,
            "total_votes": total_votes,
            "participating_workers": len(successful),
        }
    
    def _weighted_average(self, results: List[WorkerResult]) -> Dict[str, Any]:
        """Confidence-weighted averaging for numerical results."""
        successful = [r for r in results if r.success]
        
        # Try to convert results to numbers
        numeric_results = []
        for r in successful:
            try:
                val = float(r.result)
                numeric_results.append((val, r.confidence, r.worker_id))
            except (ValueError, TypeError):
                continue
        
        if not numeric_results:
            return {
                "success": False,
                "error": "No numeric results for weighted average",
                "fallback": self._consensus_formation(results),
            }
        
        # Calculate weighted average
        weighted_sum = sum(val * conf for val, conf, _ in numeric_results)
        total_confidence = sum(conf for _, conf, _ in numeric_results)
        
        if total_confidence == 0:
            return {"success": False, "error": "Zero total confidence"}
        
        average = weighted_sum / total_confidence
        
        # Calculate variance for uncertainty estimate
        values = [val for val, _, _ in numeric_results]
        variance = statistics.variance(values) if len(values) > 1 else 0
        
        return {
            "success": True,
            "result": average,
            "variance": variance,
            "confidence": total_confidence / len(numeric_results),
            "participating_workers": [wid for _, _, wid in numeric_results],
        }
